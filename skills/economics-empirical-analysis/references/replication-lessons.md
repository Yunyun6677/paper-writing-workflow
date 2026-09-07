# Replication lessons from executed cases

Read this reference when reproducing published code across Python, Stata or R.

## Sample before estimator

- Reconstruct the exact estimation sample and report N for every specification.
- `reghdfe` iteratively removes observations that are singletons in any absorbed fixed effect. Repeat removal until no new singleton appears; one pass is insufficient for multiple effects.
- Preserve missing-value rules, outcome scaling, weights and source duplicates. Never silently deduplicate because a codebook calls an identifier unique.

## Numerical parity has layers

Check in order: keys and units; N; point estimates; residual degrees of freedom; standard errors; p-values; published rounding. A coefficient match does not certify uncertainty. Clustered standard errors can differ because packages count absorbed degrees of freedom and apply finite-sample corrections differently.

Use these statuses:

- `complete`: declared scope ran and all acceptance checks passed.
- `partial`: useful declared subset ran, with missing exhibits or engines listed.
- `review-required`: code ran but a numerical, sample or design discrepancy remains.
- `blocked`: external access or authorization prevented execution; include a human handoff.

## Plotting on unattended machines

Use a headless graphics backend. A script that requires a desktop display is not automation-safe. Export both a vector format for publication and a PNG for quick inspection; inspect the rendered PNG before delivery.

## External code and data

Keep author archives in an ignored source directory unless redistribution permission is explicit. Publish independently written adapters, aggregate outputs, provenance URLs, source hashes and exact limitations. Record the source commit for mutable repositories.

Run external engines only after authorization. If an approval or browser challenge blocks a run, keep the planned command and target scope in the handoff; do not label it executed.
