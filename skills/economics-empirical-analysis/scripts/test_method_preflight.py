import json
import tempfile
import unittest
from pathlib import Path

import jsonschema
import pandas as pd

from method_preflight import preflight


class MethodPreflightTests(unittest.TestCase):
    def write_request(self, root: Path, method: str, variables: dict, options: dict | None = None) -> Path:
        request = {
            "schema_version": "econometric-method-request/1.0", "project_id": "test", "design_id": f"{method}-v1",
            "method": method, "question": "Does a policy change an outcome?", "estimand": "average treatment effect",
            "data": {"path": "data.csv"}, "variables": variables,
        }
        if options is not None:
            request["options"] = options
        path = root / "request.json"
        path.write_text(json.dumps(request), encoding="utf-8")
        return path

    def test_did_detects_reversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"id": [1, 1, 1, 2, 2, 2], "t": [1, 2, 3] * 2, "y": range(6), "d": [0, 1, 0, 0, 0, 0], "g": [2, 2, 2, 0, 0, 0]}).to_csv(root / "data.csv", index=False)
            req = self.write_request(root, "did", {"outcome": "y", "unit_id": "id", "time_id": "t", "treatment": "d", "cohort": "g"}, {"never_treated_value": 0})
            result = preflight(req, root / "out")
            self.assertEqual(result["design_status"], "blocked")
            self.assertIn("treatment-reversal", {x["code"] for x in result["issues"]})

    def test_rd_support_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"x": [-2, -1, -.5, .5, 1, 2], "y": [1, 1, 2, 3, 4, 4]}).to_csv(root / "data.csv", index=False)
            req = self.write_request(root, "rd", {"outcome": "y", "running": "x"}, {"cutoff": 0})
            result = preflight(req, root / "out")
            self.assertEqual(result["estimation_status"], "not-run")
            self.assertTrue((root / "out" / "preflight-report.tex").exists())

    def test_survey_rejects_nonpositive_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"y": [1, 0, 1], "w": [1, 0, 2], "s": [1, 1, 2], "p": [1, 2, 3]}).to_csv(root / "data.csv", index=False)
            req = self.write_request(root, "complex_survey", {"outcome": "y", "weight": "w", "strata": "s", "psu": "p"})
            result = preflight(req, root / "out")
            self.assertEqual(result["design_status"], "blocked")

    def test_missing_column_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"y": [1, 2], "d": [0, 1]}).to_csv(root / "data.csv", index=False)
            req = self.write_request(root, "dml", {"outcome": "y", "treatment": "d", "features": ["missing"]})
            result = preflight(req, root / "out")
            self.assertEqual(result["design_status"], "blocked")

    def test_rd_schema_requires_running_and_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"x": [-1, 1], "y": [0, 1]}).to_csv(root / "data.csv", index=False)
            req = self.write_request(root, "rd", {"running": "x"}, {"cutoff": 0})
            with self.assertRaises(jsonschema.ValidationError):
                preflight(req, root / "out")

    def test_invalid_treatment_code_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"id": [1, 1, 2, 2], "t": [1, 2, 1, 2], "y": [0, 1, 0, 1], "d": [0, 2, 0, 0], "g": [2, 2, 0, 0]}).to_csv(root / "data.csv", index=False)
            req = self.write_request(root, "did", {"outcome": "y", "unit_id": "id", "time_id": "t", "treatment": "d", "cohort": "g"}, {"never_treated_value": 0})
            result = preflight(req, root / "out")
            self.assertEqual(result["design_status"], "blocked")
            self.assertIn("invalid-treatment", {x["code"] for x in result["issues"]})

    def test_every_advanced_method_handler_emits_a_result(self):
        cases = {
            "event_study": ({"outcome": "y", "unit_id": "id", "time_id": "t", "treatment": "d", "cohort": "g"}, {"never_treated_value": 0}),
            "iv": ({"outcome": "y", "endogenous": ["d"], "instruments": ["z"], "controls": ["x"]}, None),
            "synthetic_control": ({"outcome": "y", "unit_id": "id", "time_id": "t", "treatment": "d"}, None),
            "sdid": ({"outcome": "y", "unit_id": "id", "time_id": "t", "treatment": "d"}, None),
            "dml": ({"outcome": "y", "treatment": "d", "features": ["x", "z"]}, {"folds": 2}),
            "spatial": ({"outcome": "y", "spatial_id": "id"}, {"weight_matrix_path": "edges.csv", "edge_source": "src", "edge_target": "dst"}),
            "network": ({"outcome": "y", "spatial_id": "id"}, {"weight_matrix_path": "edges.csv", "edge_source": "src", "edge_target": "dst"}),
            "dynamic_panel": ({"outcome": "y", "unit_id": "id", "time_id": "t"}, {"lag_order": 1}),
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for method, (variables, options) in cases.items():
                with self.subTest(method=method):
                    root = base / method
                    root.mkdir()
                    rows = []
                    for unit in [1, 2, 3]:
                        for time in [1, 2, 3, 4]:
                            rows.append({"id": unit, "t": time, "y": unit + time / 10, "d": int(unit == 1 and time >= 3), "g": 3 if unit == 1 else 0, "z": (unit + time) % 2, "x": unit * time})
                    pd.DataFrame(rows).to_csv(root / "data.csv", index=False)
                    pd.DataFrame({"src": [1, 2, 2, 3], "dst": [2, 1, 3, 2]}).to_csv(root / "edges.csv", index=False)
                    req = self.write_request(root, method, variables, options)
                    result = preflight(req, root / "out")
                    self.assertEqual(result["method"], method)
                    self.assertEqual(result["estimation_status"], "not-run")


if __name__ == "__main__":
    unittest.main()
