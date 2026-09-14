from __future__ import annotations

import unittest

from research_os.adapters import AgentExecutionRequest, MockModelAdapter
from research_os.executor import AgentExecutor


def request(run_id: str = "run-1", task_id: str = "literature") -> AgentExecutionRequest:
    return AgentExecutionRequest(
        agent_run_id=run_id,
        task_id=task_id,
        agent_identity="literature-agent",
        task_goal="Create verified evidence cards",
        allowed_skills=("social-science-literature-review",),
        allowed_tools=("pdf_parser",),
        working_context={"research_question": "synthetic question"},
        artifact_context=({"path": "input/public.pdf", "sha256": "a" * 64},),
        expected_output_schema={"$ref": "schemas/research-agent-observation.schema.json"},
        timeout_seconds=10,
        token_budget=100,
        data_sensitivity="synthetic",
    )


class ModelAdapterContractTests(unittest.TestCase):
    def test_mock_adapter_returns_normalized_schema_valid_observation(self):
        adapter = MockModelAdapter({"literature": {"outcome": "PASS", "summary": "fixture"}})
        result = AgentExecutor(adapter).execute(request())
        self.assertEqual(result["outcome"], "PASS")
        self.assertEqual(result["agent_run_id"], "run-1")
        self.assertEqual(result["provider"], "mock")
        self.assertEqual(result["token_usage"]["total_tokens"], 2)
        self.assertEqual([event["type"] for event in adapter.stream_events("run-1")], ["model.started", "model.completed"])

    def test_executor_rejects_legacy_status_only_and_mismatched_task(self):
        with self.assertRaises(ValueError):
            AgentExecutor(MockModelAdapter({"literature": {"status": "complete"}})).execute(request())
        with self.assertRaises(ValueError):
            AgentExecutor(MockModelAdapter({"literature": {"outcome": "PASS", "task_id": "other"}})).execute(request())

    def test_mock_timeout_resume_usage_and_cancel_are_deterministic(self):
        adapter = MockModelAdapter({"literature": [
            {"_inject": "timeout"},
            {"outcome": "PASS", "token_usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}},
        ]})
        executor = AgentExecutor(adapter)
        with self.assertRaises(TimeoutError):
            executor.execute(request())
        resumed = executor.resume(request(), {"retry": 1})
        self.assertEqual(resumed["token_usage"]["total_tokens"], 5)
        self.assertTrue(adapter.cancel("run-1")["cancelled"])
        self.assertFalse(adapter.cancel("missing")["cancelled"])

    def test_request_is_bounded_and_defensively_copied(self):
        req = request()
        payload = req.to_payload()
        payload["working_context"]["research_question"] = "mutated"
        self.assertEqual(req.working_context["research_question"], "synthetic question")
        self.assertFalse(hasattr(req, "canonical_state"))


if __name__ == "__main__":
    unittest.main()
