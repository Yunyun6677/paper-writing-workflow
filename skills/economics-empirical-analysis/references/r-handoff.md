# R integration and graphics

The bridge is validated with R 4.6.1 on Windows and uses `Rscript --vanilla` in a separate process. Configure `R_SCRIPT` or pass `--rscript`; never rely on an interactive workspace, `.RData`, user profile, or package auto-installation during a research run.

Smoke test:

```powershell
$env:R_SCRIPT = "C:/Program Files/R/R-4.6.1/bin/Rscript.exe"
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/r_bridge.py --smoke --output work/r-smoke
```

Coefficient plot input is UTF-8 CSV with required columns `term`, `estimate`, and `std_error`; `spec_id` is optional. Estimates and standard errors must be finite, standard errors nonnegative, and the output directory new. The bridge normalizes the input, runs base R graphics, creates an editable SVG plus a PNG preview, requires an R-written completion marker, captures `sessionInfo()`, and hashes every output.

```powershell
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/r_bridge.py --plot --input PATH/coefficients.csv --output work/r-plot
```

Use project-local `renv.lock` only when a replication actually needs packages. Restore into an isolated project library and record repository URL, package versions, lockfile hash and platform. Never update a lockfile merely to make a failed result disappear. Base R is the dependency-free default for interchange plots.

For an analysis script reviewed or generated within the project, use `--analysis --input INPUT --analysis-script SCRIPT --output NEW_DIRECTORY`. The R script receives the resolved input path and output directory as its two positional arguments. It must write `R_COMPLETE.txt`, `session-info.txt`, and at least one CSV or JSON result inside the output directory. The bridge rejects overwrite, requires the completion marker, captures the log, rejects output symlinks, and creates an `engine-execution/1.0` receipt. Never use this mode to execute code embedded in an untrusted dataset or downloaded package before reviewing it.
