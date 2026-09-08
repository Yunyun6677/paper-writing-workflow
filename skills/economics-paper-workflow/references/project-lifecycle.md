# Economics paper lifecycle

Use stage gates instead of one long prompt.

| Stage | Required input | Exit condition |
| --- | --- | --- |
| Frame | question, paper type, audience, candidate contribution | user approves a feasible question and provisional contribution |
| Design | estimand or theoretical object, assumptions, threats, data plan | design register approved; unresolved threats visible |
| Evidence | search scope and acquisition permissions | included literature is full-text verified; gaps are handed off |
| Analysis | validated data request and model registry | result bundle passes hashes and method-specific review |
| Outline | target-journal family, section purposes, evidence inputs | user approves outline and table/figure plan |
| Draft | approved outline and evidence | every claim is linked; all sections exist in LaTeX |
| Audit | manuscript, bibliography, result bundles | no blocking citation, numerical, design, privacy or build defect |
| Revision | prioritized issue list or referee letter | each issue is answered, deferred with reason, or blocked |
| Package | journal instructions and disclosure requirements | clean build, appendix, availability statement and manifest |

## Paper types

- **Empirical:** identification, data provenance and inference carry the paper.
- **Theoretical:** primitives, equilibrium/concept, propositions, proofs and empirical implications carry the paper.
- **Mixed:** theory predictions and empirical tests must map explicitly.
- **Measurement/data:** construct validity, coverage, benchmark comparisons and error structure carry the paper.
- **Replication:** target result, code/data versions and deviations carry the paper.
- **Review:** search design, evidence synthesis and boundaries carry the paper.

Do not demand hypotheses when the target journal or design does not use them. Do not add mathematical modeling merely to look economic; use it only when it clarifies the mechanism or identification.

## Versioning

Each material change creates a new manuscript or analysis version linked to its parent. Preserve the previous specification, outline, results and reviewer responses. Exploratory analysis lives outside the publication path until the user promotes it with a written rationale.
