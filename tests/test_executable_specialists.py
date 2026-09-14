from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research_os.adapters.mock import MockModelAdapter
from research_os.executor import AgentExecutor
from research_os.planner import task
from research_os.runtime import ResearchRuntime


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observation(summary: str, tool_request: dict | None = None) -> dict:
    return {"outcome": "PASS", "summary": summary, "artifacts": [], "tool_calls": [],
            "tool_requests": [tool_request] if tool_request else [], "errors": [], "next_tasks": []}


class ExecutableSpecialistTests(unittest.TestCase):
    def test_four_specialists_execute_tools_with_independent_reviewer_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "economics-paper-project/1.0", "project_id": "specialist-test",
                "title_working": "Executable specialist test", "paper_type": "review", "stage": "idea",
                "research_question": "Can executable specialists preserve evidence lineage?",
                "target_journals": [{"name": "undecided", "family": "undecided"}], "contribution_claims": [],
                "data_sensitivity": "synthetic", "approvals": {"question_and_contribution": False,
                "research_design": False, "outline_and_journal": False}, "output_format": "latex"}), encoding="utf-8")
            store = ResearchRuntime.initialize(manifest, root / "runs")
            analysis_script = project / "analysis.py"
            analysis_script.write_text(
                "import json,pathlib,sys\np=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'coefficient':2.0}))\n",
                encoding="utf-8")
            graph = [
                task("literature", "Create verified literature evidence", "agent", "literature-agent", [],
                     expected_outputs=["literature/evidence.json"], allowed_tools=["artifact_write"]),
                task("literature-review", "Review literature artifact", "verifier", "reviewer-verifier-agent", ["literature"],
                     required_inputs={"producer_task_id": "literature"}),
                task("analysis", "Run approved synthetic analysis", "agent", "empirical-agent", ["literature-review"],
                     expected_outputs=["analysis"], allowed_tools=["python"]),
                task("writing", "Write from approved artifacts", "agent", "writing-agent", ["analysis"],
                     expected_outputs=["paper/main.tex"], allowed_tools=["artifact_write"]),
                task("manuscript-review", "Independently review manuscript", "verifier", "reviewer-verifier-agent", ["writing"],
                     required_inputs={"producer_task_id": "writing"}, expected_outputs=["audit/review.json"],
                     allowed_tools=["artifact_write"]),
            ]
            state = store.load(); state["task_graph"] = graph; state["completed_tasks"] = []
            state["lifecycle_status"] = "initialized"; store.save(state, "test.graph", {})
            requests = {
                "literature": [observation("write evidence", {"name": "artifact_write", "call_id": "lit-write",
                    "arguments": {"path": "literature/evidence.json", "content": "{\"verified\":true}\n", "idempotency_key": "lit-write-001"}}), observation("evidence produced")],
                "literature-review": observation("evidence package passes"),
                "analysis": [observation("run analysis", {"name": "python", "call_id": "py-run",
                    "arguments": {"script": "analysis.py", "script_sha256": sha(analysis_script),
                    "output_directory": "analysis/run", "idempotency_key": "analysis-001",
                    "arguments": ["analysis/run/result.json"], "required_outputs": ["analysis/run/result.json"]}}), observation("analysis produced")],
                "writing": [observation("write manuscript", {"name": "artifact_write", "call_id": "paper-write",
                    "arguments": {"path": "paper/main.tex", "content": "\\documentclass{article}\\begin{document}Verified.\\end{document}\n", "idempotency_key": "paper-write-001"}}), observation("manuscript produced")],
                "manuscript-review": [observation("write audit", {"name": "artifact_write", "call_id": "audit-write",
                    "arguments": {"path": "audit/review.json", "content": "{\"status\":\"pass\"}\n", "idempotency_key": "audit-write-001"}}), observation("review passes")],
            }
            adapter = MockModelAdapter(requests); executor = AgentExecutor(adapter)
            runtime = ResearchRuntime(store, project, agent_executors={name: executor for name in
                ("literature-agent", "empirical-agent", "writing-agent", "reviewer-verifier-agent")})
            result = runtime.run(max_steps=5)
            self.assertTrue(all(item["status"] == "complete" for item in result["task_graph"]))
            self.assertEqual({run["name"] for run in result["tool_runs"]}, {"artifact_write", "python"})
            reviewer_requests = [request for request in adapter._requests.values() if request.agent_identity == "reviewer-verifier-agent"]
            self.assertTrue(reviewer_requests)
            self.assertTrue(all(request.working_context == {} for request in reviewer_requests))
            self.assertTrue(any(item["path"] == "literature/evidence.json" for item in reviewer_requests[0].artifact_context))
            writing_request = next(request for request in adapter._requests.values() if request.agent_identity == "writing-agent")
            self.assertTrue(any(item["path"] == "analysis/run/result.json" for item in writing_request.artifact_context))
            literature_request = next(request for request in adapter._requests.values() if request.agent_identity == "literature-agent")
            self.assertEqual(literature_request.tool_specs[0]["name"], "artifact_write")
            self.assertIn("idempotency_key", literature_request.tool_specs[0]["input_schema"]["required"])

    def test_specialist_cannot_write_outside_role_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir(); manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version":"economics-paper-project/1.0","project_id":"scope-test","title_working":"Scope test","paper_type":"review","stage":"idea","research_question":"Does role scoped writing prevent cross-domain mutation?","target_journals":[{"name":"undecided","family":"undecided"}],"contribution_claims":[],"data_sensitivity":"synthetic","approvals":{"question_and_contribution":False,"research_design":False,"outline_and_journal":False},"output_format":"latex"}))
            store = ResearchRuntime.initialize(manifest, root / "runs"); state = store.load()
            state["task_graph"] = [task("literature", "Attempt invalid literature write", "agent", "literature-agent", [], allowed_tools=["artifact_write"])]
            store.save(state, "test.graph", {})
            adapter = MockModelAdapter({"literature": observation("bad write", {"name":"artifact_write","call_id":"bad","arguments":{"path":"paper/escape.tex","content":"bad","idempotency_key":"bad-write-001"}})})
            result = ResearchRuntime(store, project, agent_executors={"literature-agent": AgentExecutor(adapter)}).run(max_steps=1)
            self.assertEqual(result["task_graph"][0]["status"], "waiting-human")
            self.assertFalse((project / "paper/escape.tex").exists())

    def test_invalid_followup_proposal_cannot_mutate_graph_or_register_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir(); manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version":"economics-paper-project/1.0","project_id":"proposal-firewall-test","title_working":"Proposal firewall test","paper_type":"review","stage":"idea","research_question":"Can an invalid model proposal mutate canonical state?","target_journals":[{"name":"undecided","family":"undecided"}],"contribution_claims":[],"data_sensitivity":"synthetic","approvals":{"question_and_contribution":False,"research_design":False,"outline_and_journal":False},"output_format":"latex"}))
            store = ResearchRuntime.initialize(manifest, root / "runs"); state = store.load()
            state["task_graph"] = [task("literature", "Propose bounded follow-up", "agent", "literature-agent", [])]
            store.save(state, "test.graph", {})
            invalid = observation("unsafe follow-up")
            invalid["next_tasks"] = [{
                "task_id":"unregistered-followup", "task_type":"agent", "goal":"Use an unknown tool",
                "dependencies":["literature"], "assigned_agent":"literature-agent",
                "allowed_tools":["not-a-registered-tool"], "expected_outputs":[]
            }]
            adapter = MockModelAdapter({"literature": invalid})
            result = ResearchRuntime(store, project, agent_executors={"literature-agent": AgentExecutor(adapter)}).run(max_steps=1)
            self.assertEqual([item["task_id"] for item in result["task_graph"]], ["literature"])
            self.assertEqual(result["task_graph"][0]["status"], "pending")
            self.assertEqual([item["artifact_id"] for item in result["artifacts"]], ["project-manifest"])
            self.assertEqual(result["errors"][-1]["failure_class"], "FAIL_TRANSIENT")
            self.assertIn("Unknown tool", result["errors"][-1]["message"])

    def test_invalid_strategy_replan_becomes_human_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir(); manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version":"economics-paper-project/1.0","project_id":"replan-firewall-test","title_working":"Replan firewall test","paper_type":"review","stage":"idea","research_question":"Does an unsafe replan stop at a human gate?","target_journals":[{"name":"undecided","family":"undecided"}],"contribution_claims":[],"data_sensitivity":"synthetic","approvals":{"question_and_contribution":False,"research_design":False,"outline_and_journal":False},"output_format":"latex"}))
            store = ResearchRuntime.initialize(manifest, root / "runs"); state = store.load()
            state["task_graph"] = [task("literature", "Request a bounded replan", "agent", "literature-agent", [])]
            store.save(state, "test.graph", {})
            invalid = {"outcome":"FAIL_STRATEGY", "summary":"unsafe strategy", "artifacts":[],
                       "tool_calls":[], "tool_requests":[], "errors":[], "next_tasks":[],
                       "replacement_tasks":[{
                           "task_id":"unsafe-replacement", "task_type":"agent", "goal":"Unknown tool",
                           "dependencies":["literature"], "assigned_agent":"literature-agent",
                           "allowed_tools":["not-a-registered-tool"], "expected_outputs":[]
                       }]}
            adapter = MockModelAdapter({"literature": invalid})
            result = ResearchRuntime(store, project, agent_executors={"literature-agent": AgentExecutor(adapter)}).run(max_steps=1)
            self.assertEqual([item["task_id"] for item in result["task_graph"]], ["literature"])
            self.assertEqual(result["task_graph"][0]["status"], "waiting-human")
            self.assertEqual(result["lifecycle_status"], "waiting-human")
            self.assertIn("Unsafe or invalid strategy proposal rejected", result["pending_human_actions"][-1]["question"])


if __name__ == "__main__":
    unittest.main()
