# State backends in v0.11

Research OS exposes a framework-neutral `StateBackend` contract. The existing file implementation remains the default; a transactional SQLite implementation can be selected when initializing a new run.

```powershell
.\.venv-empirical\Scripts\python.exe scripts\research_agent.py init `
  --manifest projects\example\manifest.json `
  --run-root .runtime `
  --state-backend sqlite
```

Both backends provide canonical state load/save, monotonically increasing state versions, optimistic concurrency checks, ordered events, checkpoints, recovery, and owner-checked run locks. A stale writer receives `StateConflictError` before its state is committed. A second run owner receives `RunLockError`.

The file backend keeps `state.json`, `events.jsonl`, checkpoints, and a small `backend-meta.json`. Short-lived exclusive write locks serialize compare-and-swap plus event append. The SQLite backend uses `BEGIN IMMEDIATE`, a versioned singleton state row, ordered event rows, and a run-lock table. It mirrors `state.json` and `events.jsonl` after commits for portability and inspection; SQLite remains canonical for that backend.

Artifacts continue to live on the filesystem. `ScientificMemoryStore` remains a separate query index and is not the canonical runtime state database. Backend discovery selects SQLite when `runtime-state.sqlite` exists, otherwise file state.

Current run locks require explicit release; automated stale-owner lease recovery is not implemented. Multi-host/distributed execution is out of scope and not production-certified.
