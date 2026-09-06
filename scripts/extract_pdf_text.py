#!/usr/bin/env python3
"""Extract page-labelled text from PDFs for evidence review."""

from pathlib import Path
import sys

from pypdf import PdfReader


def main() -> int:
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    reader = PdfReader(source)
    chunks = []
    for page_number, page in enumerate(reader.pages, start=1):
        chunks.append(f"\n\n===== PDF PAGE {page_number} =====\n\n{page.extract_text() or ''}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(chunks), encoding="utf-8")
    print(f"{source.name}\t{len(reader.pages)} pages\t{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
