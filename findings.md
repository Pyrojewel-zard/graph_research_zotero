# Findings — Zotero MCP × Meta Knowledge Graph

## Zotero MCP fork

Repository: `Pyrojewel-zard/zotero-mcp`

Key observations:

1. The plugin already contains a complete semantic-search subsystem and owns `zotero-mcp-vectors.sqlite`.
2. Public MCP tools are sufficient for this integration: `get_item_details`, `get_content`, `get_collections`, `get_collection_items`, `search_library`, `semantic_search`, `find_similar`, `semantic_status`, `fulltext_database`.
3. `get_content(mode=complete, format=text)` lets the graph project consume parsed text without re-opening the PDF.
4. `find_similar` already reuses the plugin's embedding/index implementation, so the graph project never needs to read raw vector BLOBs.
5. Streamable HTTP MCP normally runs at `http://127.0.0.1:23120/mcp`.

## Meta Knowledge Graph

Upstream: `Seaual/meta-knowledge-graph`

Key observations:

1. MKG's normal paper flow is `pdf_path -> PDFParser -> PaperContent -> LLMConceptExtractor`.
2. The clean integration seam is `PaperContent`: Zotero full text can be converted directly to `mkg.pdf_models.PaperContent`, then passed to `LLMConceptExtractor`.
3. MKG already provides repositories/tables for papers, concepts, paper-concept associations, concept relations, and concept extraction records.
4. Embedding similarity should remain an auxiliary paper-to-paper graph and must not be confused with MKG's hierarchical `concept_relations`.
5. Upstream MKG is not currently packaged as a directly installable Git Python dependency: setuptools rejects its flat layout because several top-level packages/directories are present.

## Vendoring decision

### ADR-005 — Vendor the complete MKG source tree

**Decision:** Ship the upstream MKG source inside this repository at:

```text
vendor/meta-knowledge-graph/
```

**Reasoning:**

- user explicitly wants one self-contained repository;
- avoids runtime `git clone` / bootstrap;
- avoids upstream packaging failure;
- preserves the exact upstream implementation for future direct modification;
- allows bridge code and MKG code to evolve together in this project;
- upstream `LICENSE` is preserved.

The vendored source was produced by GitHub Actions using the upstream `main.zip`, not by manually recreating individual files. The workflow records the exact upstream commit in `vendor/meta-knowledge-graph/UPSTREAM_VENDOR_INFO.md`.

Normal runtime resolves MKG from the vendored directory. `MKG_SOURCE_PATH` is retained only as an explicit developer override.

## Core architecture decisions

### ADR-001 — MCP boundary instead of direct SQLite access

Meta Knowledge Graph integration calls Zotero MCP tools rather than reading `zotero-mcp-vectors.sqlite`.

Benefits:

- vector-store schema remains private to the Zotero plugin;
- index migrations stay inside the plugin;
- no concurrent SQLite locking with Zotero;
- storage backend can change without breaking the graph project.

### ADR-002 — Zotero remains paper source of truth

MKG stores lightweight paper rows and derived knowledge, not another PDF copy.

Identifier preference:

1. normalized DOI;
2. fallback `zotero:<library>:<itemKey>`.

### ADR-003 — Content hash controls incremental extraction

Skip LLM extraction when the same mapped item has the same full-text SHA-256 and prior processing completed successfully.

### ADR-004 — Similarity edges remain auxiliary

Embedding-derived edges are stored separately with score/source/timestamp and can later support Leiden/Louvain clustering, bridge-paper detection, neighborhood exploration, concept-dedup context, and research-gap ranking.

## Open verification items

These require the user's actual Zotero instance:

1. Exact `get_item_details` payload shape for all item types in the running fork.
2. Whole-library enumeration behavior on the user's library size.
3. Exact `find_similar` output under the user's current embedding/model configuration.
4. Large `get_content(mode=complete)` behavior for very long papers.
5. Real LLM extraction throughput/cost.
6. End-to-end concept graph and similarity-edge quality on representative RFIC literature.
