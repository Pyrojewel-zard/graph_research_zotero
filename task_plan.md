# Task Plan — Zotero MCP × Meta Knowledge Graph

**Status:** in_progress

## Goal

Build a working integration in `Pyrojewel-zard/graph_research_zotero` that reuses the user's running `Pyrojewel-zard/zotero-mcp` as the paper/fulltext/embedding source and reuses `Seaual/meta-knowledge-graph` as the concept extraction / graph / research-discovery engine.

The implementation must avoid duplicate PDF ingestion and avoid directly coupling to the private schema of `zotero-mcp-vectors.sqlite`.

## Non-goals

- Do not replace Zotero as the source of truth for papers.
- Do not recalculate embeddings already managed by Zotero MCP.
- Do not fork/copy the full Meta Knowledge Graph source tree into this repository.
- Do not make MKG read Zotero's internal SQLite files directly.
- Do not require a second PDF copy inside MKG.

## Architecture decision

```text
Zotero 7
  ├─ metadata / collections / tags
  ├─ parsed full text
  └─ embeddings in zotero-mcp-vectors.sqlite
           │
           │ public MCP tools
           ▼
Pyrojewel-zard/zotero-mcp
  ├─ get_item_details
  ├─ get_content / fulltext_database
  ├─ get_collection_items / search_library
  └─ find_similar / semantic_search
           │
           ▼
graph_research_zotero bridge
  ├─ ZoteroMCPClient
  ├─ ZoteroPaperSource
  ├─ SyncState
  ├─ MKGBridge
  └─ CLI
           │
           ▼
Meta Knowledge Graph
  ├─ PaperContent
  ├─ LLMConceptExtractor
  ├─ papers / concepts / paper_concepts
  ├─ concept_relations / concept_extractions
  ├─ graph / Neo4j (optional)
  └─ research-point discovery
```

## Phase 1 — Repository bootstrap

**Status:** complete

- [x] Initialize README with architecture and usage direction.
- [x] Add `pyproject.toml`.
- [x] Add `.env.example` and `.gitignore`.
- [x] Add package skeleton and runtime settings.
- [x] Add minimal Streamable HTTP MCP JSON-RPC client.

## Phase 2 — Zotero source adapter

**Status:** in_progress

- [ ] Implement `ZoteroPaper` normalized model.
- [ ] Implement metadata normalization for Zotero item details.
- [ ] Implement `get_content(mode=complete, format=text)` retrieval.
- [ ] Implement collection/library item enumeration.
- [ ] Implement `find_similar` normalization.
- [ ] Add defensive handling for several Zotero MCP response shapes.

## Phase 3 — MKG bridge and incremental state

**Status:** pending

- [ ] Create additive integration tables without modifying upstream MKG schema.
- [ ] Persist Zotero `itemKey ↔ MKG identifier` mapping.
- [ ] Compute SHA-256 content hash for change detection.
- [ ] Construct `mkg.pdf_models.PaperContent` directly from Zotero content.
- [ ] Reuse `LLMConceptExtractor` without invoking `PDFParser`.
- [ ] Save concept hierarchy through MKG repositories.
- [ ] Preserve concept extraction raw response.
- [ ] Mark processing state and errors.
- [ ] Reuse existing MKG LLM config; fallback to env-based LLM config.

## Phase 4 — Embedding-derived graph edges

**Status:** pending

- [ ] Call Zotero MCP `find_similar` for mapped papers.
- [ ] Store normalized undirected/directed similarity edges with score and timestamp.
- [ ] Never read raw vector BLOBs from Zotero MCP SQLite.
- [ ] Add threshold/top-K controls.
- [ ] Keep similarity graph auxiliary to MKG concept graph.

## Phase 5 — CLI and developer workflow

**Status:** pending

- [ ] `grz doctor`
- [ ] `grz collections`
- [ ] `grz sync-item`
- [ ] `grz sync-collection`
- [ ] `grz sync-library`
- [ ] `grz build-similarity`
- [ ] `grz stats`
- [ ] Provide readable Rich output and non-zero failures.

## Phase 6 — Tests and validation

**Status:** pending

- [ ] Unit-test MCP result unwrapping/normalization.
- [ ] Unit-test content hash / identifier behavior.
- [ ] Unit-test additive DB schema and idempotent writes.
- [ ] Unit-test concept tree persistence with a fake extractor.
- [ ] Static/import sanity check.
- [ ] Document the remaining live Zotero/MKG end-to-end verification.

## Completion gate

The task is complete only when all of these are true:

- [ ] A developer can clone this repo and install it.
- [ ] `grz doctor` can verify the Zotero MCP endpoint and semantic index.
- [ ] A Zotero item can be fetched without copying/re-parsing its PDF.
- [ ] The fetched text can be passed directly into MKG concept extraction.
- [ ] Re-running unchanged papers skips LLM extraction by content hash.
- [ ] Existing Zotero embeddings can create paper similarity edges through MCP.
- [ ] Core normalization/state logic has automated tests.
- [ ] `findings.md` and `progress.md` accurately describe implemented vs unverified behavior.

## Errors encountered

| Error | Attempt | Resolution |
|---|---:|---|
| GitHub connector safety-gated one large `zotero_source.py` create request | 1 | Split implementation into smaller writes and continue from the persistent plan. |

## Next Step

Implement the Zotero source adapter in smaller files/commits, then immediately add the integration state database and MKG bridge.
