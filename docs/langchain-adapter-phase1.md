# Phase 1: optional LangChain specialist adapter

Status: implemented and locally tested with a scripted chat model; **not live-provider certified**. This phase adds no LangGraph adapter, vector database, Redis cache, or provider checkpoint.

## Interface audit

| Existing boundary | Current behavior | LangChain mapping |
| --- | --- | --- |
| `ResearchState` / `ResearchRuntime` | Canonical state, task transitions, checkpoints, event trace, human gates | Unchanged. LangChain receives a reduced `AgentExecutionRequest`, never state write access. |
| `Task` / assignment | Typed DAG task gives role, capability, tool allow-list, contract and budget | `ResearchRuntime._agent_request()` packs these into the request. |
| `ModelAdapter` / `AgentExecutor` | Adapter returns an observation; Executor validates repository schema | `LangChainSpecialistAdapter` runs `create_agent`, returns one schema-valid observation. Two optional lifecycle hooks pass a scoped tool callback and reconstruct an ephemeral request after restart. |
| `ToolRegistry` | Native execution checks manifest, approval, sensitivity, input/output schema, timeout, idempotency and receipts | `ToolBridge` intersects the task allow-list, assigned runtime manifests and `config/tool-registry.json` before exposing any `StructuredTool`. Calls go back through the Runtime callback and ToolRegistry. |
| Evidence verification | Runtime checks output artifacts and scientific contracts before completing a task | Model `PASS` alone is never a completed canonical task. Existing verifier and artifact checks remain authoritative. |

The default/manual and Codex adapters retain their previous execution path. The optional LangChain package is not imported by the core runtime or needed to run other providers.

## Minimal adapter layout

- `base.py`: optional dependency boundary and harness/runner protocols.
- `model_factory.py`: explicit `provider:model` construction or injected model for tests.
- `schemas.py`: LangChain structured-output model plus repository JSON Schema validation.
- `specialist.py`: four-role `create_agent` harness, dynamically reading the assigned `SKILL.md` as the SOP source. It has no LangGraph checkpointer or store.
- `tool_bridge.py`: dynamic, fail-closed tool exposure and scoped Runtime callback.

The four mappings are:

| Role | Capability source | Agent responsibility |
| --- | --- | --- |
| Literature | literature-review and assigned Chinese/international acquisition Skills | Retrieval and evidence proposals |
| Empirical | empirical-analysis Skill | Analysis/diagnostic proposals and permitted engine calls |
| Writing | paper-workflow `:writing` capability | Draft proposals based on approved artifact context |
| Reviewer/Verifier | paper-workflow `:audit` capability | Independent artifact-only review proposals |

Skill text is loaded from the existing file at execution time, not copied into Python constants. Role-to-capability checks reject a writing assignment that tries to load the audit capability. The `ContextPacker` and Runtime still decide what artifacts a specialist may see.

## Control and failure behavior

```text
ResearchTask → reduced AgentExecutionRequest → permitted ToolBridge tools
             → LangChain create_agent(model/tool loop)
             → structured_response → schema validation
             → AgentExecutor → ResearchRuntime scientific verification
             → canonical transition / retry / human gate
```

Unknown, staged, unassigned, sensitivity-incompatible and permission-drifted tools fail closed before binding. Tool execution uses the existing Runtime callback, so the native Tool Registry still owns side effects and receipt creation. A tool exception is returned as an explicit failed result; even if the model says `PASS`, the adapter downgrades it to `FAIL_TRANSIENT`. A tool response of `needs-human` becomes `BLOCKED` with an explicit human handoff, not an ordinary retry. Model-declared artifacts must match an actual bound tool result; model-authored tool receipts are rejected. Malformed observations and provider failures cannot complete tasks. A generated tool call outside the assignment is rejected. The provider holds no canonical state; losing its in-memory request map does not change ResearchState, and a persisted assignment can be restored by `AgentExecutor.resume()`.

The adapter rejects sensitive content by default and rejects enabled LangSmith hosted tracing. Live credentials require an explicit deployment decision. It does not supply process-level model cancellation, a hard token/cost enforcement boundary, an external-model certification, or a provider-independent persistence mechanism for an in-flight LangChain turn. Existing Runtime step limits and tool timeouts still apply; the `create_agent` recursion limit bounds the internal loop.

## Local validation

`tests/test_langchain_adapter.py` covers unknown/disallowed/hallucinated tools, four specialist Skill mappings, malformed response, model and tool failures, invented-artifact rejection, `needs-human` handoff, actual `create_agent` tool loop using a scripted model, Runtime artifact registration, provider-session loss, and the unchanged disabled-adapter path. The optional suite requires `requirements-langchain.txt`; core tests remain runnable without it. No private research data, live provider key, or external side effect is used.

## Proposed phase 2 (design only; not implemented)

Introduce an optional LangGraph **execution-only** adapter only if a measured use case needs resumable, bounded model/tool turns beyond this harness. Its graph would contain transient `assignment_id`, local message cursor and pending tool-call IDs, never canonical evidence, approvals or ResearchState. Every graph node would call the current ToolBridge, return a StructuredObservation proposal, and let ResearchRuntime perform all transitions. A LangGraph checkpoint would be treated as a disposable accelerator: deletion must trigger reconstruction from the persisted assignment, artifacts, idempotency ledger and event trace. Required tests before implementation: checkpoint deletion/replay, duplicate side-effect prevention, verifier rejection, human interrupt/resume, sensitivity policy, and cross-adapter equivalence. This design does **not** change ADR-001's canonical-state decision.

API basis: [LangChain `create_agent`](https://docs.langchain.com/oss/python/langchain/agents), [structured output](https://docs.langchain.com/oss/python/langchain/structured-output), and [tools](https://docs.langchain.com/oss/python/langchain/tools).
