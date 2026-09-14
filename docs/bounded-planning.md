# Bounded planning in v0.11

The deterministic `default_graph()` remains the safe default. A model can participate only through `PlanningAdapter`, which returns a `task-graph-proposal/1.0`; it never mutates canonical state or the live graph.

`BoundedPlanner` validates proposal schema, total task budget, approved specialist roles, registered tools, tool/data-sensitivity compatibility, high-risk human approval, DAG acyclicity, and the final-audit/final-gate order. Adaptive proposals must identify an existing parent task. Their new nodes are merged through the existing dynamic-DAG function, which adds them as dependencies of final audit and final gate.

Both initial and adaptive planning are supported. `MockPlanningAdapter` provides deterministic CI fixtures. A production model-backed planning adapter is not yet certified; model planning remains optional, and Research Director retains sole transition authority. Specification guardrails and human design gates continue to apply after planning.
