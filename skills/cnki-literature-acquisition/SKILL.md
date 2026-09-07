---
name: cnki-literature-acquisition
description: Search CNKI, obtain authorized Chinese-paper full text through a dedicated Chrome DevTools session, verify downloaded PDF/CAJ files, and archive verified records and PDFs into project folders and Zotero. Use for CNKI, Chinese core-journal retrieval, journal-specific corpus building, or CNKI-to-Zotero workflows; do not use to bypass login, payment, CAPTCHA, or access controls.
---

# CNKI Literature Acquisition

Build a lawful, auditable chain from a CNKI result to a verified local full text and Zotero attachment.

## Boundaries

- Use only the user's authorized CNKI or institutional access. The user enters credentials and solves any visible CAPTCHA manually.
- Never request, print, export, persist, or transmit browser cookies, passwords, tokens, or session headers.
- Use CNKI's visible official PDF/CAJ controls. Do not derive hidden download endpoints to bypass access checks.
- A DOI or metadata export is not full text. Mark completion only after the downloaded bytes have been verified locally.
- Use a dedicated Chrome profile for this workflow. Do not connect the MCP server to the user's ordinary Chrome profile or unrelated authenticated tabs.
- Stop after two transient failures on the same route. For access denial, payment, visible CAPTCHA, or missing full text, create a human handoff immediately.

## Before operating CNKI

1. Confirm that the `chrome-devtools-cnki` MCP tools are callable. If not, read [Chrome setup](references/chrome-setup.md). A configuration written during the current session does not make tools callable until Codex starts a new session.
2. Confirm Zotero Desktop status before any archive request. Use the Zotero skill for local search, collection inspection, and final verification.
3. Create or reuse the run's `acquisition-ledger.json` under the existing `literature-acquisition/1.0` schema. Read the parent review skill's `references/acquisition-handoff.md` when a paper cannot be obtained.
4. Search Zotero and the project literature folders first. Reuse an existing valid attachment rather than downloading or creating a duplicate.

## Browser workflow

Read [CNKI browser procedure](references/browser-procedure.md) before a live run.

1. Open CNKI in the dedicated Chrome profile and let the user complete login if required.
2. Search by topic, title, author, journal, year, and source category as needed. Extract structured rows from the DOM; do not infer metadata from snippets.
3. Rank candidates before downloading. Record every selected paper with title, authors, venue, year, source URL, importance, selection reason, and destination.
4. Navigate directly to the selected paper detail URL. Confirm the title and venue on the detail page.
5. Detect CAPTCHA only when the challenge is visibly positioned on screen. Hidden preloaded CAPTCHA nodes are not blockers.
6. Prefer the official PDF control; use CAJ only when PDF is unavailable and record the format honestly.
7. Snapshot the download directory immediately before triggering the download, then click the official control once. Do not retry until the local directory and current page state have been checked.

## Local verification and archive

Run the bundled verifier in two stages:

```powershell
python skills/cnki-literature-acquisition/scripts/verify_cnki_download.py snapshot `
  --directory PATH_TO_DOWNLOADS --output PATH_TO/snapshot.json

python skills/cnki-literature-acquisition/scripts/verify_cnki_download.py verify `
  --directory PATH_TO_DOWNLOADS --snapshot PATH_TO/snapshot.json `
  --expected-title "论文标题" --archive-dir PATH_TO_PROJECT_LITERATURE `
  --output PATH_TO/verification.json
```

Require all of the following before `fulltext-verified`:

- a new or changed file attributable to this download attempt;
- PDF or CAJ signature and a plausible file size;
- filename/title identity check, or a documented manual identity check when CNKI renames the file;
- for PDF, readable page structure and more than one page;
- a SHA-256 hash and copied project path.

CAJ remains `format: caj`; never rename it `.pdf`. A CAJ file does not satisfy a PDF-only corpus requirement.

## Zotero completion

1. Deduplicate by normalized DOI, then other persistent identifier, then normalized title + first author + year, then canonical URL.
2. For verified PDF files, reuse `scripts/zotero_import_local_fulltext.py` rather than duplicating the Zotero workflow.
3. Classify the item under the project's collection hierarchy and attach the verified local bytes.
4. Query Zotero Desktop again and verify that the child attachment is a locally readable PDF before setting `archived-local`.
5. Record Zotero item key, attachment key, local project path, version, and cloud-sync state separately.

## Required outputs

- updated `acquisition-ledger.json`;
- one `cnki-download-verification/1.0` JSON record per attempt;
- verified project PDF/CAJ path or an explicit `needs-human` handoff;
- Zotero item and attachment keys for every `archived-local` paper;
- no claim that a paper was studied until its full text was actually read.
