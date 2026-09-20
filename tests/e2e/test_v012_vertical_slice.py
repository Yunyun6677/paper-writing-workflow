from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_os.adapters.mock import MockModelAdapter
from research_os.vertical_slice import run_vertical_slice


def obs(summary: str, request: dict | None = None) -> dict:
    return {"outcome":"PASS","summary":summary,"artifacts":[],"tool_calls":[],
            "tool_requests":[request] if request else [],"errors":[],"next_tasks":[]}


class V012VerticalSliceTests(unittest.TestCase):
    def test_model_tool_loop_recovers_and_produces_verified_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            dataset = Path(tmp) / "public.csv"
            dataset.write_text("rownames,mpg,wt\na,3,1\nb,5,2\nc,7,3\nd,9,4\n", encoding="utf-8")
            dataset_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
            injected = "raise RuntimeError('INJECTED_V012_ERROR: repair the analysis implementation')\n"
            injected_hash = hashlib.sha256(injected.encode()).hexdigest()
            repaired = (
                "import csv,hashlib,json,pathlib,sys\n"
                "data=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2])\n"
                "rows=list(csv.DictReader(data.open(encoding='utf-8-sig')))\n"
                "x=[float(r['wt']) for r in rows];y=[float(r['mpg']) for r in rows]\n"
                "xm=sum(x)/len(x);ym=sum(y)/len(y);b=sum((a-xm)*(c-ym) for a,c in zip(x,y))/sum((a-xm)**2 for a in x);a=ym-b*xm\n"
                "payload={'schema_version':'v012-ols-result/1.0','model_id':'mtcars-mpg-on-wt','n':len(rows),'intercept':a,'coefficient':b,'dataset_sha256':hashlib.sha256(data.read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}\n"
                "out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload),encoding='utf-8')\n"
            )
            repaired_hash = hashlib.sha256(repaired.encode()).hexdigest()
            verify_request = {"dataset_artifact":"data/mtcars.csv","dataset_sha256":dataset_hash,
                "code_artifact":"analysis/repaired_analysis.py","result_artifact":"analysis/repaired-run/result.json",
                "execution_receipt":"analysis/repaired-run/receipt.json",
                "expected":{"n":4,"coefficient":2.0,"tolerance":1e-9,"report_value":"2.000000"}}
            responses = {
                "v012-analysis":[
                    obs("run injected failure", {"name":"python","call_id":"fail","arguments":{
                        "script":"analysis/injected_error.py","script_sha256":injected_hash,
                        "output_directory":"analysis/failed-run","idempotency_key":"v012-failure-001",
                        "arguments":["data/mtcars.csv","analysis/failed-run/never.json"],
                        "input_artifacts":["data/mtcars.csv"],"observation_mode":"error-tail",
                        "required_outputs":["analysis/failed-run/never.json"]}}),
                    obs("write repair", {"name":"artifact_write","call_id":"repair","arguments":{
                        "path":"analysis/repaired_analysis.py","content":repaired,"idempotency_key":"v012-repair-001"}}),
                    obs("execute repair", {"name":"python","call_id":"rerun","arguments":{
                        "script":"analysis/repaired_analysis.py","script_sha256":repaired_hash,
                        "output_directory":"analysis/repaired-run","idempotency_key":"v012-rerun-001",
                        "arguments":["data/mtcars.csv","analysis/repaired-run/result.json"],
                        "input_artifacts":["data/mtcars.csv"],"required_outputs":["analysis/repaired-run/result.json"]}}),
                    obs("analysis repaired and executed"),
                ],
                "v012-analysis-review":[
                    obs("verify chain", {"name":"evidence_verify","call_id":"verify-analysis","arguments":{
                        "verifier_type":"analysis_chain","request":verify_request,"output":"audit/analysis-chain.json"}}),
                    obs("analysis chain passed"),
                ],
                "v012-writing":[
                    obs("write report", {"name":"artifact_write","call_id":"write-report","arguments":{
                        "path":"paper/report.tex","idempotency_key":"v012-report-001",
                        "content":"\\documentclass{article}\\begin{document}Public mtcars associational OLS benchmark. N=4; weight coefficient: 2.000000. This is not a causal estimate.\\end{document}\n"}}),
                    obs("report written"),
                ],
                "v012-report-review":[
                    obs("verify report", {"name":"evidence_verify","call_id":"verify-report","arguments":{
                        "verifier_type":"analysis_chain","request":{**verify_request,"report_artifact":"paper/report.tex"},"output":"audit/report-chain.json"}}),
                    obs("report chain passed"),
                ],
            }
            adapter = MockModelAdapter(responses)
            with patch("research_os.vertical_slice.MTCARS_SHA256", dataset_hash), \
                 patch("research_os.vertical_slice.EXPECTED_N", 4), \
                 patch("research_os.vertical_slice.EXPECTED_COEFFICIENT", 2.0), \
                 patch("research_os.vertical_slice.DISPLAY_COEFFICIENT", "2.000000"):
                receipt = run_vertical_slice(root, adapter=adapter, dataset_source=dataset)
            self.assertEqual(receipt["status"], "pass", receipt)
            self.assertTrue(receipt["injected_failure_observed"])
            self.assertTrue(receipt["autonomous_repair_observed"])
            self.assertTrue(receipt["provenance_trace"]["reaches_raw_dataset"])


if __name__ == "__main__":
    unittest.main()
