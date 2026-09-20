from __future__ import annotations

import unittest

from research_os.adapters.base import AgentExecutionRequest
from research_os.adapters.mock import MockModelAdapter
from research_os.executor import AgentExecutor


def observation(request=None):
    return {"outcome":"PASS","summary":"bounded tool recovery","artifacts":[],"tool_calls":[],
            "tool_requests":[request] if request else [],"errors":[],"next_tasks":[]}


class AgentToolRecoveryTests(unittest.TestCase):
    def test_recoverable_tool_exception_returns_to_model(self):
        scripts = {"review":[
            observation({"name":"verify","call_id":"bad","arguments":{"malformed":True}}),
            observation({"name":"verify","call_id":"fixed","arguments":{"valid":True}}),
            observation(),
        ]}
        adapter = MockModelAdapter(scripts)
        request = AgentExecutionRequest(
            agent_run_id="recovery-run", task_id="review", agent_identity="reviewer-verifier-agent",
            task_goal="repair a malformed verifier request", allowed_tools=("verify",),
            expected_output_schema={},
        )
        seen = []
        def tool_runner(name, arguments, call_id):
            seen.append((call_id, arguments))
            if not arguments.get("valid"):
                raise KeyError("dataset_artifact")
            return {"status":"complete","artifacts":[],"errors":[]}
        result = AgentExecutor(adapter).execute(request, tool_runner)
        self.assertEqual(result["outcome"], "PASS")
        self.assertEqual([item[0] for item in seen], ["bad", "fixed"])
        self.assertEqual(result["tool_calls"][0]["status"], "failed")
        self.assertEqual(result["tool_calls"][1]["status"], "complete")

    def test_permission_error_is_not_model_recoverable(self):
        adapter = MockModelAdapter({"review":observation({"name":"verify","call_id":"denied","arguments":{}})})
        request = AgentExecutionRequest(agent_run_id="permission-run",task_id="review",
            agent_identity="reviewer-verifier-agent",task_goal="permission gate",allowed_tools=("verify",))
        with self.assertRaises(PermissionError):
            AgentExecutor(adapter).execute(request, lambda *_: (_ for _ in ()).throw(PermissionError("human gate")))


if __name__ == "__main__":
    unittest.main()
