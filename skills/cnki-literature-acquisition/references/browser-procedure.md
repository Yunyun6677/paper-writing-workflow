# CNKI browser procedure

This procedure adapts the efficient ideas in [cookjohn/cnki-skills](https://github.com/cookjohn/cnki-skills) to this repository's evidence and Zotero contracts. It uses direct navigation and small DOM operations, but adds a dedicated browser profile, no-cookie handling, byte-level download verification, deduplication, and explicit human handoff.

Selectors are observations, not permanent API guarantees. Re-read the current DOM when a selector fails; do not loop rapidly.

## Search page

On the standard CNKI search page, commonly observed selectors include:

- query input: `input.search-input`;
- search control: `input.search-btn`;
- result rows: `.result-table-list tbody tr`;
- title link: `td.name a.fz14`;
- author links: `td.author a.KnowledgeNetLink`;
- journal: `td.source a`;
- publication date: `td.date`;
- citation count: `td.quote`;
- download count: `td.download`.

Set input values and dispatch ordinary `input` or `change` events, then use the visible search control. Wait for a result-count or result-row condition. Extract title, href, authors, journal, date, citations, and downloads into JSON.

For target-journal work, constrain the journal field explicitly and verify the returned venue row by row. Search-result ranking may identify candidates, but only the paper detail page and downloaded full text establish identity.

## Paper detail page

Commonly observed selectors include:

- title: `.brief h1`;
- authors and affiliations: `.brief h3.author`;
- abstract: `.abstract-text`;
- keywords: `p.keywords a`;
- fund: `p.funds`;
- classification: `.clc-code`;
- PDF: `#pdfDown` or `.btn-dlpdf a`;
- CAJ: `#cajDown` or `.btn-dlcaj a`.

Remove only presentation suffixes such as `网络首发` from the captured title. Do not invent DOI, issue, pages, or author affiliations when absent.

## Visible CAPTCHA rule

CNKI may preload a Tencent CAPTCHA node off screen. Treat `#tcaptcha_transform_dy` as active only when it exists, is rendered, and its bounding rectangle is on screen. If visible, stop and ask the user to solve it in the dedicated Chrome window. Never simulate the slider or use a solving service.

## Download rule

Capture a filesystem snapshot first. Click the official PDF element once, falling back to CAJ only when the PDF element is absent. Then inspect the local download directory before any retry. A browser response such as `downloading` is provisional; the verifier determines success.

Do not return cookies or request headers from page JavaScript. Do not make an out-of-browser download request that assumes the browser's authenticated session.

## Metadata export

CNKI's visible export function may be used to obtain RIS/EndNote/GB/T metadata within the authenticated page. Metadata export can reduce manual transcription, but it must be cross-checked against the detail page and PDF. It never substitutes for full-text acquisition.
