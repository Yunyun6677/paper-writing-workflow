"""Least-context artifact packing for specialist model requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import dependencies
from .store import canonical_hash, sha256_file, utc_now


TEXT_SUFFIXES = {".json", ".md", ".txt", ".tex", ".bib", ".log"}
RAW_DATA_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xls", ".dta", ".sav", ".parquet", ".feather"}
ROLE_PREFIXES = {
    "research-director": ("design/", "audit/"),
    "literature-agent": ("design/", "literature/", "evidence/", "references/"),
    "empirical-agent": ("design/", "literature/", "evidence/", "analysis/"),
    "writing-agent": ("design/", "literature/", "evidence/", "references/", "analysis/", "paper/", "tables/", "figures/"),
    "reviewer-verifier-agent": ("design/", "literature/", "evidence/", "references/", "analysis/", "paper/", "tables/", "figures/", "audit/"),
}


@dataclass(frozen=True)
class PackedContext:
    artifacts: tuple[dict[str, Any], ...]
    receipt: dict[str, Any]


def _terms(value: str) -> set[str]:
    latin = re.findall(r"[a-z0-9_]{2,}", value.lower())
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", value))
    return set(latin) | {chinese[index:index + 2] for index in range(max(0, len(chinese) - 1))}


def _chunks(value: str, size: int = 1800) -> list[str]:
    return [value[index:index + size] for index in range(0, len(value), size)] or [""]


class ContextPacker:
    def __init__(self, project_dir: str | Path, *, allow_sensitive_content: bool = False):
        self.project_dir = Path(project_dir).resolve()
        self.allow_sensitive_content = allow_sensitive_content

    @staticmethod
    def _ancestor_tasks(state: dict[str, Any], item: dict[str, Any]) -> set[str]:
        by_id = {task["task_id"]: task for task in state["task_graph"]}
        ancestors = set(dependencies(item)); frontier = list(ancestors)
        while frontier:
            current = frontier.pop()
            for dependency in dependencies(by_id[current]):
                if dependency not in ancestors:
                    ancestors.add(dependency); frontier.append(dependency)
        return ancestors

    def pack(self, state: dict[str, Any], item: dict[str, Any], token_budget: int = 6000) -> PackedContext:
        if token_budget < 128:
            raise ValueError("Context token budget must be at least 128")
        ancestors = self._ancestor_tasks(state, item)
        prefixes = ROLE_PREFIXES[item["assigned_agent"]]
        sensitivity = state.get("data_sensitivity", "restricted")
        content_allowed = sensitivity in {"public", "synthetic"} or self.allow_sensitive_content
        goal_terms = _terms(item["goal"] + " " + state.get("research_question", ""))
        candidates: list[tuple[int, int, dict[str, Any]]] = []
        excluded: list[dict[str, str]] = []

        for recency, artifact in enumerate(state.get("artifacts", [])):
            producer = artifact.get("artifact_id", "").split(":", 1)[0]
            if artifact.get("artifact_id") != "project-manifest" and producer not in ancestors:
                excluded.append({"artifact_id": artifact.get("artifact_id", "unknown"), "reason": "not-a-dependency"})
                continue
            relative = str(artifact.get("path", "")).replace("\\", "/")
            if artifact.get("external"):
                record = {key: artifact[key] for key in ("artifact_id", "path", "sha256", "schema_ref", "external") if key in artifact}
                candidates.append((0, recency, record))
                continue
            if not any(relative.startswith(prefix) for prefix in prefixes):
                excluded.append({"artifact_id": artifact.get("artifact_id", "unknown"), "reason": "role-policy"})
                continue
            path = (self.project_dir / relative).resolve()
            record = {key: artifact[key] for key in ("artifact_id", "path", "sha256", "schema_ref", "external", "bytes") if key in artifact}
            if not path.is_relative_to(self.project_dir) or not path.is_file():
                record["integrity_status"] = "missing"
                candidates.append((0, recency, record)); continue
            if artifact.get("sha256") and sha256_file(path) != artifact["sha256"]:
                record["integrity_status"] = "hash-mismatch"
                candidates.append((0, recency, record)); continue
            record["integrity_status"] = "verified"
            suffix = path.suffix.lower()
            if suffix in RAW_DATA_SUFFIXES:
                record["content_policy"] = "raw-data-reference-only"
            elif not content_allowed:
                record["content_policy"] = "sensitive-reference-only"
            elif suffix not in TEXT_SUFFIXES or path.stat().st_size > 1_000_000:
                record["content_policy"] = "binary-or-large-reference-only"
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
                ranked = sorted(
                    ((len(goal_terms & _terms(chunk)), index, chunk) for index, chunk in enumerate(_chunks(text))),
                    key=lambda value: (-value[0], value[1]),
                )
                record["candidate_excerpts"] = [chunk for _score, _index, chunk in ranked[:3] if chunk]
                record["content_policy"] = "bounded-relevant-excerpts"
            score = len(goal_terms & _terms(relative + " " + " ".join(record.get("candidate_excerpts", []))))
            candidates.append((score, recency, record))

        # Prefer relevant artifacts, then recent artifacts, while preserving a hard context budget.
        used, selected = 0, []
        for _score, _recency, record in sorted(candidates, key=lambda value: (-value[0], -value[1])):
            base = {key: value for key, value in record.items() if key != "candidate_excerpts"}
            cost = max(1, len(str(base)) // 4)
            excerpts = []
            for excerpt in record.get("candidate_excerpts", []):
                excerpt_cost = max(1, len(excerpt) // 4)
                if used + cost + excerpt_cost > token_budget:
                    break
                excerpts.append(excerpt); cost += excerpt_cost
            if used + cost > token_budget:
                excluded.append({"artifact_id": record.get("artifact_id", "unknown"), "reason": "token-budget"})
                continue
            if excerpts:
                base["excerpts"] = excerpts
            selected.append(base); used += cost

        receipt = {
            "schema_version": "context-pack/1.0", "created_at": utc_now(),
            "task_id": item["task_id"], "agent": item["assigned_agent"],
            "policy": "artifact-only" if item["task_type"] == "verifier" else "least-context",
            "data_sensitivity": sensitivity, "sensitive_content_authorized": self.allow_sensitive_content,
            "token_budget": token_budget, "estimated_tokens": used,
            "selected_artifact_ids": [item.get("artifact_id") for item in selected],
            "excluded": excluded,
        }
        receipt["pack_hash"] = canonical_hash({"artifacts": selected, "receipt": receipt})
        return PackedContext(tuple(selected), receipt)
