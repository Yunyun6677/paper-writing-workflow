"""Deterministic research-plan templates and safe DAG expansion."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


AGENTS = {
    "research-director": "Owns the goal, plan, gates, reconciliation, and final completion decision.",
    "literature-agent": "Plans retrieval and converts verified full text into evidence records.",
    "empirical-agent": "Owns data diagnostics, identification, execution specifications, and numerical lineage.",
    "writing-agent": "Drafts LaTeX from approved evidence and numerical artifacts.",
    "reviewer-verifier-agent": "Independently challenges evidence entailment, identification, and artifact integrity.",
}


def task(task_id: str, title: str, kind: str, owner: str, depends_on: list[str], **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "task_id": task_id,
        "title": title,
        "kind": kind,
        "owner": owner,
        "status": "pending",
        "depends_on": depends_on,
        "inputs": extra.pop("inputs", {}),
        "expected_outputs": extra.pop("expected_outputs", []),
        "acceptance_criteria": extra.pop("acceptance_criteria", []),
        "max_retries": extra.pop("max_retries", 1),
        "retry_count": 0,
        "requires_human_approval": extra.pop("requires_human_approval", False),
        "tool_name": extra.pop("tool_name", None),
        "observation": None,
        "error": None,
    }
    result.update(extra)
    return result


def default_graph(paper_type: str) -> list[dict[str, Any]]:
    empirical = paper_type in {"empirical", "mixed", "measurement", "replication"}
    nodes = [
        task("frame", "Freeze question, scope, and contribution", "agent", "research-director", [],
             expected_outputs=["design/design-register.json"], requires_human_approval=True,
             acceptance_criteria=["research question is explicit", "high-risk choices are surfaced"]),
        task("question-gate", "Approve question and contribution", "human_gate", "research-director", ["frame"],
             requires_human_approval=True, acceptance_criteria=["explicit human decision recorded"]),
        task("literature", "Acquire, verify, and read relevant literature", "agent", "literature-agent", ["question-gate"],
             expected_outputs=["literature/acquisition-ledger.json", "literature/evidence-cards"],
             acceptance_criteria=["claims trace to inspected full text"]),
    ]
    if empirical:
        nodes.extend([
            task("empirical-design", "Specify estimand and identification design", "agent", "empirical-agent", ["question-gate"],
                 expected_outputs=["design/design-register.json"], requires_human_approval=True,
                 acceptance_criteria=["estimand and identifying assumptions are explicit"]),
            task("design-gate", "Approve empirical design", "human_gate", "research-director", ["empirical-design"],
                 requires_human_approval=True, acceptance_criteria=["explicit human decision recorded"]),
            task("analysis", "Run registered analysis and preserve receipts", "agent", "empirical-agent", ["design-gate"],
                 expected_outputs=["analysis"], acceptance_criteria=["engine receipts and hashes exist"]),
        ])
        writing_dependencies = ["literature", "analysis"]
    else:
        writing_dependencies = ["literature"]
    nodes.extend([
        task("writing", "Draft evidence-grounded LaTeX manuscript", "agent", "writing-agent", writing_dependencies,
             expected_outputs=["paper/main.tex", "paper/references.bib"],
             acceptance_criteria=["citation and numerical firewalls hold"]),
        task("verification", "Run independent evidence and artifact verification", "verifier", "reviewer-verifier-agent", ["writing"],
             tool_name="research_firewall", expected_outputs=["audit/agent-runtime-audit.json"],
             acceptance_criteria=["no blocking lineage failure"]),
        task("final-gate", "Approve final research package", "human_gate", "research-director", ["verification"],
             requires_human_approval=True, acceptance_criteria=["explicit human decision recorded"]),
    ])
    return nodes


def validate_dag(tasks: list[dict[str, Any]]) -> None:
    ids = [item["task_id"] for item in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate task_id in task graph")
    known = set(ids)
    for item in tasks:
        unknown = set(item.get("depends_on", [])) - known
        if unknown:
            raise ValueError(f"Unknown dependency for {item['task_id']}: {sorted(unknown)}")
    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {item["task_id"]: item for item in tasks}

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError(f"Cycle detected at {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in by_id[node].get("depends_on", []):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in ids:
        visit(node)


def add_dynamic_tasks(tasks: list[dict[str, Any]], additions: list[dict[str, Any]], parent_task: str) -> None:
    allowed_kinds = {"agent", "tool", "human_gate", "verifier"}
    allowed_owners = set(AGENTS)
    candidates = deepcopy(tasks)
    added_ids: list[str] = []
    for raw in additions:
        required = {"task_id", "title", "kind", "owner"}
        if not required.issubset(raw):
            raise ValueError(f"Dynamic task lacks required fields: {sorted(required - set(raw))}")
        if raw["kind"] not in allowed_kinds or raw["owner"] not in allowed_owners:
            raise ValueError("Dynamic task kind or owner is outside the approved architecture")
        dependencies = raw.get("depends_on", [parent_task])
        candidates.append(task(raw["task_id"], raw["title"], raw["kind"], raw["owner"], dependencies,
                               inputs=raw.get("inputs", {}), expected_outputs=raw.get("expected_outputs", []),
                               acceptance_criteria=raw.get("acceptance_criteria", []),
                               max_retries=raw.get("max_retries", 1), tool_name=raw.get("tool_name"),
                               requires_human_approval=raw.get("requires_human_approval", False)))
        added_ids.append(raw["task_id"])
    # The final approval cannot race ahead of dynamically discovered work.
    final_gate = next((item for item in candidates if item["task_id"] == "final-gate"), None)
    if final_gate:
        final_gate["depends_on"] = list(dict.fromkeys(final_gate["depends_on"] + added_ids))
    validate_dag(candidates)
    tasks[:] = candidates
