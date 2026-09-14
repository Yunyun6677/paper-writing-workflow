"""Verify a local public-replication benchmark without redistributing source data."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(manifest_path: Path, repository_root: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paper_results: list[dict[str, Any]] = []
    for paper in manifest["papers"]:
        file_results = []
        for expected in paper["files"]:
            path = (repository_root / expected["path"]).resolve()
            inside_root = path.is_relative_to(repository_root.resolve())
            exists = inside_root and path.is_file()
            actual_hash = sha256(path) if exists else None
            file_results.append({
                "path": expected["path"],
                "role": expected["role"],
                "exists": exists,
                "hash_matches": actual_hash == expected["sha256"],
                "actual_sha256": actual_hash,
            })
        receipt_path = (repository_root / paper["receipt_path"]).resolve()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
        receipt_status_matches = receipt.get("status") == paper["required_receipt_status"]
        integrity_passed = all(item["exists"] and item["hash_matches"] for item in file_results)
        paper_results.append({
            "paper_id": paper["paper_id"],
            "assessment": paper["assessment"],
            "integrity_passed": integrity_passed,
            "receipt_status_matches": receipt_status_matches,
            "verified": integrity_passed and receipt_status_matches,
            "warnings": paper.get("warnings", []),
            "files": file_results,
        })
    all_verified = all(item["verified"] for item in paper_results)
    warning_count = sum(len(item["warnings"]) for item in paper_results)
    return {
        "schema_version": "public-replication-benchmark-receipt/1.0",
        "benchmark_id": manifest["benchmark_id"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": manifest_path.relative_to(repository_root).as_posix(),
        "manifest_sha256": sha256(manifest_path),
        "status": "complete_with_warning" if all_verified and warning_count else ("complete" if all_verified else "failed"),
        "papers_expected": len(manifest["papers"]),
        "papers_verified": sum(item["verified"] for item in paper_results),
        "clean_passes": sum(item["verified"] and item["assessment"] == "pass" for item in paper_results),
        "warning_count": warning_count,
        "papers": paper_results,
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
        raise FileExistsError(f"Refusing to overwrite {output}; pass --force to replace a receipt")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = verify(manifest, root)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "papers_expected", "papers_verified", "clean_passes", "warning_count")}, indent=2))
    return 0 if result["status"] in {"complete", "complete_with_warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
