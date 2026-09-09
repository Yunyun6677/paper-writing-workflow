"""Atomic ResearchState persistence, checkpoints, events, and content hashes."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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

    def create(self, state: dict[str, Any]) -> None:
        if self.run_dir.exists():
            raise FileExistsError(f"Refusing to overwrite an existing run: {self.run_dir}")
        self.checkpoint_dir.mkdir(parents=True)
        atomic_json(self.state_path, state)
        self.append_event("run.created", {"project_id": state["project_id"]})
        self.checkpoint(state, "run-created")

    def load(self) -> dict[str, Any]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save(self, state: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        atomic_json(self.state_path, state)
        self.append_event(event_type, payload)
        self.checkpoint(state, event_type)

    def append_event(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "schema_version": "research-event/1.0",
            "event_id": canonical_hash({"at": utc_now(), "type": event_type, "payload": payload})[:24],
            "run_id": self.load()["run_id"] if self.state_path.exists() else payload.get("run_id", "pending"),
            "at": utc_now(),
            "type": event_type,
            "payload": payload,
        }
        with self.events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

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
                atomic_json(self.state_path, candidate)
                self.append_event("run.recovered", {"checkpoint": path.name})
                self.checkpoint(candidate, "run-recovered")
                return candidate
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")
        raise RuntimeError("No valid checkpoint is available: " + "; ".join(failures))
