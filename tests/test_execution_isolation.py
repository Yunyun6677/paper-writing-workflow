from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from research_os.isolation import ExecutionPolicy, LocalProcessBoundary


class ExecutionIsolationTests(unittest.TestCase):
    def test_path_environment_and_fail_closed_network_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); boundary = LocalProcessBoundary(root)
            policy = ExecutionPolicy(allowed_roots=(str(Path(sys.executable).parent),))
            outside = Path(tmp).parent / "outside.txt"
            with self.assertRaises(PermissionError):
                boundary.run([sys.executable, "-c", "pass", str(outside)], cwd=root, timeout=2, policy=policy)
            with self.assertRaises(PermissionError):
                boundary.run([sys.executable, "-c", "pass"], cwd=root, timeout=2, policy=policy,
                             environment={"API_KEY": "not-allowed"})
            with self.assertRaises(RuntimeError):
                boundary.run([sys.executable, "-c", "pass"], cwd=root, timeout=2,
                             policy=ExecutionPolicy(allowed_roots=(str(Path(sys.executable).parent),),
                                                    require_os_network_isolation=True))

    def test_timeout_terminates_spawned_process_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); marker = root / "child-finished.txt"
            child = root / "child.py"
            child.write_text("import pathlib,sys,time\ntime.sleep(1.5)\npathlib.Path(sys.argv[1]).write_text('leaked')\n")
            parent = root / "parent.py"
            parent.write_text(
                "import subprocess,sys,time\n"
                "subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]])\n"
                "time.sleep(10)\n"
            )
            policy = ExecutionPolicy(allowed_roots=(str(Path(sys.executable).parent),))
            result = LocalProcessBoundary(root).run(
                [sys.executable, str(parent), str(child), str(marker)], cwd=root, timeout=.3, policy=policy)
            self.assertTrue(result.timed_out)
            self.assertEqual(result.termination, "windows-job-object" if sys.platform == "win32" else "kill-process-group")
            time.sleep(1.7)
            self.assertFalse(marker.exists(), "child process survived the timeout boundary")


if __name__ == "__main__":
    unittest.main()
