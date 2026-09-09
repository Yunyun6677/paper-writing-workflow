"""Research Director loop with DAG scheduling, observations, retries, and gates."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import jsonschema

from .planner import add_dynamic_tasks, default_graph, validate_dag
from .store import ResearchStateStore, canonical_hash, sha256_file, utc_now
from .tools import ToolRegistry, default_registry


class RuntimeErrorState(RuntimeError):
    pass


def _task(state: dict[str, Any], task_id: str) -> dict[str, Any]:
    for item in state["task_graph"]:
        if item["task_id"] == task_id:
            return item
    raise KeyError(task_id)


def _ready(state: dict[str, Any]) -> list[dict[str, Any]]:
    complete = set(state["completed_tasks"])
    return [item for item in state["task_graph"] if item["status"] == "pending" and set(item["depends_on"]).issubset(complete)]


class ResearchRuntime:
    def __init__(self, store: ResearchStateStore, project_dir: str | Path, tools: ToolRegistry | None = None):
        self.store = store
        self.project_dir = Path(project_dir).resolve()
        self.tools = tools or default_registry()

    @staticmethod
    def initialize(manifest_path: str | Path, run_root: str | Path, parent_run_id: str | None = None) -> ResearchStateStore:
        manifest_path = Path(manifest_path).resolve()
        repository = Path(__file__).resolve().parents[1]
        schema = json.loads((repository / "schemas" / "economics-paper-project.schema.json").read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)
        run_id = str(uuid.uuid4())
        run_dir = Path(run_root).resolve() / manifest["project_id"] / run_id
        state = {
            "schema_version": "research-state/1.0",
            "project_id": manifest["project_id"],
            "run_id": run_id,
            "research_question": manifest["research_question"],
            "research_goal": manifest.get("title_working", manifest["research_question"]),
            "paper_type": manifest["paper_type"],
            "current_stage": "initialized",
            "task_graph": default_graph(manifest["paper_type"]),
            "active_task": None,
            "completed_tasks": [],
            "blocked_tasks": [],
            "pending_human_actions": [],
            "decisions": [],
            "evidence_registry": {"schema_refs": ["evidence-card/1.0", "literature-acquisition/1.0"], "artifact_refs": []},
            "literature_state": {"status": "pending", "artifact_refs": []},
            "empirical_state": {"status": "pending" if manifest["paper_type"] in {"empirical", "mixed", "measurement", "replication"} else "not-applicable", "artifact_refs": []},
            "manuscript_state": {"status": "pending", "artifact_refs": []},
            "audit_state": {"status": "pending", "artifact_refs": []},
            "artifacts": [{"artifact_id": "project-manifest", "path": str(manifest_path), "sha256": sha256_file(manifest_path), "schema_ref": "economics-paper-project/1.0", "external": True}],
            "tool_runs": [],
            "agent_runs": [],
            "errors": [],
            "retry_count": 0,
            "checkpoints": [],
            "parent_run_id": parent_run_id,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        validate_dag(state["task_graph"])
        ResearchRuntime._validate_state(state, repository)
        store = ResearchStateStore(run_dir)
        store.create(state)
        return store

    @staticmethod
    def _validate_state(state: dict[str, Any], repository: Path | None = None) -> None:
        root = repository or Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schemas" / "research-state.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(state)
        validate_dag(state["task_graph"])

    def _save(self, state: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
        self._validate_state(state)
        self.store.save(state, event_type, payload)

    def run(self, max_steps: int = 100) -> dict[str, Any]:
        """Run until completion, external agent observation, human gate, or hard block."""
        state = self.store.load()
        for _ in range(max_steps):
            ready = _ready(state)
            if not ready:
                unfinished = [t for t in state["task_graph"] if t["status"] not in {"complete", "skipped"}]
                statuses = {t["status"] for t in unfinished}
                if not unfinished:
                    state["current_stage"] = "complete"
                elif "waiting-human" in statuses:
                    state["current_stage"] = "waiting-human"
                elif "waiting-agent" in statuses:
                    state["current_stage"] = "waiting-agent"
                else:
                    state["current_stage"] = "blocked"
                self._save(state, "run.stopped", {"status": state["current_stage"]})
                return state
            item = ready[0]
            state["active_task"] = item["task_id"]
            state["current_stage"] = item["task_id"]
            item["status"] = "running"
            self._save(state, "task.started", {"task_id": item["task_id"], "kind": item["kind"]})
            if item["kind"] == "human_gate":
                action = {"action_id": f"gate-{item['task_id']}", "task_id": item["task_id"], "question": item["title"], "status": "pending", "created_at": utc_now()}
                state["pending_human_actions"].append(action)
                item["status"] = "waiting-human"
                state["active_task"] = None
                self._save(state, "human.interrupted", action)
                return state
            if item["kind"] == "agent":
                packet = {
                    "agent_run_id": str(uuid.uuid4()), "task_id": item["task_id"], "agent": item["owner"],
                    "status": "awaiting-observation", "instructions": item["title"], "inputs": item["inputs"],
                    "expected_outputs": item["expected_outputs"], "acceptance_criteria": item["acceptance_criteria"],
                    "created_at": utc_now(),
                }
                state["agent_runs"].append(packet)
                item["status"] = "waiting-agent"
                state["active_task"] = None
                self._save(state, "agent.delegated", packet)
                return state
            try:
                tool_inputs = dict(item.get("inputs", {}))
                if item.get("tool_name") == "research_firewall":
                    registries = {
                        "evidence_registry": state["evidence_registry"].get("artifact_refs", []),
                        "manuscript_state": state["manuscript_state"].get("artifact_refs", []),
                    }
                    if state["empirical_state"].get("status") != "not-applicable":
                        registries["empirical_state"] = state["empirical_state"].get("artifact_refs", [])
                    tool_inputs.setdefault("registries", registries)
                observation = self.tools.execute(item["tool_name"], tool_inputs, self.project_dir)
                self._apply_observation(state, item, observation, run_kind="tool")
            except Exception as exc:
                self._fail(state, item, str(exc), run_kind="tool")
                if item["status"] == "blocked":
                    return state
        raise RuntimeErrorState(f"Maximum runtime steps reached: {max_steps}")

    def observe_agent(self, task_id: str, observation: dict[str, Any]) -> dict[str, Any]:
        state = self.store.load()
        item = _task(state, task_id)
        if item["status"] != "waiting-agent":
            raise RuntimeErrorState(f"Task is not awaiting an agent observation: {task_id}")
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "research-agent-observation.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(observation)
        self._apply_observation(state, item, observation, run_kind="agent")
        return state

    def decide(self, action_id: str, approved: bool, rationale: str, actor: str = "human") -> dict[str, Any]:
        if not rationale.strip():
            raise ValueError("A decision rationale is required")
        state = self.store.load()
        action = next((x for x in state["pending_human_actions"] if x["action_id"] == action_id and x["status"] == "pending"), None)
        if not action:
            raise KeyError(action_id)
        item = _task(state, action["task_id"])
        action["status"] = "approved" if approved else "rejected"
        action["resolved_at"] = utc_now()
        decision = {"decision_id": str(uuid.uuid4()), "action_id": action_id, "task_id": item["task_id"], "approved": approved, "rationale": rationale, "actor": actor, "at": utc_now()}
        state["decisions"].append(decision)
        if approved:
            if item["kind"] == "human_gate":
                self._complete(state, item, {"status": "complete", "decision_id": decision["decision_id"]}, "human")
            else:
                # Approval resolves the handoff, not the specialist's unfinished work.
                item["status"] = "pending"
                item["error"] = None
                state["active_task"] = None
                self._save(state, "human.resolved", decision)
        else:
            item["status"] = "blocked"
            item["error"] = "Human decision rejected the gate"
            if item["task_id"] not in state["blocked_tasks"]:
                state["blocked_tasks"].append(item["task_id"])
            state["active_task"] = None
            self._save(state, "human.rejected", decision)
        return state

    def _apply_observation(self, state: dict[str, Any], item: dict[str, Any], observation: dict[str, Any], run_kind: str) -> None:
        status = observation.get("status")
        if status not in {"complete", "failed", "needs-human"}:
            raise ValueError("Observation status must be complete, failed, or needs-human")
        item["observation"] = observation
        if run_kind == "agent":
            packet = next((entry for entry in reversed(state["agent_runs"]) if entry.get("task_id") == item["task_id"] and entry.get("status") == "awaiting-observation"), None)
            if packet:
                packet["status"] = status
                packet["completed_at"] = utc_now()
        record = {"run_id": str(uuid.uuid4()), "task_id": item["task_id"], "name": item.get("tool_name") or item["owner"], "status": status, "observation_hash": canonical_hash(observation), "at": utc_now()}
        destination = state["tool_runs" if run_kind == "tool" else "agent_runs"]
        if run_kind == "agent":
            packet = next((entry for entry in reversed(state["agent_runs"]) if entry.get("task_id") == item["task_id"] and entry.get("status") == "awaiting-observation"), None)
            if packet:
                packet["status"] = status
                packet["observed_at"] = utc_now()
        if status == "complete":
            try:
                verified = self._verify_outputs(item, observation)
            except Exception as exc:
                record["status"] = "failed"
                record["validation_error"] = str(exc)
                destination.append(record)
                self._fail(state, item, str(exc), run_kind)
                return
            destination.append(record)
            for artifact in verified:
                reference = {"artifact_id": f"{item['task_id']}:{len(state['artifacts'])}", **artifact, "external": False}
                state["artifacts"].append(reference)
                domain = {
                    "literature": "literature_state",
                    "empirical-design": "empirical_state",
                    "analysis": "empirical_state",
                    "writing": "manuscript_state",
                    "verification": "audit_state",
                }.get(item["task_id"])
                if domain:
                    artifact_ref = {"path": reference["path"], "sha256": reference["sha256"], "artifact_id": reference["artifact_id"]}
                    state[domain]["artifact_refs"].append(artifact_ref)
                    if item["task_id"] == "literature":
                        state["evidence_registry"]["artifact_refs"].append(artifact_ref)
            if observation.get("next_tasks"):
                add_dynamic_tasks(state["task_graph"], observation["next_tasks"], item["task_id"])
            self._complete(state, item, observation, run_kind)
        elif status == "needs-human":
            destination.append(record)
            action = {"action_id": f"handoff-{item['task_id']}-{uuid.uuid4().hex[:8]}", "task_id": item["task_id"], "question": observation.get("human_action", "Researcher input is required"), "status": "pending", "created_at": utc_now()}
            state["pending_human_actions"].append(action)
            item["status"] = "waiting-human"
            state["active_task"] = None
            self._save(state, "human.interrupted", action)
        else:
            destination.append(record)
            self._fail(state, item, "; ".join(observation.get("errors", [])) or "agent/tool reported failure", run_kind)

    def _verify_outputs(self, item: dict[str, Any], observation: dict[str, Any]) -> list[dict[str, Any]]:
        declared = {artifact["path"]: artifact for artifact in observation.get("artifacts", [])}
        for expected in item.get("expected_outputs", []):
            path = (self.project_dir / expected).resolve()
            if not path.is_relative_to(self.project_dir) or not path.exists():
                raise ValueError(f"Expected output is missing: {expected}")
            normalized = expected.replace("\\", "/").rstrip("/")
            if path.is_file() and normalized not in declared:
                raise ValueError(f"Expected file lacks a hashed artifact declaration: {expected}")
            if path.is_dir() and not any(name == normalized or name.startswith(normalized + "/") for name in declared):
                raise ValueError(f"Expected directory lacks a hashed artifact declaration: {expected}")
        verified = []
        for relative, artifact in declared.items():
            path = (self.project_dir / relative).resolve()
            if not path.is_relative_to(self.project_dir) or not path.is_file():
                raise ValueError(f"Declared artifact is missing or outside the project: {relative}")
            digest = sha256_file(path)
            if digest != artifact["sha256"]:
                raise ValueError(f"Declared artifact hash mismatch: {relative}")
            verified.append({**artifact, "sha256": digest, "bytes": path.stat().st_size})
        return verified

    def _complete(self, state: dict[str, Any], item: dict[str, Any], observation: dict[str, Any], run_kind: str) -> None:
        item["status"] = "complete"
        item["error"] = None
        state["active_task"] = None
        if item["task_id"] not in state["completed_tasks"]:
            state["completed_tasks"].append(item["task_id"])
        domain_update = {
            "literature": ("literature_state", "complete"),
            "empirical-design": ("empirical_state", "running"),
            "analysis": ("empirical_state", "complete"),
            "writing": ("manuscript_state", "complete"),
            "verification": ("audit_state", "review-required"),
        }.get(item["task_id"])
        if domain_update:
            state[domain_update[0]]["status"] = domain_update[1]
        self._save(state, "task.completed", {"task_id": item["task_id"], "by": run_kind, "observation_hash": canonical_hash(observation)})

    def _fail(self, state: dict[str, Any], item: dict[str, Any], message: str, run_kind: str) -> None:
        item["retry_count"] += 1
        state["retry_count"] += 1
        error = {"error_id": str(uuid.uuid4()), "task_id": item["task_id"], "source": run_kind, "message": message, "retry": item["retry_count"], "at": utc_now()}
        state["errors"].append(error)
        if item["retry_count"] <= item["max_retries"]:
            item["status"] = "pending"
            item["error"] = message
        else:
            item["status"] = "blocked"
            item["error"] = message
            if item["task_id"] not in state["blocked_tasks"]:
                state["blocked_tasks"].append(item["task_id"])
            domain = {
                "literature": "literature_state", "empirical-design": "empirical_state",
                "analysis": "empirical_state", "writing": "manuscript_state", "verification": "audit_state",
            }.get(item["task_id"])
            if domain:
                state[domain]["status"] = "blocked"
        state["active_task"] = None
        self._save(state, "task.failed", error)
