"""Provider output shape; canonical validation still uses the repository schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import jsonschema

from .base import require_langchain


def observation_model() -> type:
    require_langchain()
    from pydantic import BaseModel, ConfigDict, Field

    class Artifact(BaseModel):
        path: str
        sha256: str

    class ToolCall(BaseModel):
        name: str
        call_id: str
        status: str

    class StructuredObservation(BaseModel):
        model_config = ConfigDict(extra="forbid")
        outcome: Literal["PASS", "FAIL_TRANSIENT", "FAIL_STRATEGY", "BLOCKED", "HIGH_RISK_DECISION", "GOAL_COMPLETE"]
        summary: str
        artifacts: list[Artifact] = Field(default_factory=list)
        tool_calls: list[ToolCall] = Field(default_factory=list)
        errors: list[str] = Field(default_factory=list)
        next_tasks: list[dict[str, Any]] = Field(default_factory=list)
        replacement_tasks: list[dict[str, Any]] = Field(default_factory=list)
        human_action: str | None = None
        replan: Literal["new_evidence", "robustness"] | None = None

    return StructuredObservation


def validate_observation(value: Any, repository_root: Path) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    if not isinstance(value, dict):
        raise TypeError("LangChain structured_response must be an object")
    schema_path = repository_root / "schemas" / "research-agent-observation.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(value)
    if "outcome" not in value or "summary" not in value:
        raise ValueError("LangChain observation requires outcome and summary")
    if value.get("tool_requests"):
        raise ValueError("LangChain tools must run through the bound ToolBridge")
    return value
