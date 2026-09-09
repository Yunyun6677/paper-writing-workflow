"""Deterministic operational evaluation for a Research Agent run."""

from __future__ import annotations

from typing import Any

from .store import ResearchStateStore, utc_now


def evaluate(store: ResearchStateStore) -> dict[str, Any]:
    state = store.load()
    tasks = state["task_graph"]
    total = len(tasks)
    complete = sum(item["status"] in {"complete", "skipped"} for item in tasks)
    blocked = sum(item["status"] == "blocked" for item in tasks)
    waiting = sum(item["status"] in {"waiting-agent", "waiting-human"} for item in tasks)
    integrity_errors = store.verify()
    status = "blocked" if blocked or integrity_errors else ("waiting" if waiting else ("pass" if complete == total else "review-required"))
    return {
        "schema_version": "agent-run-evaluation/1.0", "run_id": state["run_id"],
        "evaluated_at": utc_now(), "status": status,
        "metrics": {
            "tasks_total": total, "tasks_complete": complete, "tasks_blocked": blocked,
            "tasks_waiting": waiting, "completion_rate": complete / total if total else 0,
            "errors": len(state["errors"]), "retries": state["retry_count"],
            "artifacts": len(state["artifacts"]), "checkpoints": len(state["checkpoints"]),
        },
        "integrity_errors": integrity_errors,
    }
