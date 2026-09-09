"""Deterministic research guardrails operating on structured artifacts."""

from __future__ import annotations

from typing import Any


def _finding(name: str, passed: bool, detail: str, severity: str = "blocking") -> dict[str, str]:
    return {"guardrail": name, "status": "pass" if passed else "blocked", "severity": severity, "detail": detail}


def citation_guardrail(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for entry in entries:
        passed = bool(entry.get("citation_keys")) and bool(entry.get("evidence_refs")) and entry.get("verification_status") == "verified" and entry.get("entailment_status") == "passed"
        findings.append(_finding("Citation Guardrail", passed, f"claim {entry.get('claim_id', 'unknown')} citation entailment"))
    return findings


def fulltext_guardrail(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for entry in entries:
        if not entry.get("used_in_manuscript"):
            continue
        passed = entry.get("fulltext_status") == "obtained" and entry.get("actually_read") is True
        findings.append(_finding("Fulltext Guardrail", passed, f"source {entry.get('source_id', 'unknown')} full text read"))
    return findings


def numerical_claim_guardrail(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for entry in entries:
        passed = bool(entry.get("source_artifact") and entry.get("source_hash")) and entry.get("source_exists") is True and entry.get("hash_match") is True and entry.get("verification_status") == "verified"
        findings.append(_finding("Numerical Claim Guardrail", passed, f"numeric claim {entry.get('claim_id', 'unknown')} lineage"))
    return findings


def causal_claim_guardrail(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for entry in entries:
        passed = entry.get("identification_status") == "passed" or entry.get("qualified_language") is True
        findings.append(_finding("Causal Claim Guardrail", passed, f"causal claim {entry.get('claim_id', 'unknown')} identification"))
    return findings


def specification_guardrail(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    protected = {"sample", "bandwidth", "controls", "standard_errors", "fixed_effects", "outlier_rules"}
    findings = []
    for entry in entries:
        if entry.get("field") not in protected:
            continue
        passed = entry.get("reason") != "significance" and entry.get("approved") is True
        findings.append(_finding("Specification Guardrail", passed, f"change to {entry.get('field')}"))
    return findings


def sensitive_data_guardrail(data_sensitivity: str, side_effect_level: str, permission_level: str, approved: bool = False) -> list[dict[str, str]]:
    external = side_effect_level.startswith("external")
    restricted = data_sensitivity in {"restricted", "personal", "confidential"}
    passed = not (external and restricted) or (permission_level == "explicit-approval" and approved)
    return [_finding("Sensitive Data Guardrail", passed, f"{data_sensitivity} data with {side_effect_level} tool")]


def run_guardrails(bundle: dict[str, Any]) -> dict[str, Any]:
    findings = []
    findings += citation_guardrail(bundle.get("citation_claims", []))
    findings += fulltext_guardrail(bundle.get("fulltext_records", []))
    findings += numerical_claim_guardrail(bundle.get("numeric_claims", []))
    findings += causal_claim_guardrail(bundle.get("causal_claims", []))
    findings += specification_guardrail(bundle.get("specification_changes", []))
    if "tool_context" in bundle:
        context = bundle["tool_context"]
        findings += sensitive_data_guardrail(context.get("data_sensitivity", "public"), context.get("side_effect_level", "none"), context.get("permission_level", "automatic"), context.get("approved", False))
    return {"status": "blocked" if any(x["status"] == "blocked" for x in findings) else "pass", "findings": findings}
