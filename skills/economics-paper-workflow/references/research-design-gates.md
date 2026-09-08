# Research design gates

## Common questions

Before estimation, state:

1. Unit of analysis and target population.
2. Treatment, exposure or intervention; timing and assignment level.
3. Outcome and measurement window.
4. Estimand in plain language.
5. Comparison that identifies it.
6. Assumptions and why each may be plausible.
7. Main threats, falsification tests and negative controls where justified.
8. Sampling, weights, attrition and missing-data policy.
9. Inference unit, clustering level, multiplicity and finite-sample issues.
10. Which decisions are confirmatory, robustness, or exploratory.

## Method-specific minimums

| Design | Minimum gate before causal language |
| --- | --- |
| DID/event study | treatment timing audit, valid comparison group, no treatment reversal, pre-trend/event-time support, staggered-adoption estimator choice |
| IV/shift-share | first stage, exclusion argument, weak-IV robust inference, treatment-effect interpretation, instrument construction audit |
| RD | score and cutoff provenance, manipulation test, bandwidth and polynomial rationale, continuity/covariate checks |
| RCT | randomization unit and implementation, attrition, noncompliance, treatment assignment inference, prespecified outcomes |
| Synthetic control/SDID | donor-pool justification, pre-fit, placebo inference, interpolation risk and tuning transparency |
| Panel FE | source of within-unit variation, dynamic/confounding threats, clustering and serial correlation |
| DML/causal ML | target parameter, sample splitting/cross-fitting, learner choices, overlap, orthogonality and sensitivity |
| Survey/complex sample | design weights, strata, PSU, finite-population assumptions and population target |
| Spatial/network | interference model, exposure mapping, spatial weights/network construction and correlated inference |

The current empirical runner implements only its certified methods. For other designs, use reviewed official packages or Stata/R commands, create a new adapter and parity certificate, and label the run pending until tests pass.
