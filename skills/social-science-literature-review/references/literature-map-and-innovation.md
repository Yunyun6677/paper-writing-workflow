# Literature map and innovation protocol

## Mandatory literature map

Every full review must include at least one evidence-backed figure showing the topic's logical structure. A word cloud, unconnected keyword graph, or decorative mind map does not qualify.

The map must answer:

- which questions, theories, mechanisms, findings, methods, contexts, and debates structure the field;
- which findings support or contradict one another;
- which boundary conditions explain heterogeneity;
- which evidence patterns reveal gaps;
- where proposed innovations enter the literature.

Build `literature-map.json` from verified evidence cards. Each node has a stable ID, type, label, evidence locators, supporting `record_id` values, confidence, and status. Each directed edge has a typed relation, supporting records and locators, evidence status (`direct`, `synthesized`, or `inferred`), confidence, and rationale. Inferred edges must be visually distinct and described as synthesis rather than an original paper's conclusion.

Default layout is left to right:

`research question → concepts/theories → mechanisms → findings → debates/conditions → gaps → innovations`.

Place method nodes beneath the findings they test. When the graph exceeds 25 nodes, render a readable aggregate map for the review and a detailed supplementary map rather than shrinking labels.

Render both editable graph data and `literature-map.svg` with the bundled [map renderer](../scripts/render_literature_map.py). Inspect the SVG: no clipped labels, overlaps, broken Chinese text, unsupported edges, or unexplained colors. The review must include the figure, a legend, a caption, and a paragraph explaining how to read it.

Run these gates before delivery:

- no unexplained orphan nodes;
- every substantive node and edge has evidence;
- full-text evidence has a page, section, table, or figure locator;
- correlation is not drawn as causation;
- major disagreements in prose appear in the map;
- at least 90% of the review's major themes appear in the map;
- every gap connects backward to evidence and forward to a research direction;
- every innovation connects to a gap and appears in the prose;
- graph, evidence table, prose, and bibliography use consistent IDs.

## Innovation portfolio

Generate innovation candidates only from mapped evidence gaps, contradictions, boundary conditions, or method limitations. Search at least these dimensions:

- theory integration;
- untested mechanism;
- measurement improvement;
- data, population, time, or context;
- identification strategy;
- contradiction resolution;
- policy or management application.

Each innovation card states:

- nearest verified prior work and linked map nodes;
- precise unresolved gap and supporting/contrary evidence;
- proposed contribution and contribution type;
- expected observable evidence and falsification condition;
- operational variables, required data, and identification strategy;
- feasibility constraints and a targeted reverse-search query;
- novelty confidence limited to the searched databases, languages, and dates.

Score 1–5 on originality, substantive importance, evidence support, feasibility, identification credibility, and fit with the user's research profile. Report component scores, not only a total. Role 2 must reverse-search the strongest novelty claim and role 4 must audit feasibility before the lead can call it an innovation. Otherwise label it a `potential direction`.

Reject candidates that merely change a sample, rename a construct, depend on unavailable data, or claim novelty because the team did not encounter prior work.
