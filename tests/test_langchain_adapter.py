"""Optional LangChain harness tests use only synthetic data and scripted models."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from research_os.adapters.base import AgentExecutionRequest
from research_os.executor import AgentExecutor
from research_os.planner import task
from research_os.runtime import ResearchRuntime
from research_os.tools import default_registry
from research_os.adapters.langchain import LangChainSpecialistAdapter
from research_os.adapters.langchain.tool_bridge import ToolBridge


ROOT = Path(__file__).resolve().parents[1]
HAS_LANGCHAIN = importlib.util.find_spec("langchain") is not None


class CoreWithoutLangChainTests(unittest.TestCase):
    def test_core_runtime_import_does_not_require_langchain(self):
        code = (
            "import builtins\n"
            "original = builtins.__import__\n"
            "def blocked(name, *args, **kwargs):\n"
            "    if name == 'langchain' or name.startswith('langchain.') or name.startswith('langchain_core'):\n"
            "        raise ImportError('LangChain intentionally absent')\n"
            "    return original(name, *args, **kwargs)\n"
            "builtins.__import__ = blocked\n"
            "import research_os.runtime\n"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


def assignment(*, tools: tuple[str, ...] = ("artifact_write",), run_id: str = "lc-run") -> AgentExecutionRequest:
    registry = default_registry()
    return AgentExecutionRequest(
        agent_run_id=run_id, task_id="literature", agent_identity="literature-agent",
        task_goal="Inspect synthetic artifacts", allowed_skills=("social-science-literature-review",),
        allowed_tools=tools, tool_specs=tuple(registry.describe(name) for name in tools if name in
            {item["name"] for item in registry.manifests()}),
        data_sensitivity="synthetic", timeout_seconds=30,
    )


class FakeHarness:
    def __init__(self, tools, response_format, *, use_tool=False, malformed=False,
                 raise_model=False, hallucinate_tool=False, forged_artifact=False):
        self.tools = tools
        self.response_format = response_format
        self.use_tool = use_tool
        self.malformed = malformed
        self.raise_model = raise_model
        self.hallucinate_tool = hallucinate_tool
        self.forged_artifact = forged_artifact

    def invoke(self, inputs, *, config):
        if self.raise_model:
            raise RuntimeError("injected model failure")
        if self.malformed:
            return {"structured_response": {"outcome": "PASS", "summary": 3}}
        if self.use_tool:
            output = json.loads(self.tools[0].invoke({
                "path": "literature/fixture.json", "content": "{}", "idempotency_key": "test-write-001"}))
            # A mistaken model PASS must not override an observed tool failure.
            outcome = "PASS"
        else:
            outcome = "PASS"
        messages = []
        if self.hallucinate_tool:
            from langchain_core.messages import AIMessage
            messages = [AIMessage(content="", tool_calls=[
                {"name": "unassigned_tool", "args": {}, "id": "forbidden-1"}])]
        artifacts = ([{"path": "literature/forged.json", "sha256": "0" * 64}]
                     if self.forged_artifact else [])
        return {"structured_response": self.response_format(
                    outcome=outcome, summary="synthetic only", artifacts=artifacts),
                "messages": messages}


@unittest.skipUnless(HAS_LANGCHAIN, "optional LangChain test dependency is absent")
class LangChainAdapterTests(unittest.TestCase):
    def adapter(self, *, use_tool=False, malformed=False, raise_model=False,
                hallucinate_tool=False, forged_artifact=False):
        def factory(**kwargs):
            self.assertIsNone(kwargs["checkpointer"])
            self.assertIsNone(kwargs["store"])
            return FakeHarness(kwargs["tools"], kwargs["response_format"],
                               use_tool=use_tool, malformed=malformed,
                               raise_model=raise_model, hallucinate_tool=hallucinate_tool,
                               forged_artifact=forged_artifact)
        return LangChainSpecialistAdapter(model_id="test:scripted", repository_root=ROOT,
                                          model=object(), create_agent_fn=factory)

    def test_unknown_and_disallowed_tools_are_rejected_before_binding(self):
        with self.assertRaisesRegex(KeyError, "Unknown tool"):
            ToolBridge(assignment(tools=("never_registered",)), lambda *_: {}, ROOT).langchain_tools()
        bridge = ToolBridge(assignment(), lambda *_: {"status": "complete"}, ROOT)
        with self.assertRaisesRegex(PermissionError, "outside task allow-list"):
            bridge.invoke("python", {"script": "x.py"})
        self.assertEqual([tool.name for tool in bridge.langchain_tools()], ["artifact_write"])
        with self.assertRaisesRegex(PermissionError, "outside its assignment"):
            AgentExecutor(self.adapter(hallucinate_tool=True)).execute(
                assignment(), lambda *_: {"status": "complete"})

    def test_all_four_specialists_resolve_skill_source_without_policy_copy(self):
        adapter = self.adapter()
        cases = (
            ("literature-agent", "social-science-literature-review"),
            ("empirical-agent", "economics-empirical-analysis"),
            ("writing-agent", "economics-paper-workflow:writing"),
            ("reviewer-verifier-agent", "economics-paper-workflow:audit"),
        )
        for identity, capability in cases:
            request = replace(assignment(tools=()), agent_identity=identity,
                              allowed_skills=(capability,))
            instructions = adapter._instructions(request)
            self.assertIn(f"SOURCE SOP {capability}", instructions)
            self.assertIn("#", instructions)
        invalid = replace(assignment(tools=()), agent_identity="writing-agent",
                          allowed_skills=("economics-paper-workflow:audit",))
        with self.assertRaisesRegex(PermissionError, "outside the specialist role"):
            adapter._instructions(invalid)

    def test_malformed_observation_and_model_failure_cannot_complete(self):
        with self.assertRaises(Exception):
            AgentExecutor(self.adapter(malformed=True)).execute(assignment(), lambda *_: {"status": "complete"})
        with self.assertRaisesRegex(RuntimeError, "injected model failure"):
            AgentExecutor(self.adapter(raise_model=True)).execute(assignment(), lambda *_: {"status": "complete"})

    def test_tool_failure_is_explicit_and_never_becomes_pass(self):
        adapter = self.adapter(use_tool=True)
        result = AgentExecutor(adapter).execute(assignment(),
            lambda *_: (_ for _ in ()).throw(RuntimeError("injected tool failure")))
        self.assertEqual(result["outcome"], "FAIL_TRANSIENT")
        self.assertEqual(result["tool_calls"][0]["status"], "failed")
        self.assertEqual(result["provider"], "langchain")

    def test_model_cannot_invent_artifact_receipt(self):
        with self.assertRaisesRegex(ValueError, "not produced by a bound tool"):
            AgentExecutor(self.adapter(forged_artifact=True)).execute(
                assignment(), lambda *_: {"status": "complete"})

    def test_tool_needs_human_becomes_explicit_handoff(self):
        result = AgentExecutor(self.adapter(use_tool=True)).execute(
            assignment(), lambda *_: {"status": "needs-human", "artifacts": []})
        self.assertEqual(result["outcome"], "BLOCKED")
        self.assertEqual(result["tool_calls"][0]["status"], "needs-human")
        self.assertIn("researcher action", result["human_action"])

    def test_runtime_registers_only_real_tool_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "economics-paper-project/1.0", "project_id": "langchain-runtime",
                "title_working": "Runtime integration", "paper_type": "review", "stage": "idea",
                "research_question": "Can a LangChain agent produce a verified artifact?",
                "target_journals": [{"name": "undecided", "family": "undecided"}],
                "contribution_claims": [], "data_sensitivity": "synthetic",
                "approvals": {"question_and_contribution": False, "research_design": False,
                              "outline_and_journal": False}, "output_format": "latex",
            }), encoding="utf-8")
            store = ResearchRuntime.initialize(manifest, root / "runs")
            state = store.load()
            state["task_graph"] = [task("literature", "Write synthetic evidence", "agent",
                                        "literature-agent", [],
                                        expected_outputs=["literature/fixture.json"],
                                        allowed_tools=["artifact_write"])]
            store.save(state, "test.graph", {})
            adapter = self.adapter(use_tool=True)
            result = ResearchRuntime(store, project,
                agent_executors={"literature-agent": AgentExecutor(adapter)}).run(max_steps=1)
            self.assertEqual(result["task_graph"][0]["status"], "complete")
            self.assertEqual((project / "literature" / "fixture.json").read_text(encoding="utf-8"), "{}")
            self.assertEqual(result["tool_runs"][0]["name"], "artifact_write")
            self.assertTrue(any(a["path"] == "literature/fixture.json" for a in result["artifacts"]))

    def test_runtime_model_failure_does_not_complete_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "economics-paper-project/1.0", "project_id": "langchain-model-fail",
                "title_working": "Failure test", "paper_type": "review", "stage": "idea",
                "research_question": "Can a failed provider falsely complete?",
                "target_journals": [{"name": "undecided", "family": "undecided"}],
                "contribution_claims": [], "data_sensitivity": "synthetic",
                "approvals": {"question_and_contribution": False, "research_design": False,
                              "outline_and_journal": False}, "output_format": "latex",
            }), encoding="utf-8")
            store = ResearchRuntime.initialize(manifest, root / "runs")
            state = store.load()
            state["task_graph"] = [task("literature", "Inspect synthetic literature", "agent",
                                        "literature-agent", [], allowed_tools=["artifact_write"])]
            store.save(state, "test.graph", {})
            runtime = ResearchRuntime(store, root,
                agent_executors={"literature-agent": AgentExecutor(self.adapter(raise_model=True))})
            result = runtime.run(max_steps=1)
            self.assertNotEqual(result["task_graph"][0]["status"], "complete")
            self.assertNotIn("literature", result["completed_tasks"])

    def test_provider_session_loss_leaves_canonical_state_and_resume_works(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "economics-paper-project/1.0", "project_id": "langchain-session",
                "title_working": "Session test", "paper_type": "review", "stage": "idea",
                "research_question": "Can the provider session disappear safely?",
                "target_journals": [{"name": "undecided", "family": "undecided"}],
                "contribution_claims": [], "data_sensitivity": "synthetic",
                "approvals": {"question_and_contribution": False, "research_design": False,
                              "outline_and_journal": False}, "output_format": "latex",
            }), encoding="utf-8")
            store = ResearchRuntime.initialize(manifest, root / "runs")
            state_before = store.load()
            adapter = self.adapter()
            executor = AgentExecutor(adapter)
            request = assignment()
            executor.execute(request, lambda *_: {"status": "complete"})
            adapter._requests.clear()
            adapter._events.clear()
            self.assertEqual(store.load(), state_before)
            resumed = executor.resume(request, {"instruction": "reconstruct from canonical assignment"},
                                      lambda *_: {"status": "complete"})
            self.assertEqual(resumed["outcome"], "PASS")
            self.assertEqual(store.load(), state_before)

    def test_adapter_disabled_preserves_existing_waiting_agent_behavior(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "economics-paper-project/1.0", "project_id": "langchain-disabled",
                "title_working": "Disabled adapter", "paper_type": "review", "stage": "idea",
                "research_question": "Does the original manual path still wait?",
                "target_journals": [{"name": "undecided", "family": "undecided"}],
                "contribution_claims": [], "data_sensitivity": "synthetic",
                "approvals": {"question_and_contribution": False, "research_design": False,
                              "outline_and_journal": False}, "output_format": "latex",
            }), encoding="utf-8")
            store = ResearchRuntime.initialize(manifest, root / "runs")
            state = store.load()
            state["task_graph"] = [task("literature", "Inspect synthetic literature", "agent",
                                        "literature-agent", [])]
            store.save(state, "test.graph", {})
            result = ResearchRuntime(store, root, agent_executors={}).run(max_steps=1)
            self.assertEqual(result["task_graph"][0]["status"], "waiting-agent")
            self.assertNotIn("literature", result["completed_tasks"])

    def test_real_create_agent_runs_a_scripted_tool_loop(self):
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        class ScriptedChatModel(BaseChatModel):
            calls: int = 0

            @property
            def _llm_type(self):
                return "research-os-scripted"

            def bind_tools(self, tools, **kwargs):
                return self

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    message = AIMessage(content="", tool_calls=[{
                        "name": "artifact_write", "args": {"path": "literature/fixture.json",
                            "content": "{}", "idempotency_key": "test-write-001"}, "id": "call-test-1"}])
                else:
                    message = AIMessage(content="", tool_calls=[{
                        "name": "StructuredObservation",
                        "args": {"outcome": "PASS", "summary": "verified tool loop", "artifacts": [],
                                 "tool_calls": [], "errors": [], "next_tasks": [], "replacement_tasks": []},
                        "id": "call-test-2"}])
                return ChatResult(generations=[ChatGeneration(message=message)])

        model = ScriptedChatModel()
        adapter = LangChainSpecialistAdapter(model_id="test:scripted", repository_root=ROOT, model=model)
        result = AgentExecutor(adapter).execute(assignment(),
            lambda name, args, call_id: {"status": "complete", "artifacts": [], "errors": []})
        self.assertEqual(result["outcome"], "PASS")
        self.assertEqual(result["tool_calls"][0]["name"], "artifact_write")
        self.assertEqual(model.calls, 2)


if __name__ == "__main__":
    unittest.main()
