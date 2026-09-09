from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from research_os.planner import add_dynamic_tasks, default_graph, task, validate_dag
from research_os.runtime import ResearchRuntime
from research_os.store import ResearchStateStore
from research_os.tools import ToolRegistry


def manifest(path: Path, paper_type: str = "empirical") -> Path:
    value = {
        "schema_version": "economics-paper-project/1.0",
        "project_id": "runtime-test",
        "title_working": "A persistent research agent test",
        "paper_type": paper_type,
        "stage": "idea",
        "research_question": "Does a policy change the specified social outcome?",
        "target_journals": [{"name": "undecided", "family": "undecided"}],
        "contribution_claims": [],
        "research_design": {
            "unit_of_analysis": "unit", "treatment_or_exposure": "policy", "outcomes": ["outcome"],
            "estimand": "average effect", "identification_strategy": "not yet approved",
            "assumptions": ["to be reviewed"], "threats": [], "inference_plan": "to be reviewed"
        },
        "data_sensitivity": "synthetic",
        "approvals": {"question_and_contribution": False, "research_design": False, "outline_and_journal": False},
        "output_format": "latex"
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class ResearchAgentRuntimeTests(unittest.TestCase):
    def test_initialize_validates_unified_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ResearchRuntime.initialize(manifest(root / "manifest.json"), root / "runs")
            state = store.load()
            schema = json.loads((Path(__file__).parents[1] / "schemas" / "research-state.schema.json").read_text())
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(state)
            self.assertEqual(state["project_id"], "runtime-test")
            self.assertTrue(store.events_path.is_file())
            self.assertFalse(store.verify())

    def test_agent_observation_then_human_interrupt_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "design").mkdir()
            design = project / "design" / "design-register.json"
            design.write_text("{}", encoding="utf-8")
            store = ResearchRuntime.initialize(manifest(root / "manifest.json"), root / "runs")
            runtime = ResearchRuntime(store, project)
            state = runtime.run()
            self.assertEqual(state["task_graph"][0]["status"], "waiting-agent")
            state = runtime.run()
            self.assertEqual(state["current_stage"], "waiting-agent")
            self.assertEqual(state["task_graph"][0]["status"], "waiting-agent")
            import hashlib
            digest = hashlib.sha256(design.read_bytes()).hexdigest()
            runtime.observe_agent("frame", {"status": "complete", "summary": "framing completed", "artifacts": [{"path": "design/design-register.json", "sha256": digest}]})
            state = runtime.run()
            self.assertEqual(state["current_stage"], "question-gate")
            action = next(x for x in state["pending_human_actions"] if x["status"] == "pending")
            runtime.decide(action["action_id"], True, "The researcher approved the frozen question.")
            state = runtime.run()
            waiting = [x for x in state["task_graph"] if x["status"] == "waiting-agent"]
            self.assertEqual(waiting[0]["task_id"], "literature")
            self.assertFalse(store.verify())

    def test_dynamic_replanning_is_typed_and_blocks_final_gate_race(self):
        tasks = default_graph("review")
        add_dynamic_tasks(tasks, [{
            "task_id": "retrieve-missing-core", "title": "Resolve missing core full text",
            "kind": "agent", "owner": "literature-agent"
        }], "literature")
        validate_dag(tasks)
        final_gate = next(x for x in tasks if x["task_id"] == "final-gate")
        self.assertIn("retrieve-missing-core", final_gate["depends_on"])

    def test_dynamic_replanning_rejects_unapproved_agent(self):
        tasks = default_graph("review")
        with self.assertRaises(ValueError):
            add_dynamic_tasks(tasks, [{
                "task_id": "rogue", "title": "Unbounded autonomous task",
                "kind": "agent", "owner": "unapproved-agent"
            }], "literature")

    def test_checkpoint_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ResearchRuntime.initialize(manifest(root / "manifest.json", "review"), root / "runs")
            checkpoint = next(store.checkpoint_dir.glob("*.json"))
            checkpoint.write_text("{}", encoding="utf-8")
            self.assertTrue(any("hash mismatch" in item for item in store.verify()))

    def test_corrupt_canonical_state_recovers_from_latest_valid_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ResearchRuntime.initialize(manifest(root / "manifest.json", "review"), root / "runs")
            original_run_id = store.load()["run_id"]
            store.state_path.write_text("not json", encoding="utf-8")
            recovered = store.recover_latest()
            self.assertEqual(recovered["run_id"], original_run_id)
            self.assertEqual(store.load()["schema_version"], "research-state/1.0")

    def test_graph_cycle_is_rejected(self):
        tasks = default_graph("review")
        tasks[0]["depends_on"] = ["final-gate"]
        with self.assertRaises(ValueError):
            validate_dag(tasks)

    def test_human_handoff_approval_requeues_specialist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            store = ResearchRuntime.initialize(manifest(root / "manifest.json", "review"), root / "runs")
            runtime = ResearchRuntime(store, project)
            runtime.run()
            runtime.observe_agent("frame", {"status": "needs-human", "human_action": "Provide a scope decision"})
            state = store.load()
            action = next(x for x in state["pending_human_actions"] if x["status"] == "pending")
            runtime.decide(action["action_id"], True, "The requested scope detail was supplied.")
            state = runtime.run()
            self.assertEqual(next(x for x in state["task_graph"] if x["task_id"] == "frame")["status"], "waiting-agent")

    def test_tool_retry_is_bounded_and_recorded_once_per_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            store = ResearchRuntime.initialize(manifest(root / "manifest.json", "review"), root / "runs")
            state = store.load()
            state["task_graph"] = [task("fail-tool", "Failing deterministic tool", "tool", "research-director", [], tool_name="always_fail", max_retries=1)]
            store.save(state, "test.graph-replaced", {})
            registry = ToolRegistry()
            registry.register("always_fail", lambda inputs, project_dir: (_ for _ in ()).throw(RuntimeError("transient failure")))
            final = ResearchRuntime(store, project, registry).run()
            self.assertEqual(final["task_graph"][0]["status"], "blocked")
            self.assertEqual(final["retry_count"], 2)
            self.assertEqual(len(final["errors"]), 2)


if __name__ == "__main__":
    unittest.main()
