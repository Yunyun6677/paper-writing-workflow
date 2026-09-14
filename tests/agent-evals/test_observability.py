from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research_os.observability import CallbackExporter, TracePolicy, TraceRecorder, to_opentelemetry_attributes


class ObservabilityTests(unittest.TestCase):
    def state(self, sensitivity="synthetic"):
        return {"run_id": "00000000-0000-4000-8000-000000000001", "project_id": "synthetic-eval", "data_sensitivity": sensitivity}

    def test_local_trace_contains_metadata_not_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = TraceRecorder(tmp, ROOT)
            span = recorder.record(state=self.state(), name="agent.observation", kind="agent", started_at="2026-09-10T00:00:00+00:00", status="ok", agent="literature-agent", model="test-model", provider="mock", agent_run_id="agent-run-1", outcome="PASS", token_usage={"input_tokens":2,"output_tokens":1,"total_tokens":3,"cost_usd":0.01}, inputs={"secret_text": "must-not-appear", "artifact_id": "a1", "path": "evidence/a.json", "sha256": "a" * 64})
            content = (Path(tmp) / "traces.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("must-not-appear", content)
            self.assertIn("evidence/a.json", content)
            attributes = to_opentelemetry_attributes(span)
            self.assertEqual(attributes["research.agent_run_id"], "agent-run-1")
            self.assertEqual(attributes["gen_ai.provider.name"], "mock")
            self.assertEqual(attributes["gen_ai.usage.cost"], 0.01)

    def test_sensitive_trace_not_exported_without_explicit_approval(self):
        exported = []
        with tempfile.TemporaryDirectory() as tmp:
            policy = TracePolicy(external_export_enabled=True, allow_sensitive_external_export=False)
            recorder = TraceRecorder(tmp, ROOT, policy, [CallbackExporter("test", exported.append)])
            recorder.record(state=self.state("restricted"), name="tool.execute", kind="tool", started_at="2026-09-10T00:00:00+00:00", status="error", errors=[{"type": "Error", "message": "private row content"}])
            self.assertEqual(exported, [])
            span = json.loads((Path(tmp) / "traces.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(span["errors"][0]["message"], "[redacted]")


if __name__ == "__main__":
    unittest.main()
