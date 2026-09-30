"""Conservative personal-library import of a verified, project-local PDF.

This is an explicitly approved service operation, not a model tool. A receipt
is written after every remote phase so an interrupted upload is inspectable.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Mapping

from .external_tools import HttpTransport, UrllibTransport, _normalize_doi
from .store import sha256_file, utc_now


class ZoteroCloud:
    def __init__(self, *, transport: HttpTransport | None = None,
                 environment: Mapping[str, str] | None = None):
        env = environment if environment is not None else os.environ
        self.key = env.get("ZOTERO_API_KEY", "").strip()
        user_id = env.get("ZOTERO_USER_ID", "").strip()
        if not self.key or not user_id or not user_id.isdecimal():
            raise ValueError("ZOTERO_API_KEY and numeric ZOTERO_USER_ID are required")
        self.root = f"https://api.zotero.org/users/{user_id}"
        self.transport = transport or UrllibTransport()

    def _request(self, method: str, path: str, *, body: bytes | None = None,
                 content_type: str | None = None, token: str | None = None,
                 extra_headers: Mapping[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        headers = {"Zotero-API-Key": self.key, "Zotero-API-Version": "3", "Accept": "application/json"}
        if content_type: headers["Content-Type"] = content_type
        if token: headers["Zotero-Write-Token"] = token
        headers.update(extra_headers or {})
        status, _, raw = self.transport.request(method, self.root + path, headers=headers, body=body, timeout=45)
        if status >= 400:
            raise RuntimeError(f"Zotero returned HTTP {status}")
        return status, json.loads(raw) if raw else {}

    @staticmethod
    def _created_key(response: dict[str, Any]) -> str:
        if response.get("failed") or "0" not in response.get("success", {}):
            raise RuntimeError("Zotero object creation did not confirm item 0")
        return response["success"]["0"]

    def find_doi(self, doi: str) -> str | None:
        doi = _normalize_doi(doi)
        query = urllib.parse.urlencode({"q": doi, "limit": 100, "format": "json"})
        _, found = self._request("GET", "/items?" + query)
        if not isinstance(found, list) or len(found) == 100:
            raise RuntimeError("Zotero duplicate search is incomplete; import paused")
        keys = [entry["key"] for entry in found
                if isinstance(entry, dict) and _normalize_doi_if_possible(entry.get("data", {}).get("DOI", "")) == doi]
        if len(keys) > 1:
            raise RuntimeError("Multiple existing Zotero items have this DOI; manual resolution required")
        return keys[0] if keys else None

    def collections(self) -> list[dict[str, str]]:
        _, found = self._request("GET", "/collections?limit=100&format=json")
        if not isinstance(found, list) or len(found) == 100:
            raise RuntimeError("Collection listing may be incomplete; use a known key")
        return [{"key": item["key"], "name": item.get("data", {}).get("name", "")}
                for item in found if isinstance(item, dict) and item.get("key")]

    def import_pdf(self, *, doi: str, metadata: dict[str, Any], pdf: Path,
                   collection_key: str, receipt_path: Path, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Zotero cloud write requires a recorded human approval")
        doi = _normalize_doi(doi)
        if _normalize_doi(metadata.get("doi", "")) != doi:
            raise ValueError("Metadata DOI does not match requested DOI")
        if not pdf.is_file() or pdf.suffix.lower() != ".pdf" or pdf.stat().st_size > 15_000_000:
            raise ValueError("A local PDF of at most 15 MB is required")
        with pdf.open("rb") as handle:
            header = handle.read(5)
        if header != b"%PDF-":
            raise ValueError("File is not a PDF")
        if not (len(collection_key) == 8 and collection_key.isalnum()):
            raise ValueError("Use an existing eight-character Zotero collection key")
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt = {"schema_version": "zotero-cloud-import/1.0", "doi": doi,
                   "pdf_sha256": sha256_file(pdf), "collection_key": collection_key,
                   "created_at": utc_now(), "stages": [], "status": "running"}
        def record(stage: str, **details: Any) -> None:
            receipt["stages"].append({"stage": stage, "at": utc_now(), **details})
            receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            existing = self.find_doi(doi)
            if existing:
                receipt["status"] = "duplicate-existing"
                record("deduplicated", item_key=existing)
                return receipt
            # Only known fields are sent; never trust arbitrary metadata as Zotero JSON.
            authors = [{"creatorType": "author", "name": str(name)} for name in metadata.get("authors", []) if name]
            parent = {"itemType": "journalArticle", "title": metadata["title"], "DOI": doi,
                      "creators": authors, "publicationTitle": metadata.get("journal", ""),
                      "date": str(metadata.get("year", "")), "url": metadata.get("url", ""),
                      "collections": [collection_key]}
            payload = json.dumps([parent], ensure_ascii=False).encode("utf-8")
            _, response = self._request("POST", "/items", body=payload, content_type="application/json", token=str(uuid.uuid4()))
            parent_key = self._created_key(response)
            record("parent-created", item_key=parent_key)
            child = {"itemType": "attachment", "parentItem": parent_key,
                     "linkMode": "imported_file", "title": pdf.name,
                     "contentType": "application/pdf", "filename": pdf.name}
            _, response = self._request("POST", "/items", body=json.dumps([child]).encode("utf-8"),
                                        content_type="application/json", token=str(uuid.uuid4()))
            attachment_key = self._created_key(response)
            record("attachment-created", item_key=attachment_key)
            raw = pdf.read_bytes()
            md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
            mtime = round(pdf.stat().st_mtime * 1000)
            file_path = f"/items/{attachment_key}/file"
            form = urllib.parse.urlencode({"md5": md5, "filename": pdf.name,
                                           "filesize": len(raw), "mtime": mtime}).encode("ascii")
            _, auth = self._request("POST", file_path, body=form,
                                    content_type="application/x-www-form-urlencoded",
                                    extra_headers={"If-None-Match": "*"})
            if auth.get("exists") == 1:
                receipt["status"] = "complete"
                record("file-already-present", item_key=attachment_key)
                return receipt
            upload_url = auth.get("url", "")
            parsed = urllib.parse.urlparse(upload_url)
            if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith("amazonaws.com"):
                raise RuntimeError("Unexpected Zotero upload destination; manual review required")
            upload_body = auth["prefix"].encode("utf-8") + raw + auth["suffix"].encode("utf-8")
            status, _, _ = self.transport.request("POST", upload_url,
                                                  headers={"Content-Type": auth["contentType"]},
                                                  body=upload_body, timeout=120)
            if status != 201:
                raise RuntimeError(f"Zotero storage returned HTTP {status}")
            record("bytes-uploaded", item_key=attachment_key)
            register = urllib.parse.urlencode({"upload": auth["uploadKey"]}).encode("ascii")
            status, _ = self._request("POST", file_path, body=register,
                                      content_type="application/x-www-form-urlencoded",
                                      extra_headers={"If-None-Match": "*"})
            if status != 204:
                raise RuntimeError(f"Zotero upload registration returned HTTP {status}")
            receipt["status"] = "complete"
            record("file-registered", item_key=attachment_key)
            return receipt
        except Exception as exc:
            receipt["status"] = "needs-human"
            record("interrupted", error_type=type(exc).__name__, detail=str(exc)[:300])
            raise


def _normalize_doi_if_possible(value: str) -> str | None:
    try:
        return _normalize_doi(value)
    except ValueError:
        return None
