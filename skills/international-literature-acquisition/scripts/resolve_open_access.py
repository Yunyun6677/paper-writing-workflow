#!/usr/bin/env python3
"""Resolve lawful open-access locations and optionally download real PDFs.

The resolver is metadata-first. It never uses browser cookies or attempts to
bypass authentication. A downloaded file still needs document-identity review
before it becomes ``fulltext-verified`` in the acquisition ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "fulltext-resolution/1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_doi(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", value)
    return value.rstrip(" .")


def http_json(url: str, user_agent: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def candidate(
    source: str,
    url: str | None,
    *,
    url_type: str = "unknown",
    is_oa: bool | None = None,
    version: str | None = None,
    license_name: str | None = None,
) -> dict[str, Any] | None:
    if not url or not url.startswith(("http://", "https://")):
        return None
    if url_type == "unknown" and re.search(r"\.pdf(?:$|[?#])", url, re.I):
        url_type = "pdf"
    score = 0
    if url.startswith("https://"):
        score += 2
    if url_type == "pdf":
        score += 5
    if is_oa is True:
        score += 6
    if license_name:
        score += 2
    if version in {"publishedVersion", "versionOfRecord", "published"}:
        score += 2
    elif version:
        score += 1
    return {
        "source": source,
        "url": url,
        "url_type": url_type,
        "is_oa": is_oa,
        "version": version,
        "license": license_name,
        "score": score,
        "download_status": "not-attempted",
        "local_file": None,
        "sha256": None,
    }


def add_location(rows: list[dict[str, Any]], source: str, location: dict[str, Any] | None) -> None:
    if not location:
        return
    is_oa = location.get("is_oa")
    if is_oa is None and source == "unpaywall":
        is_oa = True
    pdf = candidate(
        source,
        location.get("pdf_url") or location.get("url_for_pdf"),
        url_type="pdf",
        is_oa=is_oa,
        version=location.get("version"),
        license_name=location.get("license"),
    )
    landing = candidate(
        source,
        location.get("landing_page_url") or location.get("url"),
        url_type="landing-page",
        is_oa=is_oa,
        version=location.get("version"),
        license_name=location.get("license"),
    )
    if pdf:
        rows.append(pdf)
    if landing:
        rows.append(landing)


def parse_openalex(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    primary = data.get("primary_location") or {}
    source = primary.get("source") or {}
    work = {
        "doi": normalize_doi(data.get("doi") or ""),
        "title": data.get("title"),
        "year": data.get("publication_year"),
        "venue": source.get("display_name"),
        "openalex_id": data.get("id"),
    }
    rows: list[dict[str, Any]] = []
    add_location(rows, "openalex", data.get("best_oa_location"))
    for location in data.get("locations") or []:
        add_location(rows, "openalex", location)
    return work, rows


def parse_unpaywall(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    journal = data.get("journal_name") or data.get("journal_issns")
    work = {
        "doi": normalize_doi(data.get("doi") or ""),
        "title": data.get("title"),
        "year": data.get("year"),
        "venue": journal,
    }
    rows: list[dict[str, Any]] = []
    add_location(rows, "unpaywall", data.get("best_oa_location"))
    for location in data.get("oa_locations") or []:
        add_location(rows, "unpaywall", location)
    return work, rows


def parse_crossref(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    message = data.get("message") or {}
    published = message.get("published-print") or message.get("published-online") or {}
    date_parts = published.get("date-parts") or []
    year = date_parts[0][0] if date_parts and date_parts[0] else None
    title = (message.get("title") or [None])[0]
    venue = (message.get("container-title") or [None])[0]
    work = {
        "doi": normalize_doi(message.get("DOI") or ""),
        "title": title,
        "year": year,
        "venue": venue,
        "authors": [
            " ".join(filter(None, [row.get("given"), row.get("family")]))
            for row in message.get("author") or []
        ],
    }
    rows: list[dict[str, Any]] = []
    resource = (message.get("resource") or {}).get("primary", {}).get("URL")
    landing = candidate("crossref", resource or message.get("URL"), url_type="landing-page")
    if landing:
        rows.append(landing)
    for link in message.get("link") or []:
        url_type = "pdf" if link.get("content-type") == "application/pdf" else "unknown"
        row = candidate("crossref", link.get("URL"), url_type=url_type, is_oa=None)
        if row:
            rows.append(row)
    return work, rows


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["url"].rstrip("/")
        if key not in unique or row["score"] > unique[key]["score"]:
            unique[key] = row
    return sorted(unique.values(), key=lambda row: (-row["score"], row["source"], row["url"]))


def merge_work(base: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    base = dict(base or {})
    for key, value in incoming.items():
        if value not in (None, "", []) and base.get(key) in (None, "", []):
            base[key] = value
    return base


def safe_stem(work: dict[str, Any], doi: str) -> str:
    value = work.get("title") or doi or "paper"
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", str(value)).strip("_")
    return value[:120] or "paper"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def valid_pdf_bytes(data: bytes) -> bool:
    if len(data) < 50_000 or not data.startswith(b"%PDF-") or b"%%EOF" not in data[-8192:]:
        return False
    page_markers = len(re.findall(rb"/Type\s*/Page\b", data))
    return page_markers >= 2


def download_pdf(row: dict[str, Any], directory: Path, stem: str, user_agent: str) -> dict[str, Any]:
    request = urllib.request.Request(
        row["url"],
        headers={"User-Agent": user_agent, "Accept": "application/pdf"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(80 * 1024 * 1024 + 1)
        if len(data) > 80 * 1024 * 1024:
            row["download_status"] = "failed"
            return row
        if not valid_pdf_bytes(data):
            row["download_status"] = "not-pdf"
            return row
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{stem}.pdf"
        counter = 2
        while path.exists():
            path = directory / f"{stem}_{counter}.pdf"
            counter += 1
        path.write_bytes(data)
        row["download_status"] = "verified"
        row["local_file"] = str(path.resolve())
        row["sha256"] = file_hash(path)
    except urllib.error.HTTPError as exc:
        row["download_status"] = "blocked" if exc.code in {401, 403, 407, 429, 451} else "failed"
    except (urllib.error.URLError, TimeoutError, OSError):
        row["download_status"] = "failed"
    return row


def provider_call(name: str, url: str, parser, report: dict[str, Any], user_agent: str) -> None:
    try:
        data = http_json(url, user_agent)
        work, rows = parser(data)
        report["work"] = merge_work(report["work"], work)
        report["candidates"].extend(rows)
        report["attempts"].append({"provider": name, "result": "ok", "candidate_count": len(rows)})
    except urllib.error.HTTPError as exc:
        report["attempts"].append({"provider": name, "result": f"http-{exc.code}"})
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        report["attempts"].append({"provider": name, "result": "failed", "error_type": type(exc).__name__})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doi", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--download-dir")
    args = parser.parse_args()

    doi = normalize_doi(args.doi)
    if not doi.startswith("10.") or "/" not in doi:
        raise SystemExit("--doi must be a valid DOI")

    contact = os.environ.get("UNPAYWALL_EMAIL", "").strip()
    openalex_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    agent_contact = contact or "research-workflow@example.invalid"
    user_agent = f"paper-writing-workflow/0.5 (mailto:{agent_contact})"
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "query": {"doi": doi},
        "work": None,
        "candidates": [],
        "attempts": [],
        "status": "not-found",
        "secrets_logged": False,
    }

    quoted = urllib.parse.quote(doi, safe="")
    provider_call("crossref", f"https://api.crossref.org/works/{quoted}", parse_crossref, report, user_agent)

    openalex_params = {"api_key": openalex_key} if openalex_key else {}
    openalex_url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    if openalex_params:
        openalex_url += "?" + urllib.parse.urlencode(openalex_params)
    provider_call("openalex", openalex_url, parse_openalex, report, user_agent)

    if contact:
        unpaywall_url = f"https://api.unpaywall.org/v2/{quoted}?" + urllib.parse.urlencode({"email": contact})
        provider_call("unpaywall", unpaywall_url, parse_unpaywall, report, user_agent)
    else:
        report["attempts"].append({"provider": "unpaywall", "result": "skipped-no-email"})

    report["candidates"] = deduplicate(report["candidates"])
    if report["candidates"]:
        report["status"] = "resolved"

    if args.download_dir:
        directory = Path(args.download_dir).resolve()
        stem = safe_stem(report["work"] or {}, doi)
        attempts = 0
        for row in report["candidates"]:
            if attempts >= 3:
                break
            if row["url_type"] != "pdf" or row["is_oa"] is not True:
                continue
            attempts += 1
            download_pdf(row, directory, stem, user_agent)
            if row["download_status"] == "verified":
                report["status"] = "downloaded"
                break
        if report["status"] != "downloaded" and report["candidates"]:
            report["status"] = "needs-human"

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "candidates": len(report["candidates"]), "output": str(output.resolve())}))
    return 0 if report["status"] in {"resolved", "downloaded"} else 2


if __name__ == "__main__":
    sys.exit(main())
