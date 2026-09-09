# Advanced-method source assessment

Reviewed 2026-09-09. Prefer tagged releases and official documentation over copied notebooks. Pin versions inside each research project and preserve an engine receipt. GitHub availability is not a certificate in Research OS.

| Family | Preferred upstream | Why selected | Important boundary |
| --- | --- | --- | --- |
| modern DID/event study | [PyFixest](https://github.com/py-econometrics/pyfixest), [did](https://github.com/bcallaway11/did), Stata `csdid`/`eventstudyinteract` | heterogeneous timing estimators and event-time output | do not default to TWFE under heterogeneous effects |
| IV | [linearmodels](https://github.com/bashtage/linearmodels), [ivmodels](https://github.com/mlondschien/ivmodels), Stata `ivreg2` | 2SLS plus weak-IV-robust tests | first-stage significance does not prove exclusion; multi-endogenous diagnostics need care |
| RD | [rdrobust](https://github.com/rdpackages/rdrobust) | maintained Python/R/Stata implementations of bandwidth, bias correction and plots | global high-order polynomials are not a substitute for local diagnostics |
| synthetic control | [scpi](https://github.com/nppackages/scpi) | estimation and uncertainty procedures across Python/R/Stata | pre-fit and donor sensitivity are part of validity, not cosmetic plots |
| SDID | [synthdid](https://github.com/synth-inference/synthdid) | reference implementation of unit/time-weighted SDID | canonical implementation assumes block adoption; staggered extensions need separate validation |
| DML | [DoubleML](https://github.com/DoubleML/doubleml-for-py) | explicit scores, cross-fitting and Python/R implementations | learner prediction quality does not itself identify a causal parameter |
| complex survey | R `survey`, Stata `svy`, [svy](https://github.com/samplics-org/svy) as a candidate Python bridge | design-based weights, strata, PSU and replicate methods | ordinary WLS with weights is not full complex-survey inference |
| spatial econometrics | [PySAL spreg](https://github.com/pysal/spreg), [esda](https://github.com/pysal/esda) | weights, diagnostics, spatial lag/error models and impacts | weights construction and islands must be frozen and justified |
| network/interference | [PySAL spaghetti](https://github.com/pysal/spaghetti) for graph structure plus design-specific inference | graph and topology support | no universal network estimator; exposure mapping follows the assignment mechanism |
| dynamic panel | [pydynpd](https://github.com/dazhwu/pydynpd), Stata `xtabond2`, R `pdynmc` | difference/system GMM and cross-engine benchmarks | instrument proliferation and weak moments can invalidate apparently precise output |

Do not execute source cloned from GitHub without dependency, license and code review. Do not install optional method packages into the base environment automatically. Use a project-local lockfile, synthetic test, public benchmark and cross-engine receipt before changing an adapter status from staged to certified.
