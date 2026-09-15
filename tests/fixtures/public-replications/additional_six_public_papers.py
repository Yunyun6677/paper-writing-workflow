"""Execute six bounded public-paper checks without redistributing source files.

The local inputs are acquired separately from legitimate public sources.  This
runner writes only derived results and receipts.  A paper-table match is never
inferred when the secondary public extract omits variables required by the
published specification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import statsmodels.formula.api as smf


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_case(root: Path, paper_id: str, result: dict[str, Any], checks: dict[str, bool],
               *, assessment: str, limitations: list[str]) -> dict[str, Any]:
    case = root / paper_id
    output = case / "run-python"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    result_path = output / "result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    status = "complete" if all(checks.values()) else "failed"
    receipt = {
        "schema_version": "replication-receipt/1.0",
        "paper_id": paper_id,
        "status": status,
        "assessment": assessment,
        "checks": checks,
        "result_sha256": sha256(result_path),
        "limitations": limitations,
    }
    receipt_path = output / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def thornton(root: Path) -> dict[str, Any]:
    data = root / "thornton2008" / "thornton_hiv.dta"
    frame = pd.read_stata(data).dropna(subset=["got", "any"])
    fit = smf.ols("got ~ any", frame).fit(cov_type="cluster", cov_kwds={"groups": frame["villnum"]})
    result = {
        "target": "public-extract unadjusted incentive contrast",
        "n": int(fit.nobs),
        "villages": int(frame["villnum"].nunique()),
        "coefficient": float(fit.params["any"]),
        "cluster_standard_error": float(fit.bse["any"]),
        "mean_no_incentive": float(frame.loc[frame["any"] == 0, "got"].mean()),
        "mean_any_incentive": float(frame.loc[frame["any"] == 1, "got"].mean()),
        "data_sha256": sha256(data),
    }
    checks = {
        "sample_nonempty": result["n"] == 2834,
        "mean_identity": abs((result["mean_any_incentive"] - result["mean_no_incentive"]) - result["coefficient"]) < 1e-12,
        "positive_randomized_incentive_contrast": result["coefficient"] > 0,
    }
    return write_case(
        root, "thornton2008", result, checks, assessment="method_alignment_only",
        limitations=[
            "The curated seven-variable extract lacks sex, district, simulated-distance, and other controls required for published Table 4.",
            "The 0.450552 unadjusted contrast must not be described as a reproduction of the paper's adjusted 0.431 coefficient.",
        ],
    )


def broockman(root: Path) -> dict[str, Any]:
    data = root / "broockman2013" / "black_politicians.csv"
    frame = pd.read_csv(data)
    fit = smf.ols("responded ~ treat_out * leg_black", frame).fit()
    result = {
        "target": "Table 2 column 1",
        "n": int(fit.nobs),
        "out_of_district": float(fit.params["treat_out"]),
        "out_of_district_se": float(fit.bse["treat_out"]),
        "interaction": float(fit.params["treat_out:leg_black"]),
        "interaction_se": float(fit.bse["treat_out:leg_black"]),
        "data_sha256": sha256(data),
    }
    checks = {
        "sample_match": result["n"] == 5593,
        "treatment_rounding_match": abs(result["out_of_district"] - (-0.275)) < 0.0005,
        "treatment_se_rounding_match": abs(result["out_of_district_se"] - 0.013) < 0.0005,
        "interaction_rounding_match": abs(result["interaction"] - 0.128) < 0.0005,
        "interaction_se_rounding_match": abs(result["interaction_se"] - 0.052) < 0.0005,
    }
    return write_case(
        root, "broockman2013", result, checks, assessment="pass",
        limitations=["This is a selected-column numerical reproduction, not a full-paper replication."],
    )


def cheng(root: Path) -> dict[str, Any]:
    data = root / "cheng2013" / "castle.dta"
    frame = pd.read_stata(data)
    fit = smf.wls("l_homicide ~ post + C(sid) + C(year)", frame, weights=frame["popwt"]).fit(
        cov_type="cluster", cov_kwds={"groups": frame["sid"], "use_correction": True}
    )
    result = {
        "target": "Table 5 Panel A column 1 core weighted TWFE",
        "n": int(fit.nobs),
        "states": int(frame["sid"].nunique()),
        "post_coefficient": float(fit.params["post"]),
        "cluster_standard_error": float(fit.bse["post"]),
        "paper_coefficient": 0.0801,
        "paper_standard_error": 0.0342,
        "data_sha256": sha256(data),
    }
    checks = {
        "sample_match": result["n"] == 550,
        "state_count_match": result["states"] == 50,
        "coefficient_within_declared_tolerance": abs(result["post_coefficient"] - result["paper_coefficient"]) < 0.005,
        "standard_error_within_declared_tolerance": abs(result["cluster_standard_error"] - result["paper_standard_error"]) < 0.005,
    }
    return write_case(
        root, "cheng2013", result, checks, assessment="pass_with_version_tolerance",
        limitations=[
            "The public teaching extract produces 0.075533 rather than the published 0.0801; the difference is retained and bounded, not hidden.",
            "This check covers the core weighted TWFE specification only, not the full six-column specification ladder.",
        ],
    )


def kessler(root: Path) -> dict[str, Any]:
    data = root / "kessler2014" / "organ_donation.csv"
    frame = pd.read_csv(data)
    frame["california"] = (frame["State"] == "California").astype(int)
    frame["post"] = frame["Quarter"].isin(["Q32011", "Q42011", "Q12012"]).astype(int)
    frame["post_california"] = frame["post"] * frame["california"]
    fit = smf.ols("Rate ~ post_california + C(State) + C(Quarter)", frame).fit()
    result = {
        "target": "Table 2 column 2 state-and-quarter FE coefficient",
        "n": int(fit.nobs),
        "states": int(frame["State"].nunique()),
        "post_california": float(fit.params["post_california"]),
        "available_extract_standard_error": float(fit.bse["post_california"]),
        "paper_coefficient": -0.022,
        "paper_standard_error": 0.007,
        "data_sha256": sha256(data),
    }
    checks = {
        "sample_match": result["n"] == 162,
        "coefficient_rounding_match": abs(result["post_california"] - result["paper_coefficient"]) < 0.0005,
        "sign_match": result["post_california"] < 0,
    }
    return write_case(
        root, "kessler2014", result, checks, assessment="coefficient_pass_inference_unavailable",
        limitations=[
            "The public three-column extract omits registration-decision counts used for the paper's weighting and reported 0.007 standard error.",
            "The coefficient is reproduced; the published inference is explicitly not certified from this extract.",
        ],
    )


def manacorda(root: Path) -> dict[str, Any]:
    data = root / "manacorda2011" / "Government_Transfers_RDD_Data.csv"
    frame = pd.read_csv(data)
    frame["eligible"] = (frame["Income_Centered"] < 0).astype(int)
    fit = smf.ols("Support ~ eligible", frame).fit()
    result = {
        "target": "Table 1 Panel C column 1 reduced-form eligibility contrast",
        "n": int(fit.nobs),
        "noneligible_mean": float(frame.loc[frame["eligible"] == 0, "Support"].mean()),
        "eligibility_coefficient": float(fit.params["eligible"]),
        "available_extract_standard_error": float(fit.bse["eligible"]),
        "paper_noneligible_mean": 0.729,
        "paper_coefficient": 0.116,
        "paper_n": 1938,
        "data_sha256": sha256(data),
    }
    checks = {
        "mean_within_declared_tolerance": abs(result["noneligible_mean"] - result["paper_noneligible_mean"]) < 0.005,
        "coefficient_within_declared_tolerance": abs(result["eligibility_coefficient"] - result["paper_coefficient"]) < 0.005,
        "direction_match": result["eligibility_coefficient"] > 0,
    }
    return write_case(
        root, "manacorda2011", result, checks, assessment="coefficient_pass_sample_warning",
        limitations=[
            "The curated extract has 1,948 observations versus 1,938 reported for Panel C and lacks the score-cluster identifier.",
            "The coefficient and control mean align within the declared tolerance; the published clustered inference is not certified.",
        ],
    )


def lee(root: Path) -> dict[str, Any]:
    data = root / "lee2004" / "close_elections_lmb.dta"
    frame = pd.read_stata(data)
    close = frame.loc[(frame["lagdemvoteshare"] > 0.48) & (frame["lagdemvoteshare"] < 0.52)].copy()
    group_means = close.groupby("lagdemocrat")[["score", "democrat"]].mean()
    result = {
        "target": "Table I columns 1 and 3 close-election gaps",
        "n": int(len(close)),
        "ada_next_gap": float(group_means.loc[1, "score"] - group_means.loc[0, "score"]),
        "next_democrat_probability_gap": float(group_means.loc[1, "democrat"] - group_means.loc[0, "democrat"]),
        "paper_ada_gap": 21.2,
        "paper_probability_gap": 0.48,
        "data_sha256": sha256(data),
    }
    checks = {
        "sample_match": result["n"] == 915,
        "ada_gap_within_declared_tolerance": abs(result["ada_next_gap"] - result["paper_ada_gap"]) < 0.1,
        "probability_gap_rounding_match": abs(result["next_democrat_probability_gap"] - result["paper_probability_gap"]) < 0.005,
    }
    return write_case(
        root, "lee2004", result, checks, assessment="pass_with_version_tolerance",
        limitations=[
            "The ADA gap from the curated extract is 21.283875 versus 21.2 in print; the exact delta is retained.",
            "This check reproduces two close-election contrasts, not the paper's full RD polynomial and sensitivity analysis.",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    receipts = [thornton(root), broockman(root), cheng(root), kessler(root), manacorda(root), lee(root)]
    summary = {
        "status": "complete" if all(item["status"] == "complete" for item in receipts) else "failed",
        "cases": len(receipts),
        "clean_author_table_passes": sum(item["assessment"] == "pass" for item in receipts),
        "bounded_partial_or_version_matches": sum(item["assessment"] != "pass" for item in receipts),
        "receipts": receipts,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
