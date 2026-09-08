# Progress — Zotero MCP × Meta Knowledge Graph

## Session 2026-09-08

### Completed

- Inspected `Pyrojewel-zard/zotero-mcp` and verified:
  - Streamable HTTP MCP server;
  - `get_content` complete-text path;
  - semantic index / `find_similar` path;
  - Zotero-side vector SQLite implementation.
- Inspected `Seaual/meta-knowledge-graph` and identified `PaperContent -> LLMConceptExtractor` as the clean integration seam.
- Implemented:
  - MCP JSON-RPC client;
  - Zotero paper normalization;
  - full-text retrieval;
  - collection/library enumeration;
  - incremental content-hash state;
  - direct MKG `PaperContent` construction;
  - concept extraction and explicit relation persistence;
  - similarity-edge generation from Zotero `find_similar`;
  - CLI commands and tests.
- Added GitHub Actions CI and iterated until install / Ruff / pytest / CLI smoke test all passed.
- Changed the integration model from runtime cloning to a self-contained vendored MKG tree.
- Added `.github/workflows/vendor-mkg.yml`.
- GitHub Actions successfully executed:
  - downloaded `Seaual/meta-knowledge-graph` `main.zip`;
  - unzipped it;
  - copied the complete source tree into `vendor/meta-knowledge-graph/`;
  - preserved upstream license;
  - committed the vendor import to `main` as commit `50a4bede06ee42b7f23e88fd29f7ed0d69c996d5`.
- Updated runtime/CI/docs to use `vendor/meta-knowledge-graph` directly and remove the runtime bootstrap requirement.

### CI validation

The integration CI has passed the following stages before vendoring:

```text
Install ✅
Bootstrap/source availability ✅
Ruff ✅
Pytest ✅
CLI import smoke test ✅
```

After vendoring, CI is configured to verify `vendor/meta-knowledge-graph/mkg/__init__.py` directly rather than cloning MKG.

### Important implementation discovery

Upstream MKG currently cannot be used as a normal `pip install git+https://...` dependency because setuptools detects multiple top-level packages/directories in the flat repository layout (`mkg`, `backend`, `frontend`, `docker`, `icon`). Vendoring therefore avoids a packaging problem while keeping the upstream source intact.

### Live validation still required

This GitHub-connected session cannot access the user's localhost Zotero MCP endpoint. The following must be run on the machine where Zotero is active:

```bash
grz doctor
grz sync-item <ITEM_KEY> --process
grz build-similarity --top-k 8 --min-score 0.55
grz stats
```

### Current phase

Repository implementation and vendoring: **complete**.

Live Zotero end-to-end verification: **pending**.
