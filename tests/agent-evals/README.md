# Research Agent evaluations

This suite tests scientific contracts, not prose quality by impression. The default
fixture is synthetic and contains no user data. The public-replication test reads
only the redistributable metadata and numerical verification summary already stored
under `work/replications/`; restricted source data and licensed PDFs are not copied.

Run from the repository root:

```powershell
py -m unittest discover -s tests/agent-evals -p "test_*.py" -v
```

Metrics are grouped into literature, empirical, agent-runtime, and paper gates. A
zero-length category passes vacuously only for unit-level helper use; release fixtures
must include at least one case in every category.
