# Findings — Zotero MCP × Meta Knowledge Graph

## 2026-09-08 repository inspection

### Zotero MCP fork

Repository: `Pyrojewel-zard/zotero-mcp`

Key observations:

1. The plugin already contains a complete semantic-search subsystem:
   - `semantic/embeddingService.ts`
   - `semantic/textChunker.ts`
   - `semantic/vectorStore.ts`
   - `semantic/semanticSearchService.ts`

2. `VectorStore` owns a Zotero-side SQLite database named `zotero-mcp-vectors.sqlite` and stores vectors plus chunk text/index metadata there.

3. The plugin already exposes public MCP tools that are sufficient for this project:
   - `get_item_details`
   - `get_content`
   - `get_collections`
   - `get_collection_items`
   - `search_library`
   - `semantic_search`
   - `find_similar`
   - `semantic_status`
   - `fulltext_database`

4. `get_content` supports `mode=complete` and `format=text`, so Meta Knowledge Graph does not need to open the Zotero PDF again.

5. `find_similar` already delegates to `SemanticSearchService.findSimilar()`, so the bridge can reuse the existing embedding index without reading vector BLOBs.

6. The Streamable HTTP endpoint is `/mcp`, normally on `127.0.0.1:23120`, and accepts JSON-RPC `initialize`, `tools/list`, and `tools/call`.

### Meta Knowledge Graph

Repository: `Seaual/meta-knowledge-graph`

Key observations:

1. Existing paper upload flow writes a PDF path into MKG's SQLite database.

2. `ProcessService.process_paper()` currently requires `paper['pdf_path']` and then calls `PDFParser.parse(pdf_path)` before `LLMConceptExtractor.extract()`.

3. The coupling point is therefore small: instead of changing the extractor, build `mkg.pdf_models.PaperContent` directly from Zotero and call `LLMConceptExtractor.extract(PaperContent)`.

4. `PaperContent` needs:
   - title
   - authors
   - abstract
   - full_text
   - sections
   - metadata
   - optional doi / arxiv_id / keywords / contributions

5. MKG already exposes repositories for:
   - `papers`
   - `concepts`
   - `paper_concepts`
   - `concept_relations`
   - `concept_extractions`

6. MKG's existing concept graph is hierarchical. Embedding similarity should be stored as an auxiliary paper-to-paper graph rather than pretending semantic similarity is a concept hierarchy edge.

7. MKG optionally mirrors concept data into Neo4j. The bridge should use MKG repository APIs where possible so that optional Neo4j behavior remains available.

### Planning-with-files

Repository: `OthmanAdi/planning-with-files`

The project explicitly uses its three-file model:

- `task_plan.md` — phases and completion gate
- `findings.md` — durable investigation/architecture notes
- `progress.md` — execution and test ledger

Important working rules adopted here:

- update the plan after a phase transition;
- put implementation discoveries in `findings.md`;
- log actual tests/errors in `progress.md`;
- do not mark complete until the completion gate is satisfied.

## Architecture decisions

### ADR-001 — MCP boundary instead of direct SQLite access

**Decision:** Meta Knowledge Graph integration will call Zotero MCP tools rather than reading `zotero-mcp-vectors.sqlite`.

**Reasoning:**

- keeps the vector-store schema private to the Zotero plugin;
- preserves language/model/int8/index migrations inside the plugin;
- avoids SQLite concurrency/locking concerns while Zotero is running;
- future-proofs the graph project if the Zotero plugin changes storage backends;
- directly reuses `find_similar`, which is the capability the graph actually needs.

### ADR-002 — Zotero is the paper source of truth

**Decision:** MKG stores a lightweight paper row and derived knowledge, but no duplicate PDF is required.

A stable mapping table will connect:

```text
Zotero library_id + item_key
        ↕
MKG paper identifier
```

Preferred MKG identifier:

1. normalized DOI when present;
2. fallback `zotero:<library>:<itemKey>` when DOI is unavailable.

### ADR-003 — Content hash controls incremental extraction

**Decision:** hash the complete Zotero text and skip LLM extraction when:

- the mapped Zotero item already exists;
- the content hash is unchanged;
- prior concept processing completed successfully.

This keeps daily Zotero synchronization practical for hundreds/thousands of papers.

### ADR-004 — Similarity edges remain auxiliary

**Decision:** store embedding-derived edges in `paper_similarity_edges`, with score and source metadata.

They can later be used for:

- Leiden/Louvain clustering;
- bridge-paper detection;
- local-neighborhood exploration;
- candidate concept-dedup context;
- gap/transfer hypothesis ranking.

They do not replace MKG's `concept_relations`.

## Open verification items

These require the user's actual running Zotero instance or a local clone/test environment:

1. Exact `get_item_details` payload shape for all current item types.
2. Whether `search_library` with no query is the best whole-library enumeration route for this fork or whether `fulltext_database list` should be preferred.
3. Exact `find_similar` output shape after the user's current indexing/model configuration.
4. Large `get_content(mode=complete)` behavior for very long papers.
5. Real LLM concept-extraction throughput/cost for the user's library size.
