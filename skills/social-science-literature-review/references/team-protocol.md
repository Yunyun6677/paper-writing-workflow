# Team protocol

## Seven-agent panel

A full literature review uses exactly seven expert roles in total. The lead is one of the seven.

1. `lead-editor`: freezes the question, scope, concepts, inclusion criteria, and task graph; maintains resumable checkpoints; resolves disputes; writes and signs off the final review.
2. `cross-language-discovery-specialist`: owns the single Chinese–English candidate ledger, reproducible queries, backward/forward citation chasing, coverage matrix, and stopping rule. Other experts submit targeted search requests instead of building parallel candidate lists.
3. `theory-mechanism-specialist`: reads verified full texts across economics, management, political science, and public administration; extracts theoretical traditions, causal mechanisms, institutional conditions, contradictions, and disciplinary coverage.
4. `methods-measurement-auditor`: audits data, constructs, samples, identification, robustness, external validity, evidence strength, and causal wording. It does not treat quantitative causal studies as the only legitimate evidence type.
5. `review-benchmark-specialist`: studies five to eight influential and methodologically strong reviews, extracting transferable rhetorical architecture, synthesis moves, disagreement treatment, and visual conventions without copying wording or structure wholesale.
6. `map-innovation-specialist`: builds the evidence-traceable literature map, locates theoretical breaks and structural holes, proposes testable innovations, and sends novelty claims back to role 2 for reverse searching and role 4 for feasibility review.
7. `evidence-zotero-citation-curator`: verifies identity and full text, deduplicates, exclusively controls Zotero writes, classifies and tags items, maintains evidence provenance, and audits whether each citation entails its attached claim.

Run the panel in waves rather than forcing seven simultaneous calls:

`1 → 2/7 → 3/4/5 → 6 → 2/4 reverse checks → 1/7 final audit`.

If platform capacity, network, or usage limits prevent all roles from completing, preserve partial outputs and statuses. The lead may execute missing role protocols sequentially, but the run report must distinguish `completed-by-agent`, `completed-by-lead-fallback`, `failed`, `not-run`, and `not-applicable`. A fallback run must not be described as seven-model consensus.

## Assignment packet

Each assignment must specify:

- project and research question;
- concepts and exclusions;
- sources, languages, and time coverage;
- expected output path and schema;
- maximum candidate count or stopping rule;
- whether the role may write to Zotero;
- verification and full-text requirements;
- checkpoint path and completion status vocabulary.

Only the evidence–Zotero–citation curator or lead may mutate the library. Search and reading roles return candidates or evidence cards, never independently import the same records.

Each role writes a checkpoint after every completed batch. A restart begins by reading checkpoints and auditing existing Zotero and file state; it must not repeat completed downloads or imports.

## Acquisition accountability

For acquisition-only requests, the lead and curator functions suffice; do not launch a full review panel or produce an unsolicited review. Role 2 records selected works and why they matter; role 7 owns the per-work acquisition ledger, bounded retries, attachment verification, and human-handoff queue in [acquisition-handoff.md](acquisition-handoff.md). The lead communicates unresolved important/user-requested works and task-wide access blockers to the user. A queue saved silently on disk is not a completed human handoff. Preserve pending entries across restarts and resolve them only after verifying the supplied file and Zotero attachment, or recording the user's explicit decision to defer/exclude.

## Reconciliation

The lead merges results by `record_id`, records conflicting interpretations, and sends disputes about methods to the methods and measurement auditor. An unresolved disagreement remains explicit in the evidence map; it must not be silently averaged away.

The evidence–Zotero–citation curator rejects:

- nonexistent or unverifiable works;
- a real paper with incorrect authors, year, venue, or DOI;
- claims supported only by an abstract when the record says full text was read;
- citations that are topically related but do not support the attached proposition;
- inferred numerical results without a verified table, figure, or passage locator.

The map and innovation specialist rejects an innovation claim when it lacks a verified nearest-prior-work set, an explicit gap type, a falsifiable contribution statement, or feasible data and identification requirements. Claims such as “few studies” or “no research exists” require a documented search trail and must state the databases, languages, and time range searched.
