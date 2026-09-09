from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from research_os.evaluation import evaluate
from research_os.migrations import migrate_project
from research_os.runtime import ResearchRuntime
from research_os.store import sha256_file


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_all_json_schemas_parse(self):
        for path in sorted((ROOT / "schemas").glob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)

    def test_all_agent_configs_validate(self):
        schema = json.loads((ROOT / "schemas" / "research-agent-config.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        configs = sorted((ROOT / "config" / "agents").glob("*.json"))
        self.assertEqual(len(configs), 5)
        for path in configs:
            validator.validate(json.loads(path.read_text(encoding="utf-8")))

    def test_evaluation_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "schema_version": "economics-paper-project/1.0", "project_id": "evaluation-test",
                "title_working": "Evaluation contract", "paper_type": "review", "stage": "idea",
                "research_question": "What evidence supports this review question?",
                "target_journals": [{"name": "undecided", "family": "undecided"}],
                "contribution_claims": [], "data_sensitivity": "synthetic",
                "approvals": {"question_and_contribution": False, "research_design": False, "outline_and_journal": False},
                "output_format": "latex"
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            store = ResearchRuntime.initialize(path, root / "runs")
            result = evaluate(store)
            schema = json.loads((ROOT / "schemas" / "agent-run-evaluation.schema.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(result)
            self.assertEqual(result["status"], "review-required")

    def test_reference_only_migration_preserves_legacy_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            (project / "design").mkdir(parents=True)
            value = {
                "schema_version": "economics-paper-project/1.0", "project_id": "migration-test",
                "title_working": "Migration contract", "paper_type": "review", "stage": "idea",
                "research_question": "What evidence supports this migration test question?",
                "target_journals": [{"name": "undecided", "family": "undecided"}],
                "contribution_claims": [], "data_sensitivity": "synthetic",
                "approvals": {"question_and_contribution": False, "research_design": False, "outline_and_journal": False},
                "output_format": "latex"
            }
            manifest_path = project / "project.json"
            manifest_path.write_text(json.dumps(value), encoding="utf-8")
            design_path = project / "design" / "design-register.json"
            design_path.write_text('{"legacy": true}', encoding="utf-8")
            before = {manifest_path: sha256_file(manifest_path), design_path: sha256_file(design_path)}
            store = migrate_project(project, root / "runs")
            self.assertEqual(before, {path: sha256_file(path) for path in before})
            receipt = json.loads((store.run_dir / "migration-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["strategy"], "reference-only")
            self.assertEqual(len(receipt["sources"]), 2)


if __name__ == "__main__":
    unittest.main()
