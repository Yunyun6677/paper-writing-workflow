"""Canonical runtime contracts and compatibility helpers."""

from __future__ import annotations

from typing import Any
from .memory import empty_memory


OUTCOMES = {
    "PASS", "FAIL_TRANSIENT", "FAIL_STRATEGY", "BLOCKED",
    "HIGH_RISK_DECISION", "GOAL_COMPLETE",
}
TERMINAL_TASK_STATUSES = {"complete", "skipped", "superseded"}


def normalize_outcome(observation: dict[str, Any]) -> str:
    """Accept v1 observations while exposing the explicit v2 decision vocabulary."""
    outcome = observation.get("outcome")
    if outcome:
        value = str(outcome).upper()
        if value not in OUTCOMES:
            raise ValueError(f"Unsupported observation outcome: {value}")
        return value
    legacy = observation.get("status")
    return {"complete": "PASS", "failed": "FAIL_TRANSIENT", "needs-human": "BLOCKED"}.get(legacy, "")


def dependencies(item: dict[str, Any]) -> list[str]:
    canonical = list(item.get("dependencies", []))
    legacy = list(item.get("depends_on", canonical))
    return legacy if legacy != canonical else canonical


def sync_compatibility_aliases(item: dict[str, Any]) -> None:
    """Keep persisted v1 readers usable while the runtime uses the canonical contract."""
    item["title"] = item["goal"]
    item["kind"] = item["task_type"]
    item["owner"] = item["assigned_agent"]
    item["depends_on"] = list(item["dependencies"])
    item["inputs"] = dict(item["required_inputs"])
    item["acceptance_criteria"] = list(item["success_contract"])
    item["max_retries"] = max(0, item["retry_policy"]["max_attempts"] - 1)
    item["retry_count"] = item["attempts"]

def upgrade_state_v010(state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Add v0.10 fields without deleting v0.9 state, artifacts, or history."""
    changed = any(key not in state for key in ("data_sensitivity", "lifecycle_status", "runtime_control", "memory"))
    state.setdefault("data_sensitivity", "restricted")
    state.setdefault("lifecycle_status", "initialized")
    state.setdefault("runtime_control", {"max_total_steps": 500, "max_total_tasks": 100, "max_no_progress_cycles": 3, "total_steps": 0, "no_progress_cycles": 0, "strategy_replans": 0, "max_strategy_replans": 20})
    state.setdefault("memory", empty_memory())
    for item in state.get("task_graph", []):
        before = set(item)
        item.setdefault("task_type", item.get("kind", "agent"))
        if item.get("task_id") == "verification" and item.get("tool_name") == "research_firewall":
            item["task_type"] = "final_audit"
        item.setdefault("goal", item.get("title", item.get("task_id", "legacy task")))
        item.setdefault("dependencies", list(item.get("depends_on", [])))
        item.setdefault("required_inputs", dict(item.get("inputs", {})))
        if item["task_type"] == "verifier" and not item["required_inputs"].get("producer_task_id") and item["dependencies"]:
            item["required_inputs"]["producer_task_id"] = item["dependencies"][0]
        item.setdefault("assigned_agent", item.get("owner", "research-director"))
        item.setdefault("allowed_tools", [item["tool_name"]] if item.get("tool_name") else [])
        item.setdefault("retry_policy", {"max_attempts": int(item.get("max_retries", 1)) + 1, "retry_on": ["FAIL_TRANSIENT"]})
        item.setdefault("timeout_seconds", 900)
        item.setdefault("stopping_condition", "success contract verified or failure contract activated")
        item.setdefault("success_contract", list(item.get("acceptance_criteria", [])) or ["declared outputs satisfy verification rules"])
        item.setdefault("failure_contract", ["record failure and hand off after bounded recovery"])
        item.setdefault("verification_rules", [])
        item.setdefault("attempts", int(item.get("retry_count", 0)))
        item.setdefault("strategy_replans", 0); item.setdefault("max_strategy_replans", 2)
        item.setdefault("capabilities", [])
        sync_compatibility_aliases(item)
        changed = changed or set(item) != before
    return state, changed
