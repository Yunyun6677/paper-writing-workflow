from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from research_os.runtime import ResearchRuntime
from research_os.scientific_memory import ScientificMemoryStore


def manifest(path: Path, sensitivity: str = "synthetic") -> Path:
    path.write_text(json.dumps({
        "schema_version": "economics-paper-project/1.0", "project_id": "memory-test",
        "title_working": "Scientific memory test", "paper_type": "review", "stage": "idea",
        "research_question": "How should evidence lineage be queried safely?",
        "target_journals": [{"name": "undecided", "family": "undecided"}],
        "contribution_claims": [], "data_sensitivity": sensitivity,
        "approvals": {"question_and_contribution": False, "research_design": False, "outline_and_journal": False},
        "output_format": "latex",
    }), encoding="utf-8")
    return path


class ScientificMemoryTests(unittest.TestCase):
    def test_runtime_indexes_project_tasks_and_artifacts_without_replacing_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ResearchRuntime.initialize(manifest(root / "manifest.json"), root / "runs")
            runtime = ResearchRuntime(store, root)
            database = store.run_dir / "scientific-memory.sqlite"
            self.assertTrue(database.is_file())
            project = runtime.scientific_memory.get_entity("Project", "memory-test")
            self.assertEqual(project["metadata"]["paper_type"], "review")
            self.assertGreater(len(runtime.scientific_memory.neighbors("memory-test", "Project", "memory-test", "contains")), 0)
            self.assertTrue(store.state_path.is_file())

    def test_claim_evidence_source_and_model_dataset_graph_is_queryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = ScientificMemoryStore(Path(tmp) / "memory.sqlite")
            for entity_type, entity_id, metadata in (
                ("Claim", "c1", {"claim_hash": "a" * 64}),
                ("Evidence", "e1", {"locator": "page 3", "source_sha256": "b" * 64}),
                ("Source", "s1", {"doi": "10.1/example"}),
                ("Dataset", "d1", {"artifact_id": "dataset:1", "sha256": "c" * 64}),
                ("ModelRun", "m1", {"receipt_artifact_id": "run:1"}),
            ):
                memory.put_entity(entity_type, entity_id, "p1", metadata, "public")
            memory.relate("p1", "Claim", "c1", "supported_by", "Evidence", "e1")
            memory.relate("p1", "Evidence", "e1", "extracted_from", "Source", "s1")
            memory.relate("p1", "ModelRun", "m1", "used_dataset", "Dataset", "d1")
            self.assertEqual(memory.claim_evidence("p1", "c1")[0]["target_id"], "e1")
            self.assertEqual(memory.neighbors("p1", "ModelRun", "m1", "used_dataset")[0]["target_id"], "d1")

    def test_restricted_content_and_secrets_are_rejected_but_hash_references_are_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = ScientificMemoryStore(Path(tmp) / "memory.sqlite")
            with self.assertRaises(ValueError):
                memory.put_entity("Evidence", "e1", "p1", {"text": "restricted row"}, "restricted")
            with self.assertRaises(ValueError):
                memory.put_entity("Source", "s1", "p1", {"api_key": "do-not-store"}, "public")
            memory.put_entity("Evidence", "e2", "p1", {"artifact_id": "evidence:2", "sha256": "a" * 64}, "restricted")
            self.assertIsNotNone(memory.get_entity("Evidence", "e2"))

    def test_updates_are_transactional_and_do_not_duplicate_relations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.sqlite"
            memory = ScientificMemoryStore(path)
            memory.put_entity("Task", "t1", "p1", {"status": "pending"})
            memory.put_entity("Task", "t1", "p1", {"status": "complete"})
            memory.put_entity("Artifact", "a1", "p1", {"path": "result.json", "sha256": "a" * 64})
            memory.relate("p1", "Task", "t1", "produced", "Artifact", "a1")
            memory.relate("p1", "Task", "t1", "produced", "Artifact", "a1")
            self.assertEqual(memory.get_entity("Task", "t1")["metadata"]["status"], "complete")
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM relations").fetchone()[0], 1)

    def test_unknown_schema_version_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.sqlite"
            ScientificMemoryStore(path)
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("UPDATE memory_meta SET value='scientific-memory/99.0' WHERE key='schema_version'")
                connection.commit()
            with self.assertRaises(RuntimeError):
                ScientificMemoryStore(path)

    def test_restricted_decision_rationale_is_hashed_not_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ResearchRuntime.initialize(manifest(root / "manifest.json", "restricted"), root / "runs")
            state = store.load()
            state["decisions"] = [{"decision_id":"d1", "task_id":"frame", "approved":True,
                                   "rationale":"sensitive research rationale", "actor":"human", "at":"2026-09-14T00:00:00+00:00"}]
            memory = ScientificMemoryStore(root / "memory.sqlite")
            memory.ingest_state(state)
            metadata = memory.get_entity("Decision", "d1")["metadata"]
            self.assertNotIn("rationale", metadata)
            self.assertRegex(metadata["rationale_hash"], "^[a-f0-9]{64}$")


if __name__ == "__main__":
    unittest.main()
