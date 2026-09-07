from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True)
    parser.add_argument("--stata", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    python_path, stata_path = Path(args.python).resolve(), Path(args.stata).resolve()
    left = pd.read_csv(python_path).set_index(["spec_id", "outcome", "term"]).sort_index()
    right = pd.read_csv(stata_path).set_index(["spec_id", "outcome", "term"]).sort_index()
    if not left.index.equals(right.index):
        raise ValueError("Engine result keys differ")
    deltas = {
        "estimate": float((left.estimate - right.estimate).abs().max()),
        "std_error": float((left.std_error - right.std_error).abs().max()),
        "nobs": float((left.nobs - right.nobs).abs().max()),
        "df_resid": float((left.df_resid - right.df_resid).abs().max()),
        "p_value": float((left.p_value - right.p_value).abs().max()),
    }
    # The first Stata certificate was exported at roughly seven significant digits.
    # Treat sub-1e-6 differences as serialization noise, not estimator disagreement.
    status = "complete" if max(deltas[k] for k in ["estimate", "std_error", "nobs", "df_resid"]) < 1e-6 else "review-required"
    receipt = {
        "schema_version": "replication-parity/1.0",
        "status": status,
        "engines": ["python", "stata"],
        "max_abs_deltas": deltas,
        "p_value_note": "Python reports asymptotic normal p-values; Stata regress, robust reports t p-values with residual degrees of freedom.",
        "acceptance_tolerance": 1e-6,
        "inputs": {
            "python": {"sha256": digest(python_path), "bytes": python_path.stat().st_size},
            "stata": {"sha256": digest(stata_path), "bytes": stata_path.stat().st_size},
        },
    }
    output = Path(args.output).resolve()
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
