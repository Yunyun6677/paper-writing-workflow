#!/usr/bin/env python3
"""Validate data structure and design prerequisites for advanced econometric methods.

This command never estimates an effect. It produces a guarded handoff to a
method-specific adapter and keeps capability status separate from data readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
REQUEST_SCHEMA = ROOT / "schemas" / "econometric-method-request.schema.json"
RESULT_SCHEMA = ROOT / "schemas" / "econometric-method-preflight.schema.json"

ROUTES = {
    "did": (["R: did", "Stata: csdid", "Python: pyfixest/csdid"], ["R--Stata cohort ATT parity"], ["timing audit", "comparison group", "pre-trends", "aggregation weights", "cluster level"]),
    "event_study": (["R: did/fixest", "Stata: csdid/eventstudyinteract", "Python: pyfixest"], ["R--Stata event-time parity"], ["support by event time", "reference period", "simultaneous bands", "pre-trend sensitivity"]),
    "iv": (["Python: linearmodels + ivmodels", "Stata: ivreg2", "R: ivreg/fixest"], ["Python--Stata 2SLS parity"], ["first stage", "weak-IV robust inference", "exclusion argument", "overidentification when applicable"]),
    "rd": (["Python/R/Stata: rdrobust"], ["rdrobust cross-language parity"], ["bandwidth", "robust bias correction", "density/manipulation", "covariate continuity", "donut/placebo checks"]),
    "synthetic_control": (["Python/R/Stata: scpi"], ["scpi cross-language parity"], ["donor pool", "pre-fit", "weights", "placebo/prediction intervals", "interpolation risk"]),
    "sdid": (["R: synthdid", "Python: tested adapter"], ["R benchmark parity"], ["balanced panel", "adoption structure", "unit/time weights", "placebo/bootstrap inference", "pre-fit"]),
    "dml": (["Python/R: DoubleML"], ["Python--R score parity"], ["target score", "cross-fitting", "learner registry", "overlap", "sensitivity", "cluster structure"]),
    "complex_survey": (["R: survey", "Stata: svy", "Python: validated survey adapter"], ["R--Stata design-based parity"], ["weights", "strata", "PSU", "FPC/replicate weights", "singleton strata", "subpopulation rules"]),
    "spatial": (["Python: PySAL spreg/esda", "Stata/R spatial estimators"], ["weights and impacts parity"], ["weights provenance", "islands", "Moran diagnostics", "direct/indirect impacts", "spatial dependence"]),
    "network": (["Python/R design-specific network inference"], ["simulation/randomization benchmark"], ["graph provenance", "exposure mapping", "interference assumption", "community dependence", "randomization/permutation scheme"]),
    "dynamic_panel": (["Stata: xtabond2/xtdpdsys", "Python: pydynpd", "R: pdynmc"], ["Stata--Python/R parity"], ["AR(1)/AR(2)", "Hansen/Sargan", "instrument count", "lag validity", "difference vs system GMM"]),
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_frame(request_path: Path, data_spec: dict) -> tuple[pd.DataFrame, Path]:
    raw = Path(data_spec["path"])
    path = raw if raw.is_absolute() else (request_path.parent / raw).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Data file does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, encoding=data_spec.get("encoding", "utf-8"))
    elif suffix == ".xlsx":
        if not data_spec.get("sheet"):
            raise ValueError("XLSX input requires an explicit sheet name.")
        frame = pd.read_excel(path, sheet_name=data_spec["sheet"])
    elif suffix == ".dta":
        frame = pd.read_stata(path, convert_categoricals=False)
    else:
        raise ValueError("Only CSV, XLSX and DTA are accepted by method preflight.")
    return frame, path


def issue(issues: list[dict], severity: str, code: str, message: str) -> None:
    issues.append({"severity": severity, "code": code, "message": message})


def flattened_columns(variables: dict) -> set[str]:
    names: set[str] = set()
    for value in variables.values():
        if isinstance(value, str):
            names.add(value)
        elif isinstance(value, list):
            names.update(str(x) for x in value)
    return names


def panel_checks(frame: pd.DataFrame, v: dict, issues: list[dict], summary: dict) -> pd.DataFrame | None:
    unit, time = v.get("unit_id"), v.get("time_id")
    if not unit or not time:
        return None
    dup = int(frame.duplicated([unit, time]).sum())
    summary.update({"units": int(frame[unit].nunique(dropna=True)), "periods": int(frame[time].nunique(dropna=True)), "duplicate_unit_time_rows": dup})
    if dup:
        issue(issues, "blocking", "duplicate-panel-key", f"Found {dup} duplicate unit--time rows.")
    if frame[[unit, time]].isna().any().any():
        issue(issues, "blocking", "missing-panel-key", "Unit or time identifiers contain missing values.")
    return frame.sort_values([unit, time])


def treatment_monotonic(frame: pd.DataFrame, unit: str, time: str, treatment: str) -> tuple[int, int, int]:
    ordered = frame[[unit, time, treatment]].dropna().sort_values([unit, time]).copy()
    numeric = pd.to_numeric(ordered[treatment], errors="coerce")
    invalid = int(numeric.isna().sum() + (~numeric.dropna().isin([0, 1])).sum())
    ordered[treatment] = numeric
    ordered = ordered.dropna(subset=[treatment])
    reversals = int(ordered.groupby(unit)[treatment].diff().lt(0).sum())
    treated_units = int(ordered.groupby(unit)[treatment].max().gt(0).sum())
    return reversals, treated_units, invalid


def check_did(frame: pd.DataFrame, v: dict, options: dict, issues: list[dict], summary: dict, event: bool) -> None:
    ordered = panel_checks(frame, v, issues, summary)
    if ordered is None:
        return
    reversals, treated_units, invalid_treatment = treatment_monotonic(ordered, v["unit_id"], v["time_id"], v["treatment"])
    summary["treated_units"] = treated_units
    summary["treatment_reversals"] = reversals
    summary["invalid_treatment_rows"] = invalid_treatment
    if invalid_treatment:
        issue(issues, "blocking", "invalid-treatment", "Treatment must be coded as numeric 0/1 without undocumented values.")
    if reversals:
        issue(issues, "blocking", "treatment-reversal", "Treatment switches from treated back to untreated; standard staggered-adoption assumptions fail.")
    cohort = ordered[v["cohort"]]
    never = options.get("never_treated_value")
    never_count = int((cohort == never).sum()) if "never_treated_value" in options else int(cohort.isna().sum())
    summary["never_treated_rows"] = never_count
    if never_count == 0:
        issue(issues, "review", "no-never-treated", "No never-treated observations were identified; define an admissible not-yet-treated comparison strategy.")
    periods = summary.get("periods", 0)
    if event and periods < 4:
        issue(issues, "review", "short-event-window", "Fewer than four periods provide weak event-time support.")
    issue(issues, "review", "parallel-trends-substantive", "Parallel trends cannot be established by this structural check; defend it institutionally and with diagnostics.")


def check_iv(frame: pd.DataFrame, v: dict, issues: list[dict], summary: dict) -> None:
    instruments, endogenous = v["instruments"], v["endogenous"]
    summary.update({"instruments": len(instruments), "endogenous_variables": len(endogenous), "overidentified_by_count": len(instruments) > len(endogenous)})
    for col in instruments + endogenous:
        if frame[col].nunique(dropna=True) < 2:
            issue(issues, "blocking", "no-variation", f"{col} has no usable variation.")
    numeric = frame[instruments + v.get("controls", [])].apply(pd.to_numeric, errors="coerce").dropna()
    if len(numeric) and np.linalg.matrix_rank(np.column_stack([np.ones(len(numeric)), numeric.to_numpy()])) < numeric.shape[1] + 1:
        issue(issues, "blocking", "instrument-rank", "Instruments and controls are rank deficient.")
    issue(issues, "review", "exclusion-not-testable", "The exclusion restriction is not testable from the first stage and requires institutional evidence.")
    issue(issues, "review", "weak-iv-pending", "Run weak-instrument-robust diagnostics; a single first-stage F heuristic is insufficient for multiple endogenous regressors.")


def check_rd(frame: pd.DataFrame, v: dict, options: dict, issues: list[dict], summary: dict) -> None:
    running = pd.to_numeric(frame[v["running"]], errors="coerce")
    cutoff = float(options["cutoff"])
    summary.update({"cutoff": cutoff, "left_of_cutoff": int((running < cutoff).sum()), "right_of_cutoff": int((running >= cutoff).sum()), "at_cutoff": int((running == cutoff).sum())})
    if summary["left_of_cutoff"] == 0 or summary["right_of_cutoff"] == 0:
        issue(issues, "blocking", "one-sided-support", "The running variable has no observations on one side of the cutoff.")
    if "bandwidth" in options:
        inside = (running - cutoff).abs() <= float(options["bandwidth"])
        summary["inside_declared_bandwidth"] = int(inside.sum())
        if int(inside.sum()) < 30:
            issue(issues, "review", "thin-bandwidth", "Fewer than 30 observations fall inside the declared bandwidth.")
    issue(issues, "review", "rd-diagnostics-pending", "Density/manipulation, bandwidth selection, robust bias correction and continuity checks remain required.")


def check_synthetic(frame: pd.DataFrame, v: dict, issues: list[dict], summary: dict, sdid: bool) -> None:
    ordered = panel_checks(frame, v, issues, summary)
    if ordered is None:
        return
    counts = ordered.groupby(v["unit_id"])[v["time_id"]].nunique()
    summary["balanced_panel"] = bool(counts.nunique() == 1)
    if not summary["balanced_panel"]:
        issue(issues, "blocking" if sdid else "review", "unbalanced-panel", "Panel is not balanced across units.")
    reversals, treated_units, invalid_treatment = treatment_monotonic(ordered, v["unit_id"], v["time_id"], v["treatment"])
    summary.update({"treated_units": treated_units, "treatment_reversals": reversals, "invalid_treatment_rows": invalid_treatment, "donor_units": summary.get("units", 0) - treated_units})
    if invalid_treatment:
        issue(issues, "blocking", "invalid-treatment", "Treatment must be coded as numeric 0/1 without undocumented values.")
    if reversals:
        issue(issues, "blocking", "treatment-reversal", "Treatment reversal is incompatible with the declared design.")
    if not sdid and treated_units != 1:
        issue(issues, "review", "noncanonical-scm", "Canonical single-unit SCM expects one treated unit; use a multiple-unit estimator or justify aggregation.")
    if summary["donor_units"] < 2:
        issue(issues, "blocking", "small-donor-pool", "Fewer than two untreated donor units are available.")
    issue(issues, "review", "inference-pending", "Pre-fit, donor sensitivity, placebo or prediction-interval inference remains required.")


def check_dml(frame: pd.DataFrame, v: dict, options: dict, issues: list[dict], summary: dict) -> None:
    folds = int(options.get("folds", 5))
    complete = frame[[v["outcome"], v["treatment"], *v["features"]]].dropna()
    summary.update({"complete_rows": int(len(complete)), "features": len(v["features"]), "folds": folds, "rows_per_fold": int(len(complete) // folds)})
    if len(complete) // folds < 20:
        issue(issues, "review", "small-fold", "Fewer than 20 complete observations per fold; learner and inference stability need review.")
    if complete[v["treatment"]].nunique() < 2:
        issue(issues, "blocking", "no-treatment-variation", "Treatment has no usable variation.")
    issue(issues, "review", "score-and-learners", "Select the target score, nuisance learners and tuning protocol before execution; DML does not repair an invalid design.")


def check_survey(frame: pd.DataFrame, v: dict, issues: list[dict], summary: dict) -> None:
    weights = pd.to_numeric(frame[v["weight"]], errors="coerce")
    summary.update({"positive_weight_rows": int((weights > 0).sum()), "strata": int(frame[v["strata"]].nunique(dropna=True)), "psus": int(frame[v["psu"]].nunique(dropna=True))})
    if weights.isna().any() or (weights <= 0).any():
        issue(issues, "blocking", "invalid-weights", "Survey weights contain missing, zero or negative values.")
    psu_per_stratum = frame.groupby(v["strata"])[v["psu"]].nunique()
    singletons = int((psu_per_stratum < 2).sum())
    summary["singleton_strata"] = singletons
    if singletons:
        issue(issues, "review", "singleton-strata", f"Found {singletons} strata with fewer than two PSUs; variance handling must be declared.")
    if "fpc" not in v:
        issue(issues, "info", "fpc-unspecified", "Finite-population correction is unspecified; record whether it is inapplicable or unavailable.")


def read_edges(request_path: Path, options: dict) -> tuple[pd.DataFrame, Path]:
    raw = Path(options["weight_matrix_path"])
    path = raw if raw.is_absolute() else (request_path.parent / raw).resolve()
    if path.suffix.lower() != ".csv" or not path.is_file():
        raise ValueError("Spatial/network weights must be an existing CSV edge list.")
    return pd.read_csv(path), path


def check_graph(frame: pd.DataFrame, v: dict, options: dict, request_path: Path, issues: list[dict], summary: dict, network: bool) -> None:
    edges, edge_path = read_edges(request_path, options)
    src, dst = options["edge_source"], options["edge_target"]
    if src not in edges or dst not in edges:
        issue(issues, "blocking", "edge-columns", "Declared source/target columns do not exist in the edge list.")
        return
    ids = set(frame[v["spatial_id"]].dropna().astype(str))
    edge_ids = set(edges[src].dropna().astype(str)) | set(edges[dst].dropna().astype(str))
    summary.update({"edge_rows": int(len(edges)), "analysis_ids": len(ids), "islands": len(ids - edge_ids), "self_loops": int((edges[src].astype(str) == edges[dst].astype(str)).sum()), "weights_sha256": sha256(edge_path)})
    if not ids.issubset(edge_ids):
        issue(issues, "review", "graph-islands", f"{len(ids - edge_ids)} analysis units have no recorded edge.")
    if not network:
        reverse = set(zip(edges[dst].astype(str), edges[src].astype(str)))
        pairs = set(zip(edges[src].astype(str), edges[dst].astype(str)))
        if not pairs.issubset(reverse):
            issue(issues, "review", "asymmetric-weights", "Spatial edge list is asymmetric; declare whether directionality is intended.")
    issue(issues, "review", "graph-provenance", "Document how the graph/weights were constructed and freeze it before estimating spillovers or spatial impacts.")


def check_dynamic(frame: pd.DataFrame, v: dict, options: dict, issues: list[dict], summary: dict) -> None:
    panel_checks(frame, v, issues, summary)
    lag = int(options.get("lag_order", 1))
    summary["lag_order"] = lag
    if summary.get("periods", 0) < lag + 3:
        issue(issues, "blocking", "insufficient-time", "Too few periods remain for the requested lag structure and moment conditions.")
    if summary.get("units", 0) <= summary.get("periods", 0):
        issue(issues, "review", "not-small-t-large-n", "Dynamic panel GMM is usually motivated by small T and large N; this panel does not clearly have that structure.")
    max_instruments = max(0, (summary.get("periods", 0) - lag) * (summary.get("periods", 0) - lag - 1) // 2)
    summary["uncollapsed_instrument_upper_bound"] = max_instruments
    if max_instruments >= max(1, summary.get("units", 0)):
        issue(issues, "review", "instrument-proliferation", "Potential instrument count is not smaller than the number of units; collapse/restrict lags and report counts.")
    issue(issues, "review", "gmm-diagnostics-pending", "AR(1), AR(2), Hansen/Sargan and difference-in-Hansen diagnostics remain required.")


def latex_escape(value: Any) -> str:
    text = str(value)
    table = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(table.get(ch, ch) for ch in text)


def write_latex(result: dict, path: Path) -> None:
    issue_rows = "\n".join(
        f"{latex_escape(i['severity'])} & {latex_escape(i['code'])} & {latex_escape(i['message'])} \\\\"
        for i in result["issues"]
    ) or r"info & none & 未发现结构性问题；仍须完成方法专属诊断。 \\"
    text = f"""\\documentclass[UTF8]{{ctexart}}
\\usepackage[a4paper,margin=2.5cm]{{geometry}}
\\usepackage{{booktabs,longtable,hyperref}}
\\begin{{document}}
\\section*{{计量方法准入检查}}
方法：{latex_escape(result['method'])}\\par
设计状态：{latex_escape(result['design_status'])}\\par
估计状态：not-run（本报告不包含效应估计）。\\par
\\begin{{longtable}}{{p{{0.12\\linewidth}}p{{0.22\\linewidth}}p{{0.58\\linewidth}}}}
\\toprule 严重度 & 代码 & 说明 \\\\ \\midrule
{issue_rows}
\\bottomrule
\\end{{longtable}}
\\section*{{推荐执行路线}}
首选：{latex_escape('; '.join(result['adapter_route']['preferred']))}\\par
交叉核验：{latex_escape('; '.join(result['adapter_route']['cross_check']))}\\par
\\end{{document}}
"""
    path.write_text(text, encoding="utf-8")


def preflight(request_path: Path, output_dir: Path) -> dict:
    request = read_json(request_path)
    schema = read_json(REQUEST_SCHEMA)
    jsonschema.Draft202012Validator(schema).validate(request)
    frame, source_path = load_frame(request_path, request["data"])
    variables, options = request["variables"], request.get("options", {})
    missing = sorted(flattened_columns(variables) - set(frame.columns))
    issues: list[dict] = []
    summary: dict[str, Any] = {"rows": int(len(frame)), "columns": int(len(frame.columns))}
    if missing:
        issue(issues, "blocking", "missing-columns", f"Declared columns not found: {missing}")
    else:
        method = request["method"]
        if method in {"did", "event_study"}:
            check_did(frame, variables, options, issues, summary, method == "event_study")
        elif method == "iv":
            check_iv(frame, variables, issues, summary)
        elif method == "rd":
            check_rd(frame, variables, options, issues, summary)
        elif method in {"synthetic_control", "sdid"}:
            check_synthetic(frame, variables, issues, summary, method == "sdid")
        elif method == "dml":
            check_dml(frame, variables, options, issues, summary)
        elif method == "complex_survey":
            check_survey(frame, variables, issues, summary)
        elif method in {"spatial", "network"}:
            check_graph(frame, variables, options, request_path, issues, summary, method == "network")
        elif method == "dynamic_panel":
            check_dynamic(frame, variables, options, issues, summary)

    status = "blocked" if any(i["severity"] == "blocking" for i in issues) else ("review-required" if any(i["severity"] == "review" for i in issues) else "ready-for-adapter")
    preferred, cross_check, diagnostics = ROUTES[request["method"]]
    result = {
        "schema_version": "econometric-method-preflight/1.0",
        "project_id": request["project_id"], "design_id": request["design_id"], "method": request["method"],
        "design_status": status, "estimation_status": "not-run",
        "source": {"path": request["data"]["path"], "sha256": sha256(source_path), "rows": int(len(frame)), "columns": int(len(frame.columns))},
        "summary": summary, "issues": issues,
        "adapter_route": {"status": "staged", "preferred": preferred, "cross_check": cross_check, "required_diagnostics": diagnostics},
    }
    jsonschema.Draft202012Validator(read_json(RESULT_SCHEMA)).validate(result)
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "preflight.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_latex(result, output_dir / "preflight-report.tex")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = preflight(args.request.resolve(), args.output_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"design_status": result["design_status"], "estimation_status": "not-run", "report": str(args.output_dir / "preflight.json")}, ensure_ascii=False))
    return 1 if result["design_status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
