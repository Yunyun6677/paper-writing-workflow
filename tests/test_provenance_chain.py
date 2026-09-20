from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_os.provenance import ProvenanceGraph, verify_analysis_chain
from research_os.store import sha256_file


class ProvenanceChainTests(unittest.TestCase):
    def test_backward_trace_and_analysis_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "data.csv"; dataset.write_text("x,y\n1,2\n2,4\n", encoding="utf-8")
            code = root / "analysis.py"; code.write_text("# verified code\n", encoding="utf-8")
            result = root / "result.json"
            result.write_text(json.dumps({"n":2,"coefficient":2.0,"dataset_sha256":sha256_file(dataset),"code_sha256":sha256_file(code)}), encoding="utf-8")
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps({
                "status":"complete","tool":"python",
                "inputs":[{"path":"analysis.py","sha256":sha256_file(code)},{"path":"data.csv","sha256":sha256_file(dataset)}],
                "artifacts":[{"path":"result.json","sha256":sha256_file(result)}],
            }), encoding="utf-8")
            verified = verify_analysis_chain(root, {
                "dataset_artifact":"data.csv","code_artifact":"analysis.py",
                "result_artifact":"result.json","execution_receipt":"receipt.json",
                "expected":{"n":2,"coefficient":2.0,"tolerance":1e-12,"report_value":"2.000000"},
            })
            self.assertEqual(verified["status"], "pass")
            graph = ProvenanceGraph("test")
            graph.add_file_node("raw", "RawDataset", dataset, root)
            graph.add_file_node("code", "Code", code, root)
            graph.add_file_node("run", "ModelRun", receipt, root)
            graph.add_value_node("estimate", "Estimate", coefficient=2.0, n=2)
            graph.add_value_node("claim", "NumericClaim", displayed_value="2.000000")
            graph.relate("claim", "reported_from", "estimate")
            graph.relate("estimate", "generated_by", "run")
            graph.relate("run", "executed_code", "code")
            graph.relate("run", "used_dataset", "raw")
            self.assertTrue(graph.trace("claim")["reaches_raw_dataset"])

    def test_tampered_result_blocks_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "data.csv"; dataset.write_text("x,y\n1,2\n", encoding="utf-8")
            code = root / "analysis.py"; code.write_text("# code\n", encoding="utf-8")
            result = root / "result.json"; result.write_text(json.dumps({"n":1,"coefficient":99,"dataset_sha256":sha256_file(dataset),"code_sha256":sha256_file(code)}))
            receipt = root / "receipt.json"; receipt.write_text(json.dumps({"status":"complete","tool":"python","inputs":[{"path":"analysis.py","sha256":sha256_file(code)},{"path":"data.csv","sha256":sha256_file(dataset)}],"artifacts":[{"path":"result.json","sha256":sha256_file(result)}]}))
            checked = verify_analysis_chain(root, {"dataset_artifact":"data.csv","code_artifact":"analysis.py","result_artifact":"result.json","execution_receipt":"receipt.json","expected":{"n":1,"coefficient":2.0,"tolerance":1e-12,"report_value":"2.000000"}})
            self.assertEqual(checked["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
