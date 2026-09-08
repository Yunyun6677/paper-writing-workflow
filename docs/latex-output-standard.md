# LaTeX output standard

This standard separates publication-ready deliverables from machine handoffs.

## Required layout

```text
outputs/<project-or-run>/
├─ main.tex or report.tex
├─ references.bib                 # when citations are used
├─ sections/                      # optional LaTeX sections
├─ tables/*.tex                   # reusable table fragments
├─ figures/*.{pdf,png}            # directly compilable figures
├─ figures/*.svg                  # optional editable source
└─ manifest.json                  # hashes, status and provenance
```

The final narrative must not exist only as Markdown. Markdown may be retained as a convenience preview during migration, but LaTeX is the canonical human-readable deliverable.

## Portability rules

- Save text as UTF-8 and use repository-relative paths only.
- Chinese or bilingual documents use `ctexart` and compile with XeLaTeX or LuaLaTeX. English-only documents may use standard `article` and pdfLaTeX.
- Do not depend on shell escape, `minted`, local fonts, absolute paths or editor-specific commands.
- Use `booktabs` for tables, `graphicx` for PDF/PNG figures, and `hyperref` for links.
- Keep editable SVG when useful, but also export PDF or PNG because ordinary LaTeX does not include SVG without extra tooling.
- Escape LaTeX special characters in generated text and labels.
- Store citations in `references.bib`; never fabricate a key or bibliography entry.
- Compile from a clean output directory and preserve the compile log. Missing TeX software is an explicit handoff, not a successful compilation claim.

Recommended commands:

```powershell
latexmk -xelatex -interaction=nonstopmode main.tex
# or
xelatex -interaction=nonstopmode main.tex
bibtex main
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

## Deliverable mapping

| Workflow | Canonical LaTeX output | Machine evidence |
| --- | --- | --- |
| Literature review | `main.tex`, `innovation-report.tex`, `tables/*.tex`, `references.bib` | evidence cards, candidate ledger, map JSON, audit JSON |
| CNKI/international acquisition | `acquisition-report.tex` when a report is requested | acquisition ledger and per-download verification JSON |
| Empirical analysis | `results/report.tex`, model tables `.tex`, figures PDF/PNG | coefficients CSV/JSON, bundle, engine receipts, logs |
| Replication | `replication-report.tex` | source manifest, hashes, code and comparison JSON |

JSON/CSV remain authoritative for program-to-program transfer. LaTeX is authoritative for reading, editing and publication.
