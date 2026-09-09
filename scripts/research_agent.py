#!/usr/bin/env python3
"""Command line entry point for the persistent Research OS agent kernel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_os.migrations import migrate_project
from research_os.evaluation import evaluate
from research_os.runtime import ResearchRuntime
from research_os.store import ResearchStateStore


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def runtime(args: argparse.Namespace) -> ResearchRuntime:
    return ResearchRuntime(ResearchStateStore(args.run_dir), args.project_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Persistent Research OS agent kernel")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--manifest", required=True)
    init.add_argument("--run-root", required=True)
    init.add_argument("--parent-run-id")
    migrate = sub.add_parser("migrate")
    migrate.add_argument("--project-dir", required=True)
    migrate.add_argument("--run-root", required=True)
    migrate.add_argument("--parent-run-id")
    for name in ["run", "resume", "recover", "reconstruct", "status", "verify", "evaluate"]:
        command = sub.add_parser(name)
        command.add_argument("--run-dir", required=True)
        command.add_argument("--project-dir", required=True)
    pause = sub.add_parser("pause")
    pause.add_argument("--run-dir", required=True)
    pause.add_argument("--project-dir", required=True)
    pause.add_argument("--reason", required=True)
    observe = sub.add_parser("observe")
    observe.add_argument("--run-dir", required=True)
    observe.add_argument("--project-dir", required=True)
    observe.add_argument("--task-id", required=True)
    observe.add_argument("--observation", required=True)
    decide = sub.add_parser("decide")
    decide.add_argument("--run-dir", required=True)
    decide.add_argument("--project-dir", required=True)
    decide.add_argument("--action-id", required=True)
    decide.add_argument("--approve", action="store_true")
    decide.add_argument("--reject", action="store_true")
    decide.add_argument("--rationale", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            store = ResearchRuntime.initialize(args.manifest, args.run_root, args.parent_run_id)
            emit({"status": "initialized", "run_dir": str(store.run_dir), "state": str(store.state_path)})
        elif args.command == "migrate":
            store = migrate_project(args.project_dir, args.run_root, args.parent_run_id)
            emit({"status": "migrated", "run_dir": str(store.run_dir), "receipt": str(store.run_dir / 'migration-receipt.json')})
        elif args.command in {"run", "resume"}:
            state = runtime(args).resume() if args.command == "resume" else runtime(args).run()
            emit({"run_id": state["run_id"], "stage": state["current_stage"], "completed": state["completed_tasks"], "blocked": state["blocked_tasks"], "pending_human_actions": state["pending_human_actions"]})
        elif args.command == "pause":
            state = runtime(args).pause(args.reason)
            emit({"run_id": state["run_id"], "status": state["lifecycle_status"], "stage": state["current_stage"]})
        elif args.command == "reconstruct":
            state = runtime(args).reconstruct()
            emit({"run_id": state["run_id"], "status": state["lifecycle_status"], "working_memory": state["memory"]["working"]})
        elif args.command == "status":
            state = ResearchStateStore(args.run_dir).load()
            emit({"run_id": state["run_id"], "lifecycle_status": state["lifecycle_status"], "stage": state["current_stage"], "active_task": state["active_task"], "tasks": [{"task_id": t["task_id"], "assigned_agent": t["assigned_agent"], "status": t["status"], "attempts": t["attempts"], "max_attempts": t["retry_policy"]["max_attempts"]} for t in state["task_graph"]], "pending_human_actions": state["pending_human_actions"]})
        elif args.command == "verify":
            store = ResearchStateStore(args.run_dir)
            errors = store.verify()
            ResearchRuntime._validate_state(store.load())
            emit({"status": "pass" if not errors else "blocked", "errors": errors})
            return 1 if errors else 0
        elif args.command == "evaluate":
            result = evaluate(ResearchStateStore(args.run_dir))
            schema = json.loads((ROOT / "schemas" / "agent-run-evaluation.schema.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(result)
            emit(result)
        elif args.command == "recover":
            store = ResearchStateStore(args.run_dir)
            state = store.recover_latest()
            ResearchRuntime._validate_state(state)
            emit({"status": "recovered", "run_id": state["run_id"], "stage": state["current_stage"]})
        elif args.command == "observe":
            observation = json.loads(Path(args.observation).read_text(encoding="utf-8"))
            schema = json.loads((ROOT / "schemas" / "research-agent-observation.schema.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(observation)
            state = runtime(args).observe_agent(args.task_id, observation)
            emit({"status": _status(state, args.task_id), "next_stage": state["current_stage"]})
        else:
            if args.approve == args.reject:
                raise ValueError("Choose exactly one of --approve or --reject")
            state = runtime(args).decide(args.action_id, args.approve, args.rationale)
            emit({"status": "approved" if args.approve else "rejected", "stage": state["current_stage"]})
        return 0
    except Exception as exc:
        emit({"status": "error", "error": str(exc)})
        return 2


def _status(state: dict, task_id: str) -> str:
    return next(task["status"] for task in state["task_graph"] if task["task_id"] == task_id)


if __name__ == "__main__":
    raise SystemExit(main())
