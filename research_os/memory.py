"""Schema-driven memory layers; no secret or raw restricted-data persistence."""

from __future__ import annotations

from typing import Any


FORBIDDEN_KEYS = {"secret", "token", "password", "api_key", "credential", "raw_data"}


def empty_memory() -> dict[str, Any]:
    return {
        "working": {"scope": "run", "entries": []},
        "project": {"scope": "project", "decisions": [], "revision_history": [], "artifact_refs": []},
        "researcher_preferences": {"scope": "researcher", "preferences": {}, "secret_policy": "references-only"},
        "evidence": {"scope": "evidence", "artifact_refs": [], "summary_is_not_evidence": True},
    }


def assert_safe_long_term(value: Any, path: str = "memory") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                raise ValueError(f"Long-term memory cannot store {path}.{key}")
            assert_safe_long_term(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_safe_long_term(child, f"{path}[{index}]")
