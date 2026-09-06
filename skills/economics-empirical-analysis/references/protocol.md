# Empirical workflow and handoff

## Research design before computation

Record question, observational unit, population, dependent variable, exposure/treatment, time scale, estimand, sampling/weights, design assumptions and literature-project ID. This v1 accepts a question and explicit model list for execution; it cannot infer valid identification. Treat unspecified weights/design as unresolved, not as permission to call an association causal. Restrict real-data summaries in chat to aggregates and avoid exposing household identifiers.

Logical responsibilities (not a claim of seven separately executed models): coordinator; data/provenance custodian; measurement/cleaning; identification reviewer; Python/Stata executor; replication/robustness auditor; tables/writing handoff. Use separate agents only when authorized and useful; otherwise stage these responsibilities locally.

## Data and run layout

`request.json → raw/ + metadata/ → processed/ → models/<spec_id>/ → results/ → bundle.json`.

Each input path is relative to the request file unless absolute. CSV identifiers should declare `dtypes`; Excel sheet must be named and identifiers requiring leading zeros must already be text or explicitly documented. Dates and Stata value labels are stored as metadata; analysis CSV is not a lossless interchange of all Stata attributes. Original DTA is always preserved. Tagged missing values fail with a request for a documented recode instead of being silently collapsed.

All primary keys must be unique/nonmissing as declared. Joins are explicit left joins with `one_to_one` or `many_to_one` validation, nonmissing keys and nonoverlapping non-key columns. Join coverage is logged, unmatched records are not silently discarded. Filters, code-to-missing mappings, and model complete-case losses are recorded. Each model identifies its own sample by source row indices; comparisons must check sample equality.

Models are explicit design matrices: outcome, numeric regressors, optional categorical FE, covariance and cluster field. Fail on nonnumeric/nonfinite values, zero residual degrees of freedom or rank deficiency; do not silently drop regressors. Many FE levels can exhaust memory; current dummy approach is bounded and not intended for large high-dimensional panels. Cluster inference with few clusters needs specialist review even when computation succeeds. No default stars, winner selection, or automated hypothesis hunting.

## Multiple rounds

Before results, register `spec_id`, purpose (`primary`, `robustness`, `exploratory`) and rationale. Changes create a new run ID linked by `parent_run_id`. Do not overwrite prior outputs. Retain failures and null findings. For confirmatory families specify multiplicity correction before inference. Bootstrap/permutation placebos require a justified assignment scheme, seed, repetitions and rejection criteria; they are not generic random shuffles. Advanced DID (especially staggered timing), IV diagnostics, RD bandwidth, survey weighting, nonlinear models and mediation require method-specific implementations and tests before claiming support.

## Downstream acceptance

`bundle.json` contains request/source/code hashes, environment versions, relative artifact paths and model statuses. A writing agent checks `verify`, then reads coefficients together with CI, covariance type, N, sample exclusions, unit definitions and limitations. Generated figures show coefficients with 95% CIs, not causal confirmation. Failed/partial bundles cannot be passed as completed analyses. Publication disclosure/rounding and small-cell suppression remain a human-reviewed downstream step.

## Upload and cloud backup gate

Local intake is implemented. Remote data connectors are not configured. Cloud backup remains `needs-human`: choose provider (e.g. institutional storage or a private S3-compatible destination), confirm account/region, license, consent, approved paths, encryption/access policy and retention. Never put raw data or secrets on public GitHub. DVC metadata and a configured remote are optional future integrations, not proof of a completed backup. Only read-back/hash verification can close cloud backup status; local ZIP is neither encrypted nor off-device protection. Credentials go to a provider's approved local credential mechanism, never JSON requests or chat.
