# Evaluated sources (2026-09-04)

Repository documentation was inspected, not installed wholesale or treated as security-audited code. No project code was copied.

| Source | Adopted design | Boundary |
|---|---|---|
| https://github.com/drivendataorg/cookiecutter-data-science | Separate immutable raw data, derived data, code and reports | Use a lighter per-run structure, no full template dependency |
| https://github.com/Roche/pyreadstat | Read DTA with variable/value labels and missing metadata | Preserve original file; fail on tagged missing pending an explicit rule |
| https://github.com/iterative/dvc (redirects to treeverse/dvc) | Data hashes and separately configured remote backup | No cloud destination chosen; DVC is not installed/configured |
| https://github.com/bashtage/linearmodels | Candidate for panel and IV extensions | Not yet integrated or validated in this v1 |
| https://github.com/hanlulong/stata-mcp | Possible MCP command/log bridge | Requires installed Stata and separate configuration; do not expose a server now |
| https://github.com/SepineTam/mcp-for-stata | Alternative Stata agent bridge | Compare compatibility/security at Stata onboarding; not installed |
| https://www.stata.com/python/pystata19/install.html | Official stata_setup/PyStata route | Requires licensed Stata, supported version and edition |

Prefer an official local PyStata bridge first; add MCP only if interactive tool exposure adds value. A Stata interface cannot substitute for the commercial Stata installation/license. Further methods should follow package documentation and replication tests, not generated code alone.
