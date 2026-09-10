# ADR-001: Research Agent runtime framework

- Status: Accepted
- Date: 2026-09-10
- Decision owners: Research OS maintainers
- Scope: model orchestration, durable state, tracing, and provider portability

## Context

Research OS already owns a framework-neutral `ResearchState`, typed dynamic task
DAG, artifact schemas, content hashes, checkpoints, human gates, deterministic
tools, and independent verification. The missing choice is how model turns should be
run without moving scientific truth into a provider-specific session object.

Three options were evaluated:

| Option | Strength | Main cost for this repository |
| --- | --- | --- |
| A. OpenAI Agents SDK + existing schemas | Native agents/tools/handoffs/guardrails/sessions/MCP/tracing; natural fit for Codex and OpenAI-hosted execution | Provider-specific runtime types and hosted tracing could become accidental sources of truth or expose research content if used without policy controls |
| B. LangGraph + existing Skills | Strong explicit graph, checkpoint, interrupt/resume, durable execution and memory model | Duplicates much of the current state machine and creates two graph/checkpoint authorities |
| C. Lightweight Python runtime | Small dependency surface; current state, artifacts, retries and gates remain authoritative; easiest deterministic testing | We must maintain adapters and do not receive a full model/tool ecosystem automatically |

## Decision

Use a **hybrid C + A architecture**:

1. Keep the lightweight Python runtime as the canonical control plane.
2. Make OpenAI Agents SDK the preferred optional model-runtime adapter in Codex
   environments, after integration tests and an explicit credential/configuration
   step.
3. Keep `ResearchState`, task contracts, artifacts, evidence lineage, evaluations,
   and checkpoints framework-agnostic.
4. Provide an OpenAI-compatible adapter boundary for other hosted providers and
   local servers. Provider sessions may cache execution context, but cannot be the
   sole copy of research state or evidence.
5. Do not add LangGraph to the default dependency set. A future LangGraph adapter
   is justified only for deployments whose topology or distributed durability
   exceeds the current runtime, and it must map back to canonical ResearchState.

This is not a claim that an OpenAI Agents SDK adapter is already production
certified. `config/providers.json` declares staged interfaces; all providers are
disabled until configured and tested.

## Required adapter contract

Every provider adapter must:

- accept explicit agent, model, artifact references, permitted tools, and metadata;
- return a schema-valid observation with outcome, actual model, tool-call metadata,
  token usage, and output artifact references;
- never mark a task complete directly;
- survive loss of provider session state because canonical state remains local;
- enforce project sensitivity and explicit external-content authorization;
- expose retries and errors to the Director rather than hiding them;
- permit tracing to be disabled or locally exported only.

## Consequences

The kernel stays testable without network access, API keys, a model SDK, or private
data. Codex deployments can later use Agents SDK handoffs, MCP tools, sessions and
tracing without changing evidence schemas. The tradeoff is a small maintained
adapter layer and deliberate duplication between provider telemetry and the local
scientific trace; the local trace is authoritative.

## Rejected alternatives

- **Agents SDK as the entire state store:** rejected because a provider session is
  not an evidence registry and must not replace hashes, receipts, or human gates.
- **LangGraph as a second canonical graph:** rejected because dual graph ownership
  creates recovery and migration ambiguity.
- **Direct provider calls from Specialist Skills:** rejected because it bypasses
  task budgets, tool permissions, observation validation, and verifier gates.

## Revisit triggers

Reconsider the decision when distributed workers, concurrent writers, remote
checkpointers, or multi-host locking become required; when an adapter passes the
full evaluation suite; or when a provider/runtime changes its persistence, privacy,
or tracing contract.

## Primary references

- [OpenAI agent orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration)
- [OpenAI Agents SDK sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK tracing](https://openai.github.io/openai-agents-python/tracing/)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Microsoft Agent Framework checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
