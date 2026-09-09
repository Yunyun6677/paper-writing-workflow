"""Deterministic tool contracts used by the Research Director runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import jsonschema

from .store import sha256_file, utc_now

Tool = Callable[[dict[str, Any], Path], dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, function: Tool) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = function

    def execute(self, name: str, inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
        if name not in self._tools:
            raise KeyError(f"Unknown deterministic tool: {name}")
        return self._tools[name](inputs, project_dir)


def _safe_project_path(project_dir: Path, value: str) -> Path:
    path = (project_dir / value).resolve()
    if not path.is_relative_to(project_dir.resolve()):
        raise ValueError(f"Path escapes project directory: {value}")
    return path


def schema_validate(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    document = _safe_project_path(project_dir, inputs["document"])
    schema = _safe_project_path(project_dir, inputs["schema"])
    value = json.loads(document.read_text(encoding="utf-8"))
    definition = json.loads(schema.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(definition, format_checker=jsonschema.FormatChecker()).validate(value)
    return {"status": "complete", "artifacts": [{"path": inputs["document"], "sha256": sha256_file(document)}]}


def artifact_integrity(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    artifacts = []
    errors = []
    for item in inputs.get("artifacts", []):
        path = _safe_project_path(project_dir, item["path"])
        if not path.is_file():
            errors.append(f"missing: {item['path']}")
            continue
        digest = sha256_file(path)
        if item.get("sha256") and item["sha256"] != digest:
            errors.append(f"hash mismatch: {item['path']}")
        artifacts.append({"path": item["path"], "sha256": digest, "bytes": path.stat().st_size})
    return {"status": "failed" if errors else "complete", "artifacts": artifacts, "errors": errors}


def research_firewall(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    """Check references to existing specialist artifacts; never infer scientific validity."""
    errors: list[str] = []
    checks: list[dict[str, str]] = []
    for label, references in inputs.get("registries", {}).items():
        missing = []
        if not references:
            missing.append("no artifact references registered")
        for reference in references:
            path = _safe_project_path(project_dir, reference["path"])
            if not path.is_file():
                missing.append(reference["path"])
            elif reference.get("sha256") and sha256_file(path) != reference["sha256"]:
                missing.append(reference["path"] + " (hash mismatch)")
        status = "blocked" if missing else "pass"
        checks.append({"name": label, "status": status, "detail": ", ".join(missing) or "referenced artifacts exist"})
        errors.extend(f"{label}: {item}" for item in missing)
    report = {
        "schema_version": "agent-runtime-audit/1.0",
        "created_at": utc_now(),
        "status": "blocked" if errors else "review-required",
        "checks": checks,
        "limitations": [
            "Artifact existence and hashes do not establish citation entailment or causal identification.",
            "Independent scientific review and the final human gate remain required.",
        ],
    }
    output = _safe_project_path(project_dir, inputs.get("output", "audit/agent-runtime-audit.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "failed" if errors else "complete", "artifacts": [{"path": str(output.relative_to(project_dir)).replace("\\", "/"), "sha256": sha256_file(output)}], "errors": errors}


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("schema_validate", schema_validate)
    registry.register("artifact_integrity", artifact_integrity)
    registry.register("research_firewall", research_firewall)
    return registry
