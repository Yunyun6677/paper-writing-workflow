from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1].resolve()
sys.path.insert(0, str(ROOT))

from research_os.adapters.codex_cli import CodexCLIAdapter
from research_os.vertical_slice import run_vertical_slice


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.12 real-Codex public-data vertical slice")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--dataset", help="Optional already downloaded hash-pinned mtcars CSV")
    args = parser.parse_args()
    run_root = (ROOT / args.run_root).resolve()
    if run_root.exists():
        raise FileExistsError(run_root)
    run_root.mkdir(parents=True)
    receipt = run_vertical_slice(
        run_root, dataset_source=Path(args.dataset).resolve() if args.dataset else None,
        adapter_factory=lambda project, adapter_root: CodexCLIAdapter(
            project, adapter_root, sandbox="read-only", persist_sessions=False
        ),
    )
    print(json.dumps({"status":receipt["status"],"runtime_status":receipt["runtime_status"],
                      "injected_failure_observed":receipt.get("injected_failure_observed", False),
                      "autonomous_repair_observed":receipt.get("autonomous_repair_observed", False)}, indent=2))
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
