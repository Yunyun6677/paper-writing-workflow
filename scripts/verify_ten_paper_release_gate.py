"""Verify the local ten-public-paper v0.11 release gate.

Source papers and datasets remain gitignored.  The committed manifest contains
only citations, source URLs, declared checks, and content hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.verify_public_replication_benchmark import verify as verify_base
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from verify_public_replication_benchmark import verify as verify_base


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_file(root: Path, relative: str, expected: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    inside = path.is_relative_to(root)
    exists = inside and path.is_file()
    actual = sha256(path) if exists else None
    return {
        "path": relative,
        "exists": exists,
        "hash_matches": actual == expected,
        "actual_sha256": actual,
    }


def verify(manifest_path: Path, root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_path = (root / manifest["base_manifest"]).resolve()
    base = verify_base(base_path, root)
    cases: list[dict[str, Any]] = []
    for paper in manifest["additional_papers"]:
        fulltext = paper["fulltext"]
        files = [
            check_file(root, fulltext["path"], fulltext["sha256"]),
            check_file(root, fulltext["text_path"], fulltext["text_sha256"]),
            check_file(root, paper["data"]["path"], paper["data"]["sha256"]),
            check_file(root, paper["result_path"], paper["result_sha256"]),
            check_file(root, paper["receipt_path"], paper["receipt_sha256"]),
        ]
        pdf_path = root / fulltext["path"]
        text_path = root / fulltext["text_path"]
        pdf_signature = pdf_path.read_bytes()[:5] == b"%PDF-" if pdf_path.is_file() else False
        extracted = text_path.read_text(encoding="utf-8", errors="replace") if text_path.is_file() else ""
        page_markers = extracted.count("===== PDF PAGE ")
        title_found = fulltext["title_anchor"].casefold() in extracted.casefold()
        receipt_path = root / paper["receipt_path"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
        receipt_ok = receipt.get("status") == "complete" and receipt.get("assessment") == paper["assessment"]
        verified = (
            all(item["exists"] and item["hash_matches"] for item in files)
            and pdf_signature
            and page_markers >= fulltext["minimum_pages"]
            and title_found
            and receipt_ok
        )
        cases.append({
            "paper_id": paper["paper_id"],
            "assessment": paper["assessment"],
            "verified": verified,
            "pdf_signature": pdf_signature,
            "page_markers": page_markers,
            "minimum_pages": fulltext["minimum_pages"],
            "title_anchor_found": title_found,
            "receipt_ok": receipt_ok,
            "files": files,
        })

    runtime = [
        {**check_file(root, item["path"], item["sha256"]), "proves": item["proves"]}
        for item in manifest["runtime_evidence"]
    ]
    total = base["papers_verified"] + sum(item["verified"] for item in cases)
    clean = base["clean_passes"] + sum(
        item["verified"] and item["assessment"] == "pass" for item in cases
    )
    gate_checks = {
        "base_manifest_verified": base["papers_verified"] == manifest["base_papers_required"],
        "additional_papers_verified": sum(item["verified"] for item in cases) == manifest["additional_papers_required"],
        "ten_papers_verified": total == manifest["total_papers_required"],
        "minimum_clean_matches_met": clean >= manifest["minimum_clean_author_table_matches"],
        "runtime_receipts_verified": all(item["exists"] and item["hash_matches"] for item in runtime),
    }
    passed = all(gate_checks.values())
    bounded_warning_count = base["warning_count"] + sum(
        item["assessment"] != "pass" for item in cases
    )
    return {
        "schema_version": "ten-paper-release-gate-receipt/1.0",
        "benchmark_id": manifest["benchmark_id"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete_with_warning" if passed and bounded_warning_count else ("complete" if passed else "failed"),
        "release_gate_passed": passed,
        "gate_checks": gate_checks,
        "papers_expected": manifest["total_papers_required"],
        "papers_verified": total,
        "clean_author_table_matches": clean,
        "bounded_warning_count": bounded_warning_count,
        "base_benchmark": base,
        "additional_papers": cases,
        "runtime_evidence": runtime,
        "manifest_path": manifest_path.relative_to(root).as_posix(),
        "manifest_sha256": sha256(manifest_path),
        "certification_boundary": manifest["certification_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    manifest = args.manifest.resolve()
    output = args.output.resolve()
    if output.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite {output}; pass --force to replace it")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = verify(manifest, root)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        key: result[key]
        for key in ("status", "release_gate_passed", "papers_expected", "papers_verified", "clean_author_table_matches", "bounded_warning_count")
    }, indent=2))
    return 0 if result["release_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
