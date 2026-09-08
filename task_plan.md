# Task Plan — Zotero MCP × Meta Knowledge Graph

**Status:** in_progress

## Goal

Build a working integration in `Pyrojewel-zard/graph_research_zotero` that reuses the user's running `Pyrojewel-zard/zotero-mcp` as the paper/fulltext/embedding source and ships a vendored copy of `Seaual/meta-knowledge-graph` as the concept-extraction / graph / research-discovery engine.

The implementation must avoid duplicate PDF ingestion and avoid directly coupling to the private schema of `zotero-mcp-vectors.sqlite`.

## Architecture decisions

- Zotero remains the paper source of truth.
- Zotero MCP remains the only interface to parsed full text and existing embeddings.
- MKG source is vendored in `vendor/meta-knowledge-graph/` so this repository is self-contained.
- No runtime MKG clone/bootstrap is required.
- MKG receives `PaperContent` built directly from Zotero full text, bypassing MKG PDF re-parsing.
- Embedding similarity is auxiliary to the MKG concept graph.

## Phase 1 — Repository bootstrap

**Status:** complete

- [x] README / pyproject / env / gitignore.
- [x] Package skeleton and settings.
- [x] Streamable HTTP MCP JSON-RPC client.
- [x] planning-with-files documents.

## Phase 2 — Zotero source adapter

**Status:** complete

- [x] `ZoteroPaper` normalized model.
- [x] Metadata normalization.
- [x] `get_content(mode=complete, format=text)` retrieval.
- [x] Collection/library enumeration.
- [x] `find_similar` normalization.
- [x] Defensive response-shape handling.

## Phase 3 — MKG bridge and incremental state

**Status:** complete

- [x] Additive integration tables.
- [x] Zotero `itemKey ↔ MKG identifier` mapping.
- [x] SHA-256 content hash.
- [x] Direct `PaperContent` construction.
- [x] Reuse `LLMConceptExtractor` without `PDFParser`.
- [x] Explicit concept / paper-concept / relation persistence.
- [x] LLM config reuse + env fallback.

## Phase 4 — Embedding-derived graph edges

**Status:** complete

- [x] Call Zotero MCP `find_similar`.
- [x] Store similarity score/source/timestamp.
- [x] Do not read raw Zotero vector BLOBs.
- [x] top-K / threshold controls.

## Phase 5 — CLI and developer workflow

**Status:** complete

- [x] `grz doctor`
- [x] `grz collections`
- [x] `grz sync-item`
- [x] `grz sync-collection`
- [x] `grz sync-library`
- [x] `grz build-similarity`
- [x] `grz stats`

## Phase 6 — Vendor MKG into this repository

**Status:** complete

- [x] Add one-shot GitHub workflow that downloads upstream MKG `main.zip`.
- [x] Unzip and copy the full upstream source tree into `vendor/meta-knowledge-graph/`.
- [x] Preserve upstream `LICENSE`.
- [x] Record the exact upstream commit in `UPSTREAM_VENDOR_INFO.md`.
- [x] Change runtime loading to prefer the vendored source.
- [x] Remove runtime bootstrap/clone requirement.
- [x] Change CI to validate the vendored path directly.

## Phase 7 — Tests and live validation

**Status:** partially_complete

- [x] Unit tests for normalization/state behavior.
- [x] Static/import sanity checks.
- [x] GitHub CI install / Ruff / pytest / CLI smoke test.
- [ ] Live `grz doctor` against the user's running Zotero MCP.
- [ ] Live single-paper concept extraction.
- [ ] Live `find_similar` graph-edge build.
- [ ] Validate large-library incremental synchronization.

## Completion gate

- [x] Repository contains its own MKG source tree.
- [x] A developer can clone and `pip install -e .` without separately cloning MKG.
- [x] Zotero item retrieval does not require copying/re-parsing the PDF.
- [x] Existing Zotero embeddings are reused through MCP.
- [x] Core bridge logic has automated tests.
- [ ] Live Zotero MCP end-to-end validation passes on the user's machine.

## Errors encountered

| Error | Resolution |
|---|---|
| Upstream MKG cannot be installed directly with `pip git+https` because its flat repo layout is not packaged as one Python distribution. | Vendor the upstream source tree and import `mkg` directly from `vendor/meta-knowledge-graph`. |
| This execution environment cannot directly download the GitHub source ZIP. | Use the target repository's GitHub Actions runner to download, unzip, commit, and push the upstream ZIP contents. |

## Next Step

Run the live validation on the machine where Zotero + `Pyrojewel-zard/zotero-mcp` is running:

```bash
grz doctor
grz sync-item <ITEM_KEY> --process
grz build-similarity
```
