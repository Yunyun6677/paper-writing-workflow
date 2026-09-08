---
name: economics-paper-workflow
description: Plan, write, audit, revise, and package complete economics papers by coordinating verified literature, explicit research design, reproducible empirical outputs, LaTeX manuscripts, journal fit, and submission artifacts. Use for end-to-end paper projects, section drafting, theory and identification framing, manuscript revision, referee responses, or pre-submission audits; do not use to invent evidence, choose specifications for significance, or replace a standalone acquisition-only task.
---

# Economics Paper Workflow

Turn a research question and verified evidence into a complete, auditable economics paper. This is the orchestration and writing layer above the four specialist skills; it does not duplicate their retrieval or estimation logic.

## Start safely

1. Read or create a project manifest under `schemas/economics-paper-project.schema.json`.
2. Identify the paper type and current stage. Do not force empirical-paper structure onto theory, measurement, review, or replication papers.
3. Read [project lifecycle](references/project-lifecycle.md). Load [research design gates](references/research-design-gates.md) before approving an empirical design; load [manuscript and audit](references/manuscript-and-audit.md) when drafting or reviewing; load [Chinese journal routing](references/chinese-journal-routing.md) when a domestic target journal matters.
4. Initialize a new project only when the user asks to create one:

```powershell
python skills/economics-paper-workflow/scripts/init_paper_project.py `
  --manifest PATH_TO_PROJECT_JSON --output-root projects
```

Never overwrite an existing project. Resume from its manifest and checkpoints.

## Human decision gates

Require explicit user confirmation before locking:

- the research question and intended contribution;
- the estimand, treatment/exposure, comparison and identification assumptions;
- the primary outcome, sample rules and inference plan;
- the manuscript outline and target-journal family;
- any response that changes a preregistered or previously reported specification.

Exploration may proceed in a labeled sandbox, but exploratory findings do not enter the main paper until promoted with a reason and new version.

## Evidence firewalls

- A literature claim must resolve to a verified citation and, for substantive claims, an inspected full text.
- A numerical claim must resolve to a generated table, figure, model result, or data audit artifact. Never type a coefficient, sample size, standard error, or p-value from memory.
- Causal language requires a defended identification strategy and completed method-specific diagnostics.
- Preserve null, mixed and failed results. Do not optimize the paper for statistical significance.
- Separate facts inherited from the user's manuscript from new claims. Do not silently alter empirical findings during prose revision.

## Workflow

1. **Frame** — question, contribution, audience, paper type, target-journal family and feasibility.
2. **Design** — theory or conceptual framework; estimand; variation; assumptions; threats; data and inference plan.
3. **Evidence** — use the literature-review and acquisition skills; create verified claim-evidence links.
4. **Analyze** — use the empirical skill; accept only validated bundles and engine receipts.
5. **Outline** — assign each section a purpose, evidence inputs, table/figure inputs and word budget; obtain approval.
6. **Draft** — write UTF-8 LaTeX. Lead empirical methods with the identification argument, not the equation.
7. **Audit** — run citation, numerical-claim, design, consistency, reproducibility, privacy and journal-fit checks.
8. **Revise** — address a bounded, prioritized issue list; preserve a revision log and stop after the agreed review budget.
9. **Package** — compile LaTeX, freeze hashes, produce appendix, data/code availability statement, and submission checklist. External submission remains a separate user-authorized action.

## Specialist routing

- Use `social-science-literature-review` for evidence synthesis and innovation mapping.
- Use `cnki-literature-acquisition` or `international-literature-acquisition` for full-text retrieval and Zotero archiving.
- Use `economics-empirical-analysis` for data intake, estimators, tables, figures and result bundles.
- Never claim a specialist stage succeeded without its required artifacts.

## Required deliverables

- `project.json` and stage checkpoints;
- `design/design-register.json` plus a human-readable design section;
- `paper/main.tex`, `paper/references.bib`, section files, LaTeX tables and PDF/PNG figures;
- `audit/numeric-claims.json`, citation audit, design audit and `audit/audit-report.tex`;
- `paper/revision-log.tex` for revisions;
- `submission/submission-checklist.tex`, data/code availability statement and reproducibility manifest;
- an explicit list of blocked items and user actions.

Run the deterministic audit before delivery:

```powershell
python skills/economics-paper-workflow/scripts/audit_paper.py `
  --project-dir projects/PROJECT_ID
```

Compilation success, journal compliance and external submission are separate states. Never report one as proof of the others.
