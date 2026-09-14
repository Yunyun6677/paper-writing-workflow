from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from research_os.evidence_verifier import EvidenceVerifier
from research_os.guardrails import run_guardrails
from research_os.tools import default_registry


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeAssessor:
    model_id = "entailment-fixture-v1"
    def assess(self, claim: str, evidence: str, source_role: str) -> dict:
        return {"label": "entailed", "confidence": .93, "explanation": "synthetic fixture"}


class EvidenceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        source = self.root / "paper.pdf"; source.write_bytes(b"synthetic-pdf-fixture")
        self.extraction = self.root / "paper.pages.json"
        self.extraction.write_text(json.dumps({"source":{"path":"paper.pdf","sha256":sha(source)},
            "page_count":1,"pages":[{"page":1,"text":"Trade raises income in the synthetic sample. The estimate is robust."}]}))
        self.bibliography = self.root / "sources.json"
        self.bibliography.write_text(json.dumps({"sources":[{"title":"Verified Trade Paper","doi":"10.1000/test.1","citation_key":"smith2020"}]}))

    def tearDown(self): self.temp.cleanup()

    def _citation(self, claim: str, evidence: str) -> dict:
        return {"claim_text":claim,"evidence_text":evidence,"source_role":"finding",
            "source_identity":{"title":"Verified Trade Paper","doi":"https://doi.org/10.1000/TEST.1"},
            "bibliography_artifact":"sources.json","bibliography_sha256":sha(self.bibliography),
            "extraction_artifact":"paper.pages.json","extraction_sha256":sha(self.extraction),"locator":{"page":1}}

    def test_fulltext_and_exact_citation_are_reverified(self):
        verifier = EvidenceVerifier(self.root)
        fulltext = verifier.verify_fulltext({"extraction_artifact":"paper.pages.json","extraction_sha256":sha(self.extraction)})
        citation = verifier.verify_citation(self._citation("Trade raises income", "Trade raises income in the synthetic sample."))
        self.assertEqual(fulltext["status"], "pass"); self.assertEqual(citation["status"], "pass")
        schema = json.loads((Path(__file__).parents[1]/"schemas/evidence-verification-receipt.schema.json").read_text())
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(citation)

    def test_paraphrase_requires_recorded_model_or_human_assessment(self):
        request = self._citation("Market access improves household welfare", "Trade raises income in the synthetic sample.")
        blocked = EvidenceVerifier(self.root).verify_citation(request)
        passed = EvidenceVerifier(self.root, FakeAssessor()).verify_citation(request)
        self.assertEqual(blocked["status"], "blocked"); self.assertEqual(passed["status"], "pass")
        self.assertEqual(passed["verification_method"], "model-assisted")
        self.assertEqual(passed["verifier_model"], "entailment-fixture-v1")
        self.assertEqual(passed["confidence"], .93)

    def test_numeric_value_hash_model_and_sample_are_reverified(self):
        result = self.root / "result.json"
        result.write_text(json.dumps({"spec":{"spec_id":"ols-1"},"sample_sha256":"sample-abc","coefficients":[{"term":"trade","estimate":2.0}]}))
        request = {"source_artifact":"result.json","source_sha256":sha(result),
            "value_locator":"coefficients.0.estimate","manuscript_value":2.0,"tolerance":1e-12,
            "identity_expectations":{"spec.spec_id":"ols-1","sample_sha256":"sample-abc"},
            "model_id":"ols-1","sample_id":"sample-abc"}
        passed = EvidenceVerifier(self.root).verify_numeric(request)
        request["manuscript_value"] = 2.5; blocked = EvidenceVerifier(self.root).verify_numeric(request)
        self.assertEqual(passed["status"], "pass"); self.assertEqual(blocked["status"], "blocked")

    def test_causal_language_requires_approved_identification_and_inference(self):
        design = self.root / "design.json"
        design.write_text(json.dumps({"approval":False,"research_design":{"identification_status":"pending","estimand":"ATE","inference_configuration":None}}))
        request = {"design_artifact":"design.json","design_sha256":sha(design),"claim_text":"Trade increases participation."}
        blocked = EvidenceVerifier(self.root).verify_causal(request)
        design.write_text(json.dumps({"approval":True,"research_design":{"identification_status":"passed","estimand":"ATE","inference_configuration":{"se":"HC1"}}}))
        request["design_sha256"] = sha(design); passed = EvidenceVerifier(self.root).verify_causal(request)
        self.assertEqual(blocked["status"], "blocked"); self.assertEqual(passed["status"], "pass")

    def test_upstream_pass_flags_cannot_bypass_guardrail_and_tool_writes_receipt(self):
        fake = {"schema_version":"evidence-verification/1.0","verifier_type":"citation","status":"blocked"}
        report = run_guardrails({"citation_claims":[{"claim_id":"c1","citation_keys":["smith2020"],
            "evidence_refs":["page:1"],"verification_status":"verified","entailment_status":"passed","verification_receipt":fake}]})
        self.assertEqual(report["status"], "blocked")
        tool_result = default_registry().execute("evidence_verify", {"verifier_type":"citation",
            "request":self._citation("Trade raises income", "Trade raises income in the synthetic sample."),
            "output":"audit/citation.json"}, self.root, data_sensitivity="synthetic")
        self.assertEqual(tool_result["status"], "complete")
        self.assertEqual(json.loads((self.root/"audit/citation.json").read_text())["status"], "pass")

    def test_specification_drift_is_blocked_unless_non_significance_change_was_approved(self):
        design = self.root / "design-spec.json"; model = self.root / "model.json"
        design.write_text(json.dumps({"approval":True,"research_design":{"specification":{"sample":"all","controls":["x"],"standard_errors":"HC1"}},"changes":[]}))
        model.write_text(json.dumps({"spec":{"sample":"all","controls":["x","z"],"covariance":"HC1"}}))
        request = {"design_artifact":"design-spec.json","design_sha256":sha(design),
                   "model_artifact":"model.json","model_sha256":sha(model),
                   "field_map":{"sample":"sample","controls":"controls","standard_errors":"covariance"}}
        blocked = EvidenceVerifier(self.root).verify_specification(request)
        design.write_text(json.dumps({"approval":True,"research_design":{"specification":{"sample":"all","controls":["x"],"standard_errors":"HC1"}},
            "changes":[{"field":"controls","new_value":["x","z"],"reason":"pre-specified confounder","approved":True}]}))
        request["design_sha256"] = sha(design)
        passed = EvidenceVerifier(self.root).verify_specification(request)
        self.assertEqual(blocked["status"], "blocked"); self.assertEqual(passed["status"], "pass")


if __name__ == "__main__": unittest.main()
