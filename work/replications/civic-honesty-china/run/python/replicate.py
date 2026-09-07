from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import chi2_contingency

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def outcome01(series: pd.Series) -> pd.Series:
    return series / 100 if series.max(skipna=True) > 1 else series


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--survey", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    experiment_path = Path(args.experiment).resolve()
    survey_path = Path(args.survey).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    output.mkdir(parents=True)

    data = pd.read_stata(experiment_path, convert_categoricals=False)
    survey = pd.read_stata(survey_path, convert_categoricals=False)
    required = {
        "money", "email", "wallet_recovery", "wallet_totalrecovery", "city",
        "institution", "male", "age40", "computer", "coworkers",
        "other_bystanders", "rice", "r_hnsty_nocontact", "r_hnsty_takeaway",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Missing experiment columns: {missing}")

    outcomes = ["email", "wallet_recovery", "wallet_totalrecovery"]
    table1_rows = []
    for outcome in outcomes:
        binary = outcome01(data[outcome])
        contingency = pd.crosstab(binary, data["money"])
        p_value = chi2_contingency(contingency, correction=False)[1]
        for money, group in data.assign(_outcome=binary).groupby("money"):
            table1_rows.append({
                "outcome": outcome,
                "money": int(money),
                "n": int(group["_outcome"].count()),
                "mean": float(group["_outcome"].mean()),
                "std_dev": float(group["_outcome"].std()),
                "pearson_chi2_p": float(p_value),
            })
    table1 = pd.DataFrame(table1_rows)
    table1.to_csv(output / "table1_results.csv", index=False)

    centered = ["male", "age40", "computer", "coworkers", "other_bystanders"]
    for variable in centered:
        data[f"dm_m_{variable}"] = data["money"] * (data[variable] - data[variable].mean())
    x1 = "male + age40 + computer + coworkers + other_bystanders"
    interactions = " + ".join(f"dm_m_{v}" for v in centered)
    x2 = f"rice + {x1} + {interactions}"
    specifications = [
        ("m1", "email", "money + C(city) + C(institution)"),
        ("m2", "email", f"money + {x1} + C(city) + C(institution)"),
        ("m3", "email", f"money + {x2} + C(city) + C(institution)"),
        ("m4", "wallet_recovery", "money + C(city) + C(institution)"),
        ("m5", "wallet_recovery", f"money + {x1} + C(city) + C(institution)"),
        ("m6", "wallet_recovery", f"money + {x2} + C(city) + C(institution)"),
        ("m7", "wallet_totalrecovery", "money + C(city) + C(institution)"),
        ("m8", "wallet_totalrecovery", f"money + {x1} + C(city) + C(institution)"),
        ("m9", "wallet_totalrecovery", f"money + {x2} + C(city) + C(institution)"),
    ]
    rows = []
    for spec_id, outcome, rhs in specifications:
        fitted = smf.ols(f"{outcome} ~ {rhs}", data=data).fit(cov_type="HC1")
        rows.append({
            "spec_id": spec_id,
            "outcome": outcome,
            "term": "money",
            "estimate": float(fitted.params["money"]),
            "std_error": float(fitted.bse["money"]),
            "p_value": float(fitted.pvalues["money"]),
            "nobs": int(fitted.nobs),
            "df_resid": float(fitted.df_resid),
            "covariance": "HC1",
        })
    table2 = pd.DataFrame(rows)
    table2.to_csv(output / "table2_results.csv", index=False)

    field_rates = [
        float(data["r_hnsty_nocontact"].dropna().isin([4, 5, 6]).mean() * 100),
        float(data["r_hnsty_takeaway"].dropna().isin([4, 5, 6]).mean() * 100),
    ]
    survey_rates = [float(survey["noemail"].mean() * 100), float(survey["takeaway"].mean() * 100)]
    figure_data = pd.DataFrame({
        "measure": ["Failing to contact", "Retaining the wallet"] * 2,
        "sample": ["Field employees"] * 2 + ["National survey"] * 2,
        "percent": field_rates + survey_rates,
    })
    figure_data.to_csv(output / "figure1_data.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
    for axis, (sample, frame) in zip(axes, figure_data.groupby("sample", sort=False)):
        axis.bar(frame["measure"], frame["percent"], color=["#444444", "#bbbbbb"])
        axis.set_title(sample)
        axis.set_ylim(0, 100)
        axis.tick_params(axis="x", rotation=15)
        for index, value in enumerate(frame["percent"]):
            axis.text(index, value + 2, f"{value:.1f}%", ha="center")
    axes[0].set_ylabel("Reporting rate (%)")
    fig.tight_layout()
    fig.savefig(output / "figure1.png", dpi=180)
    fig.savefig(output / "figure1.svg")
    plt.close(fig)

    artifacts = []
    for path in sorted(output.iterdir()):
        if path.is_file():
            artifacts.append({"path": path.name, "bytes": path.stat().st_size, "sha256": digest(path)})
    receipt = {
        "schema_version": "replication-receipt/1.0",
        "status": "complete",
        "paper_doi": "10.1073/pnas.2213824120",
        "engine": "python",
        "source_files": {
            "experiment": {"sha256": digest(experiment_path), "records": len(data)},
            "survey": {"sha256": digest(survey_path), "records": len(survey)},
        },
        "artifacts": artifacts,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
