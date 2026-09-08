# Manuscript writing and audit

## Section contracts

- **Title/abstract:** question, setting, design, headline result and contribution; no unsupported causal shorthand.
- **Introduction:** motivation, precise question, empirical or theoretical approach, headline magnitudes, contribution relative to nearest papers, roadmap.
- **Institution/context:** only facts needed to understand treatment, measurement or external validity.
- **Literature:** research conversations and disagreements; nearest-paper comparison, not an author list.
- **Theory/framework:** assumptions and causal logic; testable predictions mapped to outcomes and mechanisms.
- **Data:** provenance, construction, sample flow, unit, missingness and representativeness.
- **Identification/methods:** identifying variation, assumptions and threats before equations.
- **Results:** primary estimate and economic magnitude, uncertainty, sample changes and null results.
- **Robustness:** threat-driven tests; do not present a checklist of arbitrary specifications.
- **Mechanisms/heterogeneity:** distinguish preregistered, descriptive and separately identified evidence; do not call a correlation mediation.
- **Conclusion:** bounded findings, contribution, external validity, limitations and implications.

## Independent audit perspectives

Run these as separate passes when the project reaches draft or submission stage:

1. **Field editor:** contribution, positioning and audience.
2. **Identification reviewer:** estimand, assumptions, diagnostics and causal language.
3. **Data/code reviewer:** provenance, sample construction, reproducibility and privacy.
4. **Citation reviewer:** bibliographic identity, claim entailment, priority and missing contradictory evidence.
5. **Writing reviewer:** paragraph logic, terminology, unnecessary claims and journal fit.
6. **Table/figure reviewer:** source-of-truth, labels, units, notes, uncertainty and accessibility.

The writer may fix mechanical defects. Changes to outcomes, samples, estimands, models or substantive interpretations return to the user decision gate. Limit review cycles; unresolved disagreement is reported, not force-approved.

## Numerical claim registry

For every manuscript number record: claim ID, TeX location, displayed value/unit, source artifact, project/run/spec ID, source hash and verification status. Generated LaTeX tables should be included, never copied by hand.
