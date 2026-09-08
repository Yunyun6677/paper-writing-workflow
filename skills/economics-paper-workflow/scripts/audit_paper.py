#!/usr/bin/env python3
"""Deterministic structural audit for an initialized economics paper project."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "economics-paper-project.schema.json"
CLAIMS_SCHEMA = ROOT / "schemas" / "numeric-claims.schema.json"
AUDIT_SCHEMA = ROOT / "schemas" / "paper-audit.schema.json"
CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^]]*\]\s*)*\{([^}]+)\}")
BIB_RE = re.compile(r"@[A-Za-z]+\s*\{\s*([^,\s]+)")
INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
GRAPHIC_RE = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}")
WINDOWS_ABS_RE = re.compile(r"(?:[A-Za-z]:[\\/]|file://)")


def add(checks: list[dict], name: str, status: str, detail: str) -> None:
    checks.append({"name": name, "status": status, "detail": detail})


def resolve_tex_path(base: Path, raw: str, extensions: tuple[str, ...]) -> Path | None:
    candidate = base / raw
    if candidate.exists():
        return candidate
    for suffix in extensions:
        alt = candidate.with_suffix(suffix) if not candidate.suffix else candidate
        if alt.exists():
            return alt
    return None


def audit(project_dir: Path, compile_tex: bool = False) -> dict:
    project_dir = project_dir.resolve()
    checks: list[dict] = []
    manifest_path = project_dir / "project.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)
        add(checks, "project_manifest", "pass", "Manifest validates against economics-paper-project/1.0.")
    except Exception as exc:
        manifest = {}
        add(checks, "project_manifest", "blocked", str(exc))

    main = project_dir / "paper" / "main.tex"
    try:
        text = main.read_text(encoding="utf-8")
        add(checks, "main_tex_utf8", "pass", "paper/main.tex is readable UTF-8.")
    except Exception as exc:
        text = ""
        add(checks, "main_tex_utf8", "blocked", str(exc))

    tex_files = list((project_dir / "paper").rglob("*.tex")) if (project_dir / "paper").exists() else []
    all_tex = "\n".join(p.read_text(encoding="utf-8") for p in tex_files)
    unsafe = []
    if WINDOWS_ABS_RE.search(all_tex):
        unsafe.append("absolute/file URL")
    if "\\write18" in all_tex:
        unsafe.append("shell escape")
    add(checks, "portable_safe_tex", "blocked" if unsafe else "pass", ", ".join(unsafe) or "No absolute paths or shell escape detected.")

    missing_inputs = []
    for raw in INPUT_RE.findall(text):
        if not resolve_tex_path(main.parent, raw, (".tex",)):
            missing_inputs.append(raw)
    for raw in GRAPHIC_RE.findall(all_tex):
        if not resolve_tex_path(main.parent, raw, (".pdf", ".png", ".svg")):
            missing_inputs.append(raw)
    add(checks, "inputs_and_figures", "blocked" if missing_inputs else "pass", f"Missing: {missing_inputs}" if missing_inputs else "All referenced inputs and figures exist.")

    required_project_files = [
        "design/design-register.json",
        "design/research-design.tex",
        "audit/numeric-claims.json",
        "submission/data-code-availability.tex",
        "submission/reproducibility-manifest.json",
        "submission/submission-checklist.tex",
    ]
    absent_project_files = [rel for rel in required_project_files if not (project_dir / rel).exists()]
    add(checks, "required_project_artifacts", "blocked" if absent_project_files else "pass", f"Missing: {absent_project_files}" if absent_project_files else "All required workflow artifacts exist.")

    bib_path = project_dir / "paper" / "references.bib"
    bib_text = bib_path.read_text(encoding="utf-8") if bib_path.exists() else ""
    cited = {key.strip() for group in CITE_RE.findall(all_tex) for key in group.split(",")}
    known = set(BIB_RE.findall(bib_text))
    missing_citations = sorted(cited - known)
    add(checks, "citation_keys", "blocked" if missing_citations else "pass", f"Missing keys: {missing_citations}" if missing_citations else f"Resolved {len(cited)} citation keys.")

    claims_path = project_dir / "audit" / "numeric-claims.json"
    try:
        claims_document = json.loads(claims_path.read_text(encoding="utf-8"))
        claims_schema = json.loads(CLAIMS_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(claims_schema, format_checker=jsonschema.FormatChecker()).validate(claims_document)
        claims = claims_document["claims"]
        unresolved = [c.get("claim_id", "unnamed") for c in claims if not c.get("source_artifact") or not c.get("source_hash")]
        stage = manifest.get("stage")
        strict = stage in {"draft", "revision", "submission"}
        status = "blocked" if unresolved and strict else ("review-required" if unresolved else "pass")
        add(checks, "numeric_claim_provenance", status, f"Unresolved: {unresolved}" if unresolved else f"Resolved {len(claims)} registered numerical claims.")
    except Exception as exc:
        add(checks, "numeric_claim_provenance", "blocked", str(exc))

    approvals = manifest.get("approvals", {})
    pending = [key for key, value in approvals.items() if not value]
    add(checks, "human_approvals", "review-required" if pending else "pass", f"Pending: {pending}" if pending else "All recorded gates approved.")

    engine = shutil.which("xelatex")
    if compile_tex and engine and main.exists():
        proc = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=main.parent, capture_output=True, text=True, timeout=120)
        add(checks, "latex_compile", "pass" if proc.returncode == 0 else "blocked", "XeLaTeX completed." if proc.returncode == 0 else proc.stdout[-2000:])
    elif compile_tex:
        add(checks, "latex_compile", "review-required", "XeLaTeX is not installed or not on PATH.")
    else:
        add(checks, "latex_compile", "not-run", "Use --compile to request a local XeLaTeX check.")

    overall = "pass"
    if any(c["status"] == "blocked" for c in checks):
        overall = "blocked"
    elif any(c["status"] == "review-required" for c in checks):
        overall = "review-required"
    report = {
        "schema_version": "paper-audit/1.0",
        "project_id": manifest.get("project_id", project_dir.name),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "checks": checks,
    }
    audit_schema = json.loads(AUDIT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(audit_schema, format_checker=jsonschema.FormatChecker()).validate(report)
    audit_dir = project_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "audit-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(f"{c['name'].replace('_', r'\_')} & {c['status'].replace('-', r'\-')} \\\\" for c in checks)
    tex = (
        "\\documentclass[UTF8]{ctexart}\n"
        "\\usepackage[a4paper,margin=2.5cm]{geometry}\n"
        "\\usepackage{booktabs}\n"
        "\\begin{document}\n"
        "\\section*{论文项目审计}\n"
        f"总体状态：{overall.replace('-', r'\-')}。\\par\n"
        "\\begin{tabular}{ll}\\toprule\n检查项 & 状态 \\\\ \\midrule\n"
        + rows
        + "\n\\bottomrule\\end{tabular}\n\\end{document}\n"
    )
    (audit_dir / "audit-report.tex").write_text(tex, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()
    try:
        report = audit(args.project_dir, args.compile)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"overall_status": report["overall_status"], "report": str(args.project_dir / 'audit' / 'audit-report.json')}, ensure_ascii=False))
    return 1 if report["overall_status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
