"""Persistent Research Director loop: plan, execute, observe, verify, update, decide."""
from __future__ import annotations
import json, uuid
from pathlib import Path
from typing import Any
import jsonschema
from .contracts import TERMINAL_TASK_STATUSES, dependencies, normalize_outcome, sync_compatibility_aliases, upgrade_state_v010
from .memory import empty_memory
from .planner import add_dynamic_tasks, default_graph, feedback_tasks, validate_dag
from .store import ResearchStateStore, canonical_hash, sha256_file, utc_now
from .tools import ToolRegistry, default_registry

class RuntimeErrorState(RuntimeError): pass

def _task(state: dict[str, Any], task_id: str) -> dict[str, Any]:
    for item in state["task_graph"]:
        if item["task_id"] == task_id: return item
    raise KeyError(task_id)

def _ready(state: dict[str, Any]) -> list[dict[str, Any]]:
    complete = set(state["completed_tasks"])
    return [x for x in state["task_graph"] if x["status"] == "pending" and set(dependencies(x)).issubset(complete)]

class ResearchRuntime:
    def __init__(self, store: ResearchStateStore, project_dir: str | Path, tools: ToolRegistry | None = None):
        self.store, self.project_dir, self.tools = store, Path(project_dir).resolve(), tools or default_registry()

    @staticmethod
    def initialize(manifest_path: str | Path, run_root: str | Path, parent_run_id: str | None = None) -> ResearchStateStore:
        manifest_path, repository = Path(manifest_path).resolve(), Path(__file__).resolve().parents[1]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        schema = json.loads((repository / "schemas/economics-paper-project.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)
        run_id = str(uuid.uuid4()); run_dir = Path(run_root).resolve() / manifest["project_id"] / run_id
        state = {
            "schema_version": "research-state/1.0", "project_id": manifest["project_id"], "run_id": run_id,
            "research_question": manifest["research_question"], "research_goal": manifest.get("title_working", manifest["research_question"]),
            "paper_type": manifest["paper_type"], "data_sensitivity": manifest.get("data_sensitivity", "public"),
            "current_stage": "initialized", "lifecycle_status": "initialized", "task_graph": default_graph(manifest["paper_type"]),
            "active_task": None, "completed_tasks": [], "blocked_tasks": [], "pending_human_actions": [], "decisions": [],
            "evidence_registry": {"schema_refs": ["evidence-card/1.0", "literature-acquisition/1.0"], "artifact_refs": []},
            "literature_state": {"status": "pending", "artifact_refs": []},
            "empirical_state": {"status": "pending" if manifest["paper_type"] in {"empirical", "mixed", "measurement", "replication"} else "not-applicable", "artifact_refs": []},
            "manuscript_state": {"status": "pending", "artifact_refs": []}, "audit_state": {"status": "pending", "artifact_refs": []},
            "artifacts": [{"artifact_id": "project-manifest", "path": str(manifest_path), "sha256": sha256_file(manifest_path), "schema_ref": "economics-paper-project/1.0", "external": True}],
            "tool_runs": [], "agent_runs": [], "errors": [], "retry_count": 0, "checkpoints": [], "parent_run_id": parent_run_id,
            "runtime_control": {"max_total_steps": 500, "max_total_tasks": 100, "max_no_progress_cycles": 3, "total_steps": 0, "no_progress_cycles": 0, "strategy_replans": 0, "max_strategy_replans": 20},
            "memory": empty_memory(), "created_at": utc_now(), "updated_at": utc_now(),
        }
        validate_dag(state["task_graph"]); ResearchRuntime._validate_state(state, repository)
        store = ResearchStateStore(run_dir); store.create(state); return store

    @staticmethod
    def _validate_state(state: dict[str, Any], repository: Path | None = None) -> None:
        root = repository or Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schemas/research-state.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(state)
        validate_dag(state["task_graph"])

    def _save(self, state: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
        self._validate_state(state); self.store.save(state, event_type, payload)

    def _load(self) -> dict[str, Any]:
        state, changed = upgrade_state_v010(self.store.load())
        if changed:
            self._save(state, "state.compatibility-upgraded", {"target": "v0.10 additive contract", "destructive": False})
        return state

    def run(self, max_steps: int = 100) -> dict[str, Any]:
        state = self._load()
        if state.get("lifecycle_status") == "paused": return state
        state["lifecycle_status"] = "running"
        for _ in range(max_steps):
            control = state["runtime_control"]
            if control["total_steps"] >= control["max_total_steps"]:
                return self._block_run(state, "max_total_steps exhausted")
            control["total_steps"] += 1
            ready = _ready(state)
            if not ready:
                unfinished = [t for t in state["task_graph"] if t["status"] not in TERMINAL_TASK_STATUSES]
                statuses = {t["status"] for t in unfinished}
                if not unfinished:
                    final_audits = [t for t in state["task_graph"] if t["task_type"] == "final_audit"]
                    if not final_audits or any(t["status"] != "complete" for t in final_audits):
                        return self._block_run(state, "Goal cannot complete without a passed final audit")
                    state["current_stage"] = state["lifecycle_status"] = "complete"
                elif "waiting-human" in statuses: state["current_stage"] = state["lifecycle_status"] = "waiting-human"
                elif "waiting-agent" in statuses: state["current_stage"] = state["lifecycle_status"] = "waiting-agent"
                else: state["current_stage"] = state["lifecycle_status"] = "blocked"
                self._save(state, "run.stopped", {"status": state["current_stage"]}); return state
            item = ready[0]; state["active_task"] = state["current_stage"] = item["task_id"]
            item["status"] = "running"; item["attempts"] += 1; sync_compatibility_aliases(item)
            self._save(state, "task.started", {"task_id": item["task_id"], "task_type": item["task_type"], "attempt": item["attempts"]})
            if item["task_type"] == "human_gate":
                return self._handoff(state, item, item["goal"], high_risk=True)
            if item["task_type"] in {"agent", "verifier"}:
                packet = {"agent_run_id": str(uuid.uuid4()), "task_id": item["task_id"], "agent": item["assigned_agent"], "status": "awaiting-observation", "instructions": item["goal"], "inputs": item["required_inputs"], "expected_outputs": item["expected_outputs"], "success_contract": item["success_contract"], "failure_contract": item["failure_contract"], "verification_rules": item["verification_rules"], "timeout_seconds": item["timeout_seconds"], "context_policy": "artifact-only" if item["task_type"] == "verifier" else "working-memory", "created_at": utc_now()}
                state["agent_runs"].append(packet); item["status"] = "waiting-agent"; state["active_task"] = None
                self._save(state, "agent.delegated", packet); return state
            try:
                tool_inputs = dict(item["required_inputs"])
                if item.get("tool_name") == "research_firewall":
                    registries = {"evidence_registry": state["evidence_registry"].get("artifact_refs", []), "manuscript_state": state["manuscript_state"].get("artifact_refs", [])}
                    if state["empirical_state"].get("status") != "not-applicable": registries["empirical_state"] = state["empirical_state"].get("artifact_refs", [])
                    tool_inputs.setdefault("registries", registries)
                approved = any(d.get("task_id") == item["task_id"] and d.get("approved") for d in state["decisions"])
                observation = self.tools.execute(item["tool_name"], tool_inputs, self.project_dir, approved=approved, data_sensitivity=state["data_sensitivity"])
                self._apply_observation(state, item, observation, "tool")
            except PermissionError as exc:
                return self._handoff(state, item, str(exc), high_risk=True)
            except Exception as exc:
                self._fail(state, item, str(exc), "tool", "FAIL_TRANSIENT")
                if item["status"] == "blocked": return state
        state["active_task"] = None
        self._save(state, "run.yielded", {"reason": "invocation-step-limit", "max_steps": max_steps})
        return state

    def pause(self, reason: str) -> dict[str, Any]:
        if not reason.strip(): raise ValueError("Pause reason is required")
        state = self._load(); state["lifecycle_status"] = "paused"; state["active_task"] = None
        self._save(state, "run.paused", {"reason": reason}); return state

    def resume(self) -> dict[str, Any]:
        state = self._load()
        if state.get("lifecycle_status") == "complete": return state
        state["lifecycle_status"] = "running"; self._save(state, "run.resumed", {}); return self.run()

    def reconstruct(self) -> dict[str, Any]:
        state = self._load(); integrity = self.store.verify()
        missing = [a["path"] for a in state["artifacts"] if not a.get("external") and not (self.project_dir / a["path"]).is_file()]
        state["memory"]["working"]["entries"] = [{"active_task": state.get("active_task"), "current_stage": state["current_stage"], "missing_artifacts": missing, "checkpoint_errors": integrity}]
        if missing or integrity: state["lifecycle_status"] = "recovering"
        self._save(state, "run.reconstructed", {"missing_artifacts": missing, "checkpoint_errors": integrity}); return state

    def observe_agent(self, task_id: str, observation: dict[str, Any]) -> dict[str, Any]:
        state = self._load(); item = _task(state, task_id)
        if item["status"] != "waiting-agent": raise RuntimeErrorState(f"Task is not awaiting an agent observation: {task_id}")
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/research-agent-observation.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(observation)
        self._apply_observation(state, item, observation, "agent"); return state

    def decide(self, action_id: str, approved: bool, rationale: str, actor: str = "human") -> dict[str, Any]:
        if not rationale.strip(): raise ValueError("A decision rationale is required")
        state = self._load(); action = next((x for x in state["pending_human_actions"] if x["action_id"] == action_id and x["status"] == "pending"), None)
        if not action: raise KeyError(action_id)
        item = _task(state, action["task_id"]); action["status"] = "approved" if approved else "rejected"; action["resolved_at"] = utc_now()
        decision = {"decision_id": str(uuid.uuid4()), "action_id": action_id, "task_id": item["task_id"], "approved": approved, "rationale": rationale, "actor": actor, "at": utc_now()}
        state["decisions"].append(decision); state["memory"]["project"]["decisions"].append({"decision_id": decision["decision_id"], "task_id": item["task_id"], "approved": approved, "at": decision["at"]})
        if approved:
            if item["task_type"] == "human_gate": self._complete(state, item, {"outcome": "PASS", "decision_id": decision["decision_id"]}, "human")
            else:
                item["status"] = "pending"; item["error"] = None; state["active_task"] = None; self._save(state, "human.resolved", decision)
        else:
            item["status"] = "blocked"; item["error"] = "Human decision rejected the gate"
            if item["task_id"] not in state["blocked_tasks"]: state["blocked_tasks"].append(item["task_id"])
            state["active_task"] = None; state["lifecycle_status"] = "blocked"; self._save(state, "human.rejected", decision)
        return state

    def _apply_observation(self, state: dict[str, Any], item: dict[str, Any], observation: dict[str, Any], run_kind: str) -> None:
        outcome = normalize_outcome(observation)
        if not outcome: raise ValueError("Observation requires an explicit outcome or legacy status")
        item["observation"] = observation
        packet = None
        if run_kind == "agent":
            packet = next((x for x in reversed(state["agent_runs"]) if x.get("task_id") == item["task_id"] and x.get("status") == "awaiting-observation"), None)
            if packet: packet["status"] = outcome; packet["observed_at"] = utc_now()
        record = {"run_id": str(uuid.uuid4()), "task_id": item["task_id"], "name": item.get("tool_name") or item["assigned_agent"], "outcome": outcome, "observation_hash": canonical_hash(observation), "at": utc_now()}
        if run_kind == "tool": state["tool_runs"].append(record)
        if outcome in {"PASS", "GOAL_COMPLETE"}:
            try: verified = self._verify_outputs(item, observation)
            except Exception as exc:
                self._fail(state, item, str(exc), run_kind, "FAIL_TRANSIENT"); return
            for artifact in verified: self._register_artifact(state, item, artifact)
            if observation.get("next_tasks"):
                add_dynamic_tasks(state["task_graph"], observation["next_tasks"], item["task_id"], state["runtime_control"]["max_total_tasks"])
            self._complete(state, item, observation, run_kind)
        elif outcome in {"BLOCKED", "HIGH_RISK_DECISION"}:
            self._handoff(state, item, observation.get("human_action", "Researcher input is required"), high_risk=outcome == "HIGH_RISK_DECISION")
        elif outcome == "FAIL_STRATEGY":
            self._replan(state, item, observation, run_kind)
        else:
            self._fail(state, item, "; ".join(observation.get("errors", [])) or "transient failure", run_kind, outcome)

    def _replan(self, state: dict[str, Any], item: dict[str, Any], observation: dict[str, Any], run_kind: str) -> None:
        item["strategy_replans"] += 1; state["runtime_control"]["strategy_replans"] += 1
        if item["strategy_replans"] > item["max_strategy_replans"] or state["runtime_control"]["strategy_replans"] > state["runtime_control"]["max_strategy_replans"]:
            self._handoff(state, item, "Strategy replan budget exhausted", high_risk=False); return
        additions = observation.get("replacement_tasks") or observation.get("next_tasks")
        if not additions and observation.get("replan"):
            additions = feedback_tasks(observation["replan"], item["task_id"], state["runtime_control"]["strategy_replans"])
        if not additions:
            self._handoff(state, item, "A strategy failure requires replacement_tasks or researcher direction", high_risk=False); return
        add_dynamic_tasks(state["task_graph"], additions, item["task_id"], state["runtime_control"]["max_total_tasks"])
        item = _task(state, item["task_id"])
        item["status"] = "superseded"; item["error"] = observation.get("summary", "strategy superseded")
        if item["task_id"] not in state["completed_tasks"]: state["completed_tasks"].append(item["task_id"])
        state["memory"]["project"]["revision_history"].append({"task_id": item["task_id"], "reason": item["error"], "at": utc_now()})
        state["active_task"] = None; self._save(state, "plan.revised", {"task_id": item["task_id"], "new_tasks": [x["task_id"] for x in additions], "source": run_kind})

    def _handoff(self, state: dict[str, Any], item: dict[str, Any], question: str, high_risk: bool) -> dict[str, Any]:
        action = {"action_id": f"handoff-{item['task_id']}-{uuid.uuid4().hex[:8]}", "task_id": item["task_id"], "question": question, "risk": "high" if high_risk else "normal", "status": "pending", "created_at": utc_now()}
        state["pending_human_actions"].append(action); item["status"] = "waiting-human"; state["active_task"] = None; state["lifecycle_status"] = "waiting-human"
        self._save(state, "human.approval-required" if high_risk else "human.handoff", action); return state

    def _verify_outputs(self, item: dict[str, Any], observation: dict[str, Any]) -> list[dict[str, Any]]:
        declared = {a["path"]: a for a in observation.get("artifacts", [])}
        for expected in item.get("expected_outputs", []):
            path = (self.project_dir / expected).resolve()
            if not path.is_relative_to(self.project_dir) or not path.exists(): raise ValueError(f"Expected output is missing: {expected}")
            normalized = expected.replace("\\", "/").rstrip("/")
            if path.is_file() and normalized not in declared: raise ValueError(f"Expected file lacks a hashed artifact declaration: {expected}")
            if path.is_dir() and not any(k == normalized or k.startswith(normalized + "/") for k in declared): raise ValueError(f"Expected directory lacks a hashed artifact declaration: {expected}")
        verified = []
        for relative, artifact in declared.items():
            path = (self.project_dir / relative).resolve()
            if not path.is_relative_to(self.project_dir) or not path.is_file(): raise ValueError(f"Declared artifact is missing or outside the project: {relative}")
            digest = sha256_file(path)
            if digest != artifact["sha256"]: raise ValueError(f"Declared artifact hash mismatch: {relative}")
            verified.append({**artifact, "sha256": digest, "bytes": path.stat().st_size})
        return verified

    def _register_artifact(self, state: dict[str, Any], item: dict[str, Any], artifact: dict[str, Any]) -> None:
        reference = {"artifact_id": f"{item['task_id']}:{len(state['artifacts'])}", **artifact, "external": False}; state["artifacts"].append(reference)
        state["memory"]["evidence"]["artifact_refs"].append({"artifact_id": reference["artifact_id"], "sha256": reference["sha256"]})
        domain = {"literature": "literature_state", "empirical-design": "empirical_state", "analysis": "empirical_state", "writing": "manuscript_state", "manuscript-review": "audit_state", "final-audit": "audit_state"}.get(item["task_id"])
        if domain:
            ref = {"path": reference["path"], "sha256": reference["sha256"], "artifact_id": reference["artifact_id"]}; state[domain]["artifact_refs"].append(ref)
            if item["task_id"] == "literature": state["evidence_registry"]["artifact_refs"].append(ref)

    def _complete(self, state: dict[str, Any], item: dict[str, Any], observation: dict[str, Any], run_kind: str) -> None:
        item["status"] = "complete"; item["error"] = None; state["active_task"] = None
        if item["task_id"] not in state["completed_tasks"]: state["completed_tasks"].append(item["task_id"])
        domain_update = {"literature": ("literature_state", "complete"), "empirical-design": ("empirical_state", "running"), "analysis": ("empirical_state", "complete"), "writing": ("manuscript_state", "complete"), "manuscript-review": ("audit_state", "review-required"), "final-audit": ("audit_state", "complete")}.get(item["task_id"])
        if domain_update: state[domain_update[0]]["status"] = domain_update[1]
        self._save(state, "task.completed", {"task_id": item["task_id"], "by": run_kind, "observation_hash": canonical_hash(observation)})

    def _fail(self, state: dict[str, Any], item: dict[str, Any], message: str, run_kind: str, failure_class: str) -> None:
        state["retry_count"] += 1; sync_compatibility_aliases(item)
        error = {"error_id": str(uuid.uuid4()), "task_id": item["task_id"], "source": run_kind, "failure_class": failure_class, "message": message, "attempt": item["attempts"], "at": utc_now()}; state["errors"].append(error)
        if item["attempts"] < item["retry_policy"]["max_attempts"]: item["status"] = "pending"; item["error"] = message
        else:
            item["status"] = "blocked"; item["error"] = message; state["lifecycle_status"] = "blocked"
            if item["task_id"] not in state["blocked_tasks"]: state["blocked_tasks"].append(item["task_id"])
        state["active_task"] = None; self._save(state, "task.failed", error)

    def _block_run(self, state: dict[str, Any], reason: str) -> dict[str, Any]:
        state["current_stage"] = state["lifecycle_status"] = "blocked"; state["active_task"] = None
        self._save(state, "run.blocked", {"reason": reason}); return state
