# Stata 16 integration

The bridge has been validated with Stata/SE 16. Set `STATA_EXE` or pass `--stata-exe` with the location of an authorized Stata executable. Never store or reproduce a license serial or a contributor's machine-specific path. Stata 16 uses the batch bridge because official PyStata requires Stata 17 or later.

For a future Stata 17+ upgrade, the official `stata_setup` package locates the pystata module shipped with Stata. Do not install an unrelated PyPI package named pystata. Keep the batch adapter as the auditable fallback and compare both engines before switching defaults.

Validated smoke test:

```powershell
$env:STATA_EXE = "C:/Program Files/Stata18/StataSE-64.exe"
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/stata_bridge.py --smoke --output work/stata-smoke
```

This starts a separate Stata batch process with synthetic data, retains the `.do`, text log, DTA result and hashes, and checks the numerical result plus completion marker. It does not control or clear an already open Stata session.

The end-to-end parity run at `work/stata-integration-v1/stata-round-03` is the current certificate for v1 OLS/HC1 and categorical fixed effects with one-way clustered covariance. It compares coefficients and standard errors, records deltas in `stata/receipt.json`, and verifies every bundle artifact by SHA-256. Stata CSV intake must use `import delimited ..., asdouble`; omitting `asdouble` previously created avoidable precision differences. The certificate does not cover DID, IV, RD, survey estimation, high-dimensional fixed effects, or other staged methods.

MCP alternatives are future adapters. Add them only after checking platform/version and local permissions. In-memory user sessions must not be cleared. Cloud remains independently blocked until its own authorization is supplied.
