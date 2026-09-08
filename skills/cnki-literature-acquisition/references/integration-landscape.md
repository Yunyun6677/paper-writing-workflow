# CNKI integration landscape

Evaluated on 2026-09-08. External repositories were inspected as design references only; their code was not copied or installed into the public workflow.

| Route | Useful idea | Limitation or risk | Decision here |
| --- | --- | --- | --- |
| [cookjohn/cnki-skills](https://github.com/cookjohn/cnki-skills) | Chrome DevTools navigation, DOM extraction, official download controls, visible CAPTCHA handoff | Its optional attachment helper can accept browser cookies and fetch a PDF outside the visible browser; that is outside this project's credential boundary | Adopt the browser/DOM pattern, but prohibit cookie export and independently verify downloaded bytes |
| [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | MCP-owned persistent profile or connection to a separately launched debuggable Chrome | A debugging endpoint can inspect every tab in that browser profile; an MCP-launched window may be hard for the user to surface on some Windows setups | Use a dedicated profile only; offer a loopback-only, manually launched visible handoff mode |
| [Zotero translators](https://github.com/zotero/translators) | CNKI metadata translation in the browser connector | Metadata capture is not proof that the full text was downloaded, is readable, or is attached to the intended item | Use translators when convenient, then deduplicate and verify the local attachment separately |
| Manual CNKI download plus Zotero/Jasminum matching | Practical recovery when an authorized user can download but automation cannot finish the final attachment step | Filename matching and bibliographic identity can be wrong without an audit record | Keep as a `needs-human` fallback; run the same signature, page-count, title, and hash checks afterward |

## Project-specific controls

- Never connect to the user's ordinary browser profile.
- Never read, print, save, or transmit CNKI cookies, passwords, tokens, or session headers.
- Never automate CAPTCHA solving or derive hidden download endpoints.
- A successful click is only `download-triggered`; `fulltext-verified` requires local file validation.
- A Zotero metadata record is only `record-created`; `archived-local` requires a readable local attachment verified through Zotero Desktop.
- External source code and author data stay in ignored working directories unless redistribution permission is explicit.

