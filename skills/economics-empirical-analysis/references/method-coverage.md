# Method coverage and admission policy

Method names are not capabilities. Admit a method only after its estimand, identifying assumptions, data requirements, uncertainty calculation, diagnostics and cross-software behavior have a tested implementation.

## Certified in the bundled runner

- descriptive statistics;
- numeric OLS;
- categorical fixed-effect dummy absorption for bounded designs;
- HC1 and HC3 covariance;
- one-way clustered covariance;
- CSV, XLSX and DTA intake under the constraints in `protocol.md`;
- coefficient tables and plots with Python--Stata--R certificates for the tested specifications.

Do not generalize these certificates to other estimators, multi-way clustering, survey designs or large high-dimensional panels.

## Staged adapters

The following are priority extensions, not current bundled capabilities:

| Family | Minimum admission evidence | Candidate maintained implementation |
| --- | --- | --- |
| modern DID and event studies | timing cohorts, never-treated definition, anticipation, pre-trend diagnostics, aggregation weights | `pyfixest`, Callaway--Sant'Anna/Stata or R equivalents |
| IV and weak-instrument robust inference | first stage, exclusion argument, weak-IV diagnostics, clustered inference | maintained Stata/R/Python IV packages |
| RD | bandwidth, polynomial order, manipulation and covariate diagnostics, robust bias correction | `rdrobust` |
| synthetic control and SDID | donor-pool rules, pre-fit, placebo inference, tuning provenance | maintained synth/SDID packages |
| double/debiased ML | sample splitting, nuisance learners, score, overlap and sensitivity | `DoubleML` |
| nonlinear outcomes | estimand scale, marginal effects, separation/zero issues | PPML/logit/probit/count packages |
| survey/complex samples | strata, PSU, weights, finite-population rules | survey-aware Stata/R packages |
| spatial/network models | exposure graph, dependence structure, permutation/inference plan | design-specific implementation |
| panel GMM/dynamic panels | moment conditions, instrument proliferation, serial-correlation tests | maintained Stata/R packages |
| distributional methods | target quantile/decomposition, bootstrap design | maintained quantile/decomposition packages |

## Admission checklist

1. Register the question and estimand before choosing software.
2. Record a canonical published or official reference and a maintained implementation.
3. Build a synthetic truth test and at least one licensed/public benchmark.
4. Compare coefficients, samples and uncertainty with a second engine where practical.
5. Add a schema-valid receipt, diagnostics and failure states.
6. Document unsupported variants and version pins.
7. Only then move the method from staged to certified.

Useful upstream implementations include `py-econometrics/pyfixest`, `rdpackages/rdrobust` and `DoubleML/doubleml-for-py`. Their availability does not itself certify an adapter in this repository.
