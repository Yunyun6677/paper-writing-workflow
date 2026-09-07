#!/usr/bin/env python3
"""Snapshot and verify CNKI downloads without exposing browser credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

SUPPORTED = {".pdf", ".caj"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_record(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def snapshot(directory: Path) -> dict:
    files = [
        file_record(path)
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED
    ]
    files.sort(key=lambda row: (row["mtime_ns"], row["name"]), reverse=True)
    return {
        "schema_version": "cnki-download-snapshot/1.0",
        "created_at": now_iso(),
        "directory": str(directory.resolve()),
        "files": files,
    }


def normalize_title(value: str) -> str:
    return "".join(re.findall(r"[0-9a-z\u4e00-\u9fff]+", value.casefold()))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pdf_checks(path: Path) -> tuple[list[str], int | None]:
    errors: list[str] = []
    with path.open("rb") as stream:
        header = stream.read(8)
        stream.seek(max(0, path.stat().st_size - 4096))
        tail = stream.read()
    if not header.startswith(b"%PDF-"):
        errors.append("missing PDF signature")
    if b"%%EOF" not in tail:
        errors.append("missing PDF EOF marker")

    page_count = None
    try:
        from pypdf import PdfReader

        page_count = len(PdfReader(str(path)).pages)
        if page_count < 2:
            errors.append("PDF has fewer than two pages")
    except ImportError:
        errors.append("pypdf unavailable; page structure not verified")
    except Exception as exc:  # malformed/encrypted PDFs are not verified
        errors.append(f"PDF page read failed: {exc}")
    return errors, page_count


def caj_checks(path: Path) -> list[str]:
    with path.open("rb") as stream:
        header = stream.read(16)
    if b"CAJ" not in header.upper():
        return ["missing recognizable CAJ signature"]
    return []


def select_candidate(directory: Path, baseline: dict) -> Path | None:
    previous = {
        row["name"]: (row.get("size"), row.get("mtime_ns"))
        for row in baseline.get("files", [])
    }
    candidates = []
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        current = file_record(path)
        if previous.get(path.name) != (current["size"], current["mtime_ns"]):
            candidates.append(path)
    return max(candidates, key=lambda path: path.stat().st_mtime_ns, default=None)


def unique_destination(archive_dir: Path, source: Path) -> Path:
    candidate = archive_dir / source.name
    if not candidate.exists():
        return candidate
    source_hash = sha256(source)
    if sha256(candidate) == source_hash:
        return candidate
    counter = 2
    while True:
        candidate = archive_dir / f"{source.stem}_{counter}{source.suffix.lower()}"
        if not candidate.exists():
            return candidate
        counter += 1


def verify(args: argparse.Namespace) -> dict:
    directory = Path(args.directory).resolve()
    baseline = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    candidate = select_candidate(directory, baseline)
    result = {
        "schema_version": "cnki-download-verification/1.0",
        "verified_at": now_iso(),
        "expected_title": args.expected_title,
        "status": "needs-human",
        "source_file": None,
        "archive_file": None,
        "format": None,
        "size": None,
        "sha256": None,
        "page_count": None,
        "title_similarity": None,
        "checks": [],
        "errors": [],
    }
    if candidate is None:
        result["errors"].append("no new or changed PDF/CAJ file found after snapshot")
        return result

    result["source_file"] = str(candidate)
    result["format"] = candidate.suffix.lower().lstrip(".")
    result["size"] = candidate.stat().st_size
    result["sha256"] = sha256(candidate)

    if candidate.stat().st_size < args.min_bytes:
        result["errors"].append(f"file smaller than minimum {args.min_bytes} bytes")
    else:
        result["checks"].append("plausible file size")

    expected = normalize_title(args.expected_title)
    observed = normalize_title(candidate.stem)
    similarity = SequenceMatcher(None, expected, observed).ratio() if expected else 1.0
    result["title_similarity"] = round(similarity, 4)
    if similarity < args.title_threshold:
        result["errors"].append(
            f"filename/title similarity {similarity:.3f} below {args.title_threshold:.3f}"
        )
    else:
        result["checks"].append("filename matches expected title")

    if candidate.suffix.lower() == ".pdf":
        errors, page_count = pdf_checks(candidate)
        result["page_count"] = page_count
        result["errors"].extend(errors)
        if not errors:
            result["checks"].append("PDF signature, EOF, and page structure verified")
    else:
        errors = caj_checks(candidate)
        result["errors"].extend(errors)
        if not errors:
            result["checks"].append("CAJ signature verified")

    if result["errors"]:
        return result

    archive_dir = Path(args.archive_dir).resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(archive_dir, candidate)
    if not destination.exists():
        shutil.copy2(candidate, destination)
    if sha256(destination) != result["sha256"]:
        result["errors"].append("archive copy hash mismatch")
        return result

    result["archive_file"] = str(destination)
    result["checks"].append("archive copy hash verified")
    result["status"] = "fulltext-verified"
    return result


def write_json(data: dict, output: str) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if output == "-":
        sys.stdout.write(text)
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(json.dumps({"status": data.get("status", "snapshot"), "output": str(path)}))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot")
    snap.add_argument("--directory", required=True)
    snap.add_argument("--output", required=True)

    check = sub.add_parser("verify")
    check.add_argument("--directory", required=True)
    check.add_argument("--snapshot", required=True)
    check.add_argument("--expected-title", required=True)
    check.add_argument("--archive-dir", required=True)
    check.add_argument("--output", required=True)
    check.add_argument("--min-bytes", type=int, default=50_000)
    check.add_argument("--title-threshold", type=float, default=0.45)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        raise SystemExit(f"download directory not found: {directory}")
    if args.command == "snapshot":
        write_json(snapshot(directory), args.output)
        return 0
    result = verify(args)
    write_json(result, args.output)
    return 0 if result["status"] == "fulltext-verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
