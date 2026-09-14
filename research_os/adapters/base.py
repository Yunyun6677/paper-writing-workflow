"""Provider-neutral contract for executing a bounded specialist agent.

Adapters receive a deliberately reduced request, never canonical ResearchState.
They return proposals/observations; only ResearchRuntime may transition state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float | None = None

    def __post_init__(self) -> None:
        for name in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens", "reasoning_tokens"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.cost_usd is not None and self.cost_usd < 0:
            raise ValueError("cost_usd cannot be negative")


@dataclass(frozen=True)
class AgentExecutionRequest:
    agent_run_id: str
    task_id: str
    agent_identity: str
    task_goal: str
    allowed_skills: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    tool_specs: tuple[dict[str, Any], ...] = ()
    working_context: dict[str, Any] = field(default_factory=dict)
    artifact_context: tuple[dict[str, Any], ...] = ()
    expected_output_schema: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 900
    token_budget: int | None = None
    cost_budget_usd: float | None = None
    data_sensitivity: str = "restricted"
    context_policy: str = "least-context"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("agent_run_id", "task_id", "agent_identity", "task_goal"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if self.token_budget is not None and self.token_budget < 1:
            raise ValueError("token_budget must be positive")
        if self.cost_budget_usd is not None and self.cost_budget_usd < 0:
            raise ValueError("cost_budget_usd cannot be negative")

    def to_payload(self) -> dict[str, Any]:
        """Return a defensive JSON-compatible copy for provider code."""
        return deepcopy(asdict(self))


class ModelAdapter(ABC):
    """Minimal lifecycle contract implemented only in provider adapter modules."""

    provider_id: str
    model_id: str

    @abstractmethod
    def run_agent(self, request: AgentExecutionRequest) -> dict[str, Any]:
        """Start a specialist run and return a structured observation."""

    @abstractmethod
    def resume_agent(self, agent_run_id: str, response: dict[str, Any] | None = None) -> dict[str, Any]:
        """Resume an interrupted/paused adapter run."""

    @abstractmethod
    def stream_events(self, agent_run_id: str) -> Iterable[dict[str, Any]]:
        """Return normalized events observed for one adapter run."""

    @abstractmethod
    def cancel(self, agent_run_id: str) -> dict[str, Any]:
        """Request cancellation and report whether it was applied."""

    @abstractmethod
    def usage(self, agent_run_id: str) -> ModelUsage:
        """Return usage for this adapter run only."""
