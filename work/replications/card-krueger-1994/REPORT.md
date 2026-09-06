# Card–Krueger (1994) selected-results replication

**Status:** complete for Table 3's headline difference-in-differences comparison and Table 4 columns 1–5. This is not a claim that every table, robustness check, or interpretation in the paper was reproduced.

## Paper and source material

David Card and Alan B. Krueger, “Minimum Wages and Employment: A Case Study of the Fast-Food Industry in New Jersey and Pennsylvania,” *American Economic Review* 84(4), 1994, 772–793. The working-paper version is [NBER Working Paper 4509](https://doi.org/10.3386/w4509); the journal article is indexed as JSTOR 2118030.

The paper and `njmin.zip` were downloaded from [David Card's author data page](https://davidcard.berkeley.edu/data_sets.html). The archive contains 410 fixed-width survey records, a codebook, survey instruments, and the authors' SAS checking program. Source binaries and the paper PDF are kept locally but are not redistributed in this repository; their hashes are recorded in `replication_bundle.public.json`.

## Empirical design reproduced

New Jersey raised its minimum wage while neighboring Pennsylvania did not. Full-time-equivalent employment is defined as full-time workers plus managers plus one-half of part-time workers. The selected replication covers:

- Table 3: before/after means by state and the headline two-period difference in differences.
- Table 4, models 1–2: change in employment on a New Jersey indicator, without and with chain/ownership controls.
- Table 4, models 3–5: change in employment on the initial proportional wage-gap measure, with the published control sets.

These are two-period DID/regression-adjustment calculations with conventional OLS standard errors, matching the authors' supplied SAS program. The exercise does not resolve later debates about survey measurement, comparison groups, functional form, or external validity.

## Data audit

The public file has 410 records and 409 distinct `sheet` values. `sheet=407` occurs twice. The codebook calls the field a unique store identifier, while the paper explains that two restaurants were interviewed twice because duplicated phone listings were not recognized. The pipeline therefore preserves all source rows and creates `source_row` as the stable record key; it does not silently deduplicate.

The Table 4 analysis sample contains 357 records, matching the paper. The calculated headline Table 3 change-in-means DID is `2.753606` FTE employees, which rounds to the paper's `2.76` after allowing for displayed component rounding.

## Table 4 results

| Model | Target | Estimate | Standard error | N | Published rounded target |
| --- | --- | ---: | ---: | ---: | ---: |
| m1 | New Jersey | 2.325831 | 1.191596 | 357 | 2.33 (1.19) |
| m2 | New Jersey + chain/ownership controls | 2.303860 | 1.195532 | 357 | 2.30 (1.20) |
| m3 | Wage gap | 15.652890 | 6.080237 | 357 | 15.65 (6.08) |
| m4 | Wage gap + chain/ownership controls | 14.915674 | 6.205335 | 357 | 14.92 (6.21) |
| m5 | Wage gap + chain/region controls | 11.913064 | 7.394409 | 357 | 11.91 (7.39) |

The maximum absolute distance from the paper's two-decimal displayed estimates and standard errors is `0.00467`, below the `0.005` rounding bound.

## Cross-engine verification

The same analysis table and five specifications ran in Python 3/statsmodels, Stata/SE 16, and R 4.6.1. All engines report identical N and residual degrees of freedom.

- Maximum coefficient difference across any engine pair: `1.21e-13`.
- Maximum standard-error difference across any engine pair: `4.80e-14`.
- Python, Stata, and R completion status: complete.
- R coefficient plot: generated as SVG and PNG with an `engine-execution/1.0` receipt.

This establishes numerical parity for this narrow OLS/DID slice. It is not a certificate for staggered DID, modern event-study estimators, clustered inference, or arbitrary R packages.

## Re-run

Download and extract `njmin.zip` from the author page, then run from the repository root:

```powershell
./.venv-empirical/Scripts/python.exe work/replications/card-krueger-1994/run/python/replicate.py `
  --data PATH_TO/public.dat `
  --output work/replications/card-krueger-1994/run/python/new-run
```

Pass the resulting `analysis.csv` to the R and Stata scripts using explicit paths. Set `R_SCRIPT` and `STATA_EXE` to licensed local executables; neither software installation nor any license credential is included in the repository. Run `run/verify_parity.py` against the three `table4_results.csv` files. Every re-run should use a new output directory and preserve failed attempts.

## Limitations

- Only the selected Table 3 comparison and Table 4 columns 1–5 were reproduced.
- The pipeline follows the source program's sample and conventional standard errors; alternative inference is a separate robustness exercise.
- The canonical `analysis.csv` is derived from author data and is not redistributed. Users must obtain the source from the author page.
- Numerical agreement does not establish that the original causal interpretation is uniquely warranted.
