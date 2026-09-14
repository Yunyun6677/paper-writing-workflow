# Context packing in v0.11

`ContextPacker` constructs a bounded model context from verified artifact references. It never sends canonical `ResearchState`, agent hidden reasoning, raw data rows, secrets, or unrelated project history to a specialist.

Selection uses five controls:

1. task dependencies: only completed ancestor artifacts are candidates;
2. role policy: literature, empirical, writing, and reviewer roles receive only their permitted artifact domains;
3. artifact integrity: missing or hash-mismatched files are reference-only and explicitly marked;
4. relevance and recency: bounded text chunks are ranked against the task goal and research question, with recency as a tie-breaker;
5. token and security budgets: the pack stops at a hard estimated-token limit and excludes raw dataset formats from content capture.

For `restricted`, `personal`, or `confidential` projects, artifact content is reference-only unless the runtime is constructed with an explicit sensitive-content authorization. The CLI exposes this only through `--allow-external-model-content`; the project sensitivity check still applies before a Codex cloud adapter is created.

Reviewer requests contain an empty working context and artifact-only packs. Writer requests can contain completed dependency artifacts but never producer hidden reasoning. Every pack includes a local receipt with selected artifact IDs, exclusions, policy, estimated tokens, sensitivity decision, and a canonical pack hash.

The token estimate is intentionally conservative and provider-independent. It is not an exact provider tokenizer. Semantic retrieval currently uses deterministic lexical overlap; model embeddings or a vector database are not required and are not claimed.
