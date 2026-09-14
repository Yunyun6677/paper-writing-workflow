"""Run environment-dependent Tier-1 tools and persist a truthful receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from pypdf import PdfWriter

ROOT = Path(__file__).parents[1].resolve()
sys.path.insert(0, str(ROOT))

from research_os.tools import default_registry


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="work/v011-tier1-live-20260914")
    args = parser.parse_args()
    run = (ROOT / args.run).resolve()
    if run.exists():
        raise FileExistsError(run)
    run.mkdir(parents=True)
    registry = default_registry(); results = {}
    fixture = ROOT / "tests/fixtures/tier1"
    python_script = fixture / "python_smoke.py"
    results["python"] = registry.execute("python", {
        "script": python_script.relative_to(ROOT).as_posix(), "script_sha256": sha(python_script),
        "output_directory": f"{args.run}/python", "idempotency_key": "stage05-python-live",
        "arguments": [f"{args.run}/python/result.json"], "required_outputs": [f"{args.run}/python/result.json"],
    }, ROOT, data_sensitivity="synthetic")
    r_script = fixture / "r_smoke.R"
    results["r"] = registry.execute("r", {
        "script": r_script.relative_to(ROOT).as_posix(), "script_sha256": sha(r_script),
        "output_directory": f"{args.run}/r", "idempotency_key": "stage05-r-live",
        "required_outputs": [f"{args.run}/r/result.csv"], "executable": "D:/R-4.4.2/bin/Rscript.exe",
    }, ROOT, data_sensitivity="synthetic")
    stata_script = fixture / "stata_smoke.do"
    results["stata"] = registry.execute("stata", {
        "script": stata_script.relative_to(ROOT).as_posix(), "script_sha256": sha(stata_script),
        "output_directory": f"{args.run}/stata", "idempotency_key": "stage05-stata-live",
        "required_outputs": [f"{args.run}/stata/result.csv"], "executable": "D:/Stata/StataSE-64.exe",
    }, ROOT, data_sensitivity="synthetic")
    pdf = run / "sample.pdf"; writer = PdfWriter(); writer.add_blank_page(width=200, height=200)
    with pdf.open("wb") as stream: writer.write(stream)
    results["pdf_parser"] = registry.execute("pdf_parser", {
        "pdf": pdf.relative_to(ROOT).as_posix(), "source_sha256": sha(pdf),
        "output": f"{args.run}/pdf/pages.json",
    }, ROOT, data_sensitivity="synthetic")
    results["git_inspect"] = registry.execute("git_inspect", {"operation": "head"}, ROOT)
    results["latex"] = {"status": "unavailable", "reason": "No latexmk/xelatex discovered"} if not (shutil.which("latexmk") or shutil.which("xelatex")) else {"status": "discovered-not-smoked"}
    receipt = {"schema_version": "v0.11-stage-receipt/1.0", "stage": 5,
               "status": "tested-with-environment-boundary", "results": results, "production_certified": False}
    (ROOT / "tests/receipts/v011-stage05-tier1-tools.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: value["status"] for name, value in results.items()}, indent=2))
    return 0 if all(results[name]["status"] == "complete" for name in ("python", "r", "stata", "pdf_parser", "git_inspect")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
