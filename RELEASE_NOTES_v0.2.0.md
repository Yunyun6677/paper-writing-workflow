# v0.2.0 — R engine and replication expansion

Released: 2026-09-06

This release turns the empirical module into a three-engine workflow.

- Added a structured R 4.6.1 bridge for smoke tests, reviewed analysis scripts and SVG/PNG coefficient plots.
- Added `engine-execution/1.0` receipts with hashes, logs, completion markers and session information.
- Reproduced the headline DID and five selected regressions from Card and Krueger (1994) in Python, Stata 16 and R.
- Verified cross-engine parity: maximum coefficient difference `1.21e-13`; maximum standard-error difference `4.80e-14`.
- Added a source-verified replication-method catalog for future DID, IV, trade, political economy and structural-model tests.
- Kept author data, paper PDFs, derived datasets, credentials and machine-local configuration out of the public repository.

The existing Autor–Dorn–Hanson replication remains available. See `CHANGELOG.md` and each case's `REPORT.md` for exact scope and limitations.
