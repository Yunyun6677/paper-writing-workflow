# Review handoff contract

Use `schemas/literature-review-project.schema.json` for the project manifest and `schemas/evidence-card.schema.json` for each included work. For full reviews, also use `schemas/literature-map.schema.json`, `schemas/innovation-card.schema.json`, and `schemas/review-run-status.schema.json`. Preserve the existing `literature-workflow/1.0` record identifiers.

## Stable identifiers

- `record_id`: normalized DOI when available; otherwise a stable repository/database identifier or canonical-URL hash.
- `zotero_item_key`: Zotero internal item key.
- `bibtex_key`: citation key used in writing.
- These identifiers are not interchangeable.

## Verification levels

- `candidate`: found in a search but not trusted.
- `bibliographic-verified`: identity checked against an authoritative record.
- `fulltext-verified`: a valid, readable full text was acquired and inspected.
- `claim-verified`: reported claims include locators and were checked against the text.

Only `fulltext-verified` works may enter the included corpus or be automatically imported under the current user policy.

## Provenance

For every transformation, retain source name, query or URL, retrieval timestamp, acting role, and decision reason. Zotero mutations additionally retain destination collection, action (`created`, `updated`, `classified`, or `skipped`), and item key. Never record an API key.

## Full-text status

Use `cloud-synced`, `local-only`, or `metadata-only`. The current workflow admits the first two and skips `metadata-only`. An inaccessible important or user-requested item remains in the acquisition ledger and explicit human handoff, outside the included corpus until full text is verified. Track all selected works with `schemas/literature-acquisition.schema.json`; follow [acquisition-handoff.md](acquisition-handoff.md). Do not infer cloud sync from successful local attachment import.

## Required full-review artifacts

- `review-style-benchmark.md` and `.json`: benchmark selection, influence source/date, inspected full text, extracted writing features, and adopted or rejected choices.
- `candidate-ledger.json`: the single cross-language candidate ledger and reproducible search trail.
- `evidence-cards/*.json`: one card per included work.
- `concept-matrix.md` or `.csv`: theories, mechanisms, settings, methods, results, disagreements, and limitations.
- `literature-map.json`: evidence-traceable nodes and typed edges.
- `literature-map.svg`: rendered figure embedded in the final review.
- `innovation-cards/*.json`: ranked, falsifiable contribution candidates linked to evidence and map gaps.
- `run-status.json`: status of all seven roles and resumable stage checkpoints.
- `zotero-audit.json`: created, updated, classified, skipped, and failed mutations without credentials.

An output stage may consume only completed prior-stage artifacts. On restart, verify artifact integrity and external side effects, then continue from the first incomplete stage.
