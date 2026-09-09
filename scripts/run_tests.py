#!/usr/bin/env python3
"""Run all repository test entry points without requiring pytest."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
    [sys.executable, "skills/economics-empirical-analysis/scripts/test_empirical.py"],
    [sys.executable, "skills/economics-empirical-analysis/scripts/test_method_preflight.py"],
    [sys.executable, "skills/economics-empirical-analysis/scripts/test_r_bridge.py"],
    [sys.executable, "skills/economics-paper-workflow/scripts/test_paper_workflow.py"],
    [sys.executable, "skills/international-literature-acquisition/scripts/test_resolve_open_access.py"],
]


def main() -> int:
    for command in COMMANDS:
        print("RUN", " ".join(command[1:]), flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    print("All repository test entry points passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
