"""Atomic ResearchState persistence, checkpoints, events, and content hashes."""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StateConflictError(RuntimeError):
    pass


class RunLockError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


class ResearchStateStore:
    """File-backed event store. A checkpoint is written after every transition."""

    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir).resolve()
        self.state_path = self.run_dir / "state.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.checkpoint_dir = self.run_dir / "checkpoints"
        self.backend_meta_path = self.run_dir / "backend-meta.json"
        self._write_lock_path = self.run_dir / ".state-write.lock"
        self._run_lock_path = self.run_dir / ".run.lock"

    def _meta(self) -> dict[str, int]:
        if self.backend_meta_path.is_file():
            return json.loads(self.backend_meta_path.read_text(encoding="utf-8"))
        lines = len(self.events_path.read_text(encoding="utf-8").splitlines()) if self.events_path.is_file() else 0
        return {"state_version": 0, "event_sequence": lines}

    @contextmanager
    def _write_lock(self, timeout: float = 10.0):
        deadline = time.monotonic() + timeout
        while True:
            try:
                descriptor = os.open(self._write_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(descriptor, str(os.getpid()).encode("ascii")); os.close(descriptor)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise RunLockError("Timed out waiting for file state write lock")
                time.sleep(0.01)
        try:
            yield
        finally:
            try:
                self._write_lock_path.unlink()
            except FileNotFoundError:
                pass

    def create(self, state: dict[str, Any]) -> None:
        if self.run_dir.exists():
            raise FileExistsError(f"Refusing to overwrite an existing run: {self.run_dir}")
        self.checkpoint_dir.mkdir(parents=True)
        atomic_json(self.backend_meta_path, {"state_version": 1, "event_sequence": 0})
        atomic_json(self.state_path, state)
        self.append_event("run.created", {"project_id": state["project_id"]})
        self.checkpoint(state, "run-created")

    def load(self) -> dict[str, Any]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def load_with_version(self) -> tuple[dict[str, Any], int]:
        return self.load(), int(self._meta()["state_version"])

    def save(self, state: dict[str, Any], event_type: str, payload: dict[str, Any],
             expected_version: int | None = None) -> int:
        with self._write_lock():
            meta = self._meta(); current = int(meta["state_version"])
            if expected_version is not None and current != expected_version:
                raise StateConflictError(f"State version conflict: expected {expected_version}, current {current}")
            state["updated_at"] = utc_now(); meta["state_version"] = current + 1
            atomic_json(self.state_path, state)
            self._append_event_unlocked(event_type, payload, meta)
            self.checkpoint(state, event_type)
            return int(meta["state_version"])

    def append_event(self, event_type: str, payload: dict[str, Any]) -> None:
        with self._write_lock():
            meta = self._meta()
            self._append_event_unlocked(event_type, payload, meta)

    def _append_event_unlocked(self, event_type: str, payload: dict[str, Any], meta: dict[str, int]) -> None:
        meta["event_sequence"] = int(meta.get("event_sequence", 0)) + 1
        event = {
            "schema_version": "research-event/1.0",
            "event_id": canonical_hash({"at": utc_now(), "type": event_type, "payload": payload})[:24],
            "run_id": self.load()["run_id"] if self.state_path.exists() else payload.get("run_id", "pending"),
            "at": utc_now(),
            "type": event_type,
            "payload": {**payload, "event_sequence": meta["event_sequence"]},
        }
        with self.events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        atomic_json(self.backend_meta_path, meta)

    def acquire_run_lock(self, owner: str) -> dict[str, Any]:
        try:
            descriptor = os.open(self._run_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RunLockError("Run is already locked") from exc
        record = {"owner": owner, "pid": os.getpid(), "acquired_at": utc_now()}
        os.write(descriptor, json.dumps(record).encode("utf-8")); os.close(descriptor)
        return record

    def release_run_lock(self, owner: str) -> None:
        if not self._run_lock_path.is_file():
            return
        record = json.loads(self._run_lock_path.read_text(encoding="utf-8"))
        if record.get("owner") != owner:
            raise RunLockError("Run lock is owned by another actor")
        self._run_lock_path.unlink()

    def checkpoint(self, state: dict[str, Any], reason: str) -> dict[str, Any]:
        sequence = len(list(self.checkpoint_dir.glob("*.json"))) + 1
        snapshot_hash = canonical_hash(state)
        filename = f"{sequence:06d}-{snapshot_hash[:12]}.json"
        path = self.checkpoint_dir / filename
        atomic_json(path, state)
        receipt = {
            "checkpoint_id": filename[:-5],
            "path": str(path.relative_to(self.run_dir)).replace("\\", "/"),
            "state_sha256": sha256_file(path),
            "reason": reason,
            "created_at": utc_now(),
        }
        # Keep only lightweight checkpoint references in the canonical state.
        if state.get("checkpoints") is not None:
            refs = state["checkpoints"]
            if not refs or refs[-1].get("checkpoint_id") != receipt["checkpoint_id"]:
                refs.append(receipt)
                atomic_json(self.state_path, state)
        return receipt

    def verify(self) -> list[str]:
        errors: list[str] = []
        state = self.load()
        for receipt in state.get("checkpoints", []):
            path = (self.run_dir / receipt["path"]).resolve()
            if not path.is_relative_to(self.run_dir):
                errors.append(f"checkpoint escapes run directory: {receipt['path']}")
            elif not path.is_file():
                errors.append(f"missing checkpoint: {receipt['path']}")
            elif sha256_file(path) != receipt["state_sha256"]:
                errors.append(f"checkpoint hash mismatch: {receipt['path']}")
        return errors

    def recover_latest(self) -> dict[str, Any]:
        """Recover canonical state from the newest checkpoint whose filename hash matches its bytes."""
        failures: list[str] = []
        for path in sorted(self.checkpoint_dir.glob("*.json"), reverse=True):
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
                expected_prefix = path.stem.rsplit("-", 1)[-1]
                if canonical_hash(candidate)[:12] != expected_prefix:
                    raise ValueError("content hash does not match checkpoint filename")
                if candidate.get("schema_version") != "research-state/1.0":
                    raise ValueError("unsupported state schema")
                from .contracts import upgrade_state_v010
                candidate, _ = upgrade_state_v010(candidate)
                with self._write_lock():
                    meta = self._meta(); meta["state_version"] = int(meta["state_version"]) + 1
                    atomic_json(self.state_path, candidate)
                    self._append_event_unlocked("run.recovered", {"checkpoint": path.name}, meta)
                    self.checkpoint(candidate, "run-recovered")
                return candidate
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")
        raise RuntimeError("No valid checkpoint is available: " + "; ".join(failures))
