# Observability and evaluation

## Local-first observability

Every runtime run writes append-only spans to `<run_dir>/traces.jsonl`. The trace
schema is `research-trace-span/1.0`. It covers task selection, agent delegation and
observation, tool execution, artifact verification, retries/errors, and human
decisions.

Recorded fields include agent, actual or explicitly unreported model, task, tool
call metadata, input/output artifact references, latency, token usage, error class,
attempt budget, and decision identifier. The recorder deliberately omits raw
prompts, document text, dataset rows, tool arguments, credentials, and decision
rationales. Sensitive error messages are replaced with a hash and `[redacted]`.

The `attributes` object uses OpenTelemetry-compatible generative-AI names where
available (`gen_ai.operation.name`, `gen_ai.agent.name`,
`gen_ai.request.model`) and namespaced Research OS attributes. A callback exporter
is the narrow bridge for a future OpenTelemetry collector or OpenAI Agents trace
processor. Compatibility means the data can be mapped; it does not mean those SDKs
are required or that remote export is active.

`config/observability.json` defaults to:

- local trace enabled;
- content capture disabled and schema-forbidden;
- external export disabled;
- sensitive external export disabled even when an exporter is configured.

Changing an external-export setting is not sufficient authorization to transmit
restricted content. The invoking human gate must also approve the specific
operation, and v1 still exports metadata/artifact references only.

## Evaluation suite

`tests/agent-evals/` contains deterministic tests and fixtures. The default suite
uses synthetic records; a separate fixture reads only the checked-in public summary
of the Autor--Dorn--Hanson replication and explicitly preserves its limited scope.

| Gate | Metrics | Passing rule in the baseline fixture |
| --- | --- | --- |
| Literature | citation precision, DOI correctness, full-text verification, evidence entailment, duplicate rate | all positive rates 1.0 and duplicate rate 0 |
| Empirical | raw dataset hash preservation, coefficient/SE/sample reproduction, deterministic rerun | hashes match and every registered estimate is within declared tolerance |
| Agent | task completion, recovery, wrong routing, hallucinated completion, loop prevention | all tasks/recoveries pass, zero wrong routes/false completions, budgets not exceeded |
| Paper | numerical consistency, citation completeness, evidence coverage, audit pass rate | every registered claim and audit passes |

These are contract tests, not a claim that an LLM's scientific judgment has been
fully benchmarked. New public replication fixtures must identify the paper, exact
table/figure scope, source, license or redistribution boundary, and tolerance. User
private data must never be copied into the default test suite.

Run only the agent evaluations:

```powershell
.\.venv-empirical\Scripts\python.exe -m unittest discover -s tests/agent-evals -p "test_*.py" -v
```

Run all repository checks:

```powershell
.\.venv-empirical\Scripts\python.exe scripts/run_tests.py
```

Evaluation failures must remain visible. A failing metric may trigger a bounded
retry or replanning task, but it cannot be converted into a passing status by prose.
