"""Opt-in live smoke test; it may consume Codex usage and is not run in CI."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research_os.adapters import AgentExecutionRequest
from research_os.adapters.codex_cli import CodexCLIAdapter
from research_os.executor import AgentExecutor

adapter=CodexCLIAdapter(ROOT,ROOT/'work/v011-codex-live-smoke',sandbox='read-only')
request=AgentExecutionRequest(agent_run_id='stage04-live-smoke',task_id='adapter-smoke',agent_identity='reviewer-verifier-agent',task_goal='Return PASS with summary exactly: Codex CLI structured adapter smoke passed. Do not call tools or create artifacts.',allowed_skills=(),allowed_tools=(),working_context={'fixture':'public synthetic'},artifact_context=(),expected_output_schema={'$ref':'schemas/research-agent-observation.schema.json'},timeout_seconds=120,token_budget=300,data_sensitivity='synthetic',context_policy='artifact-only')
result=AgentExecutor(adapter,ROOT).execute(request)
receipt={'adapter':'codex-cli','version':'0.154.0-alpha.6.2','outcome':result['outcome'],'summary':result['summary'],'tool_calls':result['tool_calls'],'artifacts':result['artifacts'],'token_usage':result['token_usage'],'event_types':[event.get('type') for event in adapter.stream_events(request.agent_run_id)],'production_certified':False}
(ROOT/'tests/receipts/v011-stage04-codex-live-smoke.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(receipt,ensure_ascii=False))
