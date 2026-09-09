# Task Plan — Zotero MCP × Meta Knowledge Graph

**Status:** in_progress

## Goal

Build a self-contained research-discovery system in `Pyrojewel-zard/graph_research_zotero` that combines:

1. Zotero as the paper source of truth;
2. `Pyrojewel-zard/zotero-mcp` for metadata, parsed full text, and the existing full-text embedding index;
3. vendored `Seaual/meta-knowledge-graph` for machine-comparable concept extraction, graph construction, citation/research discovery;
4. Codex CLI or Claude Code CLI as an optional deep-reading execution layer;
5. `Pyrojewel-zard/ljg-skills` — initially **only `ljg-paper`** — for high-value paper deep reading;
6. a second, research-signature embedding space for cross-paper mechanism/gap/transfer analysis.

The design must avoid duplicate PDF ingestion, duplicate full-text embedding, and unnecessary agent calls across the entire library.

## Processing levels

```text
LEVEL 0 — Indexed (100% of library)
Zotero metadata + parsed fulltext + existing Zotero embedding

LEVEL 1 — Structured (selected collections / research corpus)
MKG Stage 1 + Stage 2 + concept graph + citation/similarity edges

LEVEL 2 — Deep Read (high-value papers only, typically 5–20%)
Codex/Claude + ljg-paper -> human note + PaperSignature JSON
                         -> research-signature embedding
```

Promotion from Level 1 to Level 2 should eventually be driven by signals such as user selection, PageRank/bridge score, cluster representativeness, novelty, extraction uncertainty, and adjacency to candidate research gaps. The MVP exposes manual deep-read commands first.

## Architecture decisions

- Zotero remains the paper source of truth.
- Zotero MCP remains the only interface to parsed full text and existing full-text embeddings.
- MKG source is vendored in `vendor/meta-knowledge-graph/` so this repository is self-contained.
- MKG receives `PaperContent` built directly from Zotero full text, bypassing MKG PDF re-parsing.
- Existing Zotero embedding remains the **semantic/full-text vector space**.
- New research embedding is generated only from normalized `PaperSignature`, not from the full paper again.
- `ljg-paper` is the only `ljg-*` skill in the first deep-read implementation.
- Codex/Claude are accessed behind one `AgentRunner` interface; downstream code must not depend directly on one CLI.
- Deep-read agents return a machine contract; the application persists the markdown note and JSON itself.
- MKG remains responsible for graph-level research opportunity discovery; CLI agents do not duplicate MKG's whole-graph gap agent.

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

## Phase 4 — Existing embedding-derived graph edges

**Status:** complete

- [x] Call Zotero MCP `find_similar`.
- [x] Store full-text semantic similarity score/source/timestamp.
- [x] Do not read raw Zotero vector BLOBs.
- [x] top-K / threshold controls.

## Phase 5 — Base CLI and developer workflow

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

- [x] Download upstream MKG `main.zip` with GitHub Actions.
- [x] Unzip/copy complete source into `vendor/meta-knowledge-graph/`.
- [x] Preserve upstream `LICENSE` and commit metadata.
- [x] Use vendored MKG directly at runtime/CI.

## Phase 7 — Existing bridge tests and live validation

**Status:** partially_complete

- [x] Unit tests for normalization/state behavior.
- [x] Static/import sanity checks.
- [x] GitHub CI install / Ruff / integration pytest / CLI smoke test.
- [ ] Live `grz doctor` against the user's running Zotero MCP.
- [ ] Live single-paper MKG concept extraction.
- [ ] Live Zotero `find_similar` graph-edge build.
- [ ] Validate large-library incremental synchronization.

## Phase 8 — Vendor `ljg-paper` and define deep-read contract

**Status:** in_progress

- [ ] Vendor only `skills/ljg-paper` from `Pyrojewel-zard/ljg-skills` into `.agents/skills/ljg-paper/`.
- [ ] Preserve/record upstream repository + commit.
- [ ] Define strict `PaperSignature` Pydantic schema.
- [ ] Define `DeepReadResult` containing `note_markdown` + `signature`.
- [ ] Build a prompt that combines paper content, MKG context, and the vendored `ljg-paper` instructions while treating paper text as untrusted data.

## Phase 9 — AgentRunner abstraction

**Status:** pending

- [ ] Add `AgentRunner` protocol/base class.
- [ ] Add `CodexRunner` using non-interactive `codex exec`.
- [ ] Add `ClaudeRunner` using `claude -p` print mode.
- [ ] Detect executable availability and expose it through `grz doctor`.
- [ ] Keep command/timeout/model configurable by environment variables.
- [ ] Parse/validate runner output independent of provider-specific wrappers.
- [ ] Unit-test command construction and output parsing without needing authenticated CLIs in CI.

## Phase 10 — Deep-read orchestration and persistence

**Status:** pending

- [ ] Add `DeepReadService`.
- [ ] Fetch a Zotero paper/full text through the existing MCP source.
- [ ] Ensure Level-0 mapping exists before deep read.
- [ ] Generate source hash including paper content + skill revision.
- [ ] Skip unchanged successful deep reads unless `--force`.
- [ ] Persist `notes/<paper>.md` and `analysis/<paper>.signature.json` under a deterministic data directory.
- [ ] Persist deep-read metadata/status in additive SQLite tables.
- [ ] Add `grz deep-read ITEM_KEY [--runner codex|claude] [--force]`.

## Phase 11 — Research-signature embeddings

**Status:** pending

- [ ] Define `EmbeddingProvider` interface.
- [ ] Implement OpenAI-compatible `/embeddings` provider so local/OpenAI-compatible servers can be used without coupling to one vendor.
- [ ] Embed canonicalized `PaperSignature` text only; never re-embed full paper text.
- [ ] Persist model/dimension/vector/signature hash.
- [ ] Add cosine research-similarity construction over the deep-read subset.
- [ ] Add `grz embed-research ITEM_KEY` and `grz build-research-similarity`.

## Phase 12 — Evaluation and promotion policy

**Status:** pending

- [ ] Compare full-text similarity vs research-signature similarity on representative papers.
- [ ] Surface cases where semantic similarity is low but research similarity is high (transfer candidates).
- [ ] Surface cases where semantic similarity is high but research similarity is low (competing routes / conceptual divergence).
- [ ] Add automatic Level-2 promotion only after manual MVP quality is validated.

## Completion gate for this implementation round

- [ ] `ljg-paper` is vendored/self-contained in the repo.
- [ ] `AgentRunner` supports both Codex and Claude command construction.
- [ ] A fake runner can complete a full `DeepReadService` test and produce valid note + `PaperSignature`.
- [ ] `PaperSignature` can be embedded through a fake provider and persisted.
- [ ] Research-similarity edges can be generated from persisted signature embeddings.
- [ ] CLI exposes deep-read/research-embedding commands.
- [ ] Ruff + integration pytest + CLI smoke tests pass in GitHub Actions.
- [ ] Documentation clearly separates CI-tested behavior from live CLI/Zotero behavior that still requires the user's machine.

## Errors encountered

| Error | Resolution |
|---|---|
| Upstream MKG cannot be installed directly with `pip git+https` because its flat repo layout is not packaged as one Python distribution. | Vendor the upstream source tree and import `mkg` directly from `vendor/meta-knowledge-graph`. |
| This execution environment cannot directly download the GitHub source ZIP. | Use the target repository's GitHub Actions runner to download, unzip, commit, and push upstream ZIP contents. |
| Running root-level `pytest` after vendoring also collected MKG's upstream scripts/tests, including upstream failures unrelated to this bridge. | Scope integration CI to this repository's `tests/`; preserve upstream tests untouched. |

## Next Step

Vendor `ljg-paper`, implement the deep-read data contract and `AgentRunner`, then add a fake-runner end-to-end test before wiring real CLI commands.
