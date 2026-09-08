# Source routing

Use DOI-first routing because titles and author names vary across indexes.

| Route | Purpose | Full-text rule | Credentials |
| --- | --- | --- | --- |
| Crossref | Canonical DOI and bibliographic metadata | Metadata only unless a clearly licensed resource link is returned | Optional contact email |
| OpenAlex | Work discovery, OA status, repository and PDF locations | Download only URLs reported as open locations; retain host, version, and license | `OPENALEX_API_KEY` when required |
| Unpaywall | DOI-level lawful OA location | Use `best_oa_location` or other licensed OA locations | `UNPAYWALL_EMAIL`; not a secret |
| Publisher | Version of record and official supplements | Open access or user-authorized subscription only | User login or provider API key |
| Institutional/author repository | Accepted manuscripts, reports, working papers | Confirm identity and version; do not call it the version of record | Usually none |
| Zotero Connector | Capture metadata and files visible in the authorized browser | Verify the local attachment after capture | Zotero Desktop |
| Google Scholar | Discovery and citation chaining | Follow visible lawful PDF/repository links; do not bulk scrape | User-visible browser if needed |

## Candidate ranking

Rank a candidate higher when it has a direct HTTPS PDF URL, an explicit open-access flag, a recognized license, a trusted publisher or repository host, and an identified version. Do not treat URL shape alone as proof that access is lawful.

Recommended priority:

1. Open publisher version of record.
2. Open repository accepted manuscript.
3. Open preprint or working-paper version whose identity is verified.
4. Authorized publisher version obtained through the user's institutional session.
5. Human handoff.

## Elsevier

Elsevier's `elsapy` and Scopus-oriented clients can retrieve metadata and, where the API key and institutional entitlement allow it, ScienceDirect full-text records. API success and PDF download rights are different questions. Keep the browser route for subscribed PDFs and never copy browser credentials into scripts.

## What is deliberately excluded

Sci-Hub and similar shadow-library routes are excluded because they can bypass publisher access controls and create legal, security, provenance, and reproducibility risks. A paper unavailable through lawful automatic routes becomes a named handoff; it is never silently omitted.
