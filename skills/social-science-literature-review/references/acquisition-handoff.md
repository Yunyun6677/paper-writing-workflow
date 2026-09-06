# Full-text acquisition and human handoff

Use this protocol for literature acquisition and Zotero archiving, including download-only tasks. Keep a run-level `acquisition-ledger.json` conforming to `schemas/literature-acquisition.schema.json`. This supplements, rather than replaces, candidate and citation evidence records.

## Acquisition and verification

- Record every selected work before attempting a download, with stable record ID, verified bibliography, importance, reason, and destination. Do not invent records to fill a requested count.
- Reuse existing valid local Zotero attachments first. Otherwise seek publisher open full text, lawful repositories/author versions, then authorized institutional access. Record the actual version obtained. A DOI identifies a work; it does not grant access.
- The user signs into institutional resources in the connected browser. Never request passwords, export browser cookies, or assume a browser login is inherited by an HTTP script. If the named browser is unavailable, report a run-level access blocker and request connection or user-supplied files.
- Retry a transient failure at most twice per route after checking current state; respect rate limits. Stop that route immediately for access denial, CAPTCHA, payment, or disconnected browser and hand off as appropriate. Try another authorized source when useful, without disguising a missing core work by substituting an easier paper.
- Verify file format, readability, identity, version, and completeness. A download button, HTML saved as PDF, first-page preview, or attachment metadata alone is not full-text success. Use the PDF skill when inspecting PDFs. Record CAJ explicitly; do not rename it PDF or claim Zotero-readable PDF completion without a compatible verified file.
- Deduplicate before writes and after ambiguous write failures. Attach to an existing record rather than duplicating it. Preserve unrelated collections/tags. Verify the actual local attachment is accessible and readable before marking `archived-local`; confirm cloud sync separately or leave it `unknown`.

## Explicit handoff

For every unresolved important or user-requested work, record and tell the user: title/identifier and publisher link, why it matters, routes attempted, exact failure, what the user needs to do, and where to put the file. Never request secrets. Batch these into one concise message even when no prose deliverable was requested; a material blocker must not be silent. A task-wide browser/access blocker can be handed off before individual papers are selected.

Allowed acquisition states: `pending`, `acquiring`, `fulltext-verified`, `archived-local`, `needs-human`, `deferred-by-user`. An unavailable paper is not evidence for substantive review findings. A fulltext-verified local download without a verified Zotero attachment remains unfinished for an archiving task.

After the user supplies access or a file, resume only pending items, inspect the full text, deduplicate, import, verify the attachment, and then close that handoff. If the user explicitly defers a paper, preserve the decision and any coverage limitation. Save a checkpoint after each paper and before reporting any interruption. Do not report the entire requested count as complete while unresolved records or a task-wide blocker remain.
