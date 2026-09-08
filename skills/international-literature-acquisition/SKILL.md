---
name: international-literature-acquisition
description: Discover, lawfully obtain, verify, and archive international scholarly full texts using DOI metadata, OpenAlex, Unpaywall, publisher or institutional access, and Zotero. Use for Google Scholar, ScienceDirect, Scopus, foreign-language journal retrieval, DOI-to-PDF resolution, or international-literature-to-Zotero workflows; do not use to bypass paywalls, CAPTCHA, login, or technical access controls.
---

# International Literature Acquisition

Build an auditable chain from a verified scholarly record to a readable local full text and Zotero attachment.

## Boundaries

- Use open-access copies, author or institutional repositories, preprints, publisher open access, or the user's authorized institutional subscription.
- Never use Sci-Hub, leaked credentials, shared session tokens, hidden download endpoints, or any route intended to bypass a paywall or access control.
- The user completes institutional login and any visible CAPTCHA. Never request, export, log, or persist passwords, cookies, session headers, or tokens.
- Google Scholar is a discovery aid, not a stable bulk-download API. Prefer DOI-based metadata services and follow visible lawful full-text links.
- A DOI, abstract page, HTML preview, or metadata record is not full text. Mark success only after the downloaded bytes and document identity are verified.
- Respect provider terms, licenses, robots rules, and rate limits. Stop a route after two transient failures; create a human handoff for access denial, CAPTCHA, payment, or missing full text.

## Before acquisition

1. Check Zotero Desktop with the Zotero skill and search for the DOI and normalized title before downloading.
2. Create or resume `acquisition-ledger.json` under `schemas/literature-acquisition.schema.json`.
3. Read [source routing](references/source-routing.md). For a logged-in publisher session, also read [browser procedure](references/browser-procedure.md).
4. Record each selected work before attempting download: verified title, authors, venue, year, DOI, importance, reason, and project destination.

## Route order

1. Reuse an existing readable Zotero or project attachment.
2. Resolve DOI and metadata through Crossref/OpenAlex; query Unpaywall when an email is configured.
3. Prefer an openly licensed publisher PDF, repository accepted manuscript, preprint, or author manuscript. Record the version and license.
4. If no open copy exists, use the visible official publisher page through the user's authorized institutional session.
5. If the route remains unavailable, create the explicit handoff defined in the literature-review skill's `references/acquisition-handoff.md`.

Run the resolver without downloading:

```powershell
python skills/international-literature-acquisition/scripts/resolve_open_access.py `
  --doi "10.1257/aer.103.6.2121" --output work/fulltext-resolution.json
```

Add `--download-dir PATH` to download only candidates that respond as actual PDFs. Use `UNPAYWALL_EMAIL` for the Unpaywall API and `OPENALEX_API_KEY` when OpenAlex requires authenticated API access. These values must come from environment variables and must never be written to output.

## Browser and publisher access

- Open publisher pages in a dedicated research browser profile.
- On ScienceDirect, prefer the official PDF button after the user has established Renmin University access. Elsevier API integrations may use `ELSEVIER_API_KEY`; full-text availability still depends on the user's license and provider policy.
- On Google Scholar, inspect the result's visible `[PDF]` or repository link and verify that it is a lawful host. Do not automate CAPTCHA avoidance or high-volume scraping.
- Snapshot the download directory before clicking, then verify the new file and identity before archiving.

## Verification and Zotero

For every downloaded file verify:

- PDF signature, EOF marker, plausible size, readable page structure, and more than one page;
- title/DOI identity using the document text, metadata, or a documented manual check;
- actual version obtained: version of record, accepted manuscript, submitted manuscript, or preprint;
- SHA-256 and local archive path.

Use `scripts/zotero_import_local_fulltext.py` only after verification. Attach to an existing DOI/title match rather than creating a duplicate. Confirm the local attachment key and readable file before `archived-local`; record cloud synchronization separately.

## Output contract

- Resolver output: `schemas/fulltext-resolution.schema.json`.
- Run state: `schemas/literature-acquisition.schema.json`.
- Allowed acquisition states: `pending`, `acquiring`, `fulltext-verified`, `archived-local`, `needs-human`, `deferred-by-user`.
- A substantive review may cite a record as read only after `fulltext-verified` and actual reading.
- Report every unresolved core or user-requested paper with attempted routes, exact blocker, required user action, and resume condition. Never silently replace it with an easier paper.
