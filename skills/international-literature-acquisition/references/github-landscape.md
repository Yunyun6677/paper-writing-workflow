# GitHub integration landscape

Reviewed on 2026-09-08. Repository popularity is not evidence of legal access; each component is used only for the role below.

| Project | Adopted role | Decision |
| --- | --- | --- |
| [OpenAlex Official CLI](https://github.com/ourresearch/openalex-official) | OA metadata and bulk PDF/TEI retrieval with checkpointing | Primary optional downloader for OpenAlex-authorized content |
| [Unpaywall backend](https://github.com/ourresearch/oadoi) and [extension](https://github.com/ourresearch/unpaywall-extension) | DOI-to-lawful-OA resolution | Primary OA resolver; API requires a contact email |
| [Elsevier elsapy](https://github.com/ElsevierDev/elsapy) | Scopus/ScienceDirect API client | Optional adapter when the user has an API key and entitlement |
| [Zotero Connectors](https://github.com/zotero/zotero-connectors) | Browser metadata/file capture | Primary browser-to-Zotero archive route |
| [scholarly](https://github.com/scholarly-python-package/scholarly) | Google Scholar metadata discovery | Optional and low-volume only; not the download backbone |
| [PaperQA2](https://github.com/Future-House/paper-qa) | Citation-aware reading and question answering after acquisition | Downstream reading candidate, not an access tool |
| [paperscraper](https://github.com/jannisborn/paperscraper) | PubMed and preprint-server retrieval | Useful for health/science topics; limited fit for economics and public administration |

The workflow borrows the metadata-first, checkpoint, provider-routing, and post-download verification ideas. It does not vendor these projects or inherit their credentials. Pin and review a dependency before installing it.
