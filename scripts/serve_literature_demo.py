#!/usr/bin/env python3
"""Start the local-only Research OS literature demonstration UI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_os.literature_demo_http import serve


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=str(ROOT / ".runtime" / "literature-demo"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.data_root, args.port)
