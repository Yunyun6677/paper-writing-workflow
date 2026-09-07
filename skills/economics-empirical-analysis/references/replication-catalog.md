# Replication method catalog

This catalog is a queue, not a claim that every paper has already been executed. `verified-source` means the paper and replication deposit were checked at the publisher, author, or institutional repository. `executed` requires a local report, completion marker, and artifact hashes.

| Paper | Research link | Main empirical design | Official/author source | Status |
| --- | --- | --- | --- | --- |
| Autor, Dorn & Hanson (2013), *The China Syndrome* | Import competition → local labor markets | weighted 2SLS, shift-share exposure, clustered inference | author replication archive; DOI `10.1257/aer.103.6.2121` | executed: Table 3 (1–6) |
| Card & Krueger (1994), *Minimum Wages and Employment* | policy shock → establishment employment | two-period DID, regression adjustment, sensitivity analysis | David Card author data page; DOI `10.2307/2118030` | executed: Table 3 DID and Table 4 (1–5) |
| Martinez-Bravo et al. (2022), *The Rise and Fall of Local Elections in China* | village elections → policy and autonomy | staggered policy adoption/DID, organizational mechanism tests | AEA/openICPSR `10.3886/E166506V1` | verified-source; access review pending |
| Autor et al. (2020), *Importing Political Polarization?* | China trade exposure → electoral outcomes | 2SLS, geographic exposure, heterogeneous political outcomes | AEA/openICPSR `10.3886/E119547V3` | verified-source; access review pending |
| Choi et al. (2024), *Local Economic and Political Effects of Trade Deals* | NAFTA exposure → employment and voting | event study/DID, exposure design, heterogeneity | AEA/openICPSR `10.3886/E195983V1` | verified-source; access review pending |
| Rose (2004), *Do We Really Know That the WTO Increases Trade?* | GATT/WTO membership → bilateral trade | gravity OLS, year/partner effects, clustered SE, robustness families | author data page; DOI `10.1257/000282804322970724` | verified-source; large legacy archive queued |
| Coşar & Fajgelbaum (2016), *Internal Geography, International Trade, and Regional Specialization* | external integration → Chinese regional specialization | structural model, calibration/estimation, counterfactuals | AEA replication package; DOI `10.1257/mic.20140145` | verified-source; computational audit queued |
| Yang et al. (2023), *Unraveling Controversies over Civic Honesty Measurement* | experimental treatment → alternative honesty outcomes in China | field experiment, balance tests, covariate-adjusted OLS with HC1, survey figure | authors' public GitHub deposit; DOI `10.1073/pnas.2213824120` | executed in Python: Tables 1–2 and Figure 1; Stata parity pending |
| Wiebe (2020), *Does Meritocratic Promotion Explain China's Growth?* | relative GDP growth → mayor promotion | LPM with high-dimensional FE and clustered SE; conditional/ordered logit; specification curve | author's public GitHub archive and paper | partially executed: Table 1 and Table 2 LPM (1–3) in Python; original Stata and nonlinear models pending |
| He & Wang (2017), *Do College Graduates Serving as Village Officials Help Rural China?* | graduate village officials → poverty-program delivery | staggered/two-way FE DID, event study, clustered and bootstrap inference | AEA/openICPSR `10.3886/E113682V1` | verified-source; automatic download blocked by browser challenge; human handoff |

## Method-learning rules

- Port an estimator only after recording estimand, unit, sample construction, weights, fixed effects, uncertainty, identifying assumptions, software and expected target output.
- Separate *numerical reproduction* from *design validation*. Matching a table does not validate exclusion restrictions, parallel trends, bandwidth choice or external validity.
- Prefer small, public, executable slices that add a new method certificate. Do not claim complete-paper replication when only selected tables run.
- For event studies and staggered adoption, do not treat a generic two-way fixed-effect coefficient as a universal implementation. Add cohort/timing diagnostics and method-specific tests first.
- For structural models, record solver, starting values, tolerances, random seeds and hardware-sensitive steps before attempting cross-language parity.
