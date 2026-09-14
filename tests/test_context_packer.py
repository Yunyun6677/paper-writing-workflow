from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from research_os.context import ContextPacker
from research_os.planner import task


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContextPackerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        files = {
            "literature/evidence.md": "trade governance evidence and verified citation\n",
            "analysis/result.json": '{"coefficient": 2.0, "topic": "trade governance"}\n',
            "analysis/raw.csv": "private,row\n1,2\n",
            "paper/main.tex": "hidden future draft\n",
        }
        artifacts = []
        for index, (relative, content) in enumerate(files.items()):
            path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            producer = {0: "literature", 1: "analysis", 2: "analysis", 3: "future-writing"}[index]
            artifacts.append({"artifact_id": f"{producer}:{index}", "path": relative, "sha256": digest(path), "external": False})
        self.state = {
            "research_question": "How does trade affect governance?", "data_sensitivity": "synthetic",
            "artifacts": artifacts,
            "task_graph": [
                task("literature", "evidence", "agent", "literature-agent", []),
                task("analysis", "estimate", "agent", "empirical-agent", ["literature"]),
                task("writing", "write trade governance result", "agent", "writing-agent", ["analysis"]),
                task("review", "verify result", "verifier", "reviewer-verifier-agent", ["writing"], required_inputs={"producer_task_id": "writing"}),
                task("future-writing", "future", "agent", "writing-agent", ["review"]),
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_writer_gets_dependency_artifacts_but_not_future_artifact_or_raw_rows(self):
        packed = ContextPacker(self.root).pack(self.state, self.state["task_graph"][2], 2000)
        by_path = {item["path"]: item for item in packed.artifacts}
        self.assertIn("literature/evidence.md", by_path)
        self.assertIn("analysis/result.json", by_path)
        self.assertNotIn("paper/main.tex", by_path)
        self.assertEqual(by_path["analysis/raw.csv"]["content_policy"], "raw-data-reference-only")
        self.assertNotIn("excerpts", by_path["analysis/raw.csv"])

    def test_reviewer_receives_artifacts_only_and_receipt_is_bounded(self):
        packed = ContextPacker(self.root).pack(self.state, self.state["task_graph"][3], 256)
        self.assertLessEqual(packed.receipt["estimated_tokens"], 256)
        self.assertEqual(packed.receipt["policy"], "artifact-only")
        self.assertRegex(packed.receipt["pack_hash"], "^[a-f0-9]{64}$")

    def test_sensitive_content_is_reference_only_without_explicit_authorization(self):
        self.state["data_sensitivity"] = "restricted"
        packed = ContextPacker(self.root).pack(self.state, self.state["task_graph"][2], 2000)
        self.assertTrue(all("excerpts" not in item for item in packed.artifacts))
        self.assertTrue(any(item.get("content_policy") == "sensitive-reference-only" for item in packed.artifacts))
        authorized = ContextPacker(self.root, allow_sensitive_content=True).pack(
            self.state, self.state["task_graph"][2], 2000
        )
        self.assertTrue(any("excerpts" in item for item in authorized.artifacts if item["path"].endswith(".json")))

    def test_role_policy_excludes_analysis_from_literature_agent(self):
        followup = task("followup", "trade evidence", "agent", "literature-agent", ["analysis"])
        self.state["task_graph"].append(followup)
        packed = ContextPacker(self.root).pack(self.state, followup, 2000)
        self.assertFalse(any(item["path"].startswith("analysis/") for item in packed.artifacts))


if __name__ == "__main__":
    unittest.main()
