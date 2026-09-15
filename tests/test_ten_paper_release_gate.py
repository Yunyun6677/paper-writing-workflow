import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_ten_paper_release_gate import verify


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TenPaperReleaseGateTests(unittest.TestCase):
    def test_gate_recomputes_fulltext_data_result_and_runtime_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_artifact = root / "base.csv"
            base_artifact.write_text("x\n1\n", encoding="utf-8")
            base_receipt = root / "base-receipt.json"
            base_receipt.write_text('{"status":"complete"}\n', encoding="utf-8")
            base_manifest = root / "base.json"
            base_manifest.write_text(json.dumps({
                "benchmark_id": "base",
                "certification_boundary": "fixture",
                "papers": [{
                    "paper_id": "base-paper",
                    "assessment": "pass",
                    "files": [
                        {"path": "base.csv", "role": "result", "sha256": digest(base_artifact)},
                        {"path": "base-receipt.json", "role": "execution_receipt", "sha256": digest(base_receipt)},
                    ],
                    "receipt_path": "base-receipt.json",
                    "required_receipt_status": "complete",
                }],
            }), encoding="utf-8")

            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-fixture")
            text = root / "paper.txt"
            text.write_text("===== PDF PAGE 1 =====\nFixture title\n", encoding="utf-8")
            data = root / "data.csv"
            data.write_text("x,y\n1,2\n", encoding="utf-8")
            result = root / "result.json"
            result.write_text('{"coefficient":2}\n', encoding="utf-8")
            receipt = root / "receipt.json"
            receipt.write_text('{"status":"complete","assessment":"pass"}\n', encoding="utf-8")
            runtime = root / "runtime.json"
            runtime.write_text('{"status":"passed"}\n', encoding="utf-8")
            manifest = root / "gate.json"
            manifest.write_text(json.dumps({
                "benchmark_id": "gate",
                "base_manifest": "base.json",
                "base_papers_required": 1,
                "additional_papers_required": 1,
                "total_papers_required": 2,
                "minimum_clean_author_table_matches": 2,
                "runtime_evidence": [{"path": "runtime.json", "sha256": digest(runtime), "proves": "fixture"}],
                "additional_papers": [{
                    "paper_id": "additional",
                    "assessment": "pass",
                    "fulltext": {
                        "path": "paper.pdf", "sha256": digest(pdf),
                        "text_path": "paper.txt", "text_sha256": digest(text),
                        "minimum_pages": 1, "title_anchor": "Fixture title",
                    },
                    "data": {"path": "data.csv", "sha256": digest(data)},
                    "result_path": "result.json", "result_sha256": digest(result),
                    "receipt_path": "receipt.json", "receipt_sha256": digest(receipt),
                }],
                "certification_boundary": "fixture",
            }), encoding="utf-8")

            passed = verify(manifest, root)
            self.assertTrue(passed["release_gate_passed"])
            self.assertEqual(passed["papers_verified"], 2)
            data.write_text("x,y\n1,3\n", encoding="utf-8")
            self.assertFalse(verify(manifest, root)["release_gate_passed"])


if __name__ == "__main__":
    unittest.main()
