#!/usr/bin/env python3
"""Import verified papers and PDF bytes through Zotero Desktop Connector.

The PDF is stored locally by Zotero and does not use the Zotero Web API file
upload flow. The Web API is used only for project collections and metadata
classification. Secrets are read from the environment and never logged.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

CONNECTOR = "http://127.0.0.1:23119/connector"
LOCAL_API = "http://127.0.0.1:23119/api/users/0"
WEB_API = "https://api.zotero.org"


def http_json(method: str, url: str, body=None, headers=None, timeout=60):
    req_headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return (json.loads(raw) if raw else {}), response.status


def local_get(path: str):
    return http_json("GET", LOCAL_API + path, headers={"Zotero-API-Version": "3"})[0]


def normalize_doi(value: str) -> str:
    return value.strip().lower().removeprefix("https://doi.org/").removeprefix("doi:")


def find_local_item(doi: str, title: str):
    query = doi or title
    encoded = urllib.parse.urlencode({"q": query, "qmode": "everything", "limit": 100})
    for row in local_get("/items/top?" + encoded):
        data = row.get("data", {})
        if doi and normalize_doi(data.get("DOI", "")) == normalize_doi(doi):
            return row
        if not doi and data.get("title", "").strip().casefold() == title.strip().casefold():
            return row
    return None


def children(item_key: str):
    return local_get(f"/items/{item_key}/children?limit=100")


def is_local_pdf(child: dict) -> bool:
    """Return true for PDF bytes that Zotero Desktop has stored locally.

    Connector imports are reported as ``imported_url`` rather than
    ``imported_file`` even though the enclosure is a local file in Zotero's
    storage directory.
    """
    data = child.get("data", {})
    return (
        data.get("contentType") == "application/pdf"
        and data.get("linkMode") in {"imported_file", "imported_url"}
        and bool(child.get("links", {}).get("enclosure", {}).get("href", "").startswith("file:///"))
    )


class WebZotero:
    def __init__(self):
        user_id = os.environ.get("ZOTERO_USER_ID", "").strip()
        api_key = os.environ.get("ZOTERO_API_KEY", "").strip()
        if not user_id or not api_key:
            raise RuntimeError("ZOTERO_USER_ID or ZOTERO_API_KEY is missing")
        self.root = f"{WEB_API}/users/{user_id}"
        self.headers = {"Zotero-API-Key": api_key, "Zotero-API-Version": "3"}

    def request(self, method: str, path: str, body=None, headers=None):
        merged = dict(self.headers)
        merged.update(headers or {})
        return http_json(method, self.root + path, body=body, headers=merged)[0]

    def all(self, path: str):
        rows = []
        start = 0
        joiner = "&" if "?" in path else "?"
        while True:
            page = self.request("GET", f"{path}{joiner}limit=100&start={start}")
            rows.extend(page)
            if len(page) < 100:
                return rows
            start += len(page)


def ensure_collection(z: WebZotero, name: str, parent, audit: list):
    for row in z.all("/collections"):
        data = row["data"]
        if data.get("name") == name and data.get("parentCollection", False) == parent:
            return row["key"]
    result = z.request("POST", "/collections", [{"name": name, "parentCollection": parent}])
    key = result["successful"]["0"]["key"]
    audit.append({"action": "collection-created", "name": name, "key": key})
    return key


def classify(z: WebZotero, item_key: str, collection_keys: list[str], tags: list[str], audit: list):
    row = z.request("GET", f"/items/{item_key}")
    data = row["data"]
    current_collections = list(data.get("collections", []))
    for key in collection_keys:
        if key not in current_collections:
            current_collections.append(key)
    data["collections"] = current_collections
    current_tags = {x.get("tag") for x in data.get("tags", [])}
    for tag in tags:
        if tag not in current_tags:
            data.setdefault("tags", []).append({"tag": tag, "type": 0})
    z.request(
        "PUT",
        f"/items/{item_key}",
        data,
        {"If-Unmodified-Since-Version": str(row["version"])},
    )
    audit.append({"action": "classified", "item_key": item_key})


def save_with_attachment(record: dict):
    pdf_path = Path(record["pdf_path"]).resolve()
    pdf_bytes = pdf_path.read_bytes()
    if len(pdf_bytes) < 10_000 or pdf_bytes[:5] != b"%PDF-":
        raise ValueError(f"Not a valid PDF: {pdf_path}")
    session_id = "wf-" + uuid.uuid4().hex
    connector_item_id = "item-" + uuid.uuid4().hex
    item = dict(record["item"])
    item["id"] = connector_item_id
    item.setdefault("tags", []).extend(
        [{"tag": tag} for tag in record.get("tags", [])]
    )
    http_json(
        "POST",
        CONNECTOR + "/saveItems",
        {"items": [item], "uri": record["source_url"], "sessionID": session_id},
        {"X-Zotero-Connector-API-Version": "3", "Zotero-Allowed-Request": "true"},
    )
    metadata = json.dumps(
        {
            "sessionID": session_id,
            "parentItemID": connector_item_id,
            "title": record.get("attachment_title", pdf_path.name),
            "url": record["source_url"],
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    request = urllib.request.Request(
        CONNECTOR + "/saveAttachment",
        data=pdf_bytes,
        headers={
            "Content-Type": "application/pdf",
            "Content-Length": str(len(pdf_bytes)),
            "X-Metadata": metadata,
            "Zotero-Allowed-Request": "true",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status not in (200, 201):
            raise RuntimeError(f"saveAttachment returned {response.status}")


def wait_for_item(doi: str, title: str, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = find_local_item(doi, title)
        if row:
            return row
        time.sleep(1)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--audit", required=True)
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    report = {
        "schema_version": "zotero-local-fulltext-import/1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "secrets_logged": False,
        "actions": [],
        "errors": [],
    }
    if not args.apply:
        report["planned_records"] = len(manifest["records"])
        Path(args.audit).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "dry-run", "records": len(manifest["records"])}))
        return 0

    web = WebZotero()
    hierarchy = manifest["collection_hierarchy"]
    keys = {}
    parent = False
    for name in hierarchy:
        parent = ensure_collection(web, name, parent, report["actions"])
        keys[name] = parent
    topic_key = parent
    subkeys = {}
    for name in manifest.get("subcollections", []):
        subkeys[name] = ensure_collection(web, name, topic_key, report["actions"])

    for record in manifest["records"]:
        title = record["item"]["title"]
        doi = record["item"].get("DOI", "")
        try:
            existing = find_local_item(doi, title)
            if existing:
                local_files = [child for child in children(existing["key"]) if is_local_pdf(child)]
                if not local_files:
                    report["actions"].append({
                        "action": "skipped-existing-without-local-file",
                        "item_key": existing["key"], "title": title,
                    })
                    continue
                item_key = existing["key"]
                report["actions"].append({"action": "reused", "item_key": item_key, "title": title})
            else:
                save_with_attachment(record)
                created = wait_for_item(doi, title)
                if not created:
                    raise RuntimeError("Item not visible in local API after connector import")
                item_key = created["key"]
                imported_files = [child for child in children(item_key) if is_local_pdf(child)]
                if not imported_files:
                    raise RuntimeError("Metadata created but imported PDF attachment was not verified")
                report["actions"].append({
                    "action": "created-with-local-pdf", "item_key": item_key,
                    "attachment_keys": [x["key"] for x in imported_files], "title": title,
                })

            destinations = [topic_key] + [subkeys[name] for name in record.get("subcollections", [])]
            # Connector-created items normally sync immediately; retry classification briefly.
            for attempt in range(8):
                try:
                    classify(web, item_key, destinations, record.get("tags", []), report["actions"])
                    break
                except Exception:
                    if attempt == 7:
                        raise
                    time.sleep(2)
        except Exception as exc:
            report["errors"].append({"title": title, "error": str(exc)})

    audit_path = Path(args.audit)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "complete", "actions": len(report["actions"]), "errors": len(report["errors"]), "key_printed": False}))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
