"""v0.12 public-data vertical slice: real model, recovery, verification and report."""
from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .adapters.base import ModelAdapter
from .executor import AgentExecutor
from .planner import task
from .provenance import ProvenanceGraph, verify_analysis_chain
from .runtime import ResearchRuntime
from .store import atomic_json, sha256_file, utc_now


MTCARS_URL = "https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/csv/datasets/mtcars.csv"
MTCARS_SHA256 = "4d6dfa9b029dbcc15333a6e3598803fae8ae7c4d08605040b1706e6367695058"
EXPECTED_N = 32
EXPECTED_COEFFICIENT = -5.344471572722677
DISPLAY_COEFFICIENT = "-5.344472"


def prepare_project(project: Path, dataset_source: Path | None = None) -> Path:
    if project.exists():
        raise FileExistsError(project)
    (project / "data").mkdir(parents=True)
    (project / "analysis").mkdir()
    dataset = project / "data" / "mtcars.csv"
    if dataset_source is not None:
        shutil.copyfile(dataset_source, dataset)
    else:
        with urllib.request.urlopen(MTCARS_URL, timeout=60) as response:
            dataset.write_bytes(response.read())
    if sha256_file(dataset) != MTCARS_SHA256:
        raise ValueError("Public mtcars dataset hash does not match the predeclared fixture")
    (project / "analysis" / "injected_error.py").write_bytes(
        b"raise RuntimeError('INJECTED_V012_ERROR: repair the analysis implementation')\n"
    )
    manifest = {
        "schema_version":"economics-paper-project/1.0", "project_id":"v012-public-vertical-slice",
        "title_working":"Public mtcars autonomous recovery vertical slice", "paper_type":"empirical",
        "stage":"analysis", "research_question":"What is the OLS association between vehicle weight and fuel economy in the public mtcars dataset?",
        "target_journals":[{"name":"benchmark-only","family":"undecided"}], "contribution_claims":[],
        "research_design": {
            "unit_of_analysis":"vehicle model", "treatment_or_exposure":"vehicle weight (1000 lbs)",
            "outcomes":["miles per gallon"], "estimand":"OLS slope of mpg on wt",
            "identification_strategy":"descriptive associational OLS benchmark; no causal identification",
            "assumptions":["finite numeric observations", "nonzero variance in vehicle weight"],
            "threats":["omitted vehicle characteristics", "small historical sample"],
            "inference_plan":"point-estimate verification only; no causal inference claim"
        },
        "data_sensitivity":"public", "approvals":{"question_and_contribution":True,"research_design":True,"outline_and_journal":False},
        "output_format":"latex",
    }
    atomic_json(project / "manifest.json", manifest)
    atomic_json(project / "data" / "source.json", {
        "schema_version":"public-dataset-source/1.0", "url":MTCARS_URL,
        "sha256":MTCARS_SHA256, "rows":EXPECTED_N, "dataset":"R datasets::mtcars",
        "retrieved_at":utc_now(), "redistribution":"raw bytes remain outside Git",
    })
    return project / "manifest.json"


def vertical_graph(project: Path) -> list[dict[str, Any]]:
    injected_hash = sha256_file(project / "analysis" / "injected_error.py")
    expected = {"n": EXPECTED_N, "coefficient": EXPECTED_COEFFICIENT,
                "tolerance": 1e-9, "report_value": DISPLAY_COEFFICIENT}
    analysis_goal = f"""Execute a bounded public-data OLS analysis and recover autonomously from an injected failure.
Mandatory sequence: (1) first call python on analysis/injected_error.py with hash {injected_hash}, output_directory analysis/failed-run, input_artifacts [data/mtcars.csv], observation_mode error-tail, and required_outputs [analysis/failed-run/never.json]; (2) inspect the returned failed command observation; (3) use artifact_write to create analysis/repaired_analysis.py; (4) execute that new hash-approved script with python, input data/mtcars.csv, output analysis/repaired-run/result.json, output_directory analysis/repaired-run, and input_artifacts [data/mtcars.csv].
The repaired script must use only the Python standard library, read columns mpg and wt, calculate OLS mpg = intercept + coefficient*wt, and write JSON with schema_version='v012-ols-result/1.0', model_id='mtcars-mpg-on-wt', n, intercept, coefficient, dataset_sha256, code_sha256. It must hash its own source and the dataset. Do not invent a result and do not return PASS before the successful Python receipt exists."""
    review_request = {
        "dataset_artifact":"data/mtcars.csv", "dataset_sha256":MTCARS_SHA256,
        "code_artifact":"analysis/repaired_analysis.py",
        "result_artifact":"analysis/repaired-run/result.json",
        "execution_receipt":"analysis/repaired-run/receipt.json", "expected":expected,
    }
    return [
        task("v012-analysis", analysis_goal, "agent", "empirical-agent", [],
             expected_outputs=["analysis/repaired_analysis.py", "analysis/repaired-run/result.json", "analysis/repaired-run/receipt.json"],
             allowed_tools=["artifact_write", "python"], max_attempts=1, timeout_seconds=900,
             success_contract=["one injected Python failure is observed", "repaired code executes", "hashed result and receipt exist"],
             verification_rules=["public input hash", "autonomous repair", "numeric lineage"]),
        task("v012-analysis-review", "Independently verify the complete analysis chain. Use metadata.verification_inputs.verification_request exactly as the evidence_verify request, set verifier_type analysis_chain and output audit/analysis-chain.json. Return PASS only if the deterministic tool passes. If a tool request is rejected, correct the arguments within the bounded tool loop.",
             "verifier", "reviewer-verifier-agent", ["v012-analysis"],
             required_inputs={"producer_task_id":"v012-analysis", "verification_request":review_request},
             expected_outputs=["audit/analysis-chain.json"], allowed_tools=["evidence_verify"], max_attempts=1,
             success_contract=["deterministic analysis-chain receipt passes"]),
        task("v012-writing", f"Write paper/report.tex using artifact_write. It must be valid UTF-8 LaTeX source, state this is an associational OLS benchmark rather than a causal estimate, report N={EXPECTED_N} and the verified weight coefficient exactly as {DISPLAY_COEFFICIENT}, and name the public mtcars source. Use only approved artifacts and do not add citations.",
             "agent", "writing-agent", ["v012-analysis-review"], expected_outputs=["paper/report.tex"],
             allowed_tools=["artifact_write"], max_attempts=1,
             success_contract=["report uses verified values", "causal language is absent"]),
        task("v012-report-review", "Independently verify the dataset-code-run-result-report chain. Copy metadata.verification_inputs.verification_request exactly, add report_artifact paper/report.tex, call evidence_verify with verifier_type analysis_chain and output audit/report-chain.json. Return PASS only if the deterministic receipt passes. If a tool request is rejected, correct it within the bounded tool loop.",
             "verifier", "reviewer-verifier-agent", ["v012-writing"],
             required_inputs={"producer_task_id":"v012-writing", "verification_request":review_request},
             expected_outputs=["audit/report-chain.json"], allowed_tools=["evidence_verify"], max_attempts=1,
             success_contract=["report value traces to verified model result"]),
        task("final-audit", "Run the final artifact lineage firewall", "final_audit", "reviewer-verifier-agent",
             ["v012-report-review"], tool_name="research_firewall", allowed_tools=["research_firewall"],
             required_inputs={"output":"audit/final-runtime-audit.json"},
             expected_outputs=["audit/final-runtime-audit.json"], success_contract=["all registered artifact domains exist"]),
    ]


def run_vertical_slice(root: Path, adapter: ModelAdapter | None = None,
                       dataset_source: Path | None = None,
                       adapter_factory: Callable[[Path, Path], ModelAdapter] | None = None) -> dict[str, Any]:
    project = root / "project"
    manifest = prepare_project(project, dataset_source)
    if adapter is None:
        if adapter_factory is None:
            raise ValueError("adapter or adapter_factory is required")
        adapter = adapter_factory(project, root / "adapter")
    store = ResearchRuntime.initialize(manifest, root / "runs", state_backend="sqlite")
    state = store.load(); state["task_graph"] = vertical_graph(project); state["completed_tasks"] = []
    dataset_ref = {"path":"data/mtcars.csv", "sha256":MTCARS_SHA256, "artifact_id":"public-input:dataset"}
    source_ref = {"path":"data/source.json", "sha256":sha256_file(project / "data" / "source.json"), "artifact_id":"public-input:source"}
    state["artifacts"].extend([{**dataset_ref,"schema_ref":"public-dataset/1.0","external":True},
                               {**source_ref,"schema_ref":"public-dataset-source/1.0","external":True}])
    state["evidence_registry"]["artifact_refs"].extend([dataset_ref, source_ref])
    store.save(state, "v012.vertical-slice-prepared", {"dataset_sha256":MTCARS_SHA256})
    executor = AgentExecutor(adapter)
    runtime = ResearchRuntime(store, project, agent_executors={
        "empirical-agent":executor, "writing-agent":executor, "reviewer-verifier-agent":executor,
    })
    result_state = runtime.run(max_steps=20)
    if result_state.get("lifecycle_status") != "complete":
        blocked = {
            "schema_version":"v012-vertical-slice-receipt/1.0", "created_at":utc_now(),
            "status":"blocked", "runtime_status":result_state.get("lifecycle_status"),
            "task_statuses":{item["task_id"]:item["status"] for item in result_state["task_graph"]},
            "errors":result_state.get("errors", []), "tool_runs":result_state.get("tool_runs", []),
            "injected_failure_observed":any(run.get("name") == "python" and run.get("outcome") == "failed" for run in result_state.get("tool_runs", [])),
            "autonomous_repair_observed":any(run.get("name") == "python" and run.get("outcome") == "complete" for run in result_state.get("tool_runs", [])),
            "production_certified":False,
        }
        atomic_json(root / "receipt.json", blocked)
        return blocked
    final_request = {
        "dataset_artifact":"data/mtcars.csv", "dataset_sha256":MTCARS_SHA256,
        "code_artifact":"analysis/repaired_analysis.py",
        "result_artifact":"analysis/repaired-run/result.json",
        "execution_receipt":"analysis/repaired-run/receipt.json",
        "report_artifact":"paper/report.tex",
        "expected":{"n":EXPECTED_N,"coefficient":EXPECTED_COEFFICIENT,"tolerance":1e-9,"report_value":DISPLAY_COEFFICIENT},
    }
    chain = verify_analysis_chain(project, final_request)
    graph = ProvenanceGraph("v012-public-vertical-slice")
    graph.add_file_node("dataset:mtcars", "RawDataset", project / "data/mtcars.csv", project, source_url=MTCARS_URL)
    graph.add_file_node("code:repaired", "Code", project / "analysis/repaired_analysis.py", project)
    graph.add_file_node("run:python", "ModelRun", project / "analysis/repaired-run/receipt.json", project)
    graph.add_file_node("result:ols", "TableFigure", project / "analysis/repaired-run/result.json", project)
    graph.add_value_node("estimate:wt", "Estimate", coefficient=EXPECTED_COEFFICIENT, n=EXPECTED_N)
    graph.add_file_node("claim:report", "ManuscriptClaim", project / "paper/report.tex", project, displayed_value=DISPLAY_COEFFICIENT)
    graph.relate("claim:report", "reported_from", "estimate:wt")
    graph.relate("estimate:wt", "stored_in", "result:ols")
    graph.relate("result:ols", "generated_by", "run:python")
    graph.relate("run:python", "executed_code", "code:repaired")
    graph.relate("run:python", "used_dataset", "dataset:mtcars")
    provenance_path = project / "audit" / "provenance-chain.json"
    graph.write(provenance_path, Path(__file__).resolve().parents[1] / "schemas" / "provenance-chain.schema.json")
    tool_runs = result_state.get("tool_runs", [])
    python_outcomes = [run.get("outcome") for run in tool_runs if run.get("name") == "python"]
    receipt = {
        "schema_version":"v012-vertical-slice-receipt/1.0", "created_at":utc_now(),
        "status":"pass" if result_state.get("lifecycle_status") == "complete" and chain["status"] == "pass" and python_outcomes[:1] == ["failed"] and "complete" in python_outcomes[1:] else "blocked",
        "runtime_status":result_state.get("lifecycle_status"), "task_statuses":{item["task_id"]:item["status"] for item in result_state["task_graph"]},
        "dataset":{"url":MTCARS_URL,"sha256":MTCARS_SHA256,"n":EXPECTED_N},
        "injected_failure_observed":python_outcomes[:1] == ["failed"], "autonomous_repair_observed":"complete" in python_outcomes[1:],
        "python_tool_outcomes":python_outcomes, "analysis_chain":chain,
        "provenance_trace":graph.trace("claim:report"),
        "sandbox":json.loads((project / "analysis/repaired-run/receipt.json").read_text(encoding="utf-8")).get("isolation"),
        "model_runs":[{key:item.get(key) for key in ("agent_run_id","task_id","agent","model","status")} for item in result_state.get("agent_runs", [])],
        "limitations":["LocalRestrictedBackend is not an OS-level network/filesystem security boundary.", "LaTeX source was verified but not compiled because no local TeX engine is available."],
        "production_certified":False,
    }
    atomic_json(root / "receipt.json", receipt)
    return receipt
