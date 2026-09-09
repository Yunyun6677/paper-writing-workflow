# Research Agent Runtime v0.10

## 1. Responsibility boundary

The five existing `SKILL.md` files remain the source of domain policy, SOPs, evidence rules, and specialist constraints. They are capabilities, not persistent agents. `research_os/` owns run state, planning, scheduling, tool dispatch, observation, verification, recovery, checkpoints, and human gates. A successful orchestration step never proves that a specialist method or external tool succeeded.

The runtime uses one Research Director and four specialists: Literature, Empirical, Writing, and Reviewer/Verifier. Zotero, CNKI browser, bibliographic services, PDF parsing, Python, Stata, R, LaTeX, Git, schema validation, and artifact integrity are tools. MCP is preferred for interoperable services; local statistical engines remain native adapters.

## 2. Decision loop

```text
GOAL -> LOAD STATE -> PLAN -> SELECT NEXT TASK -> SELECT AGENT/TOOL
     -> EXECUTE -> OBSERVE -> VERIFY -> UPDATE STATE -> DECIDE

PASS               -> next ready task
FAIL_TRANSIENT     -> retry within max_attempts
FAIL_STRATEGY      -> bounded DAG re-plan
BLOCKED            -> human handoff
HIGH_RISK_DECISION -> human approval
GOAL_COMPLETE      -> independent final audit, never direct completion
```

Every persisted task contains `task_id`, `task_type`, `goal`, `dependencies`, `required_inputs`, `expected_outputs`, `assigned_agent`, `allowed_tools`, `status`, `retry_policy`, `timeout_seconds`, `stopping_condition`, `success_contract`, `failure_contract`, and `verification_rules`. Compatibility aliases remain for v0.9 readers, but canonical fields govern new runs.

Infinite loops are bounded by per-task `max_attempts`, per-task and global strategy-replan budgets, maximum total task count, maximum total runtime steps, tool timeouts, and explicit stopping/failure contracts. Exhaustion blocks the run and creates an auditable handoff rather than silently continuing.

## 3. Dynamic DAG and independent verification

The initial graph is only a plan. A verifier may return `FAIL_STRATEGY` with `replan: new_evidence` to append:

```text
review -> literature follow-up -> manuscript revision -> final audit
```

or `replan: robustness` to append:

```text
review -> empirical robustness -> manuscript revision -> final audit
```

The new nodes become dependencies of final audit and final approval. Cycles, unknown dependencies, unapproved agents, duplicate task IDs, and excessive task expansion are rejected. Verifier tasks must identify a producer and cannot use the same agent identity. Reviewer packets use an artifact-only context, preventing the worker's hidden reasoning from becoming review evidence.

## 4. Scientific guardrails

- Citation Guardrail requires citation keys, evidence references, bibliographic verification, and passed entailment.
- Fulltext Guardrail prevents metadata-only sources from being represented as read full text.
- Numerical Claim Guardrail requires a verified numeric-claim record and source artifact lineage.
- Causal Claim Guardrail requires passed identification or explicitly qualified language.
- Specification Guardrail blocks significance-driven or unapproved changes to sample, bandwidth, controls, standard errors, fixed effects, and outlier rules.
- Sensitive Data Guardrail blocks restricted/personal/confidential data from unauthorized external tools.

Guardrails consume structured artifacts. Model summaries are not substitutes for evidence. Deterministic reports validate against `schemas/guardrail-report.schema.json`.

## 5. Memory and durability

- Working Memory: current run context and reconstruction diagnostics.
- Project Memory: decisions and revision history across runs.
- Researcher Preference: language, output, and engine preferences; only references are stored for credentials.
- Evidence Memory: artifact IDs, hashes, schema references, and provenance. Summaries alone never count as evidence.

Long-term memory rejects secret/token/password/API-key fields and raw restricted-data content. Important transitions are atomically saved, appended to the event trace, and checkpointed. `pause` leaves the run inert; `resume` continues the same run; `reconstruct` rebuilds current context from state and verifies artifacts; `recover` restores the newest checkpoint whose content hash matches its filename.

## 6. Tool registry

`config/tool-registry.json` declares each tool's name, description, input/output schema, side effects, permission, retry policy, timeout, credential requirement, supported data sensitivity, determinism, verifier, adapter, and implementation status. `available` means callable by the runtime; `staged` means the interface is defined but production execution has not been certified. External writes and high-risk decisions require explicit human approval.

## 7. CLI lifecycle

```powershell
python scripts/research_agent.py init --manifest PROJECT_JSON --run-root .runtime/research-runs
python scripts/research_agent.py run --run-dir RUN_DIR --project-dir PROJECT_DIR
python scripts/research_agent.py pause --run-dir RUN_DIR --project-dir PROJECT_DIR --reason "researcher away"
python scripts/research_agent.py resume --run-dir RUN_DIR --project-dir PROJECT_DIR
python scripts/research_agent.py reconstruct --run-dir RUN_DIR --project-dir PROJECT_DIR
python scripts/research_agent.py recover --run-dir RUN_DIR --project-dir PROJECT_DIR
```

`observe` accepts either legacy `status` or the explicit v0.10 `outcome`. A new session needs the repository and run directory, not the previous chat transcript.
