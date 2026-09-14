from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_os.runtime import ResearchRuntime
from research_os.state_backends import FileStateBackend, SQLiteStateBackend, open_state_backend
from research_os.store import RunLockError, StateConflictError


def write_manifest(path: Path, project_id: str) -> Path:
    path.write_text(json.dumps({
        "schema_version": "economics-paper-project/1.0", "project_id": project_id,
        "title_working": "State backend test", "paper_type": "review", "stage": "idea",
        "research_question": "Can canonical state reject concurrent stale updates?",
        "target_journals": [{"name": "undecided", "family": "undecided"}],
        "contribution_claims": [], "data_sensitivity": "synthetic",
        "approvals": {"question_and_contribution": False, "research_design": False, "outline_and_journal": False},
        "output_format": "latex",
    }), encoding="utf-8")
    return path


class StateBackendTests(unittest.TestCase):
    def _backend(self, root: Path, kind: str):
        return ResearchRuntime.initialize(
            write_manifest(root / f"{kind}.json", f"backend-{kind}"), root / "runs",
            state_backend=kind,
        )

    def test_file_and_sqlite_backends_reject_stale_state_versions(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                backend = self._backend(Path(tmp), kind)
                first, version = backend.load_with_version(); stale = json.loads(json.dumps(first))
                first["current_stage"] = "first-writer"
                next_version = backend.save(first, "test.first", {}, expected_version=version)
                self.assertEqual(next_version, version + 1)
                stale["current_stage"] = "stale-writer"
                with self.assertRaises(StateConflictError):
                    backend.save(stale, "test.stale", {}, expected_version=version)
                self.assertEqual(backend.load()["current_stage"], "first-writer")

    def test_event_sequence_is_strict_and_backend_discovery_survives_restart(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                backend = self._backend(Path(tmp), kind)
                state, version = backend.load_with_version()
                backend.save(state, "test.event", {"value": 1}, expected_version=version)
                events = [json.loads(line) for line in backend.events_path.read_text(encoding="utf-8").splitlines()]
                sequences = [item["payload"]["event_sequence"] for item in events]
                self.assertEqual(sequences, list(range(1, len(sequences) + 1)))
                reopened = open_state_backend(backend.run_dir)
                self.assertIsInstance(reopened, SQLiteStateBackend if kind == "sqlite" else FileStateBackend)
                self.assertEqual(reopened.load()["run_id"], state["run_id"])

    def test_run_locks_have_explicit_ownership(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                backend = self._backend(Path(tmp), kind)
                backend.acquire_run_lock("worker-a")
                with self.assertRaises(RunLockError):
                    backend.acquire_run_lock("worker-b")
                with self.assertRaises(RunLockError):
                    backend.release_run_lock("worker-b")
                backend.release_run_lock("worker-a")
                backend.acquire_run_lock("worker-b")
                backend.release_run_lock("worker-b")

    def test_sqlite_runtime_transition_is_transactional_and_checkpointed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir()
            backend = ResearchRuntime.initialize(
                write_manifest(project / "manifest.json", "sqlite-runtime"), root / "runs",
                state_backend="sqlite",
            )
            runtime = ResearchRuntime(backend, project)
            state = runtime.run(max_steps=1)
            self.assertEqual(state["task_graph"][0]["status"], "waiting-agent")
            self.assertFalse(backend.verify())
            self.assertGreater(backend.load_with_version()[1], 1)
            self.assertTrue((backend.run_dir / "runtime-state.sqlite").is_file())


if __name__ == "__main__":
    unittest.main()
