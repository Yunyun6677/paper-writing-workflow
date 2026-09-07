---
name: social-science-literature-review
description: Build evidence-grounded social-science literature reviews with a seven-agent expert panel, verified full-text evidence, influential-review benchmarking, mandatory literature maps, innovation scouting, and project-based Zotero organization. Use for literature discovery, screening, review writing, evidence mapping, or research-gap development; do not use for unverified citation brainstorming.
---

# Social Science Literature Review

Produce a traceable literature review whose claims can be followed from prose to an evidence card, Zotero item, and inspected full text.

## Non-negotiable rules

- Never invent or autocomplete a citation. Treat model memory and search snippets only as leads.
- Verify every included work against an authoritative bibliographic source. Match title, authors, year, venue, and persistent identifier where available.
- Do not summarize methods, findings, mechanisms, limitations, page numbers, or quotations without inspecting the full text.
- Before Zotero import, deduplicate in this order: normalized DOI, other persistent identifier, normalized title plus first author plus year, then canonical URL.
- Import automatically only after bibliographic verification and successful lawful full-text acquisition. Track every selected work through acquisition and archiving; unavailable works remain outside the included corpus, not silently removed. Read [acquisition and human handoff](references/acquisition-handoff.md) when acquiring or archiving literature. Explicitly hand inaccessible important or user-requested works to the user with the exact next action.
- For Chinese core-journal retrieval through CNKI, use the `cnki-literature-acquisition` skill when available. Its dedicated Chrome profile, verified-download record, and Zotero attachment check supplement this review skill's acquisition ledger; CNKI search results or metadata exports alone never count as full text.
- Never expose Zotero credentials in prompts, source files, logs, or outputs.
- Distinguish evidence from interpretation and uncertainty. A citation must support the exact sentence attached to it.

## Start each project

Read the project research request. If `config/research-profile.json` exists, treat it as private local configuration; otherwise start from `config/research-profile.example.json`. Never require a personal profile for a portable run or include it in public outputs. For the bundled test topic, also read [current project brief](references/current-project.md). If the task changes topic, create a new brief using [data contract](references/data-contract.md) rather than overwriting the current one.

Create or reuse a Zotero hierarchy rooted in `01_研究项目/<项目名>`. A verified item may appear in several subcollections without duplicating the underlying Zotero record.

## Team workflow

For a full literature review, use the seven-agent panel in [team protocol](references/team-protocol.md). The panel has seven expert roles in total, including the lead editor. Run independent workstreams in parallel when capacity permits; otherwise run the same seven roles in documented stages. Never claim that an expert completed work when it failed, was skipped, or was performed by the lead as fallback. The lead remains responsible for reconciliation and the final answer.

1. Formulate concepts, synonyms, causal chain, scope, inclusion criteria, and search strings.
2. Search the existing Zotero library before external sources.
3. Benchmark the rhetorical architecture of five to eight influential reviews using [review benchmark protocol](references/review-benchmark.md). Learn structures and synthesis moves, never wording.
4. Search Chinese and international sources separately; preserve each query, source, date, and result count.
5. Verify identity, deduplicate, acquire full text, and screen relevance before Zotero import.
6. Read included full texts and create one evidence card per work using the contract.
7. Build a concept matrix covering theories, mechanisms, outcomes, context, data, methods, identification, findings, contradictions, and limitations.
8. Construct the mandatory evidence-backed literature map and innovation portfolio using [map and innovation protocol](references/literature-map-and-innovation.md).
9. Write the review by research conversation, disagreement, and causal mechanism, not as an author-by-author list.
10. Run methods, novelty, citation-entailment, bibliographic, map, and Zotero audits before delivery. Report coverage gaps and inaccessible core works.

## Deliverables

For each run, preserve machine-readable records and a human-readable report. Use [data contract](references/data-contract.md) for handoffs. A final review must include search scope, inclusion logic, benchmark-informed writing plan, thematic synthesis, methodological assessment, disagreements, research gaps, ranked innovation points, and a verified bibliography in the requested style.

Every full review must contain at least one legible figure that summarizes the topic's logical structure. Deliver both a machine-readable graph and a rendered SVG; a prose-only list, word cloud, or decorative mind map does not satisfy this requirement. If rendering fails, the review remains incomplete until the figure is repaired or the missing capability is reported.
