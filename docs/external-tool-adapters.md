# External tool adapters in v0.11

## Implemented runtime adapters

`bibliographic_lookup` triangulates one DOI through official Crossref, OpenAlex, and Unpaywall APIs. It writes a bounded JSON artifact with provider attempts, normalized records, and a hash. Crossref contact, OpenAlex key, and Unpaywall email are read from environment variables and never written to artifacts or traces. Current OpenAlex policy is treated conservatively: the adapter skips it when `OPENALEX_API_KEY` is absent. Unpaywall is skipped when `UNPAYWALL_EMAIL` is absent.

`zotero_local_read` reads collections or item metadata from Zotero Desktop's version-3-compatible localhost API. `zotero_collection_create` creates one web collection only after a Runtime human approval and uses `Zotero-Write-Token` plus the persistent tool idempotency ledger. The API key and user ID are environment-only. Attachment upload remains staged because its multi-step authorization/upload/registration protocol has not been integrated and tested.

Official contracts:

- Crossref REST API: <https://api.crossref.org/>
- OpenAlex API and authentication: <https://help.openalex.org/api/> and <https://help.openalex.org/api/authentication/>
- Unpaywall API v2: <https://unpaywall.org/api/v2>
- Zotero Web/Local API v3: <https://www.zotero.org/support/dev/web_api/v3/basics>
- Zotero writes and file uploads: <https://www.zotero.org/support/dev/web_api/v3/write_requests> and <https://www.zotero.org/support/dev/web_api/v3/file_upload>

## Tested boundary on 2026-09-14

- Crossref: live public DOI lookup passed for `10.1257/aer.103.6.2121`.
- OpenAlex: mock transport passed; live test unavailable because no key was configured.
- Unpaywall: mock transport passed; live test unavailable because no contact email was configured.
- Zotero local read: mock transport passed; live status probe found the local API preference enabled but Zotero Desktop/API was not running.
- Zotero web collection write: permission, credential isolation, response, and idempotency passed with a mock transport. No real test collection was created.

## Host-mediated Tier 3

Authorized browser and CNKI operations remain staged in the Python Runtime. They continue to use the existing `cnki-literature-acquisition` Skill through a researcher-visible host browser. The runtime must not claim a download until the host returns a structured observation and the local file passes PDF/CAJ identity and hash verification. Login, CAPTCHA, payment, and access controls are never bypassed.
