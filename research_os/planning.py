"""Provider-neutral planning proposals with deterministic safety validation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema

from .planner import AGENTS, add_dynamic_tasks, task, validate_dag


class PlanningAdapter(ABC):
    @abstractmethod
    def initial_plan(self, request: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def adaptive_plan(self, request: dict[str, Any]) -> dict[str, Any]: ...


class MockPlanningAdapter(PlanningAdapter):
    def __init__(self, initial: dict[str, Any] | None = None, adaptive: dict[str, Any] | None = None):
        self.initial = deepcopy(initial); self.adaptive = deepcopy(adaptive)

    def initial_plan(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.initial is None: raise RuntimeError("No initial mock plan")
        return deepcopy(self.initial)

    def adaptive_plan(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.adaptive is None: raise RuntimeError("No adaptive mock plan")
        return deepcopy(self.adaptive)


class BoundedPlanner:
    def __init__(self, tool_manifests: list[dict[str, Any]], repository_root: str | Path | None = None):
        self.tools = {item["name"]: item for item in tool_manifests}
        root = Path(repository_root or Path(__file__).resolve().parents[1])
        self.schema = json.loads((root / "schemas/task-graph-proposal.schema.json").read_text(encoding="utf-8"))

    def validate_proposal(self, proposal: dict[str, Any], *, data_sensitivity: str,
                          max_tasks: int, existing_graph: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        jsonschema.Draft202012Validator(self.schema).validate(proposal)
        if len(proposal["tasks"]) + len(existing_graph or []) > max_tasks:
            raise ValueError("Planning proposal exceeds task budget")
        canonical = []
        for raw in proposal["tasks"]:
            if raw["assigned_agent"] not in AGENTS:
                raise ValueError(f"Unapproved agent: {raw['assigned_agent']}")
            for name in raw.get("allowed_tools", []):
                if name not in self.tools:
                    raise ValueError(f"Unknown tool in plan: {name}")
                manifest = self.tools[name]
                if data_sensitivity not in manifest["data_sensitivity"]:
                    raise PermissionError(f"Tool {name} is not authorized for {data_sensitivity} projects")
                if manifest["side_effect_level"] in {"external-write", "high-risk"} and not raw.get("requires_human_approval"):
                    raise PermissionError(f"High-risk tool task must require human approval: {raw['task_id']}")
            canonical.append(task(
                raw["task_id"], raw["goal"], raw["task_type"], raw["assigned_agent"], raw["dependencies"],
                required_inputs=raw.get("required_inputs", {}), expected_outputs=raw.get("expected_outputs", []),
                allowed_tools=raw.get("allowed_tools", []), max_attempts=raw.get("retry_policy", {}).get("max_attempts", 2),
                timeout_seconds=raw.get("timeout_seconds", 900), requires_human_approval=raw.get("requires_human_approval", False),
                verification_rules=raw.get("verification_rules", []), tool_name=raw.get("tool_name"),
            ))
        candidate = list(existing_graph or []) + canonical
        validate_dag(candidate)
        if proposal["mode"] == "initial":
            audits = [item for item in candidate if item["task_type"] == "final_audit"]
            gates = [item for item in candidate if item["task_type"] == "human_gate" and item["task_id"] == "final-gate"]
            if len(audits) != 1 or len(gates) != 1 or audits[0]["task_id"] not in gates[0]["dependencies"]:
                raise ValueError("Initial plan must preserve one final audit followed by final-gate")
        return canonical

    def merge(self, graph: list[dict[str, Any]], proposal: dict[str, Any], *, data_sensitivity: str,
              max_tasks: int) -> list[dict[str, Any]]:
        if proposal["mode"] == "initial":
            canonical = self.validate_proposal(proposal, data_sensitivity=data_sensitivity, max_tasks=max_tasks)
            graph[:] = canonical
        else:
            parent = proposal.get("parent_task_id")
            if not parent or parent not in {item["task_id"] for item in graph}:
                raise ValueError("Adaptive proposal requires an existing parent_task_id")
            self.validate_proposal(proposal, data_sensitivity=data_sensitivity, max_tasks=max_tasks, existing_graph=graph)
            add_dynamic_tasks(graph, proposal["tasks"], parent, max_tasks)
        validate_dag(graph)
        return graph

    def request_and_merge(self, adapter: PlanningAdapter, graph: list[dict[str, Any]], request: dict[str, Any],
                          *, mode: str, data_sensitivity: str, max_tasks: int) -> dict[str, Any]:
        proposal = adapter.initial_plan(deepcopy(request)) if mode == "initial" else adapter.adaptive_plan(deepcopy(request))
        if proposal.get("mode") != mode:
            raise ValueError("Planning adapter returned the wrong proposal mode")
        self.merge(graph, proposal, data_sensitivity=data_sensitivity, max_tasks=max_tasks)
        return proposal
