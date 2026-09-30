"""Synthetic-only checks for the local UI, model boundary and Zotero protocol."""

from __future__ import annotations

import json
import threading
import tempfile
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from research_os.adapters.langchain.model_factory import create_model
from research_os.literature_demo_http import DemoService, _check_pdf, handler
from research_os.zotero_cloud import ZoteroCloud


class FakeZoteroTransport:
    def __init__(self, duplicate=False, fail_upload=False):
        self.calls = []
        self.duplicate = duplicate
        self.fail_upload = fail_upload

    def request(self, method, url, *, headers=None, body=None, timeout=30):
        self.calls.append((method, url, dict(headers or {}), body))
        if method == "GET":
            if self.duplicate:
                return 200, {}, b'[{"key":"EXIST123","data":{"DOI":"10.1000/example"}}]'
            return 200, {}, b"[]"
        if url.endswith("/items") and b'"itemType": "journalArticle"' in (body or b""):
            return 200, {}, b'{"success":{"0":"AAAABBBB"},"failed":{}}'
        if url.endswith("/items"):
            return 200, {}, b'{"success":{"0":"CCCCDDDD"},"failed":{}}'
        if url.endswith("/file") and b"filesize=" in (body or b""):
            return 200, {}, json.dumps({"url": "https://s3.amazonaws.com/test",
                "contentType": "multipart/form-data; boundary=test", "prefix": "abc",
                "suffix": "xyz", "uploadKey": "upload-1"}).encode()
        if url.startswith("https://s3.amazonaws.com/"):
            if self.fail_upload:
                return 503, {}, b""
            return 201, {}, b""
        if url.endswith("/file") and b"upload=" in (body or b""):
            return 204, {}, b""
        raise AssertionError((method, url))


class DemoTests(unittest.TestCase):
    def test_create_persists_state_and_excludes_private_local_zotero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = DemoService(root)
            first.create("trial-1", "Does a public policy affect participation?")
            reopened = DemoService(root)
            status = reopened.status("trial-1")
            self.assertEqual(status["lifecycle_status"], "initialized")
            from research_os.state_backends import open_state_backend
            state = open_state_backend(reopened._run_dir("trial-1")).load()
            literature = next(t for t in state["task_graph"] if t["task_id"] == "literature")
            self.assertNotIn("zotero_local_read", literature["allowed_tools"])
            self.assertIn("pdf_page_read", literature["allowed_tools"])
            self.assertFalse(status["model_configured"])

    def test_registered_source_reaches_literature_context_with_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = DemoService(tmp)
            service.create("source-test", "How does open trade affect village governance?")
            project, _ = service._paths("source-test")
            source = project / "literature" / "inputs" / "source.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"doi":"10.1000/fixture","title":"Synthetic"}', encoding="utf-8")
            runtime = service._runtime("source-test")
            registered = runtime.register_source("literature/inputs/source.json")
            state = runtime.store.load()
            literature = next(t for t in state["task_graph"] if t["task_id"] == "literature")
            packed = runtime.context_packer.pack(state, literature)
            self.assertIn(registered["artifact_id"], packed.receipt["selected_artifact_ids"])
            self.assertTrue(any(a.get("sha256") == registered["sha256"] for a in packed.artifacts))

    def test_bad_pdf_and_external_model_consent_rejected(self):
        with self.assertRaises(ValueError):
            _check_pdf(b"not a pdf", "Some title")
        with tempfile.TemporaryDirectory() as tmp:
            service = DemoService(tmp)
            with self.assertRaises(PermissionError):
                service.upload_source("trial-1", "10.1000/example", b"%PDF-bad")

    def test_missing_model_key_never_reports_completed_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = DemoService(tmp)
            service.create("no-model", "Can policy exposure affect village participation?")
            with patch.dict("os.environ", {"RESEARCH_OS_MODEL_API_KEY": "",
                                        "RESEARCH_OS_MODEL_NAME": "",
                                        "RESEARCH_OS_MODEL_BASE_URL": ""}):
                with self.assertRaisesRegex(ValueError, "Model environment is incomplete"):
                    service.start("no-model")
            state = service.status("no-model")
            self.assertEqual(state["lifecycle_status"], "initialized")
            self.assertNotIn("writing", [t["id"] for t in state["tasks"] if t["status"] == "complete"])

    def test_zotero_requires_approval_and_deduplicates(self):
        transport = FakeZoteroTransport()
        client = ZoteroCloud(transport=transport,
                             environment={"ZOTERO_API_KEY": "test-only", "ZOTERO_USER_ID": "12345"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\nsynthetic fixture")
            fields = dict(doi="10.1000/example", metadata={"doi": "10.1000/example",
                          "title": "Synthetic paper", "authors": ["A Tester"], "journal": "Test"},
                          pdf=pdf, collection_key="ABCDEFGH", receipt_path=root / "receipt.json")
            with self.assertRaises(PermissionError):
                client.import_pdf(**fields, approved=False)
            self.assertEqual(transport.calls, [])
            receipt = client.import_pdf(**fields, approved=True)
            self.assertEqual(receipt["status"], "complete")
            self.assertEqual(receipt["stages"][-1]["stage"], "file-registered")
            self.assertNotIn("test-only", (root / "receipt.json").read_text())
            self.assertTrue(any(url.startswith("https://s3.amazonaws.com/") for _, url, _, _ in transport.calls))

    def test_model_endpoint_rejects_insecure_url(self):
        with patch.dict("os.environ", {"RESEARCH_OS_MODEL_BASE_URL": "http://insecure.example/v1",
                                    "RESEARCH_OS_MODEL_NAME": "some-model",
                                    "RESEARCH_OS_MODEL_API_KEY": "test-only"}):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                create_model("openai-compatible")

    def test_duplicate_doi_causes_no_write_and_upload_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); pdf = root / "p.pdf"; pdf.write_bytes(b"%PDF-1.4\nsynthetic")
            params = dict(doi="10.1000/example", metadata={"doi": "10.1000/example",
                          "title": "Synthetic"}, pdf=pdf, collection_key="ABCDEFGH",
                          receipt_path=root / "receipt.json", approved=True)
            transport = FakeZoteroTransport(duplicate=True)
            client = ZoteroCloud(transport=transport, environment={"ZOTERO_API_KEY": "test-only",
                                  "ZOTERO_USER_ID": "12345"})
            self.assertEqual(client.import_pdf(**params)["status"], "duplicate-existing")
            self.assertEqual([call[0] for call in transport.calls], ["GET"])
            failing = ZoteroCloud(transport=FakeZoteroTransport(fail_upload=True),
                                  environment={"ZOTERO_API_KEY": "test-only", "ZOTERO_USER_ID": "12345"})
            with self.assertRaisesRegex(RuntimeError, "storage returned HTTP 503"):
                failing.import_pdf(**params)
            receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "needs-human")
            self.assertEqual(receipt["stages"][-1]["stage"], "interrupted")

    def test_loopback_http_requires_token_and_reopens_persisted_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = DemoService(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler(service))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(base + "/", timeout=5) as response:
                    html = response.read().decode("utf-8")
                self.assertIn(service.token, html)
                body = json.dumps({"project_id": "http-test", "question":
                                   "Can an open policy change political participation?"}).encode()
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(urllib.request.Request(base + "/api/projects", data=body,
                        headers={"Content-Type": "application/json"}), timeout=5)
                self.assertEqual(denied.exception.code, 403)
                request = urllib.request.Request(base + "/api/projects", data=body,
                    headers={"Content-Type": "application/json", "X-Research-Token": service.token})
                with urllib.request.urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 201)
                reopened = DemoService(tmp)
                self.assertEqual(reopened.status("http-test")["lifecycle_status"], "initialized")
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
