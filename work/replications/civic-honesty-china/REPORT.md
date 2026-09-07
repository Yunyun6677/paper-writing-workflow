# Yang et al. (2023) selected-results replication

**Status:** Python and Stata replication complete for Table 2 columns 1–9; Python also reproduces Table 1 and the two-panel attitude figure. This is not a full-paper replication.

## Source and scope

Qian Yang et al., “Unraveling Controversies over Civic Honesty Measurement: An Extended Field Replication in China,” *PNAS* 120(29), 2023, DOI `10.1073/pnas.2213824120`.

The authors' public GitHub deposit provides Stata 16 code, two DTA files, CSV equivalents and a codebook. The source repository was pinned at commit `5d7c9eeba928ba101252f221d114f05d64f116fc`. The archive has no repository-level license declaration, so its row-level data and original code are used locally but not redistributed here. This case publishes independently written adapters and aggregate outputs only.

The executed slice covers:

- Table 1 treatment-group means, standard deviations and Pearson chi-squared tests for email response, wallet recovery and complete wallet recovery.
- Table 2's nine OLS specifications with city/institution fixed effects, HC1 standard errors, recipient/environment controls, rice share and treatment-covariate interactions.
- Figure 1's attitude rates for field employees and a national survey.

## Results

The no-money versus money email response rates are `22.18%` and `32.66%`; the Pearson test gives `p=0.00887`. Complete wallet recovery falls from `75.00%` to `65.73%` (`p=0.02373`), while overall wallet recovery changes little (`p=0.66550`). These reproduce the published Table 1 values.

For Table 2, the money-treatment coefficient is `10.2137` percentage points in column 1 and `12.1425` in column 2, reproducing the paper's displayed `10.21` and `12.14`. All nine point estimates, HC1 standard errors, p-values and specification sample sizes are saved in `run/python/output-v3/table2_results.csv`.

Python and Stata agree on N and residual degrees of freedom exactly. Across all nine specifications, the maximum exported coefficient difference is `4.66e-7` and the maximum standard-error difference is `4.34e-8`, below the `1e-6` acceptance tolerance for Stata's initial seven-significant-digit CSV. Python uses asymptotic normal p-values for HC1 while Stata uses residual-degree-of-freedom t p-values; the maximum p-value difference is `0.00047` and is intentionally retained.

The figure initially failed because the host lacked Tk. The failed run was preserved locally; the final script uses a headless backend and exports both SVG and PNG. Missing Likert responses are excluded from denominators, matching Stata's `graph bar` behavior.

## Still incomplete

- Reproduce supplementary tables, the cross-country analysis and all manuscript figures.
- Audit randomization, multiple testing and the substantive validity of alternative honesty measures; numerical reproduction does not resolve those questions.
- Re-run the higher-precision Stata export when external-process approval is available; this is a serialization refinement, not an unresolved estimator difference.

## Re-run

Download the authors' repository, then pass the two DTA paths explicitly:

```powershell
./.venv-empirical/Scripts/python.exe work/replications/civic-honesty-china/run/python/replicate.py `
  --experiment PATH_TO_EXPERIMENT_DTA `
  --survey PATH_TO_SURVEY_DTA `
  --output work/replications/civic-honesty-china/run/python/new-run
```

Always use a new output directory. Do not upload the row-level source files to this repository.
