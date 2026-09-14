from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from research_os.adapters.mock import MockModelAdapter
from research_os.executor import AgentExecutor
from research_os.native_tools import artifact_write
from research_os.planner import task
from research_os.runtime import ResearchRuntime
from research_os.tools import GENERIC_OUTPUT, ToolRegistry, ToolSpec, default_registry

from tests.e2e.test_public_projects import ProjectHarness, obs, write_request


class FaultInjectionE2ETests(unittest.TestCase):
    def test_model_timeout_is_retried_then_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = ProjectHarness(Path(tmp), "e2e-model-timeout", False)
            graph = [task(
                "literature", "Retry a bounded model timeout", "agent", "literature-agent", [],
                expected_outputs=["literature/evidence.json"], allowed_tools=["artifact_write"],
                max_attempts=2,
            )]
            scripts = {"literature": [
                {"_inject": "timeout"},
                obs("write after retry", write_request("literature/evidence.json", "{}\n", "retry-write")),
                obs("complete after retry"),
            ]}
            runtime, _ = harness.install(graph, scripts)
            state = runtime.run(max_steps=4)
            item = state["task_graph"][0]
            self.assertEqual(item["status"], "complete")
            self.assertEqual(item["attempts"], 2)
            self.assertEqual(state["retry_count"], 1)

    def test_malformed_observation_cannot_bypass_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = ProjectHarness(Path(tmp), "e2e-malformed", False)
            graph = [task(
                "literature", "Reject malformed model output", "agent", "literature-agent", [],
                max_attempts=1,
            )]
            runtime, _ = harness.install(graph, {"literature": {"summary": "missing outcome"}})
            state = runtime.run(max_steps=2)
            self.assertEqual(state["task_graph"][0]["status"], "blocked")
            self.assertIn("not valid", state["errors"][0]["message"])

    def test_missing_artifact_is_rejected_then_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = ProjectHarness(Path(tmp), "e2e-missing-artifact", False)
            graph = [task(
                "literature", "Require an actual hashed artifact", "agent", "literature-agent", [],
                expected_outputs=["literature/evidence.json"], allowed_tools=["artifact_write"],
                max_attempts=2,
            )]
            bad = obs("false completion", artifacts=[{
                "path": "literature/evidence.json", "sha256": "0" * 64,
            }])
            scripts = {"literature": [
                bad,
                obs("repair", write_request("literature/evidence.json", "{}\n", "repair-write")),
                obs("complete"),
            ]}
            runtime, _ = harness.install(graph, scripts)
            state = runtime.run(max_steps=4)
            self.assertEqual(state["task_graph"][0]["status"], "complete")
            self.assertTrue(any("Expected output is missing" in error["message"] for error in state["errors"]))

    def test_network_failure_is_bounded_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = ProjectHarness(Path(tmp), "e2e-network-failure", False)
            attempts = {"count": 0}

            def unstable_network(_inputs, _project):
                attempts["count"] += 1
                if attempts["count"] == 1:
                    raise ConnectionError("injected network failure")
                return {"status": "complete", "artifacts": [], "errors": []}

            registry = ToolRegistry()
            registry.register(ToolSpec(
                "network_probe", "Synthetic network failure injector", {"type": "object"},
                GENERIC_OUTPUT, side_effect_level="none", timeout=1,
                data_sensitivity=["synthetic"],
            ), unstable_network)
            state = harness.store.load()
            state["task_graph"] = [task(
                "network", "Retry a transient network failure", "tool", "research-director", [],
                tool_name="network_probe", max_attempts=2,
            )]
            state["completed_tasks"] = []
            harness.store.save(state, "e2e.network-graph", {})
            final = ResearchRuntime(harness.store, harness.project, tools=registry).run(max_steps=3)
            self.assertEqual(final["task_graph"][0]["status"], "complete")
            self.assertEqual(attempts["count"], 2)

    def test_tool_timeout_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = ProjectHarness(Path(tmp), "e2e-tool-timeout", False)

            def delayed(_inputs, _project):
                time.sleep(0.1)
                return {"status": "complete", "artifacts": [], "errors": []}

            registry = ToolRegistry()
            registry.register(ToolSpec(
                "delayed", "Synthetic timeout injector", {"type": "object"}, GENERIC_OUTPUT,
                side_effect_level="none", timeout=0.01, data_sensitivity=["synthetic"],
            ), delayed)
            state = harness.store.load()
            state["task_graph"] = [task(
                "timeout", "Block after a bounded tool timeout", "tool", "research-director", [],
                tool_name="delayed", max_attempts=1,
            )]
            state["completed_tasks"] = []
            harness.store.save(state, "e2e.timeout-graph", {})
            final = ResearchRuntime(harness.store, harness.project, tools=registry).run(max_steps=2)
            self.assertEqual(final["task_graph"][0]["status"], "blocked")
            self.assertIn("timed out", final["errors"][0]["message"])

    def test_idempotency_ledger_prevents_duplicate_local_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            registry = default_registry()
            inputs = {
                "path": "literature/once.json", "content": "{}\n",
                "idempotency_key": "same-write-001",
            }
            first = registry.execute("artifact_write", inputs, project, data_sensitivity="synthetic")
            second = registry.execute("artifact_write", inputs, project, data_sensitivity="synthetic")
            self.assertFalse(first.get("idempotent_replay", False))
            self.assertTrue(second["idempotent_replay"])
            self.assertEqual(first["artifacts"], second["artifacts"])
            with self.assertRaises(ValueError):
                registry.execute("artifact_write", {**inputs, "content": "changed\n"}, project,
                                 data_sensitivity="synthetic")

    def test_restart_resume_and_corrupt_state_recovery_preserve_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = ProjectHarness(Path(tmp), "e2e-restart", False)
            graph = [
                task("literature", "First durable task", "agent", "literature-agent", [],
                     expected_outputs=["literature/evidence.json"], allowed_tools=["artifact_write"]),
                task("writing", "Second durable task", "agent", "writing-agent", ["literature"],
                     expected_outputs=["paper/main.tex"], allowed_tools=["artifact_write"]),
            ]
            first_adapter = MockModelAdapter({"literature": [
                obs("write", write_request("literature/evidence.json", "{}\n", "restart-lit")), obs("done"),
            ]})
            first_runtime = ResearchRuntime(
                harness.store, harness.project,
                agent_executors={"literature-agent": AgentExecutor(first_adapter)},
            )
            state = harness.store.load()
            state["task_graph"] = graph
            state["completed_tasks"] = []
            harness.store.save(state, "e2e.restart-graph", {})
            after_first = first_runtime.run(max_steps=1)
            self.assertEqual(after_first["completed_tasks"], ["literature"])

            second_adapter = MockModelAdapter({"writing": [
                obs("write", write_request("paper/main.tex", "draft\n", "restart-paper")), obs("done"),
            ]})
            restarted = ResearchRuntime(
                harness.store, harness.project,
                agent_executors={"writing-agent": AgentExecutor(second_adapter)},
            )
            after_second = restarted.run(max_steps=1)
            self.assertEqual(after_second["completed_tasks"], ["literature", "writing"])

            newest_checkpoint = sorted(harness.store.checkpoint_dir.glob("*.json"))[-1]
            newest_checkpoint.write_text("corrupted checkpoint", encoding="utf-8")
            self.assertTrue(any("hash mismatch" in item for item in harness.store.verify()))
            harness.store.state_path.write_text("corrupted", encoding="utf-8")
            recovered = harness.store.recover_latest()
            self.assertEqual(recovered["completed_tasks"], ["literature", "writing"])
            reconstructed = restarted.reconstruct()
            self.assertEqual(reconstructed["completed_tasks"], ["literature", "writing"])
            self.assertFalse(reconstructed["memory"]["working"]["entries"][0]["missing_artifacts"])

    def test_human_rejection_blocks_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = ProjectHarness(Path(tmp), "e2e-human-reject", False)
            state = harness.store.load()
            state["task_graph"] = [task(
                "final-gate", "Require explicit approval", "human_gate", "research-director", [],
            )]
            state["completed_tasks"] = []
            harness.store.save(state, "e2e.human-gate", {})
            runtime = ResearchRuntime(harness.store, harness.project)
            waiting = runtime.run(max_steps=1)
            action = next(item for item in waiting["pending_human_actions"] if item["status"] == "pending")
            rejected = runtime.decide(action["action_id"], False, "Injected researcher rejection")
            self.assertEqual(rejected["lifecycle_status"], "blocked")
            self.assertEqual(rejected["task_graph"][0]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
