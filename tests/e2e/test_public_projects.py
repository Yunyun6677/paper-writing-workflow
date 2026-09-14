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


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def obs(summary: str, request: dict | None = None, **extra) -> dict:
    value = {"outcome":"PASS","summary":summary,"artifacts":[],"tool_calls":[],"tool_requests":[],"errors":[],"next_tasks":[]}
    if request: value["tool_requests"] = [request]
    value.update(extra); return value


def write_request(path: str, content: str, call_id: str) -> dict:
    return {"name":"artifact_write","call_id":call_id,"arguments":{"path":path,"content":content,
            "idempotency_key":call_id + "-idempotency"}}


class ProjectHarness:
    def __init__(self, root: Path, project_id: str, empirical: bool):
        self.root = root; self.project = root / "project"; self.project.mkdir()
        manifest = self.project / "manifest.json"
        manifest_value = {"schema_version":"economics-paper-project/1.0","project_id":project_id,
            "title_working":"Synthetic E2E project","paper_type":"empirical" if empirical else "review","stage":"idea",
            "research_question":"Can the bounded workflow complete using only public or synthetic artifacts?",
            "target_journals":[{"name":"undecided","family":"undecided"}],"contribution_claims":[],
            "data_sensitivity":"synthetic","approvals":{"question_and_contribution":False,"research_design":False,
            "outline_and_journal":False},"output_format":"latex"}
        if empirical:
            manifest_value["research_design"] = {
                "unit_of_analysis": "synthetic row",
                "treatment_or_exposure": "x",
                "outcomes": ["y"],
                "estimand": "OLS slope",
                "identification_strategy": "descriptive OLS",
                "assumptions": ["synthetic linear data"],
                "threats": [],
                "inference_plan": "point estimate only",
            }
        manifest.write_text(json.dumps(manifest_value), encoding="utf-8")
        self.store = ResearchRuntime.initialize(manifest, root / "runs")

    def install(self, graph: list[dict], scripts: dict) -> tuple[ResearchRuntime, MockModelAdapter]:
        state = self.store.load(); state["task_graph"] = graph; state["completed_tasks"] = []; state["lifecycle_status"] = "initialized"
        self.store.save(state, "e2e.graph", {})
        adapter = MockModelAdapter(scripts); executor = AgentExecutor(adapter)
        agents = {name:executor for name in ("literature-agent","empirical-agent","writing-agent","reviewer-verifier-agent")}
        return ResearchRuntime(self.store, self.project, agent_executors=agents), adapter

    @staticmethod
    def finish_human_gate(runtime: ResearchRuntime, state: dict) -> dict:
        action = next(item for item in state["pending_human_actions"] if item["status"] == "pending")
        runtime.decide(action["action_id"], True, "Synthetic E2E approval")
        return runtime.run(max_steps=2)


def graph(empirical: bool) -> list[dict]:
    nodes = [
        task("literature","Build literature evidence","agent","literature-agent",[],expected_outputs=["literature/evidence.json"],allowed_tools=["artifact_write"]),
        task("literature-review","Verify literature","verifier","reviewer-verifier-agent",["literature"],required_inputs={"producer_task_id":"literature"}),
    ]
    if empirical:
        nodes += [
            task("analysis","Run public OLS","agent","empirical-agent",["literature-review"],expected_outputs=["analysis"],allowed_tools=["python"]),
            task("empirical-review","Verify OLS number","verifier","reviewer-verifier-agent",["analysis"],required_inputs={"producer_task_id":"analysis"},expected_outputs=["audit/numeric.json"],allowed_tools=["evidence_verify"]),
        ]
    dependencies = ["literature-review", "empirical-review"] if empirical else ["literature-review"]
    nodes += [
        task("writing","Write LaTeX","agent","writing-agent",dependencies,expected_outputs=["paper/main.tex"],allowed_tools=["artifact_write"]),
        task("manuscript-review","Review manuscript","verifier","reviewer-verifier-agent",["writing"],required_inputs={"producer_task_id":"writing"}),
        task("final-audit","Audit lineage","final_audit","reviewer-verifier-agent",["manuscript-review"],tool_name="research_firewall",allowed_tools=["research_firewall"],expected_outputs=["audit/agent-runtime-audit.json"]),
        task("final-gate","Approve package","human_gate","research-director",["final-audit"]),
    ]
    return nodes


class PublicProjectE2ETests(unittest.TestCase):
    def test_a_literature_only_project_reaches_final_human_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = ProjectHarness(Path(tmp), "e2e-literature", False)
            scripts = {
                "literature":[obs("write evidence",write_request("literature/evidence.json","{\"claim\":\"synthetic\"}\n","lit")),obs("done")],
                "literature-review":obs("verified"),
                "writing":[obs("write",write_request("paper/main.tex","\\documentclass{article}\\begin{document}Synthetic.\\end{document}\n","paper")),obs("done")],
                "manuscript-review":obs("pass"),
            }
            runtime, _ = h.install(graph(False), scripts); waiting = runtime.run(max_steps=20)
            self.assertEqual(waiting["lifecycle_status"], "waiting-human")
            complete = h.finish_human_gate(runtime, waiting); self.assertEqual(complete["lifecycle_status"], "complete")

    def test_b_public_csv_ols_is_executed_and_numerically_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = ProjectHarness(Path(tmp), "e2e-ols", True)
            (h.project/"data.csv").write_text("x,y\n1,3\n2,5\n3,7\n", encoding="utf-8")
            script = h.project/"ols.py"; script.write_text("import csv,json,pathlib,sys\nr=list(csv.DictReader(open(sys.argv[1])));x=[float(i['x']) for i in r];y=[float(i['y']) for i in r];mx=sum(x)/len(x);my=sum(y)/len(y);b=sum((a-mx)*(c-my) for a,c in zip(x,y))/sum((a-mx)**2 for a in x);p=pathlib.Path(sys.argv[2]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'spec':{'spec_id':'ols-1'},'sample_sha256':'public-3','coefficient':b}))\n", encoding="utf-8")
            py = {"name":"python","call_id":"ols","arguments":{"script":"ols.py","script_sha256":sha(script),"output_directory":"analysis/run","idempotency_key":"ols-public-001","arguments":["data.csv","analysis/run/result.json"],"required_outputs":["analysis/run/result.json"]}}
            verify = {"name":"evidence_verify","call_id":"num","arguments":{"verifier_type":"numeric","request":{"source_artifact":"analysis/run/result.json","value_locator":"coefficient","manuscript_value":2.0,"identity_expectations":{"spec.spec_id":"ols-1","sample_sha256":"public-3"},"model_id":"ols-1","sample_id":"public-3"},"output":"audit/numeric.json"}}
            scripts = {"literature":[obs("write",write_request("literature/evidence.json","{\"public\":true}\n","lit")),obs("done")],"literature-review":obs("pass"),
                "analysis":[obs("run",py),obs("done")],"empirical-review":[obs("verify",verify),obs("pass")],
                "writing":[obs("write",write_request("paper/main.tex","\\documentclass{article}\\begin{document}The coefficient is 2.\\end{document}\n","paper")),obs("done")],"manuscript-review":obs("pass")}
            runtime, _ = h.install(graph(True), scripts); waiting = runtime.run(max_steps=30)
            self.assertEqual(json.loads((h.project/"analysis/run/result.json").read_text())["coefficient"], 2.0)
            self.assertEqual(json.loads((h.project/"audit/numeric.json").read_text())["status"], "pass")
            self.assertEqual(h.finish_human_gate(runtime, waiting)["lifecycle_status"], "complete")

    def test_c_reviewer_rejection_creates_legal_feedback_branch_and_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = ProjectHarness(Path(tmp), "e2e-feedback", False)
            scripts = {"literature":[obs("write",write_request("literature/evidence.json","{\"claim\":1}\n","lit")),obs("done")],"literature-review":obs("pass"),
                "writing":[obs("write",write_request("paper/main.tex","draft\n","paper")),obs("done")],
                "manuscript-review":obs("robustness missing",outcome="FAIL_STRATEGY",replan="robustness"),
                "robustness-followup-01":[obs("write robust",write_request("analysis/robustness-01/result.json","{\"robust\":true}\n","robust")),obs("done")],
                "manuscript-revision-01":[obs("revise",write_request("paper/revision-01.tex","revised\n","revision")),obs("done")]}
            runtime, _ = h.install(graph(False), scripts); waiting = runtime.run(max_steps=30)
            self.assertTrue((h.project/"paper/revision-01.tex").is_file())
            self.assertTrue(any(item["task_id"] == "robustness-followup-01" for item in waiting["task_graph"]))
            self.assertEqual(h.finish_human_gate(runtime, waiting)["lifecycle_status"], "complete")


if __name__ == "__main__": unittest.main()
