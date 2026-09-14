"""StateBackend contract and transactional SQLite implementation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from .store import (
    ResearchStateStore, RunLockError, StateConflictError, atomic_json, canonical_hash,
    sha256_file, utc_now,
)


class StateBackend(Protocol):
    run_dir: Path
    state_path: Path
    events_path: Path
    checkpoint_dir: Path

    def create(self, state: dict[str, Any]) -> None: ...
    def load(self) -> dict[str, Any]: ...
    def load_with_version(self) -> tuple[dict[str, Any], int]: ...
    def save(self, state: dict[str, Any], event_type: str, payload: dict[str, Any],
             expected_version: int | None = None) -> int: ...
    def verify(self) -> list[str]: ...
    def recover_latest(self) -> dict[str, Any]: ...
    def acquire_run_lock(self, owner: str) -> dict[str, Any]: ...
    def release_run_lock(self, owner: str) -> None: ...


FileStateBackend = ResearchStateStore


class SQLiteStateBackend:
    """SQLite canonical state/events with filesystem artifacts and checkpoints."""

    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir).resolve()
        self.state_path = self.run_dir / "state.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.checkpoint_dir = self.run_dir / "checkpoints"
        self.database_path = self.run_dir / "runtime-state.sqlite"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _initialize_schema(connection: sqlite3.Connection) -> None:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS backend_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT OR IGNORE INTO backend_meta(key, value) VALUES('schema_version', 'sqlite-state/1.0');
            CREATE TABLE IF NOT EXISTS canonical_state(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                run_id TEXT NOT NULL,
                at TEXT NOT NULL,
                type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS run_locks(
                lock_name TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                acquired_at TEXT NOT NULL
            );
        """)
        version = connection.execute("SELECT value FROM backend_meta WHERE key='schema_version'").fetchone()[0]
        if version != "sqlite-state/1.0":
            raise RuntimeError(f"Unsupported SQLite state schema: {version}")

    def create(self, state: dict[str, Any]) -> None:
        if self.run_dir.exists():
            raise FileExistsError(f"Refusing to overwrite an existing run: {self.run_dir}")
        self.checkpoint_dir.mkdir(parents=True)
        connection = self._connect()
        try:
            self._initialize_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            self._checkpoint_unlocked(state, "run-created")
            payload = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            connection.execute(
                "INSERT INTO canonical_state VALUES(1, 1, ?, ?, ?)",
                (payload, canonical_hash(state), utc_now()),
            )
            self._insert_event(connection, state["run_id"], "run.created", {"project_id": state["project_id"]})
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            connection.close()
        atomic_json(self.state_path, state)
        self._export_events()

    def load_with_version(self) -> tuple[dict[str, Any], int]:
        connection = self._connect()
        try:
            self._initialize_schema(connection)
            row = connection.execute("SELECT version, state_json FROM canonical_state WHERE singleton=1").fetchone()
            if row is None:
                raise FileNotFoundError("SQLite canonical state is not initialized")
            return json.loads(row["state_json"]), int(row["version"])
        finally:
            connection.close()

    def load(self) -> dict[str, Any]:
        return self.load_with_version()[0]

    def save(self, state: dict[str, Any], event_type: str, payload: dict[str, Any],
             expected_version: int | None = None) -> int:
        connection = self._connect()
        try:
            self._initialize_schema(connection); connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT version FROM canonical_state WHERE singleton=1").fetchone()
            if row is None:
                raise FileNotFoundError("SQLite canonical state is not initialized")
            current = int(row["version"])
            if expected_version is not None and current != expected_version:
                raise StateConflictError(f"State version conflict: expected {expected_version}, current {current}")
            state["updated_at"] = utc_now(); version = current + 1
            self._checkpoint_unlocked(state, event_type)
            serialized = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            connection.execute(
                "UPDATE canonical_state SET version=?, state_json=?, state_hash=?, updated_at=? WHERE singleton=1",
                (version, serialized, canonical_hash(state), utc_now()),
            )
            self._insert_event(connection, state["run_id"], event_type, payload)
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            connection.close()
        atomic_json(self.state_path, state); self._export_events()
        return version

    @staticmethod
    def _insert_event(connection: sqlite3.Connection, run_id: str, event_type: str,
                      payload: dict[str, Any]) -> None:
        sequence = int(connection.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM events").fetchone()[0])
        at = utc_now(); enriched = {**payload, "event_sequence": sequence}
        event_id = canonical_hash({"run_id": run_id, "sequence": sequence, "type": event_type, "payload": enriched})[:24]
        connection.execute(
            "INSERT INTO events(event_id, run_id, at, type, payload_json) VALUES(?, ?, ?, ?, ?)",
            (event_id, run_id, at, event_type, json.dumps(enriched, ensure_ascii=False, sort_keys=True)),
        )

    def _export_events(self) -> None:
        connection = self._connect()
        try:
            rows = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
        finally:
            connection.close()
        lines = []
        for row in rows:
            lines.append(json.dumps({
                "schema_version": "research-event/1.0", "event_id": row["event_id"],
                "run_id": row["run_id"], "at": row["at"], "type": row["type"],
                "payload": json.loads(row["payload_json"]),
            }, ensure_ascii=False, allow_nan=False))
        self.events_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def append_event(self, event_type: str, payload: dict[str, Any]) -> None:
        state = self.load(); connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._insert_event(connection, state["run_id"], event_type, payload)
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            connection.close()
        self._export_events()

    def _checkpoint_unlocked(self, state: dict[str, Any], reason: str) -> dict[str, Any]:
        sequence = len(list(self.checkpoint_dir.glob("*.json"))) + 1
        snapshot_hash = canonical_hash(state); filename = f"{sequence:06d}-{snapshot_hash[:12]}.json"
        path = self.checkpoint_dir / filename; atomic_json(path, state)
        receipt = {"checkpoint_id": filename[:-5], "path": path.relative_to(self.run_dir).as_posix(),
                   "state_sha256": sha256_file(path), "reason": reason, "created_at": utc_now()}
        refs = state.setdefault("checkpoints", [])
        if not refs or refs[-1].get("checkpoint_id") != receipt["checkpoint_id"]:
            refs.append(receipt)
        return receipt

    def checkpoint(self, state: dict[str, Any], reason: str) -> dict[str, Any]:
        return self._checkpoint_unlocked(state, reason)

    def verify(self) -> list[str]:
        errors = []
        state, _version = self.load_with_version()
        for receipt in state.get("checkpoints", []):
            path = (self.run_dir / receipt["path"]).resolve()
            if not path.is_relative_to(self.run_dir):
                errors.append(f"checkpoint escapes run directory: {receipt['path']}")
            elif not path.is_file():
                errors.append(f"missing checkpoint: {receipt['path']}")
            elif sha256_file(path) != receipt["state_sha256"]:
                errors.append(f"checkpoint hash mismatch: {receipt['path']}")
        connection = self._connect()
        try:
            row = connection.execute("SELECT state_json, state_hash FROM canonical_state WHERE singleton=1").fetchone()
            if row and canonical_hash(json.loads(row["state_json"])) != row["state_hash"]:
                errors.append("canonical SQLite state hash mismatch")
        finally:
            connection.close()
        return errors

    def recover_latest(self) -> dict[str, Any]:
        failures = []
        for path in sorted(self.checkpoint_dir.glob("*.json"), reverse=True):
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
                if canonical_hash(candidate)[:12] != path.stem.rsplit("-", 1)[-1]:
                    raise ValueError("content hash does not match checkpoint filename")
                _state, version = self.load_with_version()
                self.save(candidate, "run.recovered", {"checkpoint": path.name}, expected_version=version)
                return candidate
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")
        raise RuntimeError("No valid checkpoint is available: " + "; ".join(failures))

    def acquire_run_lock(self, owner: str) -> dict[str, Any]:
        connection = self._connect(); acquired_at = utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO run_locks(lock_name, owner, acquired_at) VALUES('canonical-run', ?, ?)",
                (owner, acquired_at),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback(); raise RunLockError("Run is already locked") from exc
        finally:
            connection.close()
        return {"owner": owner, "acquired_at": acquired_at}

    def release_run_lock(self, owner: str) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT owner FROM run_locks WHERE lock_name='canonical-run'").fetchone()
            if row is not None and row["owner"] != owner:
                raise RunLockError("Run lock is owned by another actor")
            connection.execute("DELETE FROM run_locks WHERE lock_name='canonical-run'")
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            connection.close()


def open_state_backend(run_dir: str | Path) -> StateBackend:
    root = Path(run_dir).resolve()
    if (root / "runtime-state.sqlite").is_file():
        return SQLiteStateBackend(root)
    return FileStateBackend(root)
