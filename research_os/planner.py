"""Deterministic planning, bounded dynamic DAG expansion, and specialist routing."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from .contracts import dependencies, sync_compatibility_aliases

AGENTS = {
    "research-director": "Owns goals, planning, gates, reconciliation, and completion.",
    "literature-agent": "Uses literature skills to acquire and convert verified full text into evidence.",
    "empirical-agent": "Uses the empirical skill for design, diagnostics, execution, and numerical lineage.",
    "writing-agent": "Drafts LaTeX only from approved artifacts.",
    "reviewer-verifier-agent": "Independently verifies worker artifacts from an artifact-only context.",
}
CAPABILITIES = {
    "research-director": ["economics-paper-workflow:orchestration"],
    "literature-agent": ["social-science-literature-review", "cnki-literature-acquisition", "international-literature-acquisition"],
    "empirical-agent": ["economics-empirical-analysis"],
    "writing-agent": ["economics-paper-workflow:writing"],
    "reviewer-verifier-agent": ["economics-paper-workflow:audit"],
}

def task(task_id: str, title: str, kind: str, owner: str, depends_on: list[str], **extra: Any) -> dict[str, Any]:
    max_attempts = extra.pop("max_attempts", extra.pop("max_retries", 1) + 1)
    result: dict[str, Any] = {
        "task_id": task_id, "task_type": kind, "goal": title, "dependencies": list(depends_on),
        "required_inputs": extra.pop("required_inputs", extra.pop("inputs", {})),
        "expected_outputs": extra.pop("expected_outputs", []), "assigned_agent": owner,
        "allowed_tools": extra.pop("allowed_tools", []), "status": "pending",
        "retry_policy": {"max_attempts": max_attempts, "retry_on": ["FAIL_TRANSIENT"]},
        "timeout_seconds": extra.pop("timeout_seconds", 900),
        "stopping_condition": extra.pop("stopping_condition", "success contract verified or failure contract activated"),
        "success_contract": extra.pop("success_contract", extra.pop("acceptance_criteria", ["declared outputs satisfy verification rules"])),
        "failure_contract": extra.pop("failure_contract", ["record error and evidence", "do not infer success", "handoff after bounded recovery"]),
        "verification_rules": extra.pop("verification_rules", []), "attempts": 0,
        "strategy_replans": 0, "max_strategy_replans": extra.pop("max_strategy_replans", 2),
        "requires_human_approval": extra.pop("requires_human_approval", False),
        "tool_name": extra.pop("tool_name", None), "observation": None, "error": None,
        "capabilities": CAPABILITIES.get(owner, []),
    }
    result.update(extra)
    sync_compatibility_aliases(result)
    return result

def default_graph(paper_type: str) -> list[dict[str, Any]]:
    empirical = paper_type in {"empirical", "mixed", "measurement", "replication"}
    nodes = [
        task("frame", "Freeze research question, scope, and contribution", "agent", "research-director", [], expected_outputs=["design/design-register.json"], requires_human_approval=True, success_contract=["research question is explicit", "high-risk choices are surfaced"]),
        task("question-gate", "Approve question and contribution", "human_gate", "research-director", ["frame"], requires_human_approval=True, success_contract=["explicit human decision recorded"]),
        task("literature", "Acquire, verify, and read relevant literature", "agent", "literature-agent", ["question-gate"], expected_outputs=["literature/acquisition-ledger.json", "literature/evidence-cards"], success_contract=["claims trace to inspected full text"], verification_rules=["citation entailment", "full-text status", "provenance and hashes"]),
        task("literature-review", "Independently verify the literature evidence package", "verifier", "reviewer-verifier-agent", ["literature"], required_inputs={"producer_task_id": "literature"}, success_contract=["citation and full-text guardrails pass"], verification_rules=["reviewer differs from producer"]),
    ]
    if empirical:
        nodes += [
            task("empirical-design", "Specify estimand and identification design", "agent", "empirical-agent", ["question-gate", "literature-review"], expected_outputs=["design/design-register.json"], requires_human_approval=True, success_contract=["estimand and identifying assumptions are explicit"]),
            task("design-review", "Independently verify identification and specification", "verifier", "reviewer-verifier-agent", ["empirical-design"], required_inputs={"producer_task_id": "empirical-design"}, success_contract=["design diagnostics pass"]),
            task("design-gate", "Approve empirical design", "human_gate", "research-director", ["design-review"], requires_human_approval=True, success_contract=["explicit human decision recorded"]),
            task("analysis", "Run registered analysis and preserve execution receipts", "agent", "empirical-agent", ["design-gate"], expected_outputs=["analysis"], success_contract=["engine receipts and hashes exist"], verification_rules=["numerical lineage", "specification lock", "reproducibility"]),
            task("empirical-review", "Independently verify empirical artifacts and claims", "verifier", "reviewer-verifier-agent", ["analysis"], required_inputs={"producer_task_id": "analysis"}, success_contract=["numeric, causal, and specification guardrails pass"]),
        ]
        writing_dependencies = ["literature-review", "empirical-review"]
    else:
        writing_dependencies = ["literature-review"]
    nodes += [
        task("writing", "Draft the evidence-grounded LaTeX manuscript", "agent", "writing-agent", writing_dependencies, expected_outputs=["paper/main.tex", "paper/references.bib"], success_contract=["citation and numerical firewalls hold"]),
        task("manuscript-review", "Independently review evidence, methods, consistency, privacy, and journal fit", "verifier", "reviewer-verifier-agent", ["writing"], required_inputs={"producer_task_id": "writing"}, expected_outputs=["audit/agent-runtime-audit.json"], success_contract=["all blocking guardrails pass"], verification_rules=["citation entailment", "numerical consistency", "research design", "empirical specification", "robustness logic", "manuscript consistency", "reproducibility", "data/privacy", "journal fit"]),
        task("final-audit", "Run final integrity and scientific-contract audit", "final_audit", "reviewer-verifier-agent", ["manuscript-review"], tool_name="research_firewall", allowed_tools=["research_firewall"], expected_outputs=["audit/agent-runtime-audit.json"], success_contract=["no blocking lineage failure"]),
        task("final-gate", "Approve the final research package", "human_gate", "research-director", ["final-audit"], requires_human_approval=True, success_contract=["explicit human decision recorded"]),
    ]
    validate_dag(nodes)
    return nodes

def validate_dag(tasks: list[dict[str, Any]]) -> None:
    ids = [item["task_id"] for item in tasks]
    if len(ids) != len(set(ids)): raise ValueError("Duplicate task_id in task graph")
    known, by_id = set(ids), {item["task_id"]: item for item in tasks}
    for item in tasks:
        unknown = set(dependencies(item)) - known
        if unknown: raise ValueError(f"Unknown dependency for {item['task_id']}: {sorted(unknown)}")
        if item.get("task_type") == "verifier":
            producer = item.get("required_inputs", {}).get("producer_task_id")
            if not producer:
                raise ValueError(f"Verifier must declare producer_task_id: {item['task_id']}")
            if producer and by_id[producer].get("assigned_agent") == item.get("assigned_agent"):
                raise ValueError(f"Verifier must be independent of producer: {item['task_id']}")
    visiting, visited = set(), set()
    def visit(node: str) -> None:
        if node in visiting: raise ValueError(f"Cycle detected at {node}")
        if node in visited: return
        visiting.add(node)
        for dependency in dependencies(by_id[node]): visit(dependency)
        visiting.remove(node); visited.add(node)
    for node in ids: visit(node)

def add_dynamic_tasks(tasks: list[dict[str, Any]], additions: list[dict[str, Any]], parent_task: str, max_total_tasks: int = 100) -> None:
    if len(tasks) + len(additions) > max_total_tasks: raise ValueError("Dynamic task budget exceeded")
    allowed_kinds, candidates, added_ids = {"agent", "tool", "human_gate", "verifier", "final_audit"}, deepcopy(tasks), []
    for raw in additions:
        task_id, title = raw.get("task_id"), raw.get("goal", raw.get("title"))
        kind, owner = raw.get("task_type", raw.get("kind")), raw.get("assigned_agent", raw.get("owner"))
        if not all([task_id, title, kind, owner]): raise ValueError("Dynamic task requires task_id, goal, task_type, and assigned_agent")
        if kind not in allowed_kinds or owner not in AGENTS: raise ValueError("Dynamic task kind or agent is outside the approved architecture")
        deps = raw.get("dependencies", raw.get("depends_on", [parent_task]))
        candidates.append(task(task_id, title, kind, owner, deps, required_inputs=raw.get("required_inputs", raw.get("inputs", {})), expected_outputs=raw.get("expected_outputs", []), allowed_tools=raw.get("allowed_tools", []), success_contract=raw.get("success_contract") or raw.get("acceptance_criteria") or ["declared outputs satisfy verification rules"], failure_contract=raw.get("failure_contract") or ["record failure and hand off after bounded recovery"], verification_rules=raw.get("verification_rules", []), max_attempts=raw.get("retry_policy", {}).get("max_attempts", raw.get("max_retries", 1) + 1), timeout_seconds=raw.get("timeout_seconds", raw.get("timeout", 900)), stopping_condition=raw.get("stopping_condition", "verified or handed off"), tool_name=raw.get("tool_name"), requires_human_approval=raw.get("requires_human_approval", False)))
        added_ids.append(task_id)
    for item in candidates:
        if item["task_id"] in {"final-audit", "final-gate"}:
            item["dependencies"] = list(dict.fromkeys(dependencies(item) + added_ids)); sync_compatibility_aliases(item)
    validate_dag(candidates); tasks[:] = candidates

def feedback_tasks(request: str, parent_task: str, sequence: int) -> list[dict[str, Any]]:
    """Build acyclic review feedback branches; each branch remains bounded by runtime budgets."""
    suffix = f"{sequence:02d}"
    if request == "new_evidence":
        evidence = f"literature-followup-{suffix}"
        return [
            {"task_id": evidence, "goal": "Acquire and verify evidence requested by review", "task_type": "agent", "assigned_agent": "literature-agent", "dependencies": [parent_task], "expected_outputs": ["literature/evidence-cards"], "verification_rules": ["full-text status", "citation entailment"]},
            {"task_id": f"manuscript-revision-{suffix}", "goal": "Revise manuscript using verified new evidence", "task_type": "agent", "assigned_agent": "writing-agent", "dependencies": [evidence], "expected_outputs": ["paper/main.tex"], "verification_rules": ["citation entailment", "manuscript consistency"]},
        ]
    if request == "robustness":
        robustness = f"robustness-followup-{suffix}"
        return [
            {"task_id": robustness, "goal": "Run pre-specified robustness analysis requested by review", "task_type": "agent", "assigned_agent": "empirical-agent", "dependencies": [parent_task], "expected_outputs": ["analysis"], "verification_rules": ["specification lock", "numerical lineage", "reproducibility"]},
            {"task_id": f"manuscript-revision-{suffix}", "goal": "Revise manuscript after verified robustness results", "task_type": "agent", "assigned_agent": "writing-agent", "dependencies": [robustness], "expected_outputs": ["paper/main.tex"], "verification_rules": ["numerical consistency", "manuscript consistency"]},
        ]
    raise ValueError(f"Unsupported feedback request: {request}")
