"""Prepare Card-Krueger public fixed-width data and reproduce selected tables."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm


FIELDS = [
    ("sheet", 1, 3), ("chain", 5, 5), ("co_owned", 7, 7), ("state", 9, 9),
    ("southj", 11, 11), ("centralj", 13, 13), ("northj", 15, 15), ("pa1", 17, 17),
    ("pa2", 19, 19), ("shore", 21, 21), ("ncalls", 23, 24), ("empft", 26, 30),
    ("emppt", 32, 36), ("nmgrs", 38, 42), ("wage_st", 44, 48), ("inctime", 50, 54),
    ("firstinc", 56, 60), ("bonus", 62, 62), ("pctaff", 64, 68), ("meals", 70, 70),
    ("open", 72, 76), ("hrsopen", 78, 82), ("psoda", 84, 88), ("pfry", 90, 94),
    ("pentree", 96, 100), ("nregs", 102, 103), ("nregs11", 105, 106), ("type2", 108, 108),
    ("status2", 110, 110), ("date2", 112, 117), ("ncalls2", 119, 120), ("empft2", 122, 126),
    ("emppt2", 128, 132), ("nmgrs2", 134, 138), ("wage_st2", 140, 144), ("inctime2", 146, 150),
    ("firstin2", 152, 156), ("special2", 158, 158), ("meals2", 160, 160), ("open2r", 162, 166),
    ("hrsopen2", 168, 172), ("psoda2", 174, 178), ("pfry2", 180, 184),
    ("pentree2", 186, 190), ("nregs2", 192, 193), ("nregs112", 195, 196),
]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(source: Path) -> pd.DataFrame:
    names = [field[0] for field in FIELDS]
    colspecs = [(field[1] - 1, field[2]) for field in FIELDS]
    data = pd.read_fwf(source, colspecs=colspecs, names=names, na_values=["."], dtype=float)
    if len(data) != 410:
        raise ValueError("Expected 410 survey records")
    data.insert(0, "source_row", np.arange(1, len(data) + 1))
    data["emptot"] = data["empft"] + 0.5 * data["emppt"] + data["nmgrs"]
    data["emptot2"] = data["empft2"] + 0.5 * data["emppt2"] + data["nmgrs2"]
    data["demp"] = data["emptot2"] - data["emptot"]
    data["dwage"] = data["wage_st2"] - data["wage_st"]
    data["nj"] = data["state"]
    data["bk"] = (data["chain"] == 1).astype(int)
    data["kfc"] = (data["chain"] == 2).astype(int)
    data["roys"] = (data["chain"] == 3).astype(int)
    data["closed"] = (data["status2"] == 3).astype(int)
    data["gap"] = np.where(
        data["state"] == 0, 0,
        np.where(data["wage_st"] >= 5.05, 0, np.where(data["wage_st"] > 0, (5.05 - data["wage_st"]) / data["wage_st"], np.nan)),
    )
    data["analysis_sample"] = (data["demp"].notna() & ((data["closed"] == 1) | data["dwage"].notna())).astype(int)
    return data


def table3(data: pd.DataFrame) -> pd.DataFrame:
    records = []
    for label, column in [("fte_before", "emptot"), ("fte_after", "emptot2"), ("change_in_means", None)]:
        pa = data.loc[data.nj == 0, "emptot2" if label == "fte_after" else "emptot"].mean()
        nj = data.loc[data.nj == 1, "emptot2" if label == "fte_after" else "emptot"].mean()
        if label == "change_in_means":
            pa = data.loc[data.nj == 0, "emptot2"].mean() - data.loc[data.nj == 0, "emptot"].mean()
            nj = data.loc[data.nj == 1, "emptot2"].mean() - data.loc[data.nj == 1, "emptot"].mean()
        records.append({"row": label, "pa": pa, "nj": nj, "nj_minus_pa": nj - pa})
    balanced = data[data.emptot.notna() & data.emptot2.notna()]
    pa = balanced.loc[balanced.nj == 0, "demp"].mean(); nj = balanced.loc[balanced.nj == 1, "demp"].mean()
    records.append({"row": "balanced_change", "pa": pa, "nj": nj, "nj_minus_pa": nj - pa})
    adjusted = data.copy()
    temporary = adjusted.status2.isin([2, 4, 5]) & adjusted.emptot.notna()
    adjusted.loc[temporary, "emptot2"] = 0
    adjusted["adjusted_change"] = adjusted["emptot2"] - adjusted["emptot"]
    available = adjusted.adjusted_change.notna()
    pa = adjusted.loc[available & (adjusted.nj == 0), "adjusted_change"].mean()
    nj = adjusted.loc[available & (adjusted.nj == 1), "adjusted_change"].mean()
    records.append({"row": "temporary_closed_as_zero", "pa": pa, "nj": nj, "nj_minus_pa": nj - pa})
    return pd.DataFrame(records)


def table4(data: pd.DataFrame) -> pd.DataFrame:
    sample = data[data.analysis_sample == 1].copy()
    specifications = {
        "m1": ("nj", ["nj"]),
        "m2": ("nj", ["nj", "bk", "kfc", "roys", "co_owned"]),
        "m3": ("gap", ["gap"]),
        "m4": ("gap", ["gap", "bk", "kfc", "roys", "co_owned"]),
        "m5": ("gap", ["gap", "bk", "kfc", "roys", "centralj", "southj", "pa1", "pa2"]),
    }
    rows = []
    for spec_id, (target, regressors) in specifications.items():
        frame = sample[["demp", *regressors]].dropna()
        fit = sm.OLS(frame["demp"], sm.add_constant(frame[regressors], has_constant="add")).fit()
        rows.append({
            "spec_id": spec_id, "term": target, "estimate": float(fit.params[target]),
            "std_error": float(fit.bse[target]), "n": int(fit.nobs), "df_resid": float(fit.df_resid),
        })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source, output = Path(args.data).resolve(), Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("Output exists; use a new directory")
    output.mkdir(parents=True)
    data = prepare(source)
    data.to_csv(output / "analysis.csv", index=False)
    t3, t4 = table3(data), table4(data)
    t3.to_csv(output / "table3_results.csv", index=False)
    t4.to_csv(output / "table4_results.csv", index=False)
    targets = {"m1": (2.33, 1.19), "m2": (2.30, 1.20), "m3": (15.65, 6.08), "m4": (14.92, 6.21), "m5": (11.91, 7.39)}
    deltas = []
    for row in t4.itertuples():
        coefficient, standard_error = targets[row.spec_id]
        deltas.extend([abs(row.estimate - coefficient), abs(row.std_error - standard_error)])
    receipt = {
        "schema_version": "replication-receipt/1.0", "status": "complete",
        "paper_identifier": "JSTOR:2118030", "working_paper_doi": "10.3386/w4509",
        "source_sha256": sha256(source), "records": len(data), "unique_sheet_ids": int(data.sheet.nunique()),
        "duplicate_sheet_records": int(data.sheet.duplicated(keep=False).sum()),
        "analysis_sample": int(data.analysis_sample.sum()),
        "table3_did": float(t3.loc[t3.row == "change_in_means", "nj_minus_pa"].iloc[0]),
        "author_rounded_max_abs_delta": max(deltas),
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
