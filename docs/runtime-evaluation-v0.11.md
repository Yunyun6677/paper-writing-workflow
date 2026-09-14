# Runtime evaluation in v0.11

The runtime evaluator keeps the original task/checkpoint counters and adds evidence-aware groups for routing, planning, literature, empirical work, writing, recovery, and efficiency.

Scientific scores are computed only from registered JSON verification receipts whose current file hash matches canonical state. A task marked complete, an upstream `passed` flag, or model prose cannot create a scientific score. When the required evidence is absent, the value is `null` and its path appears in `unavailable_metrics`; absence is never converted to 100%.

Implemented run-level measurements include specialist routing, tool allow-list routing, DAG validity, human corrections, replanning outcome, verified citation/full-text/numeric/causal/specification receipts, artifact consistency, bounded-loop status, token/model/tool counts, and local trace wall time. DOI correctness, duplicate literature rate, coefficient/SE rerun match, unnecessary-task rate, and duplicate external side-effect rate remain unavailable unless a benchmark fixture or dedicated receipt supplies the required comparison.

The existing `research_os/evals.py` fixture suite remains the benchmark layer for known-answer synthetic and public replication packages. The runtime evaluator and benchmark evaluator serve different purposes and do not substitute for one another.
