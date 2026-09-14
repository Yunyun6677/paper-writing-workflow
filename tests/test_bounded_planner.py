from __future__ import annotations

import unittest

from research_os.planner import default_graph
from research_os.planning import BoundedPlanner, MockPlanningAdapter
from research_os.tools import default_registry


def proposal(tasks, mode="initial", parent=None):
    return {"schema_version":"task-graph-proposal/1.0", "proposal_id":"proposal-001",
            "mode":mode, "reason":"bounded synthetic planning test", "parent_task_id":parent, "tasks":tasks}


class BoundedPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = BoundedPlanner(default_registry().manifests())

    def test_valid_initial_proposal_preserves_final_audit_gate(self):
        value = proposal([
            {"task_id":"literature","task_type":"agent","goal":"Collect evidence","dependencies":[],
             "assigned_agent":"literature-agent","allowed_tools":["artifact_write"]},
            {"task_id":"review","task_type":"verifier","goal":"Verify evidence","dependencies":["literature"],
             "required_inputs":{"producer_task_id":"literature"},"assigned_agent":"reviewer-verifier-agent","allowed_tools":[]},
            {"task_id":"final-audit","task_type":"final_audit","goal":"Audit package","dependencies":["review"],
             "assigned_agent":"reviewer-verifier-agent","allowed_tools":["research_firewall"],"tool_name":"research_firewall"},
            {"task_id":"final-gate","task_type":"human_gate","goal":"Approve package","dependencies":["final-audit"],
             "assigned_agent":"research-director","allowed_tools":[]},
        ])
        graph = []
        returned = self.planner.request_and_merge(MockPlanningAdapter(initial=value), graph, {"goal":"test"},
            mode="initial", data_sensitivity="synthetic", max_tasks=10)
        self.assertEqual(returned["proposal_id"], "proposal-001")
        self.assertEqual(graph[-1]["task_id"], "final-gate")

    def test_unknown_tool_cycle_and_high_risk_without_gate_are_rejected(self):
        base = {"task_id":"x","task_type":"agent","goal":"Unsafe task","dependencies":[],
                "assigned_agent":"literature-agent","allowed_tools":["unknown"]}
        with self.assertRaises(ValueError):
            self.planner.validate_proposal(proposal([base]), data_sensitivity="public", max_tasks=5)
        high_risk = {**base, "allowed_tools":["zotero_collection_create"]}
        with self.assertRaises(PermissionError):
            self.planner.validate_proposal(proposal([high_risk]), data_sensitivity="public", max_tasks=5)
        cyclic = [
            {**base, "allowed_tools":[], "dependencies":["y"]},
            {**base, "task_id":"y", "allowed_tools":[], "dependencies":["x"]},
        ]
        with self.assertRaises(ValueError):
            self.planner.validate_proposal(proposal(cyclic), data_sensitivity="public", max_tasks=5)

    def test_adaptive_merge_is_bounded_and_protects_final_dependencies(self):
        graph = default_graph("review")
        value = proposal([{
            "task_id":"literature-followup-test","task_type":"agent","goal":"Fill evidence gap",
            "dependencies":["manuscript-review"],"assigned_agent":"literature-agent",
            "allowed_tools":["artifact_write"],"expected_outputs":["literature/followup-test"]
        }], mode="adaptive", parent="manuscript-review")
        self.planner.merge(graph, value, data_sensitivity="synthetic", max_tasks=20)
        audit = next(item for item in graph if item["task_id"] == "final-audit")
        gate = next(item for item in graph if item["task_id"] == "final-gate")
        self.assertIn("literature-followup-test", audit["dependencies"])
        self.assertIn("literature-followup-test", gate["dependencies"])
        with self.assertRaises(ValueError):
            self.planner.merge(graph, {**value, "proposal_id":"proposal-002",
                "tasks":[{**value["tasks"][0], "task_id":"overflow"}]},
                data_sensitivity="synthetic", max_tasks=len(graph))


if __name__ == "__main__":
    unittest.main()
