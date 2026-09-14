from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_os.external_tools import register_external_tools
from research_os.tools import ToolRegistry


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, url, *, headers=None, body=None, timeout=30):
        self.calls.append({"method": method, "url": url, "headers": dict(headers or {}), "body": body})
        if "crossref" in url:
            value = {"message": {"DOI": "10.1257/aer.103.6.2121", "title": ["The China Syndrome"],
                     "container-title": ["American Economic Review"], "author": [{"given":"David","family":"Autor"}],
                     "type": "journal-article", "URL": "https://doi.org/10.1257/aer.103.6.2121"}}
        elif "openalex" in url:
            value = {"id":"https://openalex.org/W1","doi":"https://doi.org/10.1257/aer.103.6.2121",
                     "title":"The China Syndrome","publication_year":2013,"type":"article","cited_by_count":1,
                     "primary_location":{"source":{"display_name":"American Economic Review"}},
                     "open_access":{"is_oa":True},"best_oa_location":{"pdf_url":"https://example.org/paper.pdf"}}
        elif "unpaywall" in url:
            value = {"doi":"10.1257/aer.103.6.2121","title":"The China Syndrome","year":2013,
                     "journal_name":"American Economic Review","is_oa":True,"oa_status":"green",
                     "best_oa_location":{"url_for_pdf":"https://example.org/paper.pdf"}}
        elif "127.0.0.1" in url:
            value = [{"key":"LOCAL001","data":{"title":"Local test item"}}]
        elif "api.zotero.org" in url and method == "POST":
            value = {"successful":{"0":{"key":"COLL001","data":{"name":"Project collection"}}}}
        else:
            raise AssertionError(url)
        return 200, {"Content-Type":"application/json"}, json.dumps(value).encode("utf-8")


class ExternalToolTests(unittest.TestCase):
    def test_bibliographic_lookup_triangulates_without_persisting_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = FakeTransport(); registry = ToolRegistry()
            secrets = {"CROSSREF_MAILTO":"researcher@example.org", "OPENALEX_API_KEY":"FAKE_TEST_VALUE",
                       "UNPAYWALL_EMAIL":"researcher@example.org"}
            register_external_tools(registry, transport, secrets)
            result = registry.execute("bibliographic_lookup", {
                "doi":"https://doi.org/10.1257/AER.103.6.2121", "output":"literature/lookup.json"
            }, Path(tmp), data_sensitivity="public")
            self.assertEqual(result["providers_completed"], 3)
            persisted = (Path(tmp)/"literature/lookup.json").read_text(encoding="utf-8")
            self.assertNotIn("FAKE_TEST_VALUE", persisted)
            self.assertNotIn("researcher@example.org", persisted)
            self.assertTrue(json.loads(persisted)["credential_values_logged"] is False)

    def test_openalex_and_unpaywall_missing_credentials_are_explicitly_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = FakeTransport(); registry = ToolRegistry(); register_external_tools(registry, transport, {})
            registry.execute("bibliographic_lookup", {
                "doi":"10.1257/aer.103.6.2121", "output":"literature/lookup.json"
            }, Path(tmp), data_sensitivity="public")
            payload = json.loads((Path(tmp)/"literature/lookup.json").read_text())
            skipped = {item["provider"] for item in payload["attempts"] if item["status"] == "skipped-missing-credential"}
            self.assertEqual(skipped, {"openalex", "unpaywall"})
            self.assertEqual([item["provider"] for item in payload["records"]], ["crossref"])

    def test_zotero_local_read_uses_localhost_and_writes_hashed_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = FakeTransport(); registry = ToolRegistry(); register_external_tools(registry, transport, {})
            result = registry.execute("zotero_local_read", {
                "action":"search_items", "query":"governance", "limit":5, "output":"literature/zotero.json"
            }, Path(tmp), data_sensitivity="personal")
            self.assertEqual(result["result_count"], 1)
            self.assertIn("127.0.0.1:23119", transport.calls[0]["url"])
            self.assertRegex(result["artifacts"][0]["sha256"], "^[a-f0-9]{64}$")

    def test_zotero_external_write_requires_approval_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = FakeTransport(); registry = ToolRegistry()
            register_external_tools(registry, transport, {"ZOTERO_API_KEY":"FAKE_TEST_VALUE","ZOTERO_USER_ID":"123"})
            inputs = {"name":"Project collection", "output":"literature/zotero-write.json",
                      "idempotency_key":"collection-create-001"}
            with self.assertRaises(PermissionError):
                registry.execute("zotero_collection_create", inputs, Path(tmp), data_sensitivity="personal")
            first = registry.execute("zotero_collection_create", inputs, Path(tmp), approved=True, data_sensitivity="personal")
            second = registry.execute("zotero_collection_create", inputs, Path(tmp), approved=True, data_sensitivity="personal")
            self.assertTrue(second["idempotent_replay"])
            self.assertEqual(sum(call["method"] == "POST" for call in transport.calls), 1)
            persisted = (Path(tmp)/"literature/zotero-write.json").read_text()
            self.assertNotIn("FAKE_TEST_VALUE", persisted)
            self.assertNotIn("collection-create-001", persisted)
            self.assertEqual(first["artifacts"], second["artifacts"])


if __name__ == "__main__":
    unittest.main()
