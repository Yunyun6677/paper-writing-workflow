"""Artifact-aware evaluation for one Research Agent run.

Unavailable scientific metrics are reported as null rather than inferred from
task completion or model assertions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .planner import validate_dag
from .state_backends import StateBackend
from .store import sha256_file, utc_now


EXPECTED_AGENT = {
    "human_gate": "research-director",
    "final_audit": "reviewer-verifier-agent",
    "verifier": "reviewer-verifier-agent",
}


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _events(store: StateBackend) -> list[dict[str, Any]]:
    if not store.events_path.is_file():
        return []
    return [json.loads(line) for line in store.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _traces(store: StateBackend) -> list[dict[str, Any]]:
    path = store.run_dir / "traces.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _infer_project_dir(state: dict[str, Any], supplied: str | Path | None) -> Path | None:
    if supplied is not None:
        return Path(supplied).resolve()
    manifest = next((item for item in state.get("artifacts", []) if item.get("artifact_id") == "project-manifest"), None)
    return Path(manifest["path"]).resolve().parent if manifest else None


def _verification_receipts(state: dict[str, Any], project_dir: Path | None) -> list[dict[str, Any]]:
    if project_dir is None:
        return []
    receipts = []
    for artifact in state.get("artifacts", []):
        if artifact.get("external") or not str(artifact.get("path", "")).lower().endswith(".json"):
            continue
        path = (project_dir / artifact["path"]).resolve()
        if not path.is_relative_to(project_dir) or not path.is_file():
            continue
        if artifact.get("sha256") and sha256_file(path) != artifact["sha256"]:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            continue
        if value.get("schema_version") == "evidence-verification/1.0":
            receipts.append(value)
    return receipts


def evaluate(store: StateBackend, project_dir: str | Path | None = None) -> dict[str, Any]:
    state = store.load(); tasks = state["task_graph"]; total = len(tasks)
    complete = sum(item["status"] in {"complete", "skipped", "superseded"} for item in tasks)
    blocked = sum(item["status"] == "blocked" for item in tasks)
    waiting = sum(item["status"] in {"waiting-agent", "waiting-human"} for item in tasks)
    integrity_errors = store.verify(); events = _events(store); traces = _traces(store)
    resolved_project = _infer_project_dir(state, project_dir)
    receipts = _verification_receipts(state, resolved_project)
    by_type = {
        verifier_type: [item for item in receipts if item.get("verifier_type") == verifier_type]
        for verifier_type in ("citation", "fulltext", "numeric", "causal", "specification")
    }
    routing_checks = []
    for item in tasks:
        expected = EXPECTED_AGENT.get(item["task_type"])
        if expected:
            routing_checks.append(item["assigned_agent"] == expected)
        elif item["task_type"] == "agent":
            routing_checks.append(item["assigned_agent"] in {
                "research-director", "literature-agent", "empirical-agent", "writing-agent",
            })
    task_by_id = {item["task_id"]: item for item in tasks}
    tool_routes = [
        run.get("name") in task_by_id.get(run.get("task_id"), {}).get("allowed_tools", [])
        for run in state.get("tool_runs", []) if run.get("task_id") in task_by_id
    ]
    try:
        validate_dag(tasks); valid_dag = True
    except ValueError:
        valid_dag = False
    decisions = state.get("decisions", [])
    replanned = [item for item in tasks if item.get("strategy_replans", 0) > 0]
    successful_replans = sum(item["status"] == "superseded" for item in replanned)
    citation = by_type["citation"]; fulltext = by_type["fulltext"]; numeric = by_type["numeric"]
    causal = by_type["causal"]; specification = by_type["specification"]
    artifact_failures = []
    if resolved_project is not None:
        for artifact in state.get("artifacts", []):
            if artifact.get("external"):
                continue
            path = (resolved_project / artifact["path"]).resolve()
            if not path.is_relative_to(resolved_project) or not path.is_file() or (
                artifact.get("sha256") and sha256_file(path) != artifact["sha256"]
            ):
                artifact_failures.append(artifact.get("artifact_id"))
    token_total = sum(
        int((item.get("observation") or {}).get("token_usage", {}).get("total_tokens") or 0)
        for item in tasks
    )
    cost_values = [
        (item.get("observation") or {}).get("token_usage", {}).get("cost_usd")
        for item in tasks
        if (item.get("observation") or {}).get("token_usage", {}).get("cost_usd") is not None
    ]
    recovered = [event for event in events if event.get("type") == "run.recovered"]
    resumed = [event for event in events if event.get("type") == "run.resumed"]
    status = "blocked" if blocked or integrity_errors or not valid_dag else (
        "waiting" if waiting else ("pass" if complete == total else "review-required")
    )
    metric_groups = {
        "routing": {
            "correct_specialist_rate": _ratio(sum(routing_checks), len(routing_checks)),
            "incorrect_tool_rate": _ratio(sum(not value for value in tool_routes), len(tool_routes)),
        },
        "planning": {
            "valid_dag": valid_dag,
            "unnecessary_task_rate": None,
            "human_correction_rate": _ratio(sum(not item.get("approved", False) for item in decisions), len(decisions)),
            "replanning_success": _ratio(successful_replans, len(replanned)),
        },
        "literature": {
            "citation_precision": _ratio(sum(item["status"] == "pass" for item in citation), len(citation)),
            "doi_correctness": None,
            "fulltext_verification_precision": _ratio(sum(item["status"] == "pass" for item in fulltext), len(fulltext)),
            "claim_entailment_accuracy": _ratio(sum(item["status"] == "pass" for item in citation), len(citation)),
            "duplicate_rate": None,
        },
        "empirical": {
            "result_reproducibility": None,
            "coefficient_match": _ratio(sum(item["status"] == "pass" for item in numeric), len(numeric)),
            "se_match": None,
            "sample_match": _ratio(sum(bool(item.get("output", {}).get("identity_match")) for item in numeric), len(numeric)),
            "specification_drift_rate": _ratio(sum(bool(item.get("output", {}).get("specification_drift")) for item in specification), len(specification)),
            "causal_design_compatibility": _ratio(sum(item["status"] == "pass" for item in causal), len(causal)),
        },
        "writing": {
            "unsupported_citation_rate": _ratio(sum(item["status"] != "pass" for item in citation), len(citation)),
            "unsupported_numerical_claim_rate": _ratio(sum(item["status"] != "pass" for item in numeric), len(numeric)),
            "manuscript_artifact_consistency": not artifact_failures if state.get("manuscript_state", {}).get("artifact_refs") else None,
        },
        "runtime": {
            "recovery_success": (not integrity_errors) if recovered else None,
            "checkpoint_resume_success": (not integrity_errors) if resumed else None,
            "duplicate_side_effect_rate": None,
            "false_completion_rate": _ratio(len(artifact_failures), complete),
            "infinite_loop_prevention": state["runtime_control"]["total_steps"] <= state["runtime_control"]["max_total_steps"],
        },
        "efficiency": {
            "tokens": token_total,
            "model_requests": len(state.get("agent_runs", [])),
            "cost_usd": sum(float(value) for value in cost_values) if cost_values else None,
            "wall_time_ms": sum(float(item.get("latency_ms", 0)) for item in traces),
            "tools_per_completed_task": _ratio(len(state.get("tool_runs", [])), complete),
        },
    }
    unavailable = [
        f"{group}.{name}" for group, values in metric_groups.items()
        for name, value in values.items() if value is None
    ]
    return {
        "schema_version": "agent-run-evaluation/1.0", "run_id": state["run_id"],
        "evaluated_at": utc_now(), "status": status,
        "metrics": {
            "tasks_total": total, "tasks_complete": complete, "tasks_blocked": blocked,
            "tasks_waiting": waiting, "completion_rate": complete / total if total else 0,
            "errors": len(state["errors"]), "retries": state["retry_count"],
            "artifacts": len(state["artifacts"]), "checkpoints": len(state["checkpoints"]),
        },
        "metric_groups": metric_groups, "unavailable_metrics": unavailable,
        "measurement_notes": [
            "Null means evidence was unavailable; it is not treated as success.",
            "Scientific metrics derive only from registered, hash-matching verification receipts.",
        ],
        "integrity_errors": integrity_errors + [f"artifact mismatch: {item}" for item in artifact_failures],
    }
