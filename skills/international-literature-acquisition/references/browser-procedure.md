# Authorized publisher browser procedure

Use this procedure for ScienceDirect and other publisher platforms when an open copy was not found.

1. Start a dedicated research browser profile. Do not attach automation to unrelated personal browsing sessions.
2. Navigate to the DOI or verified publisher record.
3. Let the user complete the university-library or publisher login. Do not inspect credential fields or export session data.
4. Confirm the visible title, authors, journal, year, and DOI against the ledger.
5. Confirm that the page indicates open access or the user's institutional entitlement.
6. Take a filesystem snapshot of the configured download directory.
7. Click the visible official PDF download control once.
8. Check the filesystem before retrying. A new HTML page, zero-byte file, or preview is not success.
9. Verify PDF structure, identity, version, and SHA-256; copy it to the project literature directory.
10. Deduplicate in Zotero, attach the verified file, classify it under the research project, and verify the local attachment.

Pause for the user when login expires, a visible CAPTCHA appears, payment is required, or the provider denies access. The handoff must name the work and exact blocker.
