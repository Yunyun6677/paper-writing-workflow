from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from research_os.sandbox import DockerSandboxBackend, LocalRestrictedBackend, SandboxRequest


class SandboxBackendTests(unittest.TestCase):
    def test_local_backend_executes_without_secret_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); script = root / "probe.py"
            script.write_text(
                "import os\nprint(os.getenv('RESEARCH_OS_NETWORK_POLICY'))\n"
                "print('LEAK' if any('TOKEN' in k for k in os.environ) else 'CLEAN')\n",
                encoding="utf-8",
            )
            result = LocalRestrictedBackend(root).run(SandboxRequest(
                command=(sys.executable, str(script)), network_policy="deny",
            ))
            self.assertEqual(result.returncode, 0)
            self.assertIn("deny", result.stdout)
            self.assertIn("CLEAN", result.stdout)
            self.assertEqual(result.isolation["sandbox_backend"], "local-restricted")
            self.assertFalse(result.isolation["production_security_boundary"])

    def test_local_backend_rejects_escaping_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(PermissionError):
                LocalRestrictedBackend(root).run(SandboxRequest(
                    command=(sys.executable, "-c", "print(1)"), working_directory="..",
                ))

    def test_docker_backend_fails_closed_when_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DockerSandboxBackend(tmp, "python:3.12", docker_executable=Path(tmp) / "missing-docker")
            self.assertFalse(backend.available())
            with self.assertRaises(FileNotFoundError):
                backend.run(SandboxRequest(command=("python", "-V")))


if __name__ == "__main__":
    unittest.main()
