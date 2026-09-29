# LangChain / LangGraph integration architecture audit

Status: design audit of `main` at `d411477` (2026-09-29). This document describes proposed boundaries, not certified scientific capability. PR-1 below is an incremental hardening of the LangChain adapter already on `main`; it does not recreate that adapter or change canonical state semantics.

## A. Current dependency map

```text
Human / CLI
    → ResearchRuntime (sole canonical transition authority)
        → StateBackend (File or SQLite): ResearchState + scientific checkpoints + ordered events
        → BoundedPlanner ← PlanningAdapter: validated TaskGraphProposal only
        → ContextPacker: role/dependency/hash/sensitivity-filtered artifact references
        → AgentExecutor → ModelAdapter: StructuredObservation proposal only
             → optional LangChain create_agent → scoped ToolBridge
        → ToolRegistry: permission, input/output schema, idempotency, receipt, timeout
             → native/external adapters → SandboxBackend for generated code
        → deterministic output checks / scientific guardrails
        → ScientificMemoryStore: rebuildable SQLite entity/relation index
        → local TraceRecorder

Filesystem artifacts + SHA-256 → state.artifacts (current artifact registry)
                            ↘ EvidenceVerifier rereads actual bytes/locators
                             ↘ ProvenanceGraph / analysis-chain verifier
```

`ResearchState` is a schema-validated JSON object. Its `artifacts` list is currently the canonical artifact registry; there is no separate `ArtifactRegistry` service. `ResearchRuntime._register_artifact` adds verified references only after `_verify_outputs` checks paths and hashes. `ScientificMemoryStore.ingest_state` follows a canonical save and is a rebuildable index, not an alternative state writer. The analysis `ProvenanceGraph` exists as a portable artifact, but automatic full-paper lineage is not yet implemented. `ContextPacker` currently ranks bounded excerpts lexically, and `EvidenceVerifier` checks source files and their hashes rather than trusting model status fields. `LocalRestrictedBackend` has process/path controls but is not OS-enforced network or filesystem isolation; Docker remains uncertified.

## B. Mapping to framework concepts

| Research OS | LangChain / LangGraph analogue | Authority limit |
| --- | --- | --- |
| `AgentExecutionRequest` + `ModelAdapter` | LangChain model/harness input | Reduced, per-task context only |
| `LangChainSpecialistAdapter` | `create_agent` model/tool loop | Returns observation; no state transition |
| `ToolRegistry` + `ToolBridge` | LangChain tools | Native registry is permission/side-effect authority |
| `PlanningAdapter` + `BoundedPlanner` | Planner/model proposal + validator | Proposal cannot directly mutate DAG |
| `ContextPacker` | Retriever/context assembly | Retrieval may rank; artifact access must be rechecked |
| `ResearchRuntime` task loop | LangGraph orchestration candidate | Runtime remains the only canonical control plane |
| `StateBackend` / scientific checkpoints | LangGraph checkpointer | Different lifetimes and authority; graph checkpoint disposable |
| `ScientificMemoryStore` | Long-term store/query graph | Index can be rebuilt; JSON artifacts remain authoritative |
| `EvidenceVerifier` / provenance | No framework substitute | Scientific fact checks remain independent |

The current optional LangChain harness has no checkpointer or store. It is tested with a scripted model, not a live-provider production certification. Existing manual/Codex paths remain supported.

## C. Minimal additional interfaces

1. **PR-1:** keep `ModelAdapter`; harden the existing LangChain adapter's observation boundary. No new canonical schema or model-session store is needed.
2. **Later retrieval PR:** a small `SemanticIndex` interface with `upsert_verified_chunk`, `query_candidates`, `delete_source`, and `rebuild`, returning candidate IDs/locators/scores, never verified claims. An `EmbeddingAdapter` may wrap LangChain embeddings behind provider-neutral metadata and sensitivity policy.
3. **Later cache PR:** a `CacheBackend` with typed namespace, partition, expiry, lineage dependencies and invalidate operations. Redis is one optional implementation, not an authority.
4. **Later graph PR:** an `ExecutionOrchestrator`/LangGraph adapter that consumes a persisted task assignment and returns StructuredObservation. It does not expose `save_research_state` or direct artifact approval.

Do not introduce these later interfaces into PR-1 merely as empty abstractions.

## D. Retain; do not rewrite

Retain `ResearchRuntime`, `ResearchState` and its migration rules, `StateBackend`, `BoundedPlanner`, `ModelAdapter`, `AgentExecutor`, `ToolRegistry`, `ContextPacker`'s security filter, `ScientificMemoryStore`, `EvidenceVerifier`, `SandboxBackend`, artifact hashing, idempotency records, human gates, local tracing, the five Skills and their SOP files. New retrieval/ranking may be plugged into context selection only **after** the current dependency, role, hash and sensitivity filters; it must never weaken them. ADR-001's canonical-state decision remains in force even though the long-term roadmap gives LangGraph an orchestration role.

## E. Proposed semantic-index record

The vector row is a search pointer, not a source document or evidence receipt:

| Field group | Proposed fields |
| --- | --- |
| Identity | `project_id`, `index_generation`, `chunk_id`, `source_artifact_id`, `source_sha256`, `chunk_sha256` |
| Locator | `source_type`, `page_start`, `page_end`, `section`, `char_start`, `char_end`, `locator_version` |
| Embedding | `embedding_provider`, `embedding_model`, `model_revision`, `dimension`, `normalization`, `embedding_version` |
| Access | `data_sensitivity`, `access_scope`, `license_class`, `external_embedding_authorized`, `retention_policy` |
| Lifecycle | `source_schema_version`, `chunker_version`, `indexed_at`, `superseded_at`, `tombstone` |

Use a stable `chunk_id = H(project_id, source_sha256, locator, chunker_version)` and store only identifiers/hashes and vectors by default. A local index may hold encrypted or access-controlled text only if policy permits; restricted raw data and licensed full text must not be sent to an external embedding provider by default. Retrieval first filters project/role/sensitivity/license, then returns candidate IDs. `ContextPacker` rehydrates the canonical artifact, checks current hash and locator, applies its own policy, and only then passes bounded excerpts to a specialist. A vector score cannot set `actually_read`, `entailment=passed` or `verification_status=verified`.

## F. Cache taxonomy, keys and invalidation

| Cache | Key inputs (always include tenant/project and sensitivity partition) | Invalidate / refuse |
| --- | --- | --- |
| Embedding | content/chunk hash, provider, model revision, dimension, normalization, chunker version, authorization class | Source bytes/chunker/model/permission change; no shared cross-project restricted cache |
| Retrieval | normalized query hash, filters, role, `k`, index generation, embedding/reranker versions | Any index generation or ACL change; short TTL for changing external corpora |
| LLM response | exact packed-context and SOP hashes, task contract, model/provider/config, output schema version, tool manifest set | Artifact/decision/skill/model/schema change; disable by default for human approvals, scientific judgments and sensitive content |
| Read-only tool result | tool name/version, normalized inputs, credential scope, provider dataset/version, access policy | TTL or source/version/authorization change; never treat cached result as a fresh verification receipt |
| Artifact byte cache | SHA-256 content address plus schema/retention class | Immutable bytes may be reused, but mutable aliases must be invalidated on source change; rehash on read |

No cache key contains raw credentials or restricted text. For sensitive keyed hashes use a project-scoped keyed digest rather than a globally guessable content hash. External-write operations are **not** served from a general cache: the existing idempotency ledger and post-write receipt remain the only replay mechanism. Negative lookups have short TTL; failed verifier outcomes and revoked approvals are not cached into success. Cache hits are observations, not evidence.

## G. LangGraph integration boundary

An optional graph may schedule bounded execution of **one Runtime-assigned task**, not replace the Research Director's canonical DAG. Its State may contain `run_id`, `task_id`, `agent_run_id`, assignment hash, internal cursor, pending tool-call IDs and opaque ephemeral message references. It must not contain canonical `decisions`, `evidence_registry`, artifact lineage or approval flags as authoritative fields. Graph nodes may call only the scoped ToolBridge; the final node emits a schema-valid StructuredObservation to `AgentExecutor`/`ResearchRuntime`. Runtime then validates output bytes and scientific contracts and performs the only transition.

LangGraph checkpoints are disposable execution accelerators. Restart after deletion requires reloading the canonical assignment, event trace, idempotency ledger and artifacts, then safely replaying or restarting the bounded task. A LangGraph interrupt cannot substitute for a Runtime human gate. Every side-effecting node needs a stable idempotency key and receipt before replay. No LangGraph adapter is implemented in PR-1.

## H. Proposed PR sequence

1. **PR-1 — LangChain adapter boundary hardening:** preserve the existing optional `create_agent` integration; reject model-invented artifact receipts, correctly surface tool `needs-human`, validate negative paths and provider neutrality. No Runtime state semantics change.
2. **PR-2 — disposable LangGraph execution orchestration:** opt-in graph for one task, persistent assignment mapping, safe replay and interrupt routing; no parallel canonical DAG.
3. **PR-3 — semantic retrieval index:** local-first, hash-bound chunk pointers, provider-neutral embeddings, rehydration through ContextPacker; no evidence promotion by similarity.
4. **PR-4 — typed caches:** local backend first, Redis optional; partitioned keys, TTL, invalidation and idempotency separation.
5. **PR-5 — integrated public evaluation:** failure-injected end-to-end public projects combining graph, retrieval and cache, with false-completion and privacy gates.

Each PR is independently revertible. Do not change a capability from staged to production-certified solely because deterministic tests pass.

## I. Migration risks

- Two competing graph/state authorities; mitigation: graph state never writes canonical scientific fields.
- Lost graph checkpoint after a side effect; mitigation: stable idempotency key, persisted Runtime receipt and reconstruction test.
- Stale or cross-project vector hit; mitigation: project/role/ACL filtering plus source hash/locator revalidation.
- Cached false success or revoked permission; mitigation: no cached approval/verifier success, sensitivity partition and invalidation on authorization changes.
- Provider-specific types leaking into schemas; mitigation: keep imports and type translation inside adapters.
- ScientificMemoryStore index lag after canonical save (these are separate stores); mitigation: treat index as rebuildable, reconcile from state/artifacts before retrieval, never promote it to authority.
- Overstating provenance coverage or sandbox safety; mitigation: retain four-level capability matrix and public failure-injection evidence.

## J. Tests required per PR

| PR | Minimum new tests in addition to complete existing suite |
| --- | --- |
| 1 | forged artifact/tool receipt rejection; `needs-human` handoff; unknown/staged/disallowed tool; malformed observation/model failure; legacy adapter unchanged; no core LangChain import requirement |
| 2 | checkpoint deletion and deterministic reconstruction; model/tool interruption; duplicate side-effect prevention; human reject; verifier reject; graph/state divergence; bounded loop |
| 3 | model/chunker/source hash drift; wrong project/role/license exclusion; restricted content not exported; stale locator rejection; index deletion/rebuild; semantic result cannot create verified evidence |
| 4 | key collision and cross-project isolation; TTL/invalidation; permission revocation; failed/negative results; no cached external write; artifact tamper; Redis outage fallback |
| 5 | public task recovery, citation/numeric lineage, privacy, false completion, index/cache deletion and end-to-end rerun equivalence |

Official API references used for this design: [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents), [vector-store interface](https://docs.langchain.com/oss/python/integrations/vectorstores), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), and [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts).
