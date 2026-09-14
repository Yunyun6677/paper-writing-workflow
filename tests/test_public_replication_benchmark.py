import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_public_replication_benchmark import verify


class PublicReplicationBenchmarkTests(unittest.TestCase):
    def test_hash_and_receipt_are_recomputed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.csv"
            artifact.write_text("x\n1\n", encoding="utf-8")
            receipt = root / "receipt.json"
            receipt.write_text('{"status":"complete"}\n', encoding="utf-8")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = {
                "benchmark_id": "fixture",
                "certification_boundary": "fixture only",
                "papers": [{
                    "paper_id": "paper",
                    "assessment": "pass",
                    "files": [
                        {"path": "artifact.csv", "role": "result", "sha256": digest(artifact)},
                        {"path": "receipt.json", "role": "execution_receipt", "sha256": digest(receipt)},
                    ],
                    "receipt_path": "receipt.json",
                    "required_receipt_status": "complete",
                }],
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = verify(manifest_path, root)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["papers_verified"], 1)
            artifact.write_text("x\n2\n", encoding="utf-8")
            self.assertEqual(verify(manifest_path, root)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
