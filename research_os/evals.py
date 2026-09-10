"""Deterministic research-agent evaluations over synthetic or public fixtures."""
from __future__ import annotations

from typing import Any


def _ratio(passed: int, total: int) -> float:
    return passed / total if total else 1.0


def _doi(value: str | None) -> str:
    return (value or "").strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def evaluate_literature(fixture: dict[str, Any]) -> dict[str, Any]:
    citations = fixture.get("citations", [])
    precise = sum(bool(x.get("source_exists")) and bool(x.get("entailment")) for x in citations)
    doi_correct = sum(_doi(x.get("expected_doi")) == _doi(x.get("actual_doi")) for x in citations)
    fulltext_required = [x for x in citations if x.get("fulltext_required")]
    fulltext_verified = sum(x.get("fulltext_status") == "FULL_TEXT_OBTAINED" and bool(x.get("fulltext_hash")) for x in fulltext_required)
    fingerprints = [x.get("fingerprint") for x in citations if x.get("fingerprint")]
    duplicates = len(fingerprints) - len(set(fingerprints))
    metrics = {
        "citation_precision": _ratio(precise, len(citations)),
        "doi_correctness": _ratio(doi_correct, len(citations)),
        "fulltext_verification": _ratio(fulltext_verified, len(fulltext_required)),
        "evidence_entailment": _ratio(sum(bool(x.get("entailment")) for x in citations), len(citations)),
        "duplicate_rate": _ratio(duplicates, len(fingerprints)),
    }
    return {"category": "literature", "status": "pass" if all(metrics[k] == 1 for k in metrics if k != "duplicate_rate") and metrics["duplicate_rate"] == 0 else "fail", "metrics": metrics}


def evaluate_empirical(fixture: dict[str, Any]) -> dict[str, Any]:
    expected, actual = fixture.get("expected", []), fixture.get("actual", [])
    by_key = {(x["term"], x.get("spec")): x for x in actual}
    tolerance = float(fixture.get("tolerance", 1e-8))
    coefficient_pass = se_pass = sample_pass = missing_rows = 0
    coefficient_delta = se_delta = 0.0
    for row in expected:
        match = by_key.get((row["term"], row.get("spec")), {})
        if not match:
            missing_rows += 1
            continue
        cdelta = abs(float(row["coefficient"]) - float(match["coefficient"]))
        sdelta = abs(float(row["standard_error"]) - float(match["standard_error"]))
        coefficient_delta, se_delta = max(coefficient_delta, cdelta), max(se_delta, sdelta)
        coefficient_pass += cdelta <= tolerance
        se_pass += sdelta <= tolerance
        sample_pass += row.get("n") == match.get("n")
    metrics = {
        "dataset_preservation": fixture.get("dataset_hash_before") == fixture.get("dataset_hash_after"),
        "coefficient_reproduction": _ratio(coefficient_pass, len(expected)),
        "se_reproduction": _ratio(se_pass, len(expected)),
        "sample_reproduction": _ratio(sample_pass, len(expected)),
        "deterministic_rerun": fixture.get("rerun_hash_1") == fixture.get("rerun_hash_2"),
        "max_coefficient_delta": coefficient_delta,
        "max_se_delta": se_delta,
        "missing_result_rows": missing_rows,
    }
    required = [metrics["dataset_preservation"], metrics["coefficient_reproduction"] == 1, metrics["se_reproduction"] == 1, metrics["sample_reproduction"] == 1, metrics["deterministic_rerun"]]
    return {"category": "empirical", "status": "pass" if all(required) else "fail", "metrics": metrics}


def evaluate_agent(fixture: dict[str, Any]) -> dict[str, Any]:
    tasks = fixture.get("tasks", [])
    routes = fixture.get("routes", [])
    completions = fixture.get("completion_claims", [])
    recoveries = fixture.get("recoveries", [])
    metrics = {
        "task_completion": _ratio(sum(x.get("status") in {"complete", "skipped", "superseded"} for x in tasks), len(tasks)),
        "recovery_success": _ratio(sum(bool(x.get("recovered")) for x in recoveries), len(recoveries)),
        "incorrect_tool_routing": _ratio(sum(x.get("actual_tool") != x.get("expected_tool") for x in routes), len(routes)),
        "hallucinated_completion": _ratio(sum(bool(x.get("claimed_complete")) and not bool(x.get("artifacts_verified")) for x in completions), len(completions)),
        "infinite_loop_prevention": int(fixture.get("steps", 0)) <= int(fixture.get("max_steps", 0)) and int(fixture.get("attempts", 0)) <= int(fixture.get("max_attempts", 0)),
    }
    passed = metrics["task_completion"] == 1 and metrics["recovery_success"] == 1 and metrics["incorrect_tool_routing"] == 0 and metrics["hallucinated_completion"] == 0 and metrics["infinite_loop_prevention"]
    return {"category": "agent", "status": "pass" if passed else "fail", "metrics": metrics}


def evaluate_paper(fixture: dict[str, Any]) -> dict[str, Any]:
    numeric = fixture.get("numeric_claims", [])
    citations = fixture.get("citations", [])
    evidence = fixture.get("evidence_requirements", [])
    audits = fixture.get("audits", [])
    metrics = {
        "numerical_consistency": _ratio(sum(bool(x.get("artifact_match")) for x in numeric), len(numeric)),
        "citation_completeness": _ratio(sum(bool(x.get("citation_present")) and bool(x.get("supported")) for x in citations), len(citations)),
        "evidence_coverage": _ratio(sum(bool(x.get("covered")) for x in evidence), len(evidence)),
        "audit_pass_rate": _ratio(sum(x.get("status") == "pass" for x in audits), len(audits)),
    }
    return {"category": "paper", "status": "pass" if all(value == 1 for value in metrics.values()) else "fail", "metrics": metrics}


def evaluate_suite(fixture: dict[str, Any]) -> dict[str, Any]:
    reports = [evaluate_literature(fixture["literature"]), evaluate_empirical(fixture["empirical"]), evaluate_agent(fixture["agent"]), evaluate_paper(fixture["paper"])]
    return {"schema_version": "research-agent-eval-suite/1.0", "status": "pass" if all(x["status"] == "pass" for x in reports) else "fail", "reports": reports}
