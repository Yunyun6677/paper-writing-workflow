from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from research_os.adapters import AgentExecutionRequest
from research_os.adapters.codex_cli import CodexCLIAdapter
from research_os.executor import AgentExecutor

class FakeProcess:
    returncode=0
    def __init__(self,command,**kwargs):
        Path(command[command.index("--output-last-message")+1]).write_text(json.dumps({"outcome":"PASS","summary":"real-cli-shape","artifacts":[],"tool_calls":[],"errors":[],"next_tasks":[]}),encoding="utf8")
    def communicate(self,timeout=None):return ('{"type":"thread.started","thread_id":"abc"}\n{"type":"turn.completed","usage":{"input_tokens":4,"output_tokens":2,"total_tokens":6}}\n','')
    def kill(self):pass
    def poll(self):return self.returncode

class CodexCLIAdapterTests(unittest.TestCase):
    def test_command_adapter_parses_structured_output_and_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();exe=root/'codex.exe';exe.write_bytes(b'MZ')
            adapter=CodexCLIAdapter(work,root/'runs',executable=exe)
            req=AgentExecutionRequest(agent_run_id='run-1',task_id='frame',agent_identity='research-director',task_goal='Bounded synthetic frame',data_sensitivity='synthetic',timeout_seconds=5)
            with patch('research_os.adapters.codex_cli.subprocess.Popen',FakeProcess):result=AgentExecutor(adapter).execute(req)
            self.assertEqual(result['outcome'],'PASS');self.assertEqual(result['token_usage']['total_tokens'],6)
            self.assertTrue((root/'runs/run-1/request.json').is_file())
            self.assertEqual([e['type'] for e in adapter.stream_events('run-1')],['thread.started','turn.completed'])
    def test_unknown_ephemeral_session_refuses_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();exe=root/'codex.exe';exe.write_bytes(b'MZ')
            with self.assertRaises(KeyError):CodexCLIAdapter(work,root/'runs',executable=exe).resume_agent('run-1')

    def test_ephemeral_adapter_supports_audited_stateless_continuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();exe=root/'codex.exe';exe.write_bytes(b'MZ')
            adapter=CodexCLIAdapter(work,root/'runs',executable=exe)
            req=AgentExecutionRequest(agent_run_id='run-2',task_id='frame',agent_identity='research-director',task_goal='continue',data_sensitivity='synthetic',timeout_seconds=5)
            with patch('research_os.adapters.codex_cli.subprocess.Popen',FakeProcess):
                adapter.run_agent(req);adapter.resume_agent('run-2',{'tool_results':[]})
            self.assertTrue((root/'runs/run-2/round-001/events.jsonl').is_file())
            self.assertTrue((root/'runs/run-2/round-002/events.jsonl').is_file())
if __name__=='__main__':unittest.main()
