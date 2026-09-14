from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_os.tools import default_registry


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    result = default_registry().execute("bibliographic_lookup", {
        "doi": "10.1257/aer.103.6.2121",
        "providers": ["crossref"],
        "output": "literature/crossref.json",
        "timeout_seconds": 30,
    }, root, data_sensitivity="public")
    payload = json.loads((root / "literature/crossref.json").read_text(encoding="utf-8"))
    title = payload["records"][0]["title"] if payload["records"] else None
    if result["status"] != "complete" or payload["doi"] != "10.1257/aer.103.6.2121" or not title:
        raise SystemExit("Crossref live smoke failed identity contract")
    print(json.dumps({"status":"passed", "provider":"crossref", "doi":payload["doi"],
                      "title":title, "artifact_sha256":result["artifacts"][0]["sha256"]}))
