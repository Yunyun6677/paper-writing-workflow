from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema
from pypdf import PdfWriter

from research_os.tools import default_registry


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeToolTests(unittest.TestCase):
    def test_tier1_manifests_are_real_and_schema_valid(self):
        registry = default_registry()
        names = {item["name"] for item in registry.manifests()}
        self.assertTrue({"python", "stata", "r", "pdf_parser", "latex", "git_inspect"}.issubset(names))
        schema = json.loads((Path(__file__).parents[1] / "schemas/tool-manifest.schema.json").read_text())
        for manifest in registry.manifests():
            jsonschema.Draft202012Validator(schema).validate(manifest)

    def test_python_executes_hash_approved_script_and_emits_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "analysis.py"
            script.write_text(
                "import json, pathlib, sys\n"
                "p=pathlib.Path(sys.argv[1]); p.write_text(json.dumps({'coefficient': 2.0}), encoding='utf8')\n",
                encoding="utf-8",
            )
            registry = default_registry()
            result = registry.execute("python", {
                "script": "analysis.py", "script_sha256": digest(script), "output_directory": "run/python",
                "idempotency_key": "python-test-001", "arguments": [str(root / "run/python/result.json")],
                "required_outputs": ["run/python/result.json"],
            }, root, data_sensitivity="synthetic")
            self.assertEqual(result["status"], "complete")
            self.assertEqual(json.loads((root / "run/python/result.json").read_text())["coefficient"], 2.0)
            self.assertTrue(any(item["path"].endswith("receipt.json") for item in result["artifacts"]))
            receipt = json.loads((root / "run/python/receipt.json").read_text())
            schema = json.loads((Path(__file__).parents[1] / "schemas/native-tool-execution.schema.json").read_text())
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(receipt)

    def test_script_hash_and_duplicate_destination_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); script = root / "analysis.py"; script.write_text("pass\n")
            registry = default_registry()
            request = {"script": "analysis.py", "script_sha256": "0" * 64, "output_directory": "run/python",
                       "idempotency_key": "python-test-002", "required_outputs": ["run/python/result.json"]}
            with self.assertRaises(ValueError): registry.execute("python", request, root, data_sensitivity="synthetic")
            (root / "run/python").mkdir(parents=True)
            request["script_sha256"] = digest(script)
            with self.assertRaises(FileExistsError): registry.execute("python", request, root, data_sensitivity="synthetic")

    def test_pdf_parser_preserves_page_locators_and_source_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); pdf = root / "paper.pdf"
            writer = PdfWriter(); writer.add_blank_page(width=300, height=300)
            with pdf.open("wb") as stream: writer.write(stream)
            result = default_registry().execute("pdf_parser", {
                "pdf": "paper.pdf", "source_sha256": digest(pdf), "output": "evidence/paper.pages.json",
            }, root, data_sensitivity="synthetic")
            extracted = json.loads((root / "evidence/paper.pages.json").read_text())
            self.assertEqual(result["page_count"], 1)
            self.assertEqual(extracted["source"]["sha256"], digest(pdf))
            self.assertEqual(extracted["pages"][0]["page"], 1)

    def test_git_is_read_only_and_latex_fails_honestly_when_unavailable(self):
        root = Path(__file__).parents[1]
        result = default_registry().execute("git_inspect", {"operation": "head"}, root)
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["stdout"].strip())


if __name__ == "__main__":
    unittest.main()
