"""Deterministic adapter used for CI and failure injection, never production."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable

from .base import AgentExecutionRequest, ModelAdapter, ModelUsage


class MockModelAdapter(ModelAdapter):
    provider_id = "mock"

    def __init__(self, scripts: dict[str, list[dict[str, Any]] | dict[str, Any]] | None = None, model_id: str = "mock-deterministic-v1"):
        self.model_id = model_id
        self._scripts: dict[str, list[dict[str, Any]]] = {}
        for key, value in (scripts or {}).items():
            self._scripts[key] = deepcopy(value if isinstance(value, list) else [value])
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._usage: dict[str, ModelUsage] = {}
        self._cancelled: set[str] = set()
        self._requests: dict[str, AgentExecutionRequest] = {}

    def _next(self, request: AgentExecutionRequest) -> dict[str, Any]:
        if request.agent_run_id in self._cancelled:
            raise RuntimeError(f"Mock run is cancelled: {request.agent_run_id}")
        queue = self._scripts.get(request.task_id, [])
        if not queue:
            raise RuntimeError(f"No deterministic mock observation for task: {request.task_id}")
        value = deepcopy(queue.pop(0))
        injected = value.pop("_inject", None)
        if injected == "timeout":
            self._events[request.agent_run_id].append({"type": "model.timeout", "task_id": request.task_id})
            raise TimeoutError(f"Injected mock timeout: {request.task_id}")
        if injected == "exception":
            raise RuntimeError(f"Injected mock exception: {request.task_id}")
        usage = value.get("token_usage", {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
        self._usage[request.agent_run_id] = ModelUsage(**{k: v for k, v in usage.items() if k in ModelUsage.__dataclass_fields__})
        self._events[request.agent_run_id].append({"type": "model.completed", "task_id": request.task_id, "outcome": value.get("outcome")})
        return value

    def run_agent(self, request: AgentExecutionRequest) -> dict[str, Any]:
        if request.agent_run_id in self._requests:
            raise ValueError(f"Duplicate mock agent_run_id: {request.agent_run_id}")
        self._requests[request.agent_run_id] = request
        self._events[request.agent_run_id].append({"type": "model.started", "task_id": request.task_id})
        return self._next(request)

    def resume_agent(self, agent_run_id: str, response: dict[str, Any] | None = None) -> dict[str, Any]:
        if agent_run_id not in self._requests:
            raise KeyError(agent_run_id)
        self._events[agent_run_id].append({"type": "model.resumed", "response_present": response is not None})
        return self._next(self._requests[agent_run_id])

    def stream_events(self, agent_run_id: str) -> Iterable[dict[str, Any]]:
        return iter(deepcopy(self._events.get(agent_run_id, [])))

    def cancel(self, agent_run_id: str) -> dict[str, Any]:
        if agent_run_id not in self._requests:
            return {"agent_run_id": agent_run_id, "cancelled": False, "reason": "unknown-run"}
        self._cancelled.add(agent_run_id)
        self._events[agent_run_id].append({"type": "model.cancelled"})
        return {"agent_run_id": agent_run_id, "cancelled": True}

    def usage(self, agent_run_id: str) -> ModelUsage:
        return self._usage.get(agent_run_id, ModelUsage())
