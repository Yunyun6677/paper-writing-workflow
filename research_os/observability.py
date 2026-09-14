"""Local-first tracing with OpenTelemetry and OpenAI Agents compatible semantics."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol

import jsonschema

from .store import utc_now


SENSITIVE_LEVELS = {"restricted", "personal", "confidential"}


@dataclass(frozen=True)
class TracePolicy:
    enabled: bool = True
    local_export_enabled: bool = True
    external_export_enabled: bool = False
    include_sensitive_content: bool = False
    allow_sensitive_external_export: bool = False

    @classmethod
    def from_file(cls, path: str | Path | None) -> "TracePolicy":
        if path is None or not Path(path).is_file():
            return cls()
        config_path = Path(path)
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        schema_path = config_path.parent.parent / "schemas" / "observability-policy.schema.json"
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(raw)
        return cls(**{key: raw[key] for key in cls.__dataclass_fields__ if key in raw})


class TraceExporter(Protocol):
    name: str
    def export(self, span: dict[str, Any]) -> None: ...


class CallbackExporter:
    """Adapter boundary for an OTel collector or OpenAI Agents trace processor."""
    def __init__(self, name: str, callback: Callable[[dict[str, Any]], None]):
        self.name = name
        self.callback = callback

    def export(self, span: dict[str, Any]) -> None:
        self.callback(span)


def _artifact_refs(value: Any) -> list[dict[str, str | None]]:
    found: list[dict[str, str | None]] = []
    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if any(key in node for key in ("artifact_id", "path", "sha256")):
                found.append({"artifact_id": node.get("artifact_id"), "path": node.get("path"), "sha256": node.get("sha256")})
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(value)
    unique: dict[tuple[Any, Any, Any], dict[str, str | None]] = {}
    for item in found:
        unique[(item["artifact_id"], item["path"], item["sha256"])] = item
    return list(unique.values())


def _usage(value: dict[str, Any] | None) -> dict[str, int | None]:
    raw = value or {}
    return {
        "input_tokens": raw.get("input_tokens"),
        "output_tokens": raw.get("output_tokens"),
        "total_tokens": raw.get("total_tokens"),
        "cached_tokens": raw.get("cached_tokens"),
        "reasoning_tokens": raw.get("reasoning_tokens"),
    }


def elapsed_ms(started_at: str, ended_at: str | None = None) -> float:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat((ended_at or utc_now()).replace("Z", "+00:00"))
    return max(0.0, (end - start).total_seconds() * 1000)


class TraceRecorder:
    def __init__(self, run_dir: str | Path, repository_root: str | Path, policy: TracePolicy | None = None, exporters: list[TraceExporter] | None = None):
        self.run_dir = Path(run_dir).resolve()
        self.path = self.run_dir / "traces.jsonl"
        self.policy = policy or TracePolicy.from_file(Path(repository_root) / "config" / "observability.json")
        self.exporters = exporters or []
        self.schema = json.loads((Path(repository_root) / "schemas" / "research-trace-span.schema.json").read_text(encoding="utf-8"))

    def record(self, *, state: dict[str, Any], name: str, kind: str, started_at: str, status: str,
               agent: str | None = None, model: str | None = None, task: dict[str, Any] | None = None,
               agent_run_id: str | None = None, provider: str | None = None,
               tool: str | None = None, outcome: str | None = None,
               tool_calls: list[dict[str, Any]] | None = None, inputs: Any = None, outputs: Any = None,
               token_usage: dict[str, Any] | None = None, errors: list[dict[str, Any]] | None = None,
               human_decisions: list[dict[str, Any]] | None = None, parent_span_id: str | None = None,
               attributes: dict[str, Any] | None = None, external_approved: bool = False) -> dict[str, Any] | None:
        if not self.policy.enabled:
            return None
        ended_at = utc_now()
        sensitivity = state.get("data_sensitivity", "restricted")
        safe_errors = []
        for error in errors or []:
            message = str(error.get("message", ""))
            safe_errors.append({"type": error.get("type", "Error"), "message": message if sensitivity not in SENSITIVE_LEVELS else "[redacted]", "message_sha256": hashlib.sha256(message.encode()).hexdigest() if message else None})
        task_id = task.get("task_id") if task else None
        agent_name = agent or (task.get("assigned_agent") if task else None)
        model_name = model or (task.get("model") if task else None)
        span = {
            "schema_version": "research-trace-span/1.0",
            "trace_id": "trace_" + state["run_id"].replace("-", "")[:32],
            "span_id": uuid.uuid4().hex,
            "parent_span_id": parent_span_id,
            "run_id": state["run_id"],
            "project_id": state["project_id"],
            "agent_run_id": agent_run_id,
            "name": name,
            "kind": kind,
            "started_at": started_at,
            "ended_at": ended_at,
            "latency_ms": elapsed_ms(started_at, ended_at),
            "status": status,
            "outcome": outcome,
            "agent": agent_name,
            "model": model_name,
            "provider": provider,
            "task": task_id,
            "tool": tool,
            "retry": bool(task and task.get("attempts", 0) > 1),
            "cost_usd": (token_usage or {}).get("cost_usd"),
            "tool_calls": [{"name": call.get("name"), "call_id": call.get("call_id"), "status": call.get("status")} for call in (tool_calls or [])],
            "input_artifacts": _artifact_refs(inputs),
            "output_artifacts": _artifact_refs(outputs),
            "token_usage": _usage(token_usage),
            "errors": safe_errors,
            "retries": {"attempt": task.get("attempts", 0) if task else 0, "max_attempts": task.get("retry_policy", {}).get("max_attempts", 1) if task else 1},
            "human_decisions": [{"decision_id": d.get("decision_id"), "approved": d.get("approved"), "actor": d.get("actor")} for d in (human_decisions or [])],
            "data_sensitivity": sensitivity,
            "content_capture": False,
            "export_policy": "local-only",
            "attributes": {
                "gen_ai.operation.name": name,
                "gen_ai.agent.name": agent_name,
                "gen_ai.request.model": model_name,
                "gen_ai.provider.name": provider,
                "gen_ai.usage.cost": (token_usage or {}).get("cost_usd"),
                "research.project_id": state["project_id"],
                "research.run_id": state["run_id"],
                "research.task_id": task_id,
                "research.agent_run_id": agent_run_id,
                "research.tool.name": tool,
                "research.outcome": outcome,
                **(attributes or {}),
            },
        }
        jsonschema.Draft202012Validator(self.schema, format_checker=jsonschema.FormatChecker()).validate(span)
        if self.policy.local_export_enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(span, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        if self.policy.external_export_enabled:
            if sensitivity in SENSITIVE_LEVELS and not (self.policy.allow_sensitive_external_export and external_approved):
                return span
            span["export_policy"] = "external-redacted"
            for exporter in self.exporters:
                exporter.export(span)
        return span


def to_opentelemetry_attributes(span: dict[str, Any]) -> dict[str, Any]:
    """Return content-free scalar attributes suitable for an OTel span exporter."""
    values = {
        "research.run_id": span["run_id"], "research.project_id": span["project_id"],
        "research.task_id": span.get("task"), "research.agent_run_id": span.get("agent_run_id"),
        "research.agent": span.get("agent"), "research.tool": span.get("tool"),
        "research.outcome": span.get("outcome"), "gen_ai.provider.name": span.get("provider"),
        "gen_ai.request.model": span.get("model"), "gen_ai.usage.input_tokens": span["token_usage"].get("input_tokens"),
        "gen_ai.usage.output_tokens": span["token_usage"].get("output_tokens"),
        "gen_ai.usage.total_tokens": span["token_usage"].get("total_tokens"),
        "gen_ai.usage.cost": span.get("cost_usd"), "research.latency_ms": span["latency_ms"],
        "research.retry": span["retry"], "research.status": span["status"],
    }
    return {key: value for key, value in values.items() if value is not None}
