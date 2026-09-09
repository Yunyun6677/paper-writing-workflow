"""Non-destructive migration from existing Research OS project artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from .runtime import ResearchRuntime
from .store import ResearchStateStore, sha256_file, utc_now


KNOWN_ARTIFACTS = {
    "project.json": "economics-paper-project/1.0",
    "design/design-register.json": "design-register/1.0",
    "audit/numeric-claims.json": "numeric-claims/1.0",
    "audit/audit-report.json": "paper-audit/1.0",
    "literature/acquisition-ledger.json": "literature-acquisition/1.0",
    "literature/run-status.json": "review-run-status/1.0",
}


def migrate_project(project_dir: str | Path, run_root: str | Path, parent_run_id: str | None = None) -> ResearchStateStore:
    """Create ResearchState while retaining legacy files as immutable referenced sources."""
    project = Path(project_dir).resolve()
    manifest = project / "project.json"
    if not manifest.is_file():
        raise FileNotFoundError(f"Missing economics paper manifest: {manifest}")
    store = ResearchRuntime.initialize(manifest, run_root, parent_run_id)
    state = store.load()
    sources: list[dict[str, Any]] = []
    for relative, schema_ref in KNOWN_ARTIFACTS.items():
        path = project / relative
        if path.is_file():
            reference = {
                "artifact_id": f"legacy:{relative}", "path": str(path), "sha256": sha256_file(path),
                "schema_ref": schema_ref, "external": True, "migration_mode": "reference-only",
            }
            state["artifacts"].append(reference)
            sources.append(reference)
            if schema_ref in {"evidence-card/1.0", "literature-acquisition/1.0", "review-run-status/1.0"}:
                state["literature_state"]["artifact_refs"].append({"artifact_id": reference["artifact_id"]})
            elif schema_ref in {"numeric-claims/1.0", "engine-execution/1.0"}:
                state["empirical_state"]["artifact_refs"].append({"artifact_id": reference["artifact_id"]})
            elif schema_ref == "paper-audit/1.0":
                state["audit_state"]["artifact_refs"].append({"artifact_id": reference["artifact_id"]})
    receipt = {
        "schema_version": "research-state-migration/1.0", "strategy": "reference-only",
        "source_project": str(project), "created_at": utc_now(), "sources": sources,
        "guarantees": ["legacy files were not modified", "source hashes were recorded", "scientific completion status was not inferred"],
    }
    repository = Path(__file__).resolve().parents[1]
    receipt_schema = json.loads((repository / "schemas" / "research-state-migration.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(receipt_schema, format_checker=jsonschema.FormatChecker()).validate(receipt)
    receipt_path = store.run_dir / "migration-receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state["artifacts"].append({
        "artifact_id": "migration-receipt", "path": "migration-receipt.json",
        "sha256": sha256_file(receipt_path), "schema_ref": "research-state-migration/1.0", "external": False,
    })
    store.save(state, "migration.completed", {"source_count": len(sources), "strategy": "reference-only"})
    return store
