# Research OS v1 Roadmap

The roadmap is organized as vertical release gates. A schema, prompt, adapter stub or mock-only test cannot advance a capability.

## v0.12 — Production Runtime

Already completed in development:

- framework-neutral `SandboxBackend` with tested `LocalRestrictedBackend` and staged `DockerSandboxBackend`;
- byte-exact cross-platform agent artifact writing;
- structured recoverable tool errors while permission errors remain human gates;
- reviewer verification contracts without producer hidden reasoning;
- minimal backward analysis chain and tamper test;
- real Codex public-data failure→repair→verification→LaTeX-source vertical slice.

Release gate still required:

- Docker live isolation certificate;
- real LaTeX compiler certificate;
- restart during a live long-running model/tool task;
- scholarly/data external-tool E2E;
- predeclared v0.12 thresholds and full regression.

## v0.13 — Research Compiler

1. ADR for compiler/model responsibility.
2. Versioned `ResearchSpec`, `CandidateResearchDesign`, `HypothesisGraph` and `DataRequirement` schemas.
3. IdeaCompiler proposal adapter with deterministic schema and policy validation.
4. Separate Novelty, Feasibility, Data Availability and Identification receipts.
5. Minimal public benchmark: short idea → multiple designs → evidence-backed gate outcomes. Exact-prior-study and missing-data cases must fail closed.

No design is selected because it produces a desirable sign or significant coefficient.

## v0.14 — Scientific Experiment Manager

1. `SocialScienceExperimentTree` and bounded branch budget.
2. `AnalysisPlan` / `SpecificationRegistry` with immutable confirmatory versions.
3. Exploratory-by-default new analyses and approval-gated promotion.
4. Predeclared specification multiverse with full distribution reporting.
5. Branch scoring limited to identification/evidence/reproducibility/information/cost criteria.
6. Failure, falsification and negative-result benchmark cases.

## v0.15 — Autonomous Manuscript

1. Full data chaining through transformations, merges, filters, estimates, tables and claims.
2. `trace-claim CLAIM_ID` CLI.
3. Typed ClaimGraph and evidence contracts by claim class.
4. Independent Literature, Identification, Statistical, Reproducibility and Writing/Claim review receipts.
5. Bounded reviewer-rejection revision loop.
6. Compiled journal-neutral LaTeX and reproducibility package.

## v1.0 — Autonomous Research Agent

The release benchmark begins with only a human idea and a lawful public-data environment. Thresholds are frozen before execution. The system must discover and verify literature/data, compare designs, execute and diagnose analysis, preserve failures, run falsification/robustness, write qualified conclusions, rerun reproducibly and stop at the human release gate.

Hard zero-tolerance metrics:

- false completion = 0;
- fabricated citation = 0;
- untracked numeric claim = 0;
- unverified full-text claim = 0;
- significance-driven confirmatory specification change = 0;
- unauthorized external/restricted-data action = 0.

## Method certification lane

Modern DID/event study, IV/weak-IV, RD/rdrobust, synthetic control, SDID, DML, survey, spatial, network/interference and dynamic-panel capabilities advance separately. Each needs a synthetic known-truth test, public replication, failure/assumption test, numeric lineage, and cross-engine test when applicable. A generic preflight PASS never equals estimator certification.
