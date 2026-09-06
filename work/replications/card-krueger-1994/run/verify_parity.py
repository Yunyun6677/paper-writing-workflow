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
    parser.add_argument("--r", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paths = {name: Path(value).resolve() for name, value in {"python": args.python, "stata": args.stata, "r": args.r}.items()}
    frames = {name: pd.read_csv(path).set_index(["spec_id", "term"]).sort_index() for name, path in paths.items()}
    if not (frames["python"].index.equals(frames["stata"].index) and frames["python"].index.equals(frames["r"].index)):
        raise ValueError("Engine result keys differ")
    deltas = {}
    for left, right in [("python", "stata"), ("python", "r"), ("stata", "r")]:
        deltas[f"{left}_{right}_coefficient"] = float((frames[left].estimate - frames[right].estimate).abs().max())
        deltas[f"{left}_{right}_standard_error"] = float((frames[left].std_error - frames[right].std_error).abs().max())
    status = "complete" if max(deltas.values()) < 1e-8 else "review-required"
    receipt = {
        "schema_version": "replication-parity/1.0", "status": status, "engines": ["python", "stata", "r"],
        "max_abs_deltas": deltas,
        "inputs": {name: {"sha256": digest(path), "bytes": path.stat().st_size} for name, path in paths.items()},
    }
    output = Path(args.output).resolve()
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
