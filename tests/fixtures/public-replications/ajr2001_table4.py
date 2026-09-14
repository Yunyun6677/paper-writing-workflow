"""Reproduce AJR (2001) Table 4 columns 1-2 from a public Stata file."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.sandbox.regression.gmm import IV2SLS


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fit(frame: pd.DataFrame, latitude: bool) -> dict[str, float | int | bool]:
    columns = ["logpgp95", "avexpr", "logem4"] + (["lat_abst"] if latitude else [])
    sample = frame.loc[frame["baseco"] == 1, columns].dropna()
    y = sample["logpgp95"].to_numpy()
    x_parts = [np.ones(len(sample)), sample["avexpr"].to_numpy()]
    z_parts = [np.ones(len(sample)), sample["logem4"].to_numpy()]
    if latitude:
        x_parts.append(sample["lat_abst"].to_numpy())
        z_parts.append(sample["lat_abst"].to_numpy())
    fitted = IV2SLS(y, np.column_stack(x_parts), np.column_stack(z_parts)).fit()
    return {
        "column": 2 if latitude else 1,
        "n": int(fitted.nobs),
        "institution_coefficient": float(fitted.params[1]),
        "institution_standard_error": float(fitted.bse[1]),
        "latitude_included": latitude,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--paper", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data, paper, output = args.data.resolve(), args.paper.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    output.mkdir(parents=True)
    frame = pd.read_stata(data, convert_categoricals=False)
    required = {"baseco", "logpgp95", "avexpr", "logem4", "lat_abst"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing AJR variables: {missing}")
    results = pd.DataFrame([fit(frame, False), fit(frame, True)])
    results.to_csv(output / "table4_columns_1_2.csv", index=False)
    targets = [(0.94, 0.16), (1.00, 0.22)]
    checks = []
    for row, (coefficient, standard_error) in zip(results.to_dict("records"), targets):
        checks.append({
            "column": row["column"],
            "coefficient_rounding_match": abs(row["institution_coefficient"] - coefficient) < 0.005,
            "standard_error_rounding_match": abs(row["institution_standard_error"] - standard_error) < 0.005,
            "sample_match": row["n"] == 64,
        })
    receipt = {
        "schema_version": "replication-receipt/1.0",
        "status": "complete" if all(all(value for key, value in item.items() if key != "column") for item in checks) else "failed",
        "paper_doi": "10.1257/aer.91.5.1369",
        "target": "Table 4, Panel A, columns 1-2",
        "data_sha256": sha256(data),
        "paper_sha256": sha256(paper),
        "checks": checks,
        "limitations": [
            "This is a selected-table numerical reproduction, not a full-paper replication.",
            "Coefficient reproduction does not independently validate the exclusion restriction.",
        ],
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
