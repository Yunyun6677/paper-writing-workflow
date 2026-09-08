#!/usr/bin/env python3
"""Offline unit tests for the OA resolver."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("resolve_open_access.py")
SPEC = importlib.util.spec_from_file_location("resolve_open_access", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_normalize_doi() -> None:
    assert MODULE.normalize_doi("https://doi.org/10.1234/ABC.1 ") == "10.1234/abc.1"


def test_openalex_candidates() -> None:
    work, rows = MODULE.parse_openalex(
        {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1234/demo",
            "title": "A Demo Paper",
            "publication_year": 2024,
            "primary_location": {"source": {"display_name": "Demo Journal"}},
            "best_oa_location": {
                "pdf_url": "https://repository.example/demo.pdf",
                "landing_page_url": "https://repository.example/demo",
                "is_oa": True,
                "version": "acceptedVersion",
                "license": "cc-by",
            },
            "locations": [],
        }
    )
    assert work["doi"] == "10.1234/demo"
    assert work["venue"] == "Demo Journal"
    assert any(row["url_type"] == "pdf" and row["is_oa"] for row in rows)


def test_unpaywall_and_dedupe() -> None:
    _, rows = MODULE.parse_unpaywall(
        {
            "doi": "10.1234/demo",
            "title": "A Demo Paper",
            "best_oa_location": {
                "url_for_pdf": "https://repository.example/demo.pdf",
                "url": "https://repository.example/demo",
                "version": "publishedVersion",
                "license": "cc-by",
            },
            "oa_locations": [],
        }
    )
    duplicate = dict(rows[0])
    duplicate["score"] -= 1
    result = MODULE.deduplicate(rows + [duplicate])
    assert len(result) == 2
    assert result[0]["url_type"] == "pdf"


def test_pdf_checks() -> None:
    fake = b"%PDF-1.7\n" + b"/Type /Page " * 2 + b"x" * 50_000 + b"\n%%EOF"
    assert MODULE.valid_pdf_bytes(fake)
    assert not MODULE.valid_pdf_bytes(b"<html>login</html>")


if __name__ == "__main__":
    for test in [test_normalize_doi, test_openalex_candidates, test_unpaywall_and_dedupe, test_pdf_checks]:
        test()
    print("4 tests passed")
