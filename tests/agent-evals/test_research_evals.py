from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research_os.evals import evaluate_agent, evaluate_empirical, evaluate_literature, evaluate_paper, evaluate_suite
from research_os.providers import OpenAICompatibleAdapter, ProviderRegistry, ProviderRequest


class ResearchEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "tests/agent-evals/fixtures/synthetic-research-suite.json").read_text(encoding="utf-8"))

    def test_literature_eval(self):
        report = evaluate_literature(self.fixture["literature"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["metrics"]["duplicate_rate"], 0)

    def test_empirical_eval(self):
        report = evaluate_empirical(self.fixture["empirical"])
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["metrics"]["dataset_preservation"])

    def test_agent_eval_detects_false_completion_and_loop(self):
        broken = dict(self.fixture["agent"])
        broken["completion_claims"] = [{"claimed_complete": True, "artifacts_verified": False}]
        broken["steps"] = 11
        report = evaluate_agent(broken)
        self.assertEqual(report["status"], "fail")
        self.assertGreater(report["metrics"]["hallucinated_completion"], 0)
        self.assertFalse(report["metrics"]["infinite_loop_prevention"])

    def test_paper_eval(self):
        self.assertEqual(evaluate_paper(self.fixture["paper"])["status"], "pass")

    def test_complete_suite(self):
        report = evaluate_suite(self.fixture)
        self.assertEqual(report["status"], "pass")
        self.assertEqual({x["category"] for x in report["reports"]}, {"literature", "empirical", "agent", "paper"})

    def test_public_replication_summary(self):
        policy = json.loads((ROOT / "tests/agent-evals/fixtures/public-replication-adh2013.json").read_text(encoding="utf-8"))
        bundle = json.loads((ROOT / policy["source"]).read_text(encoding="utf-8"))
        verification = bundle["verification"]
        self.assertEqual(verification["status"], policy["required_status"])
        self.assertLessEqual(verification["python_stata_max_abs_coefficient_delta"], policy["max_coefficient_delta"])
        self.assertLessEqual(verification["python_stata_max_abs_standard_error_delta"], policy["max_standard_error_delta"])
        self.assertFalse(bundle["scope"]["full_paper_replication_claimed"])

    def test_provider_registry_and_injected_openai_compatible_transport(self):
        registry = ProviderRegistry(ROOT)
        adapter = OpenAICompatibleAdapter("openai-compatible", lambda payload: {
            "outcome": "PASS", "model": payload["model"], "summary": "synthetic",
            "token_usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
        })
        registry.register(adapter)
        observation = registry.get("openai-compatible").execute(ProviderRequest(
            agent="literature-agent", model="synthetic-model", instructions="fixture only",
            input_artifacts=[{"artifact_id": "fixture", "sha256": "a" * 64}],
            data_sensitivity="synthetic",
        ))
        self.assertEqual(observation.outcome, "PASS")
        self.assertEqual(observation.token_usage["total_tokens"], 3)
        with self.assertRaises(PermissionError):
            adapter.execute(ProviderRequest(agent="empirical-agent", model="synthetic-model", instructions="restricted fixture"))


if __name__ == "__main__":
    unittest.main()
