"""SQLite scientific-memory index over portable Research OS artifacts.

The database is a local query/control layer. JSON artifacts and their hashes
remain authoritative; the index never replaces them or stores raw datasets.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .memory import assert_safe_long_term
from .store import canonical_hash, utc_now


ENTITY_TABLES = {
    "Project": "projects",
    "ResearchQuestion": "research_questions",
    "Decision": "decisions",
    "Claim": "claims",
    "Evidence": "evidence",
    "Source": "sources",
    "Artifact": "artifacts",
    "Dataset": "datasets",
    "ModelRun": "model_runs",
    "Task": "tasks",
    "Revision": "revisions",
}

RESTRICTED_CONTENT_KEYS = {
    "content", "text", "excerpt", "fulltext", "rows", "records", "values", "observations",
}


class ScientificMemoryStore:
    """Local provenance graph with small transactions and no provider coupling."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS memory_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            existing = connection.execute("SELECT value FROM memory_meta WHERE key='schema_version'").fetchone()
            if existing is not None and existing[0] != "scientific-memory/1.0":
                raise RuntimeError(f"Unsupported scientific-memory schema: {existing[0]}")
            connection.execute(
                "INSERT OR IGNORE INTO memory_meta(key, value) VALUES('schema_version', 'scientific-memory/1.0')"
            )
            for table in ENTITY_TABLES.values():
                connection.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        entity_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        sensitivity TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        metadata_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_project ON {table}(project_id)")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, source_type, source_id, predicate, target_type, target_id)
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(project_id, source_type, source_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(project_id, target_type, target_id)")

    @staticmethod
    def _validate_metadata(metadata: dict[str, Any], sensitivity: str) -> None:
        assert_safe_long_term(metadata, "scientific_memory")
        if sensitivity in {"restricted", "personal", "confidential"}:
            stack: list[Any] = [metadata]
            while stack:
                value = stack.pop()
                if isinstance(value, dict):
                    forbidden = {str(key).lower() for key in value} & RESTRICTED_CONTENT_KEYS
                    if forbidden:
                        raise ValueError("Restricted scientific memory stores references and hashes, not content: " + ", ".join(sorted(forbidden)))
                    stack.extend(value.values())
                elif isinstance(value, list):
                    stack.extend(value)

    def put_entity(self, entity_type: str, entity_id: str, project_id: str,
                   metadata: dict[str, Any], sensitivity: str = "public") -> dict[str, Any]:
        with self._connection() as connection:
            return self._put_entity(connection, entity_type, entity_id, project_id, metadata, sensitivity)

    def _put_entity(self, connection: sqlite3.Connection, entity_type: str, entity_id: str,
                    project_id: str, metadata: dict[str, Any], sensitivity: str) -> dict[str, Any]:
        if entity_type not in ENTITY_TABLES:
            raise ValueError(f"Unsupported scientific-memory entity: {entity_type}")
        if not entity_id or not project_id:
            raise ValueError("entity_id and project_id are required")
        self._validate_metadata(metadata, sensitivity)
        payload = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest, now = canonical_hash(metadata), utc_now()
        table = ENTITY_TABLES[entity_type]
        connection.execute(f"""
            INSERT INTO {table}(entity_id, project_id, sensitivity, metadata_json, metadata_hash, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_id) DO UPDATE SET
                project_id=excluded.project_id,
                sensitivity=excluded.sensitivity,
                metadata_json=excluded.metadata_json,
                metadata_hash=excluded.metadata_hash,
                updated_at=excluded.updated_at
        """, (entity_id, project_id, sensitivity, payload, digest, now, now))
        return {"entity_type": entity_type, "entity_id": entity_id, "metadata_hash": digest}

    def relate(self, project_id: str, source_type: str, source_id: str, predicate: str,
               target_type: str, target_id: str, metadata: dict[str, Any] | None = None) -> str:
        with self._connection() as connection:
            return self._relate(connection, project_id, source_type, source_id, predicate,
                                target_type, target_id, metadata)

    def _relate(self, connection: sqlite3.Connection, project_id: str, source_type: str,
                source_id: str, predicate: str, target_type: str, target_id: str,
                metadata: dict[str, Any] | None = None) -> str:
        if source_type not in ENTITY_TABLES or target_type not in ENTITY_TABLES:
            raise ValueError("Relation endpoints must be known scientific-memory entities")
        metadata = metadata or {}
        assert_safe_long_term(metadata, "scientific_memory.relation")
        relation_id = canonical_hash({
            "project_id": project_id, "source_type": source_type, "source_id": source_id,
            "predicate": predicate, "target_type": target_type, "target_id": target_id,
        })
        connection.execute("""
            INSERT INTO relations(relation_id, project_id, source_type, source_id, predicate,
                                  target_type, target_id, metadata_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, source_type, source_id, predicate, target_type, target_id)
            DO UPDATE SET metadata_json=excluded.metadata_json
        """, (relation_id, project_id, source_type, source_id, predicate, target_type, target_id,
              json.dumps(metadata, ensure_ascii=False, sort_keys=True), utc_now()))
        return relation_id

    def ingest_state(self, state: dict[str, Any]) -> dict[str, int]:
        """Index canonical identifiers and artifact lineage without copying artifact content."""
        project_id, sensitivity = state["project_id"], state.get("data_sensitivity", "restricted")
        counts = {key: 0 for key in ENTITY_TABLES}
        with self._connection() as connection:
            self._put_entity(connection, "Project", project_id, project_id, {
                "run_id": state["run_id"], "research_goal": state["research_goal"],
                "paper_type": state["paper_type"], "lifecycle_status": state["lifecycle_status"],
            }, sensitivity)
            question_id = "rq-" + canonical_hash(state["research_question"])[:20]
            question_metadata = {"question_hash": canonical_hash(state["research_question"])}
            if sensitivity in {"public", "synthetic"}:
                question_metadata["text"] = state["research_question"]
            self._put_entity(connection, "ResearchQuestion", question_id, project_id, question_metadata, sensitivity)
            self._relate(connection, project_id, "Project", project_id, "has_question", "ResearchQuestion", question_id)
            counts["Project"] = counts["ResearchQuestion"] = 1
            task_ids = {item.get("task_id") for item in state.get("task_graph", [])}
            for item in state.get("task_graph", []):
                metadata = {key: item.get(key) for key in (
                    "task_type", "goal", "assigned_agent", "status", "dependencies", "attempts",
                    "strategy_replans", "allowed_tools",
                )}
                self._put_entity(connection, "Task", item["task_id"], project_id, metadata, sensitivity)
                self._relate(connection, project_id, "Project", project_id, "contains", "Task", item["task_id"])
                counts["Task"] += 1
            for item in state.get("decisions", []):
                decision_metadata = {key: item.get(key) for key in ("task_id", "approved", "actor", "at")}
                if sensitivity in {"public", "synthetic"}:
                    decision_metadata["rationale"] = item.get("rationale")
                elif item.get("rationale"):
                    decision_metadata["rationale_hash"] = canonical_hash(item["rationale"])
                self._put_entity(connection, "Decision", item["decision_id"], project_id,
                                 decision_metadata, sensitivity)
                self._relate(connection, project_id, "Decision", item["decision_id"], "decides", "Task", item["task_id"])
                counts["Decision"] += 1
            for item in state.get("artifacts", []):
                artifact_id = item["artifact_id"]
                self._put_entity(connection, "Artifact", artifact_id, project_id, {
                    key: item.get(key) for key in ("path", "sha256", "schema_ref", "external", "bytes")
                }, sensitivity)
                producer = artifact_id.split(":", 1)[0]
                if producer in task_ids:
                    self._relate(connection, project_id, "Task", producer, "produced", "Artifact", artifact_id)
                counts["Artifact"] += 1
            for index, item in enumerate(state.get("agent_runs", [])):
                run_id = item.get("agent_run_id") or item.get("run_id") or f"agent-{index}"
                self._put_entity(connection, "ModelRun", run_id, project_id, {
                    key: item.get(key) for key in ("task_id", "agent", "model", "status", "created_at", "observed_at")
                }, sensitivity)
                if item.get("task_id"):
                    self._relate(connection, project_id, "ModelRun", run_id, "executed_for", "Task", item["task_id"])
                counts["ModelRun"] += 1
            for index, item in enumerate(state.get("memory", {}).get("project", {}).get("revision_history", [])):
                revision_id = item.get("revision_id") or "revision-" + canonical_hash({"index": index, **item})[:20]
                revision_metadata = dict(item)
                if sensitivity not in {"public", "synthetic"} and revision_metadata.get("reason"):
                    revision_metadata["reason_hash"] = canonical_hash(revision_metadata.pop("reason"))
                self._put_entity(connection, "Revision", revision_id, project_id, revision_metadata, sensitivity)
                if item.get("task_id"):
                    self._relate(connection, project_id, "Revision", revision_id, "revises", "Task", item["task_id"])
                counts["Revision"] += 1
        return counts

    def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        if entity_type not in ENTITY_TABLES:
            raise ValueError(f"Unsupported scientific-memory entity: {entity_type}")
        with self._connection() as connection:
            row = connection.execute(
                f"SELECT * FROM {ENTITY_TABLES[entity_type]} WHERE entity_id = ?", (entity_id,)
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def neighbors(self, project_id: str, entity_type: str, entity_id: str,
                  predicate: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM relations WHERE project_id=? AND source_type=? AND source_id=?"
        parameters: list[Any] = [project_id, entity_type, entity_id]
        if predicate is not None:
            query += " AND predicate=?"
            parameters.append(predicate)
        query += " ORDER BY created_at, relation_id"
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def claim_evidence(self, project_id: str, claim_id: str) -> list[dict[str, Any]]:
        return self.neighbors(project_id, "Claim", claim_id, "supported_by")
