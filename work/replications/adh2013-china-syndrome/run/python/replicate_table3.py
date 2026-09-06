from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = PROJECT / "original" / "Autor-Dorn-Hanson-ChinaSyndrome-FileArchive" / "dta" / "workfile_china.dta"
DEFAULT_STATA_RESULTS = PROJECT / "run" / "stata" / "table3_results.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent

REGION_CONTROLS = [
    "reg_midatl",
    "reg_encen",
    "reg_wncen",
    "reg_satl",
    "reg_escen",
    "reg_wscen",
    "reg_mount",
    "reg_pacif",
]

SPECIFICATIONS = [
    ["t2"],
    ["l_shind_manuf_cbp", "t2"],
    ["l_shind_manuf_cbp", *REGION_CONTROLS, "t2"],
    ["l_shind_manuf_cbp", *REGION_CONTROLS, "l_sh_popedu_c", "l_sh_popfborn", "l_sh_empl_f", "t2"],
    ["l_shind_manuf_cbp", *REGION_CONTROLS, "l_sh_routine33", "l_task_outsource", "t2"],
    [
        "l_shind_manuf_cbp",
        *REGION_CONTROLS,
        "l_sh_popedu_c",
        "l_sh_popfborn",
        "l_sh_empl_f",
        "l_sh_routine33",
        "l_task_outsource",
        "t2",
    ],
]

# Rounded values distributed in the authors' tab_ipw_manuf_2.scsv.
AUTHOR_COEFFICIENTS = np.array([-0.746, -0.610, -0.538, -0.508, -0.562, -0.596])
AUTHOR_STANDARD_ERRORS = np.array([0.068, 0.094, 0.091, 0.081, 0.096, 0.099])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cluster_meat(design: np.ndarray, residual: np.ndarray, groups: np.ndarray) -> np.ndarray:
    meat = np.zeros((design.shape[1], design.shape[1]))
    for group in np.unique(groups):
        score = (design[groups == group] * residual[groups == group, None]).sum(axis=0)
        meat += np.outer(score, score)
    return meat


def weighted_first_stage(
    endogenous: np.ndarray,
    instruments: np.ndarray,
    weights: np.ndarray,
    groups: np.ndarray,
) -> tuple[float, float, float]:
    root_weight = np.sqrt(weights)
    x = instruments * root_weight[:, None]
    y = endogenous * root_weight
    bread = np.linalg.inv(x.T @ x)
    beta = bread @ x.T @ y
    residual = y - x @ beta
    covariance = bread @ cluster_meat(x, residual, groups) @ bread
    n, k = x.shape
    group_count = len(np.unique(groups))
    covariance *= (group_count / (group_count - 1)) * ((n - 1) / (n - k))
    standard_error = np.sqrt(np.diag(covariance))
    return float(beta[0]), float(standard_error[0]), float((beta[0] / standard_error[0]) ** 2)


def weighted_2sls(
    outcome: np.ndarray,
    endogenous: np.ndarray,
    exogenous: np.ndarray,
    excluded_instrument: np.ndarray,
    weights: np.ndarray,
    groups: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    root_weight = np.sqrt(weights)
    x_raw = np.column_stack([endogenous, exogenous, np.ones(len(outcome))])
    z_raw = np.column_stack([excluded_instrument, exogenous, np.ones(len(outcome))])
    x = x_raw * root_weight[:, None]
    z = z_raw * root_weight[:, None]
    y = outcome * root_weight

    z_cross_inverse = np.linalg.inv(z.T @ z)
    fitted_x = z @ z_cross_inverse @ z.T @ x
    information = x.T @ fitted_x
    bread = np.linalg.inv(information)
    beta = bread @ x.T @ z @ z_cross_inverse @ z.T @ y
    residual = y - x @ beta

    # Stata ivregress 2sls, cluster() uses this uncorrected cluster sandwich.
    covariance = bread @ cluster_meat(fitted_x, residual, groups) @ bread
    return beta, np.sqrt(np.diag(covariance))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replicate ADH (2013) Table 3 columns 1-6.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--stata-results", type=Path, default=DEFAULT_STATA_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_path = args.data.resolve()
    stata_results_path = args.stata_results.resolve()
    output_path = args.output.resolve()
    frame = pd.read_stata(data_path, convert_categoricals=False)
    rows: list[dict[str, float | int]] = []

    for index, controls in enumerate(SPECIFICATIONS, start=1):
        required = [
            "d_sh_empl_mfg",
            "d_tradeusch_pw",
            "d_tradeotch_pw_lag",
            "timepwt48",
            "statefip",
            *controls,
        ]
        sample = frame[required].dropna()
        exogenous = sample[controls].to_numpy(dtype=float)
        outcome = sample["d_sh_empl_mfg"].to_numpy(dtype=float)
        endogenous = sample["d_tradeusch_pw"].to_numpy(dtype=float)
        excluded = sample["d_tradeotch_pw_lag"].to_numpy(dtype=float)
        weights = sample["timepwt48"].to_numpy(dtype=float)
        groups = sample["statefip"].to_numpy()

        first_x = np.column_stack([excluded, exogenous, np.ones(len(sample))])
        first_b, first_se, first_f = weighted_first_stage(endogenous, first_x, weights, groups)
        beta, standard_error = weighted_2sls(outcome, endogenous, exogenous, excluded, weights, groups)
        rows.append(
            {
                "specification": index,
                "coefficient": float(beta[0]),
                "standard_error": float(standard_error[0]),
                "observations": len(sample),
                "clusters": len(np.unique(groups)),
                "first_stage_coefficient": first_b,
                "first_stage_standard_error": first_se,
                "first_stage_F": first_f,
            }
        )

    results = pd.DataFrame(rows)
    stata = pd.read_csv(stata_results_path)
    coefficient_delta = np.abs(results["coefficient"] - stata["coefficient"])
    standard_error_delta = np.abs(results["standard_error"] - stata["standard_error"])
    author_coefficient_delta = np.abs(results["coefficient"] - AUTHOR_COEFFICIENTS)
    author_standard_error_delta = np.abs(results["standard_error"] - AUTHOR_STANDARD_ERRORS)

    receipt = {
        "schema_version": "replication-receipt/1.0",
        "paper_doi": "10.1257/aer.103.6.2121",
        "target": "Table 3, import-exposure coefficient, columns 1-6",
        "status": "complete",
        "data_sha256": sha256(data_path),
        "stata_python_max_abs_coefficient_delta": float(coefficient_delta.max()),
        "stata_python_max_abs_standard_error_delta": float(standard_error_delta.max()),
        "author_rounded_max_abs_coefficient_delta": float(author_coefficient_delta.max()),
        "author_rounded_max_abs_standard_error_delta": float(author_standard_error_delta.max()),
        "assertions": {
            "all_samples_1444": bool((results["observations"] == 1444).all()),
            "all_cluster_counts_48": bool((results["clusters"] == 48).all()),
            "stata_python_coefficients_within_1e-10": bool((coefficient_delta < 1e-10).all()),
            "stata_python_standard_errors_within_1e-7": bool((standard_error_delta < 1e-7).all()),
            "author_rounded_values_within_0.0005": bool(
                (author_coefficient_delta < 0.0005).all() and (author_standard_error_delta < 0.0005).all()
            ),
        },
    }
    if not all(receipt["assertions"].values()):
        receipt["status"] = "review-required"

    output_path.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path / "table3_results.csv", index=False)
    (output_path / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    if receipt["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
