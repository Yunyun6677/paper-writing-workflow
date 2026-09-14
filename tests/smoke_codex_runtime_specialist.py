"""Optional live smoke: Runtime -> Codex -> tool broker -> verified artifact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1].resolve()
sys.path.insert(0, str(ROOT))

from research_os.adapters.codex_cli import CodexCLIAdapter
from research_os.executor import AgentExecutor
from research_os.planner import task
from research_os.runtime import ResearchRuntime
from research_os.store import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--run", required=True); args = parser.parse_args()
    root = (ROOT / args.run).resolve()
    if root.exists(): raise FileExistsError(root)
    project = root / "project"; project.mkdir(parents=True)
    manifest = project / "manifest.json"
    manifest.write_text(json.dumps({"schema_version":"economics-paper-project/1.0","project_id":"codex-specialist-smoke","title_working":"Live bounded specialist smoke","paper_type":"review","stage":"idea","research_question":"Can the live specialist request a bounded tool and return verified evidence?","target_journals":[{"name":"undecided","family":"undecided"}],"contribution_claims":[],"data_sensitivity":"synthetic","approvals":{"question_and_contribution":False,"research_design":False,"outline_and_journal":False},"output_format":"latex"}), encoding="utf-8")
    store = ResearchRuntime.initialize(manifest, root / "runs"); state = store.load()
    state["task_graph"] = [task("frame", "Use artifact_write to create design/codex-live-smoke.json containing a JSON object with keys status='verified' and synthetic=true. Do not claim completion until the tool result is returned.", "agent", "research-director", [], expected_outputs=["design/codex-live-smoke.json"], allowed_tools=["artifact_write"], max_attempts=1)]
    store.save(state, "smoke.graph", {})
    adapter = CodexCLIAdapter(project, root / "adapter", sandbox="read-only", persist_sessions=False)
    runtime = ResearchRuntime(store, project, agent_executors={"research-director": AgentExecutor(adapter)})
    result = runtime.run(max_steps=1); artifact = project / "design/codex-live-smoke.json"
    receipt = {"schema_version":"v0.11-stage-receipt/1.0","stage":7,"status":result["task_graph"][0]["status"],
               "artifact_exists":artifact.is_file(),"artifact":json.loads(artifact.read_text()) if artifact.is_file() else None,
               "artifact_sha256":sha256_file(artifact) if artifact.is_file() else None,
               "agent_runs":result["agent_runs"],"tool_runs":result["tool_runs"],"production_certified":False}
    receipt_dir = ROOT / "tests/receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    # Preserve every attempt. The stable filename is only a latest-result index.
    (receipt_dir / f"v011-stage07-codex-specialist-{root.name}.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (receipt_dir / "v011-stage07-codex-specialist-live.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"task_status":receipt["status"],"artifact_exists":receipt["artifact_exists"],"tool_runs":len(receipt["tool_runs"])}, indent=2))
    return 0 if receipt["status"] == "complete" and receipt["artifact_exists"] else 1


if __name__ == "__main__": raise SystemExit(main())
