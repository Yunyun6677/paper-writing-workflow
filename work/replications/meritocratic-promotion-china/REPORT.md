# Wiebe (2020) selected-results replication

**Status:** Python reconstruction complete for Table 1 and the linear-probability models in Table 2 columns 1–3. Original Stata execution and nonlinear models remain pending, so the overall case is partial.

## Source and scope

Michael Wiebe, “Does Meritocratic Promotion Explain China's Growth?”, 2020 dissertation chapter/working paper. The author archive was pinned at GitHub commit `bc82d1152fd228e206ab661dd02e64b9cca0d580`; the paper PDF was obtained from the author's research site.

The archive includes raw and analysis-ready mayor/prefecture data, Stata 16 code and local copies of required Stata packages. It has no repository-level license declaration, so source data and author code are not redistributed here.

The executed slice covers:

- Table 1 summary statistics on the paper's baseline estimation sample.
- Table 2 columns 1–3: linear-probability models of promotion on cumulative average relative GDP growth, with province-year and additional fixed effects and prefecture-clustered uncertainty.
- A coefficient-and-95%-interval plot for the three specifications.

## Results and discovered compatibility issue

Naive dummy-variable OLS initially returned `5658 / 5198 / 5173` observations instead of the paper's `5640 / 5172 / 5141`. The cause was `reghdfe`'s iterative deletion of singleton fixed-effect groups. After implementing the same iterative rule, every specification matches the paper's N exactly.

The reconstructed GDP-growth coefficients are:

| Model | Python | Paper |
| --- | ---: | ---: |
| LPM 1 | -0.033530 | -0.034 |
| LPM 2 | -0.090859 | -0.091 |
| LPM 3 | -0.060339 | -0.060 |

All point estimates match the displayed three-decimal targets. Python's clustered standard errors are `0.084775`, `0.089787`, and `0.108995`, versus displayed paper values `0.085`, `0.089`, and `0.108`. The last two exceed a strict three-decimal rounding match. The likely source is software-specific absorbed-degree-of-freedom and finite-cluster corrections, but this remains a hypothesis until the bundled Stata/reghdfe environment runs successfully.

## Still incomplete

- Run the author's Stata 16 archive and compare exact LPM standard errors.
- Reproduce conditional Logit and Ordered Logit columns 4–9.
- Reproduce specification curves, robustness, heterogeneity, connections, pollution, corruption and secretary analyses.
- Independently assess promotion measurement and the causal interpretation; the reported models are associational.

## Re-run

```powershell
./.venv-empirical/Scripts/python.exe work/replications/meritocratic-promotion-china/run/python/replicate.py `
  --data PATH_TO/promotion_national.dta `
  --output work/replications/meritocratic-promotion-china/run/python/new-run
```

Use a new output directory and keep the author's data outside Git.
