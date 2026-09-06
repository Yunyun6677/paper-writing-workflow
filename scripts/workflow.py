#!/usr/bin/env python3
"""Read-only Phase 1 utilities for the personal literature workflow."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://127.0.0.1:23119"


def api_json(path: str):
    request = urllib.request.Request(BASE + path, headers={"Zotero-API-Version": "3"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def api_all(path: str):
    records = []
    start = 0
    joiner = "&" if "?" in path else "?"
    while start < 10000:
        page = api_json(f"{path}{joiner}limit=100&start={start}")
        records.extend(page)
        if len(page) < 100:
            return records
        start += len(page)
    raise RuntimeError(f"Pagination safety limit reached for {path}")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def doctor(_: argparse.Namespace) -> int:
    try:
        schema = api_json("/api/schema")
        connector = urllib.request.urlopen(BASE + "/connector/ping", timeout=10).read().decode("utf-8")
        print(json.dumps({
            "ok": True,
            "local_api": {"reachable": True, "schema_version": schema.get("version")},
            "connector": {"reachable": True, "response": connector},
        }, ensure_ascii=False, indent=2))
        return 0
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


def snapshot(args: argparse.Namespace) -> int:
    items = api_all("/api/users/0/items")
    collections = api_all("/api/users/0/collections")
    tags = api_all("/api/users/0/tags")
    types = Counter(x.get("data", {}).get("itemType", "unknown") for x in items)
    payload = {
        "schema_version": "zotero-library-snapshot/1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {"kind": "zotero-local-api", "base_url": BASE, "read_only": True},
        "counts": {"items": len(items), "collections": len(collections), "tags": len(tags), "item_types": dict(types)},
        "collections": [
            {"key": x["key"], "name": x["data"].get("name", ""), "parent_collection": x["data"].get("parentCollection", False)}
            for x in collections
        ],
    }
    write_json(Path(args.out), payload)
    print(str(Path(args.out).resolve()))
    return 0


def new_request(args: argparse.Namespace) -> int:
    payload = {
        "schema_version": "research-request/1.0",
        "request_id": str(uuid.uuid4()),
        "research_question": "请在这里填写一个可检索的研究问题",
        "concepts": ["数字经济", "国际贸易"],
        "date_range": {"from": 2000, "to": datetime.now().year},
        "languages": ["zh-CN", "en"],
        "sources": ["OpenAlex", "Crossref", "CNKI-export"],
        "target_collection": "00_Inbox",
        "max_results_per_source": 50,
        "notes": "国内数据库结果优先导出 RIS/BibTeX；导入 Zotero 前人工确认。"
    }
    write_json(Path(args.out), payload)
    print(str(Path(args.out).resolve()))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor").set_defaults(func=doctor)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--out", required=True)
    snap.set_defaults(func=snapshot)
    req = sub.add_parser("new-request")
    req.add_argument("--out", required=True)
    req.set_defaults(func=new_request)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
