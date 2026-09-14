from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

import jsonschema

from research_os.evaluation import evaluate
from research_os.runtime import ResearchRuntime


class RuntimeEvaluationV011Tests(unittest.TestCase):
    @staticmethod
    def _manifest(project: Path) -> Path:
        manifest = project / "manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": "economics-paper-project/1.0", "project_id": "eval-test",
            "title_working": "Runtime evaluation test", "paper_type": "review", "stage": "idea",
            "research_question": "Can evaluation avoid inventing unavailable scientific scores?",
            "target_journals": [{"name": "undecided", "family": "undecided"}],
            "contribution_claims": [], "data_sensitivity": "synthetic",
            "approvals": {"question_and_contribution": False, "research_design": False, "outline_and_journal": False},
            "output_format": "latex"
        }), encoding="utf-8")
        return manifest

    def test_expanded_metrics_are_evidence_aware_and_unavailable_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir()
            manifest = self._manifest(project)
            store = ResearchRuntime.initialize(manifest, root / "runs")
            ResearchRuntime(store, project)
            report = evaluate(store, project)
            schema = json.loads((Path(__file__).parents[1] / "schemas/agent-run-evaluation.schema.json").read_text())
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(report)
            self.assertTrue(report["metric_groups"]["planning"]["valid_dag"])
            self.assertIsNone(report["metric_groups"]["literature"]["doi_correctness"])
            self.assertIn("literature.doi_correctness", report["unavailable_metrics"])
            self.assertEqual(report["metric_groups"]["efficiency"]["model_requests"], 0)

    def test_registered_hash_matching_verification_receipt_produces_measured_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir()
            store = ResearchRuntime.initialize(self._manifest(project), root / "runs")
            receipt = project / "audit/numeric.json"; receipt.parent.mkdir()
            receipt.write_text(json.dumps({
                "schema_version": "evidence-verification/1.0", "verifier_type": "numeric",
                "status": "pass", "output": {"identity_match": True}
            }), encoding="utf-8")
            state = store.load()
            state["artifacts"].append({
                "artifact_id": "empirical-review:1", "path": "audit/numeric.json",
                "sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(), "external": False,
            })
            store.save(state, "test.verification-receipt", {})
            report = evaluate(store, project)
            self.assertEqual(report["metric_groups"]["empirical"]["coefficient_match"], 1.0)
            self.assertEqual(report["metric_groups"]["writing"]["unsupported_numerical_claim_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
