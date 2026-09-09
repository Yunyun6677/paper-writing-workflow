from __future__ import annotations
import hashlib, json, tempfile, unittest
from pathlib import Path
import jsonschema
from research_os.guardrails import run_guardrails
from research_os.memory import assert_safe_long_term
from research_os.planner import default_graph, feedback_tasks, task, validate_dag
from research_os.runtime import ResearchRuntime
from research_os.store import ResearchStateStore
from research_os.tools import ToolRegistry, ToolSpec, default_registry

ROOT = Path(__file__).parents[1]

def make_manifest(path: Path, paper_type: str = "review") -> Path:
    value = {"schema_version": "economics-paper-project/1.0", "project_id": "v010-test", "title_working": "Agent loop contract", "paper_type": paper_type, "stage": "idea", "research_question": "What evidence supports this agent loop test?", "target_journals": [{"name": "undecided", "family": "undecided"}], "contribution_claims": [], "data_sensitivity": "synthetic", "approvals": {"question_and_contribution": False, "research_design": False, "outline_and_journal": False}, "output_format": "latex"}
    path.write_text(json.dumps(value), encoding="utf-8"); return path

class AgentRuntimeV010Tests(unittest.TestCase):
    def test_every_task_has_canonical_contract_and_independent_verifier(self):
        graph = default_graph("empirical"); validate_dag(graph)
        required = {"task_id", "task_type", "goal", "dependencies", "required_inputs", "expected_outputs", "assigned_agent", "allowed_tools", "status", "retry_policy", "timeout_seconds", "stopping_condition", "success_contract", "failure_contract", "verification_rules"}
        for item in graph: self.assertTrue(required.issubset(item))
        by_id = {x["task_id"]: x for x in graph}
        for item in graph:
            producer = item["required_inputs"].get("producer_task_id")
            if producer: self.assertNotEqual(item["assigned_agent"], by_id[producer]["assigned_agent"])

    def test_feedback_branches_return_to_literature_or_empirical_then_writing(self):
        evidence = feedback_tasks("new_evidence", "manuscript-review", 1)
        robust = feedback_tasks("robustness", "manuscript-review", 2)
        self.assertEqual([x["assigned_agent"] for x in evidence], ["literature-agent", "writing-agent"])
        self.assertEqual([x["assigned_agent"] for x in robust], ["empirical-agent", "writing-agent"])

    def test_pause_resume_and_reconstruct_do_not_require_chat_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir()
            store = ResearchRuntime.initialize(make_manifest(root / "manifest.json"), root / "runs")
            runtime = ResearchRuntime(store, project); self.assertEqual(runtime.pause("researcher away")["lifecycle_status"], "paused")
            self.assertEqual(runtime.run()["lifecycle_status"], "paused")
            resumed = runtime.resume(); self.assertEqual(resumed["task_graph"][0]["status"], "waiting-agent")
            reconstructed = runtime.reconstruct(); self.assertTrue(reconstructed["memory"]["working"]["entries"])

    def test_strategy_failure_replans_with_bounded_dynamic_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir()
            store = ResearchRuntime.initialize(make_manifest(root / "manifest.json"), root / "runs")
            runtime = ResearchRuntime(store, project); runtime.run()
            state = store.load(); frame = state["task_graph"][0]; frame["expected_outputs"] = []
            store.save(state, "test.contract-relaxed", {})
            runtime.observe_agent("frame", {"outcome": "FAIL_STRATEGY", "summary": "scope needs evidence", "replan": "new_evidence"})
            state = store.load(); self.assertEqual(next(x for x in state["task_graph"] if x["task_id"] == "frame")["status"], "superseded")
            self.assertTrue(any(x["task_id"].startswith("literature-followup") for x in state["task_graph"]))

    def test_tool_registry_contract_permission_timeout_and_schema(self):
        registry = default_registry(); manifest_schema = json.loads((ROOT / "schemas/tool-manifest.schema.json").read_text())
        for value in registry.manifests(): jsonschema.Draft202012Validator(manifest_schema).validate(value)
        gated = ToolRegistry(); gated.register(ToolSpec("gated", "A gated external write test tool.", {"type": "object"}, {"type": "object", "required": ["status"]}, "external-write", "explicit-approval", timeout=1, data_sensitivity=["public"]), lambda inputs, root: {"status": "complete"})
        with self.assertRaises(PermissionError): gated.execute("gated", {}, ROOT)

    def test_all_scientific_guardrails_block_unsafe_claims(self):
        report = run_guardrails({"citation_claims": [{"claim_id": "c1", "citation_keys": [], "evidence_refs": [], "verification_status": "unverified", "entailment_status": "failed"}], "fulltext_records": [{"source_id": "s1", "used_in_manuscript": True, "fulltext_status": "metadata-only", "actually_read": False}], "numeric_claims": [{"claim_id": "n1", "verification_status": "unverified"}], "causal_claims": [{"claim_id": "k1", "identification_status": "failed", "qualified_language": False}], "specification_changes": [{"field": "controls", "reason": "significance", "approved": False}], "tool_context": {"data_sensitivity": "restricted", "side_effect_level": "external-write", "permission_level": "automatic"}})
        self.assertEqual(report["status"], "blocked"); self.assertEqual(len(report["findings"]), 6)

    def test_long_term_memory_rejects_secrets_and_raw_data(self):
        with self.assertRaises(ValueError): assert_safe_long_term({"api_key": "never-store"})
        with self.assertRaises(ValueError): assert_safe_long_term({"raw_data": [1, 2]})

    def test_declared_tool_catalog_entries_validate(self):
        catalog = json.loads((ROOT / "config/tool-registry.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "schemas/tool-manifest.schema.json").read_text(encoding="utf-8"))
        for tool in catalog["tools"]: jsonschema.Draft202012Validator(schema).validate(tool)

if __name__ == "__main__": unittest.main()
