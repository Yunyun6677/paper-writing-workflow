#!/usr/bin/env python3
"""Add existing Zotero items to project collections without duplicating them."""

import argparse
import json
from pathlib import Path

from zotero_import_local_fulltext import WebZotero, classify


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--audit", required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    zotero = WebZotero()
    actions = []
    errors = []
    topic = manifest["topic_collection_key"]
    collection_keys = manifest["collection_keys"]
    for record in manifest["items"]:
        try:
            destinations = [topic] + [collection_keys[name] for name in record["collections"]]
            classify(zotero, record["key"], destinations, record.get("tags", []), actions)
        except Exception as exc:
            errors.append({"item_key": record["key"], "error": str(exc)})
    report = {
        "schema_version": manifest["schema_version"],
        "actions": actions,
        "errors": errors,
        "secrets_logged": False
    }
    Path(args.audit).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"classified": len(actions), "errors": len(errors)}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
