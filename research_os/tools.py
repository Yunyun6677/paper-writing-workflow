"""Unified tool registry with explicit permissions, schemas, retries, and adapters."""
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
import jsonschema
from .guardrails import run_guardrails
from .store import sha256_file, utc_now

Tool = Callable[[dict[str, Any], Path], dict[str, Any]]

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    side_effect_level: str = "none"
    permission_level: str = "automatic"
    retry_policy: dict[str, Any] | None = None
    timeout: int = 60
    credential_requirement: str = "none"
    data_sensitivity: list[str] | None = None
    deterministic: bool = True
    verifier: str = "schema-and-receipt"
    adapter: str = "native"
    implementation_status: str = "available"

    def manifest(self) -> dict[str, Any]:
        value = asdict(self)
        value["retry_policy"] = value["retry_policy"] or {"max_attempts": 1}
        value["data_sensitivity"] = value["data_sensitivity"] or ["public", "synthetic"]
        return value

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, Tool]] = {}

    def register(self, spec: ToolSpec | str, function: Tool) -> None:
        if isinstance(spec, str):
            spec = ToolSpec(spec, f"Legacy native tool {spec}", {"type": "object"}, {"type": "object"})
        if spec.name in self._tools: raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = (spec, function)

    def describe(self, name: str) -> dict[str, Any]:
        return self._tools[name][0].manifest()

    def manifests(self) -> list[dict[str, Any]]:
        return [spec.manifest() for spec, _ in self._tools.values()]

    def execute(self, name: str, inputs: dict[str, Any], project_dir: Path, *, approved: bool = False, data_sensitivity: str = "public") -> dict[str, Any]:
        if name not in self._tools: raise KeyError(f"Unknown tool: {name}")
        spec, function = self._tools[name]
        if spec.implementation_status != "available": raise RuntimeError(f"Tool is registered but not available: {name}")
        if spec.permission_level == "explicit-approval" and not approved: raise PermissionError(f"Tool requires human approval: {name}")
        if data_sensitivity not in (spec.data_sensitivity or ["public", "synthetic"]): raise PermissionError(f"Tool {name} is not authorized for {data_sensitivity} data")
        jsonschema.Draft202012Validator(spec.input_schema).validate(inputs)
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(function, inputs, project_dir)
        try:
            result = future.result(timeout=spec.timeout)
        except FutureTimeout as exc:
            future.cancel(); pool.shutdown(wait=False, cancel_futures=True)
            raise TimeoutError(f"Tool timed out after {spec.timeout}s: {name}") from exc
        else:
            pool.shutdown(wait=True)
        jsonschema.Draft202012Validator(spec.output_schema).validate(result)
        return result

def _safe_project_path(project_dir: Path, value: str) -> Path:
    path = (project_dir / value).resolve()
    if not path.is_relative_to(project_dir.resolve()): raise ValueError(f"Path escapes project directory: {value}")
    return path

def schema_validate(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    document = _safe_project_path(project_dir, inputs["document"])
    schema = _safe_project_path(project_dir, inputs["schema"])
    jsonschema.Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")), format_checker=jsonschema.FormatChecker()).validate(json.loads(document.read_text(encoding="utf-8")))
    return {"status": "complete", "artifacts": [{"path": inputs["document"], "sha256": sha256_file(document)}]}

def artifact_integrity(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    artifacts, errors = [], []
    for item in inputs.get("artifacts", []):
        path = _safe_project_path(project_dir, item["path"])
        if not path.is_file(): errors.append(f"missing: {item['path']}"); continue
        digest = sha256_file(path)
        if item.get("sha256") and item["sha256"] != digest: errors.append(f"hash mismatch: {item['path']}")
        artifacts.append({"path": item["path"], "sha256": digest, "bytes": path.stat().st_size})
    return {"status": "failed" if errors else "complete", "artifacts": artifacts, "errors": errors}

def research_firewall(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    errors, checks = [], []
    for label, references in inputs.get("registries", {}).items():
        missing = []
        if not references: missing.append("no artifact references registered")
        for reference in references:
            path = _safe_project_path(project_dir, reference["path"])
            if not path.is_file() or (reference.get("sha256") and sha256_file(path) != reference["sha256"]):
                missing.append(reference["path"])
        checks.append({"name": label, "status": "blocked" if missing else "pass", "detail": ", ".join(missing) or "referenced artifacts exist"})
        errors += [f"{label}: {item}" for item in missing]
    report = {"schema_version": "agent-runtime-audit/1.0", "created_at": utc_now(), "status": "blocked" if errors else "review-required", "checks": checks, "limitations": ["Artifact integrity does not establish scientific validity.", "Independent scientific review and final human approval remain required."]}
    output = _safe_project_path(project_dir, inputs.get("output", "audit/agent-runtime-audit.json")); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "failed" if errors else "complete", "artifacts": [{"path": str(output.relative_to(project_dir)).replace("\\", "/"), "sha256": sha256_file(output)}], "errors": errors}

def research_guardrails(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    bundle = dict(inputs.get("bundle", {}))
    numeric = []
    for claim in bundle.get("numeric_claims", []):
        claim = dict(claim); source = claim.get("source_artifact")
        path = _safe_project_path(project_dir, source) if source else None
        claim["source_exists"] = bool(path and path.is_file())
        claim["hash_match"] = bool(path and path.is_file() and claim.get("source_hash") == sha256_file(path))
        numeric.append(claim)
    bundle["numeric_claims"] = numeric
    report = run_guardrails(bundle)
    output = _safe_project_path(project_dir, inputs.get("output", "audit/scientific-guardrails.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = [finding["detail"] for finding in report["findings"] if finding["status"] == "blocked"]
    return {"status": "failed" if errors else "complete", "artifacts": [{"path": str(output.relative_to(project_dir)).replace("\\", "/"), "sha256": sha256_file(output)}], "errors": errors}

GENERIC_OUTPUT = {"type": "object", "required": ["status"], "properties": {"status": {"enum": ["complete", "failed", "needs-human"]}, "artifacts": {"type": "array"}, "errors": {"type": "array"}}, "additionalProperties": True}

def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec("schema_validate", "Validate a project JSON artifact against a local schema.", {"type": "object", "required": ["document", "schema"]}, GENERIC_OUTPUT, "local-read", timeout=60, data_sensitivity=["public", "synthetic", "restricted", "personal", "confidential"]), schema_validate)
    registry.register(ToolSpec("artifact_integrity", "Verify project artifact existence and hashes.", {"type": "object", "properties": {"artifacts": {"type": "array"}}}, GENERIC_OUTPUT, "local-read", timeout=60, data_sensitivity=["public", "synthetic", "restricted", "personal", "confidential"]), artifact_integrity)
    registry.register(ToolSpec("research_firewall", "Write a deterministic final lineage audit receipt.", {"type": "object", "properties": {"registries": {"type": "object"}, "output": {"type": "string"}}}, GENERIC_OUTPUT, "local-write", timeout=60, data_sensitivity=["public", "synthetic", "restricted", "personal", "confidential"]), research_firewall)
    registry.register(ToolSpec("research_guardrails", "Evaluate structured citation, full-text, numerical, causal, specification, and privacy contracts.", {"type": "object", "properties": {"bundle": {"type": "object"}, "output": {"type": "string"}}}, GENERIC_OUTPUT, "local-write", timeout=60, data_sensitivity=["public", "synthetic", "restricted", "personal", "confidential"], verifier="guardrail-report-schema"), research_guardrails)
    return registry
