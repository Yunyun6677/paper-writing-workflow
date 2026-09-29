"""Expose only task-permitted, registry-declared tools to create_agent."""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

import jsonschema

from ..base import AgentExecutionRequest
from .base import ToolRunner, require_langchain


class ToolBridge:
    def __init__(self, request: AgentExecutionRequest, runner: ToolRunner | None,
                 repository_root: str | Path):
        self.request = request
        self.runner = runner
        self.repository_root = Path(repository_root).resolve()
        registry = json.loads((self.repository_root / "config" / "tool-registry.json").read_text(encoding="utf-8"))
        manifest_schema = json.loads((self.repository_root / "schemas" / "tool-manifest.schema.json").read_text(encoding="utf-8"))
        self.configured = {item["name"]: item for item in registry["tools"]}
        self.task_specs = {item["name"]: item for item in request.tool_specs}
        if len(self.task_specs) != len(request.tool_specs):
            raise ValueError("Duplicate tool specifications in assignment")
        for item in request.tool_specs:
            jsonschema.Draft202012Validator(manifest_schema).validate(item)
        self.calls: list[dict[str, str]] = []
        self.artifacts: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def _manifest(self, name: str) -> dict[str, Any]:
        if name not in self.configured:
            raise KeyError(f"Unknown tool: {name}")
        if name not in self.request.allowed_tools:
            raise PermissionError(f"Tool is outside task allow-list: {name}")
        if name not in self.task_specs:
            raise PermissionError(f"Tool lacks an assigned runtime specification: {name}")
        configured, assigned = self.configured[name], self.task_specs[name]
        if configured["implementation_status"] != "available" or assigned["implementation_status"] != "available":
            raise RuntimeError(f"Tool is staged: {name}")
        if self.request.data_sensitivity not in configured["data_sensitivity"] or self.request.data_sensitivity not in assigned["data_sensitivity"]:
            raise PermissionError(f"Tool is not permitted for {self.request.data_sensitivity}: {name}")
        # Config is a policy manifest; the runtime spec is more precise about
        # arguments and outputs (e.g. artifact_write has typed properties).
        for field in ("side_effect_level", "permission_level", "data_sensitivity"):
            if configured[field] != assigned[field]:
                raise ValueError(f"Tool manifest differs from runtime: {name}/{field}")
        if not set(configured["input_schema"].get("required", [])).issubset(
            assigned["input_schema"].get("required", [])
        ):
            raise ValueError(f"Runtime tool spec drops a config-required input: {name}")
        return assigned

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        manifest = self._manifest(name)
        if self.runner is None:
            raise RuntimeError("No ResearchRuntime tool callback is bound")
        jsonschema.Draft202012Validator(manifest["input_schema"]).validate(arguments)
        if manifest["side_effect_level"] == "external-write" and not arguments.get("idempotency_key"):
            raise ValueError("External writes require an idempotency_key")
        call_id = f"lc-{uuid.uuid4().hex}"
        try:
            result = self.runner(name, arguments, call_id)
        except PermissionError:
            raise
        except Exception as exc:
            result = {"status": "failed", "artifacts": [], "errors": [str(exc)[:1000]],
                      "error_class": type(exc).__name__}
        if not isinstance(result, dict) or result.get("status") not in {"complete", "failed", "needs-human"}:
            raise ValueError(f"Tool returned an invalid status: {name}")
        with self._lock:
            self.calls.append({"name": name, "call_id": call_id, "status": result["status"]})
            self.artifacts.extend(result.get("artifacts", []))
        return result

    def langchain_tools(self) -> list[Any]:
        require_langchain()
        from langchain_core.tools import StructuredTool

        tools = []
        for name in self.request.allowed_tools:
            manifest = self._manifest(name)
            if self.runner is None:
                raise RuntimeError("No ResearchRuntime tool callback is bound")

            def execute(_name: str = name, **kwargs: Any) -> str:
                return json.dumps(self.invoke(_name, kwargs), ensure_ascii=False, sort_keys=True)

            tools.append(StructuredTool.from_function(
                func=execute, name=name, description=manifest["description"],
                args_schema=manifest["input_schema"], infer_schema=False,
            ))
        return tools
