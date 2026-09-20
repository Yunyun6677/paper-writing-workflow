"""Scientific claim verification against real project artifacts.

Upstream ``passed`` flags are intentionally ignored.  A verification receipt is
derived again from source identity, locators, bytes and design artifacts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Protocol

from .store import canonical_hash, sha256_file, utc_now
from .provenance import verify_analysis_chain


class EntailmentAssessor(Protocol):
    model_id: str
    def assess(self, claim: str, evidence: str, source_role: str) -> dict[str, Any]: ...


def _normal(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def _doi(value: str | None) -> str:
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", value or "", flags=re.I).strip().casefold()


def _pointer(value: Any, pointer: str) -> Any:
    current = value
    for part in pointer.strip("/.").replace("/", ".").split(".") if pointer.strip("/.") else []:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


class EvidenceVerifier:
    def __init__(self, project_dir: str | Path, assessor: EntailmentAssessor | None = None):
        self.project_dir = Path(project_dir).resolve(); self.assessor = assessor

    def _path(self, value: str) -> Path:
        path = (self.project_dir / value).resolve()
        if not path.is_relative_to(self.project_dir): raise ValueError("Verification path escapes project")
        return path

    def _checked(self, value: str, expected_hash: str | None) -> Path:
        path = self._path(value)
        if not path.is_file(): raise FileNotFoundError(path)
        if expected_hash and sha256_file(path).casefold() != expected_hash.casefold():
            raise ValueError(f"Artifact hash mismatch: {value}")
        return path

    def verify_fulltext(self, request: dict[str, Any]) -> dict[str, Any]:
        extraction = self._checked(request["extraction_artifact"], request.get("extraction_sha256"))
        payload = json.loads(extraction.read_text(encoding="utf-8")); source = payload.get("source", {})
        source_path = self._checked(source["path"], source.get("sha256"))
        pages = payload.get("pages", []); text_pages = sum(bool(page.get("text", "").strip()) for page in pages)
        passed = payload.get("page_count") == len(pages) and len(pages) > 0 and text_pages > 0
        return self._receipt("fulltext", "deterministic", [extraction, source_path], passed,
                             {"page_count": len(pages), "text_pages": text_pages,
                              "source_sha256": sha256_file(source_path)}, 1.0)

    def verify_citation(self, request: dict[str, Any]) -> dict[str, Any]:
        bibliography = self._checked(request["bibliography_artifact"], request.get("bibliography_sha256"))
        extraction = self._checked(request["extraction_artifact"], request.get("extraction_sha256"))
        records = json.loads(bibliography.read_text(encoding="utf-8")); records = records.get("sources", records)
        identity = request["source_identity"]
        matches = [item for item in records if
                   (_doi(identity.get("doi")) and _doi(item.get("doi")) == _doi(identity.get("doi"))) or
                   (_normal(item.get("title")) == _normal(identity.get("title")))]
        if len(matches) != 1:
            return self._receipt("citation", "deterministic", [bibliography, extraction], False,
                                 {"reason": "bibliographic identity is missing or ambiguous", "matches": len(matches)}, 1.0)
        pages = json.loads(extraction.read_text(encoding="utf-8")).get("pages", [])
        page_number = int(request["locator"]["page"])
        page = next((item for item in pages if item.get("page") == page_number), None)
        evidence = request["evidence_text"]
        present = bool(page and _normal(evidence) in _normal(page.get("text", "")))
        method, confidence, entailment, assessment = "deterministic", 1.0, False, {}
        if present and _normal(request["claim_text"]) in _normal(evidence):
            entailment = True
        elif present and request.get("human_verification", {}).get("approved") is True:
            method = "human"; entailment = True; confidence = 1.0
            assessment = {"reviewer": request["human_verification"].get("reviewer")}
        elif present and self.assessor is not None:
            method = "model-assisted"; assessment = self.assessor.assess(request["claim_text"], evidence, request["source_role"])
            entailment = assessment.get("label") == "entailed"; confidence = float(assessment.get("confidence", 0))
        passed = present and entailment and request["source_role"] in {"theory", "method", "finding", "context", "counterevidence"}
        output = {"bibliographic_identity": matches[0], "locator": {"page": page_number},
                  "evidence_present": present, "entailment": "passed" if entailment else "not-passed",
                  "source_role": request["source_role"], "assessment": assessment}
        return self._receipt("citation", method, [bibliography, extraction], passed, output, confidence,
                             getattr(self.assessor, "model_id", None) if method == "model-assisted" else None)

    def verify_numeric(self, request: dict[str, Any]) -> dict[str, Any]:
        artifact = self._checked(request["source_artifact"], request.get("source_sha256"))
        suffix = artifact.suffix.lower()
        if suffix == ".json":
            data = json.loads(artifact.read_text(encoding="utf-8")); actual = _pointer(data, request["value_locator"])
            identities = {pointer: _pointer(data, pointer) for pointer in request.get("identity_expectations", {})}
        elif suffix == ".csv":
            with artifact.open(encoding="utf-8-sig", newline="") as stream: rows = list(csv.DictReader(stream))
            selector = request.get("row_selector", {}); found = [row for row in rows if all(str(row.get(k)) == str(v) for k, v in selector.items())]
            if len(found) != 1: raise ValueError("Numeric CSV locator must select exactly one row")
            actual = found[0][request["value_locator"]]; identities = {}
        else:
            raise ValueError("Deterministic numeric verification supports JSON or CSV artifacts")
        expected = request["manuscript_value"]; tolerance = float(request.get("tolerance", 0))
        try:
            numeric_match = math.isclose(float(actual), float(expected), rel_tol=tolerance, abs_tol=tolerance)
        except (TypeError, ValueError):
            numeric_match = _normal(actual) == _normal(expected)
        identity_match = all(_normal(identities[pointer]) == _normal(value) for pointer, value in request.get("identity_expectations", {}).items())
        passed = numeric_match and identity_match
        return self._receipt("numeric", "deterministic", [artifact], passed,
            {"actual_value": actual, "manuscript_value": expected, "value_match": numeric_match,
             "identity_values": identities, "identity_match": identity_match,
             "model_id": request.get("model_id"), "sample_id": request.get("sample_id")}, 1.0)

    def verify_causal(self, request: dict[str, Any]) -> dict[str, Any]:
        design_path = self._checked(request["design_artifact"], request.get("design_sha256"))
        design = json.loads(design_path.read_text(encoding="utf-8")); specification = design.get("research_design") or {}
        identification = specification.get("identification_status")
        estimand = specification.get("estimand")
        inference = specification.get("inference_configuration")
        approved = design.get("approval") is True
        claim = _normal(request["claim_text"])
        causal_terms = ("causes", "effect of", "leads to", "increases", "decreases", "影响", "导致", "提高", "降低")
        qualified_terms = ("associated", "suggests", "may", "可能", "相关", "关联")
        causal_language = any(term in claim for term in causal_terms)
        qualified = any(term in claim for term in qualified_terms)
        design_pass = identification == "passed" and bool(estimand) and bool(inference) and approved
        compatible = design_pass or not causal_language or qualified
        return self._receipt("causal", "deterministic", [design_path], compatible,
            {"identification_status": identification, "estimand": estimand, "inference_configuration": inference,
             "design_approved": approved, "causal_language": causal_language, "qualified_language": qualified,
             "language_compatible": compatible}, 1.0)

    def verify_specification(self, request: dict[str, Any]) -> dict[str, Any]:
        design_path = self._checked(request["design_artifact"], request.get("design_sha256"))
        model_path = self._checked(request["model_artifact"], request.get("model_sha256"))
        design = json.loads(design_path.read_text(encoding="utf-8")); model = json.loads(model_path.read_text(encoding="utf-8"))
        approved_spec = (design.get("research_design") or {}).get("specification", {})
        executed_spec = model.get("spec", {})
        field_map = request.get("field_map", {"sample":"sample", "bandwidth":"bandwidth", "controls":"controls",
            "standard_errors":"covariance", "fixed_effects":"fixed_effects", "outlier_rules":"outlier_rules"})
        changes = []
        for protected, executed_name in field_map.items():
            expected = approved_spec.get(protected); actual = executed_spec.get(executed_name)
            if _normal(expected) == _normal(actual): continue
            approvals = [change for change in design.get("changes", []) if change.get("field") == protected and
                         change.get("approved") is True and change.get("reason") != "significance" and
                         _normal(change.get("new_value")) == _normal(actual)]
            changes.append({"field":protected,"approved_value":expected,"executed_value":actual,
                            "authorized_change":bool(approvals)})
        passed = design.get("approval") is True and all(change["authorized_change"] for change in changes)
        return self._receipt("specification", "deterministic", [design_path, model_path], passed,
            {"design_approved":design.get("approval") is True,"changes":changes,
             "specification_drift":any(not change["authorized_change"] for change in changes)}, 1.0)

    def verify_analysis_chain(self, request: dict[str, Any]) -> dict[str, Any]:
        """Verify a complete public-data analysis chain without trusting model claims."""
        result = verify_analysis_chain(self.project_dir, request)
        inputs = []
        hash_keys = {
            "dataset_artifact": "dataset_sha256", "code_artifact": "code_sha256",
            "result_artifact": "result_sha256", "execution_receipt": "execution_receipt_sha256",
            "report_artifact": "report_sha256",
        }
        for key in hash_keys:
            if request.get(key):
                inputs.append(self._checked(request[key], request.get(hash_keys[key])))
        return self._receipt(
            "analysis_chain", "deterministic", inputs, result["status"] == "pass",
            {"checks": result["checks"], "verified_values": result["verified_values"]}, 1.0,
        )

    def _receipt(self, verifier_type: str, method: str, inputs: list[Path], passed: bool,
                 output: dict[str, Any], confidence: float, model: str | None = None) -> dict[str, Any]:
        input_hashes = [{"path": path.relative_to(self.project_dir).as_posix(), "sha256": sha256_file(path)} for path in inputs]
        return {"schema_version": "evidence-verification/1.0", "verifier_type": verifier_type,
                "verification_method": method, "status": "pass" if passed else "blocked",
                "input_hashes": input_hashes, "input_bundle_hash": canonical_hash(input_hashes),
                "output": output, "output_hash": canonical_hash(output), "confidence": confidence,
                "verifier_model": model, "timestamp": utc_now()}
