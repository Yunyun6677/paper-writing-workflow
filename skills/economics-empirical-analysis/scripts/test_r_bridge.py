from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("r_bridge.py")
SPEC = importlib.util.spec_from_file_location("r_bridge", MODULE_PATH)
r_bridge = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(r_bridge)


class RBridgeTests(unittest.TestCase):
    def test_coefficient_contract_accepts_valid_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coefficients.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["spec_id", "term", "estimate", "std_error"])
                writer.writeheader(); writer.writerow({"spec_id": "m1", "term": "treat", "estimate": 1.2, "std_error": 0.3})
            r_bridge.validate_coefficients(path)

    def test_coefficient_contract_rejects_negative_se(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coefficients.csv"
            path.write_text("term,estimate,std_error\nx,1,-1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                r_bridge.validate_coefficients(path)

    def test_output_must_be_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                r_bridge.fresh_output(directory)

    def test_rscript_requires_explicit_valid_executable(self):
        with self.assertRaises(ValueError):
            r_bridge.rscript_path("definitely-not-rscript.exe")


if __name__ == "__main__":
    unittest.main(verbosity=2)
