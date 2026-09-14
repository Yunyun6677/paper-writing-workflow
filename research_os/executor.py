"""AgentExecutor validates adapter output without owning ResearchState."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import jsonschema

from .adapters.base import AgentExecutionRequest, ModelAdapter


class AgentExecutor:
    def __init__(self, adapter: ModelAdapter, repository_root: str | Path | None = None):
        self.adapter = adapter
        self.repository_root = Path(repository_root or Path(__file__).resolve().parents[1]).resolve()
        self.observation_schema = json.loads(
            (self.repository_root / "schemas" / "research-agent-observation.schema.json").read_text(encoding="utf-8")
        )

    def execute(self, request: AgentExecutionRequest,
                tool_runner: Callable[[str, dict[str, Any], str], dict[str, Any]] | None = None,
                max_tool_rounds: int = 8) -> dict[str, Any]:
        observation = self.validate_observation(self.adapter.run_agent(request), request)
        return self._drive(request, observation, tool_runner, max_tool_rounds)

    def _drive(self, request: AgentExecutionRequest, observation: dict[str, Any],
               tool_runner: Callable[[str, dict[str, Any], str], dict[str, Any]] | None,
               max_tool_rounds: int) -> dict[str, Any]:
        calls: list[dict[str, Any]] = []; artifacts: list[dict[str, Any]] = []
        for _ in range(max_tool_rounds):
            requests = observation.get("tool_requests", [])
            if not requests:
                observation["tool_calls"] = calls + observation.get("tool_calls", [])
                known = {(item["path"], item["sha256"]) for item in observation.get("artifacts", [])}
                observation["artifacts"] = observation.get("artifacts", []) + [item for item in artifacts if (item["path"], item["sha256"]) not in known]
                return self.validate_observation(observation, request)
            if tool_runner is None:
                raise RuntimeError("Agent requested tools but no tool runner was supplied")
            results = []
            for item in requests:
                name, call_id = item["name"], item["call_id"]
                if name not in request.allowed_tools:
                    raise PermissionError(f"Agent requested a tool outside its assignment: {name}")
                arguments = item.get("arguments", {})
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                if not isinstance(arguments, dict):
                    raise TypeError("Tool arguments must decode to a JSON object")
                result = tool_runner(name, arguments, call_id)
                results.append({"call_id": call_id, "name": name, "result": result})
                calls.append({"name": name, "call_id": call_id, "status": result.get("status", "unknown")})
                artifacts.extend(result.get("artifacts", []))
            observation = self.validate_observation(
                self.adapter.resume_agent(request.agent_run_id, {"tool_results": results}), request)
        if not observation.get("tool_requests"):
            observation["tool_calls"] = calls + observation.get("tool_calls", [])
            known = {(item["path"], item["sha256"]) for item in observation.get("artifacts", [])}
            observation["artifacts"] = observation.get("artifacts", []) + [
                item for item in artifacts if (item["path"], item["sha256"]) not in known
            ]
            return self.validate_observation(observation, request)
        raise RuntimeError(f"Agent exceeded bounded tool rounds: {max_tool_rounds}")

    def resume(self, request: AgentExecutionRequest, response: dict[str, Any] | None = None,
               tool_runner: Callable[[str, dict[str, Any], str], dict[str, Any]] | None = None,
               max_tool_rounds: int = 8) -> dict[str, Any]:
        observation = self.adapter.resume_agent(request.agent_run_id, response)
        return self._drive(request, self.validate_observation(observation, request), tool_runner, max_tool_rounds)

    def validate_observation(self, value: dict[str, Any], request: AgentExecutionRequest) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise TypeError("Model adapter must return a JSON object")
        jsonschema.Draft202012Validator(
            self.observation_schema, format_checker=jsonschema.FormatChecker()
        ).validate(value)
        # Executable adapters use the explicit decision vocabulary. Legacy status-only
        # observations remain accepted by the manual CLI but cannot pass this boundary.
        if "outcome" not in value:
            raise ValueError("Executable model observations require an explicit outcome")
        observed_run = value.get("agent_run_id")
        if observed_run is not None and observed_run != request.agent_run_id:
            raise ValueError("Observation agent_run_id does not match the assignment")
        observed_task = value.get("task_id")
        if observed_task is not None and observed_task != request.task_id:
            raise ValueError("Observation task_id does not match the assignment")
        result = deepcopy(value)
        result.setdefault("agent_run_id", request.agent_run_id)
        result.setdefault("task_id", request.task_id)
        result.setdefault("provider", self.adapter.provider_id)
        result.setdefault("model", self.adapter.model_id)
        result.setdefault("artifacts", [])
        result.setdefault("tool_calls", [])
        result.setdefault("errors", [])
        result.setdefault("token_usage", self.adapter.usage(request.agent_run_id).__dict__)
        # Revalidate after normalized metadata is added.
        jsonschema.Draft202012Validator(
            self.observation_schema, format_checker=jsonschema.FormatChecker()
        ).validate(result)
        return result
