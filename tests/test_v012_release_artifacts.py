import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V012ReleaseArtifactTests(unittest.TestCase):
    def test_public_vertical_slice_receipt_is_bounded_and_complete(self):
        receipt = json.loads(
            (ROOT / "tests" / "receipts" / "v012-public-sandbox-vertical-slice.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["runtime_status"], "complete")
        self.assertTrue(receipt["injected_failure_observed"])
        self.assertTrue(receipt["autonomous_repair_observed"])
        self.assertEqual(receipt["python_tool_outcomes"], ["failed", "complete"])
        self.assertTrue(all(receipt["analysis_chain_checks"].values()))
        self.assertTrue(receipt["reaches_raw_dataset"])
        self.assertFalse(receipt["dataset"]["raw_data_committed"])
        self.assertFalse(receipt["sandbox"]["production_security_boundary"])
        self.assertFalse(receipt["production_certified"])
        self.assertEqual(len(receipt["model_runs"]), 4)

    def test_public_report_and_manifest_preserve_certification_boundary(self):
        report = (ROOT / "outputs" / "v012-public-vertical-slice" / "report-uncompiled-live.tex").read_text(
            encoding="utf-8"
        )
        manifest = json.loads(
            (ROOT / "outputs" / "v012-public-vertical-slice" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        # The receipt preserves machine precision; the manuscript reports the
        # same verified estimate rounded to six decimal places.
        self.assertIn("-5.344472", report)
        self.assertIn("32", report)
        self.assertIn("associational", report.lower())
        self.assertIn("not be interpreted causally", report.lower())
        self.assertEqual(manifest["numeric_chain_status"], "pass")
        self.assertEqual(manifest["compile_status"], "not-run-no-local-tex-engine")
        self.assertIn("not represented as a byte-identical copy", manifest["note"])


if __name__ == "__main__":
    unittest.main()
