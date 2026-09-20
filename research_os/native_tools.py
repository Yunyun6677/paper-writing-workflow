"""Real, bounded Tier-1 tool adapters for local research artifacts.

The adapters in this module never accept shell command strings.  Every path is
resolved below the project root and every successful execution emits a receipt
containing input/output hashes.  Stronger process-group isolation is provided
by the execution boundary added in v0.11 stage 6.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .store import sha256_file, utc_now
from .tools import GENERIC_OUTPUT, ToolRegistry, ToolSpec, _safe_project_path
from .sandbox import LocalRestrictedBackend, SandboxRequest
from .evidence_verifier import EvidenceVerifier


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _fresh_output(project_dir: Path, value: str) -> Path:
    output = _safe_project_path(project_dir, value)
    if output.exists():
        raise FileExistsError(f"Output already exists; idempotency key must use a fresh destination: {value}")
    output.mkdir(parents=True)
    return output


def _artifact(path: Path, project_dir: Path) -> dict[str, Any]:
    return {"path": _relative(path, project_dir), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _command_receipt(
    *, project_dir: Path, output: Path, tool: str, executable: Path,
    inputs: list[Path], started: float, returncode: int, stdout: str, stderr: str,
    idempotency_key: str,
    isolation: dict[str, Any] | None = None, timed_out: bool = False,
    observation_mode: str = "none",
) -> dict[str, Any]:
    stdout_path, stderr_path = output / "stdout.txt", output / "stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    produced = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "receipt.json")
    def bounded(value: str) -> str:
        normalized = value.replace(str(project_dir), "[PROJECT]").replace(str(project_dir).replace("\\", "/"), "[PROJECT]")
        return normalized[-2000:]
    receipt = {
        "schema_version": "native-tool-execution/1.0", "status": "complete" if returncode == 0 else "failed",
        "tool": tool, "executable_name": executable.name, "idempotency_key": idempotency_key,
        "started_at": utc_now(), "elapsed_seconds": round(time.monotonic() - started, 3), "returncode": returncode,
        "inputs": [_artifact(path, project_dir) for path in inputs],
        "artifacts": [_artifact(path, project_dir) for path in produced],
        "errors": [] if returncode == 0 else [f"{tool} exited with code {returncode}"],
        "isolation": isolation or {}, "timed_out": timed_out,
        "command_observation": {
            "mode": observation_mode,
            "stdout_tail": bounded(stdout) if observation_mode == "error-tail" and returncode != 0 else "",
            "stderr_tail": bounded(stderr) if observation_mode == "error-tail" and returncode != 0 else "",
        },
    }
    _write_json(output / "receipt.json", receipt)
    receipt["artifacts"].append(_artifact(output / "receipt.json", project_dir))
    return receipt


def _verify_required_outputs(receipt: dict[str, Any], project_dir: Path, required: list[str]) -> dict[str, Any]:
    missing = [value for value in required if not _safe_project_path(project_dir, value).is_file()]
    if missing:
        receipt["status"] = "failed"
        receipt["errors"].append("missing required outputs: " + ", ".join(missing))
    else:
        known = {item["path"] for item in receipt["artifacts"]}
        for value in required:
            path = _safe_project_path(project_dir, value)
            if _relative(path, project_dir) not in known:
                receipt["artifacts"].append(_artifact(path, project_dir))
    return receipt


def python_execute(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    script = _safe_project_path(project_dir, inputs["script"])
    if not script.is_file() or script.suffix.lower() != ".py":
        raise ValueError("Python tool requires a project-local .py script")
    if sha256_file(script) != inputs["script_sha256"]:
        raise ValueError("Python script hash does not match the approved artifact")
    output = _fresh_output(project_dir, inputs["output_directory"])
    executable = Path(inputs.get("executable") or sys.executable).resolve()
    if executable.name.lower() not in {"python", "python.exe", "python3", "python3.exe"} or not executable.is_file():
        raise ValueError("Python executable is missing or has an unexpected name")
    arguments = [str(value) for value in inputs.get("arguments", [])]
    started = time.monotonic()
    completed = LocalRestrictedBackend(project_dir).run(SandboxRequest(
        command=tuple([str(executable), str(script), *arguments]),
        working_directory=".", timeout_seconds=inputs.get("process_timeout", 300),
        workspace_mode="project-write", network_policy="deny",
    ))
    input_artifacts = [_safe_project_path(project_dir, value) for value in inputs.get("input_artifacts", [])]
    for path in input_artifacts:
        if not path.is_file():
            raise FileNotFoundError(f"Declared input artifact is missing: {_relative(path, project_dir)}")
    receipt = _command_receipt(project_dir=project_dir, output=output, tool="python", executable=executable,
                            inputs=[script, *input_artifacts], started=started, returncode=completed.returncode,
                            stdout=completed.stdout, stderr=completed.stderr,
                            idempotency_key=inputs["idempotency_key"], isolation=completed.isolation,
                            timed_out=completed.timed_out,
                            observation_mode=inputs.get("observation_mode", "none"))
    return _verify_required_outputs(receipt, project_dir, inputs["required_outputs"])


def _engine_execute(inputs: dict[str, Any], project_dir: Path, engine: str) -> dict[str, Any]:
    script = _safe_project_path(project_dir, inputs["script"])
    suffix = ".do" if engine == "stata" else ".R"
    if not script.is_file() or script.suffix.lower() != suffix.lower():
        raise ValueError(f"{engine} tool requires a project-local {suffix} script")
    if sha256_file(script) != inputs["script_sha256"]:
        raise ValueError(f"{engine} script hash does not match the approved artifact")
    output = _fresh_output(project_dir, inputs["output_directory"])
    configured = inputs.get("executable")
    if engine == "stata":
        configured = configured or os.environ.get("STATA_EXE") or "D:/Stata/StataSE-64.exe"
        executable = Path(configured).resolve()
        allowed = {"statase-64.exe", "statamp-64.exe", "statabe-64.exe", "stata-64.exe"}
        command = [str(executable), "/e", "do", str(script)]
    else:
        configured = configured or os.environ.get("R_SCRIPT") or shutil.which("Rscript")
        if not configured:
            candidates = sorted(Path("D:/").glob("R-*/bin/Rscript.exe"), reverse=True)
            configured = str(candidates[0]) if candidates else ""
        executable = Path(configured).resolve()
        allowed = {"rscript", "rscript.exe"}
        command = [str(executable), "--vanilla", str(script), *[str(value) for value in inputs.get("arguments", [])]]
    if not executable.is_file() or executable.name.lower() not in allowed:
        raise FileNotFoundError(f"Verified {engine} executable is unavailable")
    started = time.monotonic()
    completed = LocalRestrictedBackend(project_dir).run(SandboxRequest(
        command=tuple(command), working_directory=_relative(output, project_dir),
        timeout_seconds=inputs.get("process_timeout", 300), workspace_mode="project-write",
        network_policy="deny",
    ))
    receipt = _command_receipt(project_dir=project_dir, output=output, tool=engine, executable=executable,
                            inputs=[script], started=started, returncode=completed.returncode,
                            stdout=completed.stdout, stderr=completed.stderr,
                            idempotency_key=inputs["idempotency_key"], isolation=completed.isolation,
                            timed_out=completed.timed_out,
                            observation_mode=inputs.get("observation_mode", "none"))
    return _verify_required_outputs(receipt, project_dir, inputs["required_outputs"])


def stata_execute(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    return _engine_execute(inputs, project_dir, "stata")


def r_execute(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    return _engine_execute(inputs, project_dir, "r")


def pdf_parse(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    source = _safe_project_path(project_dir, inputs["pdf"])
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError("PDF parser requires a project-local PDF")
    if inputs.get("source_sha256") and sha256_file(source) != inputs["source_sha256"]:
        raise ValueError("PDF source hash mismatch")
    output = _safe_project_path(project_dir, inputs["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("PDF parse output already exists")
    reader = PdfReader(source)
    pages = []
    for number, page in enumerate(reader.pages, 1):
        pages.append({"page": number, "text": page.extract_text() or ""})
    payload = {"schema_version": "pdf-extraction/1.0", "source": _artifact(source, project_dir),
               "page_count": len(pages), "pages": pages, "created_at": utc_now()}
    _write_json(output, payload)
    return {"status": "complete", "artifacts": [_artifact(output, project_dir)], "errors": [],
            "page_count": len(pages), "text_pages": sum(bool(page["text"].strip()) for page in pages)}


def artifact_write(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    output = _safe_project_path(project_dir, inputs["path"])
    if output.exists():
        raise FileExistsError("Artifact already exists; revisions require a new path")
    content = inputs["content"]
    if len(content.encode("utf-8")) > 2_000_000:
        raise ValueError("Artifact write exceeds the 2 MB bounded payload")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    # Byte-exact UTF-8 avoids platform newline translation changing an
    # agent-approved script hash between Windows and POSIX hosts.
    temporary.write_bytes(content.encode("utf-8"))
    temporary.replace(output)
    digest = sha256_file(output)
    if inputs.get("expected_sha256") and inputs["expected_sha256"] != digest:
        output.unlink()
        raise ValueError("Written artifact hash did not match the proposal")
    return {"status": "complete", "artifacts": [_artifact(output, project_dir)], "errors": [],
            "idempotency_key": inputs["idempotency_key"]}


def evidence_verify(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    verifier = EvidenceVerifier(project_dir)
    method = getattr(verifier, "verify_" + inputs["verifier_type"])
    receipt = method(inputs["request"])
    output = _safe_project_path(project_dir, inputs["output"])
    if output.exists(): raise FileExistsError("Verification receipt already exists")
    _write_json(output, receipt)
    return {"status": "complete" if receipt["status"] == "pass" else "failed",
            "artifacts": [_artifact(output, project_dir)],
            "errors": [] if receipt["status"] == "pass" else [f"{inputs['verifier_type']} verification blocked"]}


def latex_compile(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    source = _safe_project_path(project_dir, inputs["source"])
    if not source.is_file() or source.suffix.lower() != ".tex":
        raise ValueError("LaTeX tool requires a project-local .tex source")
    configured = inputs.get("executable") or shutil.which("latexmk") or shutil.which("xelatex")
    if not configured:
        raise FileNotFoundError("No latexmk or xelatex executable is available")
    executable = Path(configured).resolve()
    if executable.name.lower() not in {"latexmk", "latexmk.exe", "xelatex", "xelatex.exe"}:
        raise ValueError("Unexpected LaTeX executable")
    output = _fresh_output(project_dir, inputs["output_directory"])
    if executable.name.lower().startswith("latexmk"):
        command = [str(executable), "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "-outdir=" + str(output), str(source)]
    else:
        command = [str(executable), "-interaction=nonstopmode", "-halt-on-error", "-output-directory=" + str(output), str(source)]
    started = time.monotonic()
    completed = LocalRestrictedBackend(project_dir).run(SandboxRequest(
        command=tuple(command), working_directory=_relative(source.parent, project_dir),
        timeout_seconds=inputs.get("process_timeout", 300), workspace_mode="project-write",
        network_policy="deny",
    ))
    receipt = _command_receipt(project_dir=project_dir, output=output, tool="latex", executable=executable,
                               inputs=[source], started=started, returncode=completed.returncode,
                               stdout=completed.stdout, stderr=completed.stderr,
                               idempotency_key=inputs["idempotency_key"], isolation=completed.isolation,
                               timed_out=completed.timed_out)
    expected = output / (source.stem + ".pdf")
    if completed.returncode == 0 and not expected.is_file():
        raise RuntimeError("LaTeX reported success but no PDF was produced")
    return receipt


def git_inspect(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    executable_value = shutil.which("git")
    if not executable_value:
        raise FileNotFoundError("Git executable is unavailable")
    executable = Path(executable_value).resolve()
    operations = {"status": ["status", "--porcelain=v1"], "head": ["rev-parse", "HEAD"],
                  "diff": ["diff", "--no-ext-diff", "--stat"]}
    command = operations[inputs["operation"]]
    started = time.monotonic()
    completed = LocalRestrictedBackend(project_dir).run(SandboxRequest(
        command=tuple([str(executable), *command]), working_directory=".",
        timeout_seconds=60, workspace_mode="read-only", network_policy="deny",
    ))
    return {"status": "complete" if completed.returncode == 0 else "failed", "operation": inputs["operation"],
            "returncode": completed.returncode, "elapsed_seconds": round(time.monotonic() - started, 3),
            "stdout": completed.stdout, "stderr": completed.stderr, "artifacts": [],
            "errors": [] if completed.returncode == 0 else ["git inspection failed"]}


SCRIPT_INPUT = {
    "type": "object", "additionalProperties": False,
    "required": ["script", "script_sha256", "output_directory", "idempotency_key", "required_outputs"],
    "properties": {
        "script": {"type": "string", "minLength": 1},
        "script_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "output_directory": {"type": "string", "minLength": 1},
        "idempotency_key": {"type": "string", "minLength": 8},
        "required_outputs": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "arguments": {"type": "array", "items": {"type": ["string", "number", "integer", "boolean"]}},
        "input_artifacts": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "observation_mode": {"enum": ["none", "error-tail"]},
        "executable": {"type": "string"}, "process_timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
    },
}


def register_tier1_tools(registry: ToolRegistry) -> ToolRegistry:
    sensitivity = ["public", "synthetic", "restricted", "personal", "confidential"]
    common = dict(output_schema=GENERIC_OUTPUT, side_effect_level="local-write", permission_level="automatic",
                  retry_policy={"max_attempts": 1}, timeout=3660, credential_requirement="none",
                  data_sensitivity=sensitivity, deterministic=True, verifier="native-execution-receipt")
    registry.register(ToolSpec("python", "Execute one hash-approved project-local Python script without a shell.", SCRIPT_INPUT, **common), python_execute)
    registry.register(ToolSpec("stata", "Execute one hash-approved project-local Stata do-file using a licensed engine.", SCRIPT_INPUT, credential_requirement="licensed local executable", **{k:v for k,v in common.items() if k!="credential_requirement"}), stata_execute)
    registry.register(ToolSpec("r", "Execute one hash-approved project-local R script using Rscript vanilla mode.", SCRIPT_INPUT, **common), r_execute)
    registry.register(ToolSpec("pdf_parser", "Extract page-addressable text from one hash-verified project-local PDF.",
        {"type":"object","additionalProperties":False,"required":["pdf","output"],"properties":{"pdf":{"type":"string"},"output":{"type":"string"},"source_sha256":{"type":"string","pattern":"^[a-f0-9]{64}$"}}}, GENERIC_OUTPUT,
        "local-write", timeout=180, data_sensitivity=sensitivity, verifier="page-count-text-coverage"), pdf_parse)
    registry.register(ToolSpec("artifact_write", "Write one bounded UTF-8 artifact to an agent-scoped project path.",
        {"type":"object","additionalProperties":False,"required":["path","content","idempotency_key"],"properties":{"path":{"type":"string","minLength":1},"content":{"type":"string"},"idempotency_key":{"type":"string","minLength":8},"expected_sha256":{"type":"string","pattern":"^[a-f0-9]{64}$"}}}, GENERIC_OUTPUT,
        "local-write", timeout=60, data_sensitivity=sensitivity, verifier="artifact-hash", deterministic=True), artifact_write)
    registry.register(ToolSpec("evidence_verify", "Recompute citation, full-text, numerical, or causal verification from artifacts.",
        {"type":"object","additionalProperties":False,"required":["verifier_type","request","output"],"properties":{"verifier_type":{"enum":["citation","fulltext","numeric","causal","specification","analysis_chain"]},"request":{"type":"object"},"output":{"type":"string","minLength":1}}}, GENERIC_OUTPUT,
        "local-write", timeout=120, data_sensitivity=sensitivity, verifier="evidence-verification-receipt", deterministic=True), evidence_verify)
    latex_status = "available" if (shutil.which("latexmk") or shutil.which("xelatex")) else "staged"
    registry.register(ToolSpec("latex", "Compile one approved project-local LaTeX source and hash its output.", SCRIPT_INPUT | {"required":["source","output_directory","idempotency_key"],"properties": {"source":{"type":"string"},"output_directory":{"type":"string"},"idempotency_key":{"type":"string","minLength":8},"executable":{"type":"string"},"process_timeout":{"type":"integer","minimum":1,"maximum":900}}}, implementation_status=latex_status, **common), latex_compile)
    registry.register(ToolSpec("git_inspect", "Inspect local Git status, HEAD, or diff statistics without changing repository state.",
        {"type":"object","additionalProperties":False,"required":["operation"],"properties":{"operation":{"enum":["status","head","diff"]}}}, GENERIC_OUTPUT,
        "local-read", timeout=60, data_sensitivity=sensitivity, verifier="return-code", deterministic=True), git_inspect)
    return registry
