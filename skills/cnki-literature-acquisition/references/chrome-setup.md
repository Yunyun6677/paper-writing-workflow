# Dedicated Chrome setup for CNKI

Use a dedicated persistent Chrome profile so the MCP server cannot inspect the user's ordinary browsing profile. The profile may contain CNKI/RUC login state, but should contain no unrelated accounts or tabs.

## Runtime

- Chrome 144 or newer.
- Node.js 20.19+, 22.12+, or 23+.
- `chrome-devtools-mcp` pinned to a reviewed version rather than `latest`.
- MCP arguments: `--slim`, `--no-usage-statistics`, `--no-performance-crux`, and `--redact-network-headers`.
- Do not use `--accept-insecure-certs`, `--allow-unrestricted-paths`, or the user's default Chrome data directory.

Example Codex registration on Windows:

```powershell
codex mcp add chrome-devtools-cnki -- `
  D:\Node.js\npx.cmd -y chrome-devtools-mcp@1.8.0 `
  --user-data-dir=D:\AI\Codex\paper-writing-workflow\.runtime\chrome-cnki-profile `
  --slim --no-usage-statistics --no-performance-crux --redact-network-headers
```

The actual Node/npm path and repository path must be verified locally. This is a persistent Codex configuration change and must be explicitly authorized after explaining that the MCP can read and operate pages inside the dedicated profile.

After registration, fully restart Codex or start a new Codex session. Merely writing the configuration does not add tools to an already-running session.

On first use, the MCP launches the dedicated Chrome profile. The user signs into CNKI or the university access portal manually. Never copy cookies or credentials into prompts, files, scripts, or logs.

## Probe

The setup is complete only when all are true:

1. `codex mcp list` shows `chrome-devtools-cnki` enabled.
2. A new Codex session exposes the Chrome DevTools navigation and JavaScript-evaluation tools.
3. The dedicated browser opens CNKI and the page visibly shows the expected institutional access state.
4. A harmless DOM read returns the current page title and hostname.
5. The workflow can trigger one authorized PDF download and the local verifier confirms its bytes.

If any check fails, record the exact failed layer: Codex configuration, MCP process, Chrome launch, login/access, CAPTCHA, CNKI download, local verification, or Zotero archive.
