from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
import pandas as pd
import statsmodels.formula.api as smf

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def drop_absorbed_singletons(frame: pd.DataFrame, fixed_effects: list[list[str]]) -> pd.DataFrame:
    """Match reghdfe's iterative removal of singleton fixed-effect groups."""
    result = frame.copy()
    previous = -1
    while previous != len(result):
        previous = len(result)
        keep = pd.Series(True, index=result.index)
        for keys in fixed_effects:
            keep &= result.groupby(keys, dropna=False)[keys[0]].transform("size") > 1
        result = result.loc[keep]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(args.data).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    output.mkdir(parents=True)
    data = pd.read_stata(source, convert_categoricals=False)

    required = {
        "promotion2", "avg_relgrowth", "age", "age2", "sex", "home_pref",
        "patron_connection", "initlgdp", "initlpop", "provcode", "year",
        "tenure", "edu_code", "preftype", "prefcode",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Missing analysis columns: {missing}")

    summary_map = {
        "annual_gdp_growth": "rgdpgrowth",
        "average_relative_growth": "rel_growth",
        "log_gdp": "lgdp",
        "log_population": "lpop",
        "promotion": "promotion2",
        "age": "age",
        "sex": "sex",
        "education": "edu_code",
        "tenure": "tenure",
        "arrested": "arrested_dummy",
        "home_prefecture": "home_pref",
        "political_connection": "patron_connection",
    }
    summary_sample = data.dropna(subset=["promotion2", "avg_relgrowth", "provcode", "year", "prefcode"])
    summary_sample = drop_absorbed_singletons(summary_sample, [["provcode", "year"]])
    summary_rows = []
    for label, variable in summary_map.items():
        if variable not in data:
            continue
        values = summary_sample[variable].dropna()
        summary_rows.append({
            "variable": label,
            "mean": float(values.mean()),
            "minimum": float(values.min()),
            "median": float(values.median()),
            "maximum": float(values.max()),
            "count": int(values.count()),
        })
    pd.DataFrame(summary_rows).to_csv(output / "table1_summary.csv", index=False)

    province_year = "C(provcode):C(year)"
    mayor = "age + age2 + sex + home_pref + patron_connection"
    specifications = [
        ("m1", f"promotion2 ~ avg_relgrowth + {province_year}",
         ["promotion2", "avg_relgrowth", "prefcode"], [["provcode", "year"]]),
        ("m2", f"promotion2 ~ avg_relgrowth + {mayor} + {province_year} + C(tenure) + C(edu_code)",
         ["promotion2", "avg_relgrowth", "age", "age2", "sex", "home_pref", "patron_connection", "prefcode"],
         [["provcode", "year"], ["tenure"], ["edu_code"]]),
        ("m3", f"promotion2 ~ avg_relgrowth + initlgdp + initlpop + {mayor} + {province_year} + C(tenure) + C(edu_code) + C(preftype)",
         ["promotion2", "avg_relgrowth", "initlgdp", "initlpop", "age", "age2", "sex", "home_pref", "patron_connection", "prefcode"],
         [["provcode", "year"], ["tenure"], ["edu_code"], ["preftype"]]),
    ]
    published = {
        "m1": {"estimate": -0.034, "std_error": 0.085, "nobs": 5640},
        "m2": {"estimate": -0.091, "std_error": 0.089, "nobs": 5172},
        "m3": {"estimate": -0.060, "std_error": 0.108, "nobs": 5141},
    }
    rows = []
    for spec_id, formula, variables, fixed_effects in specifications:
        estimation = data.dropna(subset=variables + sum(fixed_effects, [])).copy()
        estimation = drop_absorbed_singletons(estimation, fixed_effects)
        base = smf.ols(formula, data=estimation, missing="raise").fit()
        fitted = base.get_robustcov_results(cov_type="cluster", groups=estimation["prefcode"])
        names = list(base.params.index)
        index = names.index("avg_relgrowth")
        target = published[spec_id]
        rows.append({
            "spec_id": spec_id,
            "term": "avg_relgrowth",
            "estimate": float(fitted.params[index]),
            "std_error": float(fitted.bse[index]),
            "p_value": float(fitted.pvalues[index]),
            "nobs": int(fitted.nobs),
            "df_resid": float(fitted.df_resid),
            "clusters": int(estimation["prefcode"].nunique()),
            "published_estimate": target["estimate"],
            "published_std_error": target["std_error"],
            "published_nobs": target["nobs"],
            "estimate_abs_delta": abs(float(fitted.params[index]) - target["estimate"]),
            "std_error_abs_delta": abs(float(fitted.bse[index]) - target["std_error"]),
        })
    results = pd.DataFrame(rows)
    results.to_csv(output / "table2_lpm_results.csv", index=False)

    yerr = 1.96 * results["std_error"]
    fig, axis = plt.subplots(figsize=(6.5, 4))
    axis.errorbar(results["estimate"], results["spec_id"], xerr=yerr, fmt="o", color="#235789", capsize=4)
    axis.axvline(0, color="#666666", linewidth=1)
    axis.set_xlabel("GDP-growth coefficient (95% CI)")
    axis.set_ylabel("LPM specification")
    axis.set_title("Mayor promotion and relative GDP growth")
    fig.tight_layout()
    fig.savefig(output / "table2_lpm_coefficients.png", dpi=180)
    fig.savefig(output / "table2_lpm_coefficients.svg")
    plt.close(fig)

    artifacts = []
    for path in sorted(output.iterdir()):
        if path.is_file():
            artifacts.append({"path": path.name, "bytes": path.stat().st_size, "sha256": digest(path)})
    receipt = {
        "schema_version": "replication-receipt/1.0",
        "status": "complete",
        "paper_title": "Does meritocratic promotion explain China's growth?",
        "engine": "python",
        "scope": "Table 1 summaries and Table 2 LPM columns 1-3",
        "source_sha256": digest(source),
        "source_records": len(data),
        "artifacts": artifacts,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
