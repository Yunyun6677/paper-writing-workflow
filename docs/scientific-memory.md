# Scientific memory in v0.11

`ScientificMemoryStore` is a local SQLite index over the portable JSON artifacts and canonical `ResearchState`. It is not a replacement for evidence files, datasets, execution receipts, or checkpoints.

## Entities and relations

The first schema indexes Project, ResearchQuestion, Decision, Claim, Evidence, Source, Artifact, Dataset, ModelRun, Task, and Revision. The relation table supports, among others:

- `Claim -> supported_by -> Evidence`
- `Evidence -> extracted_from -> Source`
- `ModelRun -> used_dataset -> Dataset`
- `Task -> produced -> Artifact`
- `Project -> contains -> Task`

Runtime state transitions transactionally refresh project, task, decision, artifact, model-run, and revision indexes. Claim/evidence/source and dataset/model-run links are inserted only by code that has stable artifact identifiers; the store does not infer scientific relationships from prose.

## Authority and privacy

- JSON artifacts plus hashes remain authoritative and portable.
- SQLite is the query and control layer. Deleting it must not destroy research evidence.
- Secret, token, password, credential, API-key, and raw-data keys are rejected.
- Restricted/personal/confidential records may store references, locators, identifiers, and hashes, but not text, excerpts, rows, observations, or values. Decision rationales and revision reasons are reduced to hashes at this sensitivity.
- The store is local and has no network exporter.

## Migration

The database records `scientific-memory/1.0` in `memory_meta`. A different version fails closed. Future migrations must be explicit, transactional, reversible through database backup, and may not silently change JSON artifacts. This stage does not migrate or delete the existing four-layer `ResearchState.memory` structure.

## Current boundary

Transactions and uniqueness constraints are implemented and tested. Cross-process run locking and optimistic concurrency belong to the later `SQLiteStateBackend` stage. Semantic relevance and token-bounded selection belong to `ContextPacker`; this store currently provides exact entity and relation queries only.
