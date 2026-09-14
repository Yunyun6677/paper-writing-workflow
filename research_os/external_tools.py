"""Real Tier-2 scholarly metadata and Zotero adapters.

Credentials are read only from environment variables and are never written to
requests, receipts, traces, or artifacts. Browser/CNKI remains host-mediated.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Protocol

from .store import canonical_hash, sha256_file, utc_now
from .tools import GENERIC_OUTPUT, ToolRegistry, ToolSpec, _safe_project_path


class HttpTransport(Protocol):
    def request(self, method: str, url: str, *, headers: Mapping[str, str] | None = None,
                body: bytes | None = None, timeout: int = 30) -> tuple[int, Mapping[str, str], bytes]: ...


class UrllibTransport:
    def request(self, method: str, url: str, *, headers: Mapping[str, str] | None = None,
                body: bytes | None = None, timeout: int = 30) -> tuple[int, Mapping[str, str], bytes]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
            raise PermissionError("HTTP transport permits HTTPS or Zotero localhost only")
        request = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read(20_000_001)


def _normalize_doi(value: str) -> str:
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix): normalized = normalized[len(prefix):].strip()
    if not normalized.startswith("10.") or "/" not in normalized or len(normalized) > 300:
        raise ValueError("A valid DOI is required")
    return normalized


def _write_artifact(project_dir: Path, output: str, value: dict[str, Any]) -> dict[str, Any]:
    path = _safe_project_path(project_dir, output)
    if path.exists():
        raise FileExistsError(f"External tool output already exists: {output}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {"path": path.relative_to(project_dir).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _json(transport: HttpTransport, method: str, url: str, headers: Mapping[str, str],
          body: bytes | None = None, timeout: int = 30) -> tuple[int, dict[str, Any]]:
    status, _response_headers, content = transport.request(method, url, headers=headers, body=body, timeout=timeout)
    if len(content) > 20_000_000:
        raise ValueError("External JSON response exceeds 20 MB")
    value = json.loads(content.decode("utf-8"))
    return status, value


def _crossref_record(value: dict[str, Any]) -> dict[str, Any]:
    message = value.get("message", {})
    return {
        "provider": "crossref", "doi": message.get("DOI"),
        "title": (message.get("title") or [None])[0],
        "authors": [" ".join(filter(None, (item.get("given"), item.get("family")))) for item in message.get("author", [])],
        "container_title": (message.get("container-title") or [None])[0],
        "published": message.get("published-print") or message.get("published-online"),
        "type": message.get("type"), "url": message.get("URL"),
    }


def _openalex_record(value: dict[str, Any]) -> dict[str, Any]:
    primary = value.get("primary_location") or {}; source = primary.get("source") or {}
    return {
        "provider": "openalex", "id": value.get("id"), "doi": value.get("doi"),
        "title": value.get("title"), "publication_year": value.get("publication_year"),
        "container_title": source.get("display_name"), "type": value.get("type"),
        "cited_by_count": value.get("cited_by_count"), "open_access": value.get("open_access"),
        "best_oa_location": value.get("best_oa_location"),
    }


def _unpaywall_record(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "unpaywall", "doi": value.get("doi"), "title": value.get("title"),
        "year": value.get("year"), "journal_name": value.get("journal_name"),
        "is_oa": value.get("is_oa"), "oa_status": value.get("oa_status"),
        "best_oa_location": value.get("best_oa_location"),
    }


def register_external_tools(registry: ToolRegistry, transport: HttpTransport | None = None,
                            environment: Mapping[str, str] | None = None) -> ToolRegistry:
    transport = transport or UrllibTransport(); environment = environment if environment is not None else os.environ
    common_headers = {"Accept": "application/json", "User-Agent": "paper-writing-workflow/0.11"}

    def bibliographic_lookup(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
        doi = _normalize_doi(inputs["doi"]); quoted = urllib.parse.quote(doi, safe="")
        records, attempts = [], []
        providers = inputs.get("providers", ["crossref", "openalex", "unpaywall"])
        calls: list[tuple[str, str, dict[str, str], Any]] = []
        if "crossref" in providers:
            headers = dict(common_headers)
            contact = environment.get("CROSSREF_MAILTO", "").strip()
            if contact: headers["User-Agent"] += f" (mailto:{contact})"
            calls.append(("crossref", f"https://api.crossref.org/works/{quoted}", headers, _crossref_record))
        if "openalex" in providers:
            key = environment.get("OPENALEX_API_KEY", "").strip()
            if key:
                headers = {**common_headers, "Authorization": f"Bearer {key}"}
                calls.append(("openalex", f"https://api.openalex.org/works/https://doi.org/{quoted}", headers, _openalex_record))
            else:
                attempts.append({"provider": "openalex", "status": "skipped-missing-credential"})
        if "unpaywall" in providers:
            email = environment.get("UNPAYWALL_EMAIL", "").strip()
            if email:
                url = f"https://api.unpaywall.org/v2/{quoted}?" + urllib.parse.urlencode({"email": email})
                calls.append(("unpaywall", url, common_headers, _unpaywall_record))
            else:
                attempts.append({"provider": "unpaywall", "status": "skipped-missing-credential"})
        for provider, url, headers, parser in calls:
            try:
                status, value = _json(transport, "GET", url, headers, timeout=inputs.get("timeout_seconds", 30))
                records.append(parser(value)); attempts.append({"provider": provider, "status": "complete", "http_status": status})
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                attempts.append({"provider": provider, "status": "failed", "error_type": type(exc).__name__})
        payload = {
            "schema_version": "bibliographic-lookup/1.0", "created_at": utc_now(), "doi": doi,
            "records": records, "attempts": attempts, "credential_values_logged": False,
            "lookup_hash": canonical_hash(records),
        }
        artifact = _write_artifact(project_dir, inputs["output"], payload)
        return {"status": "complete" if records else "failed", "artifacts": [artifact],
                "errors": [] if records else ["No provider returned a record"], "providers_completed": len(records)}

    def zotero_local_read(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
        action = inputs["action"]
        if action == "collections":
            endpoint = "http://127.0.0.1:23119/api/users/0/collections"
        else:
            parameters = urllib.parse.urlencode({"q": inputs.get("query", ""), "qmode": "titleCreatorYear", "limit": inputs.get("limit", 25), "format": "json"})
            endpoint = "http://127.0.0.1:23119/api/users/0/items?" + parameters
        status, value = _json(transport, "GET", endpoint, {**common_headers, "Zotero-API-Version": "3"}, timeout=inputs.get("timeout_seconds", 15))
        payload = {"schema_version": "zotero-local-read/1.0", "created_at": utc_now(), "action": action,
                   "http_status": status, "results": value, "credential_values_logged": False}
        artifact = _write_artifact(project_dir, inputs["output"], payload)
        return {"status": "complete", "artifacts": [artifact], "errors": [],
                "result_count": len(value) if isinstance(value, list) else 1}

    def zotero_collection_create(inputs: dict[str, Any], project_dir: Path) -> dict[str, Any]:
        key = environment.get("ZOTERO_API_KEY", "").strip(); user_id = environment.get("ZOTERO_USER_ID", "").strip()
        if not key or not user_id:
            raise PermissionError("ZOTERO_API_KEY and ZOTERO_USER_ID environment variables are required")
        body = json.dumps([{"name": inputs["name"], "parentCollection": inputs.get("parent_collection", False)}]).encode("utf-8")
        headers = {**common_headers, "Content-Type": "application/json", "Zotero-API-Version": "3",
                   "Zotero-API-Key": key, "Zotero-Write-Token": inputs["idempotency_key"]}
        status, value = _json(transport, "POST", f"https://api.zotero.org/users/{urllib.parse.quote(user_id, safe='')}/collections", headers, body, inputs.get("timeout_seconds", 30))
        payload = {"schema_version": "zotero-write/1.0", "created_at": utc_now(), "action": "create_collection",
                   "http_status": status, "response": value, "credential_values_logged": False,
                   "idempotency_key_hash": canonical_hash(inputs["idempotency_key"])}
        artifact = _write_artifact(project_dir, inputs["output"], payload)
        return {"status": "complete", "artifacts": [artifact], "errors": [], "idempotency_key": inputs["idempotency_key"]}

    lookup_input = {"type":"object","additionalProperties":False,"required":["doi","output"],"properties":{
        "doi":{"type":"string","minLength":6},"output":{"type":"string","minLength":1},
        "providers":{"type":"array","uniqueItems":True,"items":{"enum":["crossref","openalex","unpaywall"]}},
        "timeout_seconds":{"type":"integer","minimum":1,"maximum":120}}}
    registry.register(ToolSpec("bibliographic_lookup", "Triangulate one DOI through Crossref, OpenAlex, and Unpaywall.",
        lookup_input, GENERIC_OUTPUT, "external-read", "automatic", {"max_attempts":3}, 180,
        "CROSSREF_MAILTO optional; OPENALEX_API_KEY and UNPAYWALL_EMAIL provider-specific", ["public", "synthetic", "restricted", "personal", "confidential"],
        False, "identifier-triangulation", "native-http", "available"), bibliographic_lookup)
    local_input = {"type":"object","additionalProperties":False,"required":["action","output"],"properties":{
        "action":{"enum":["collections","search_items"]},"query":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":100},
        "output":{"type":"string","minLength":1},"timeout_seconds":{"type":"integer","minimum":1,"maximum":60}}}
    registry.register(ToolSpec("zotero_local_read", "Read collections or item metadata from Zotero Desktop localhost API.",
        local_input, GENERIC_OUTPUT, "local-read", "automatic", {"max_attempts":2}, 90, "running Zotero Desktop local API",
        ["public","synthetic","restricted","personal","confidential"], False, "zotero-v3-response-and-artifact-hash", "native-http", "available"), zotero_local_read)
    write_input = {"type":"object","additionalProperties":False,"required":["name","output","idempotency_key"],"properties":{
        "name":{"type":"string","minLength":1,"maxLength":200},"parent_collection":{"oneOf":[{"type":"string"},{"const":False}]},
        "output":{"type":"string","minLength":1},"idempotency_key":{"type":"string","minLength":8,"maxLength":128},
        "timeout_seconds":{"type":"integer","minimum":1,"maximum":60}}}
    registry.register(ToolSpec("zotero_collection_create", "Create one authorized Zotero Web API v3 collection.",
        write_input, GENERIC_OUTPUT, "external-write", "explicit-approval", {"max_attempts":1}, 90,
        "ZOTERO_API_KEY and ZOTERO_USER_ID", ["public","personal"], False,
        "zotero-write-token-and-response", "native-http", "available"), zotero_collection_create)
    return registry
