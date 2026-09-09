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

**Status:** complete

- [x] Vendor only `skills/ljg-paper` from `Pyrojewel-zard/ljg-skills` into `.agents/skills/ljg-paper/`.
- [x] Preserve/record upstream repository + commit.
- [x] Define strict `PaperSignature` Pydantic schema.
- [x] Define `DeepReadResult` containing `note_markdown` + `signature`.
- [x] Build a prompt that combines paper content, MKG context, and the vendored `ljg-paper` instructions while treating paper text as untrusted data.

## Phase 9 — AgentRunner abstraction

**Status:** complete_mvp

- [x] Add `AgentRunner` protocol/base class.
- [x] Add `CodexRunner` using non-interactive `codex exec`.
- [x] Add `ClaudeRunner` using Claude Code print/JSON mode.
- [x] Detect executable availability and expose it through `grz doctor`.
- [x] Keep command/timeout/model configurable by environment variables.
- [x] Parse/validate runner output independent of provider-specific wrappers.
- [x] Unit-test command construction and output parsing without authenticated CLIs in CI.
- [ ] Live authenticated Codex CLI execution on the user's machine.
- [ ] Live authenticated Claude Code CLI execution on the user's machine.

## Phase 10 — Deep-read orchestration and persistence

**Status:** complete_mvp

- [x] Add `DeepReadService`.
- [x] Fetch a Zotero paper/full text through the existing MCP source.
- [x] Ensure Level-0 mapping exists before deep read.
- [x] Generate source hash including paper content + skill revision + runner + contract version.
- [x] Skip unchanged successful deep reads unless `--force`.
- [x] Persist deterministic `note.md` + `signature.json` artifacts.
- [x] Persist deep-read metadata/status in additive SQLite tables.
- [x] Add `grz deep-read ITEM_KEY [--runner codex|claude] [--force]`.
- [x] Test complete orchestration with a deterministic fake runner in CI.
- [ ] Live deep read of representative Zotero papers.

## Phase 11 — Research-signature embeddings

**Status:** complete_mvp

- [x] Define `EmbeddingProvider` interface.
- [x] Implement OpenAI-compatible `/embeddings` provider for hosted/local compatible servers.
- [x] Embed canonicalized `PaperSignature` text only; never re-embed full paper text.
- [x] Persist model/dimension/vector/signature hash.
- [x] Add cosine research-similarity construction over the deep-read subset.
- [x] Add `grz embed-research ITEM_KEY` and `grz build-research-similarity`.
- [x] Test vector persistence and research-similarity edge construction with deterministic fake embeddings.
- [ ] Live embedding endpoint/model quality validation.

## Phase 12 — Evaluation and promotion policy

**Status:** pending

- [ ] Compare full-text similarity vs research-signature similarity on representative papers.
- [ ] Surface cases where semantic similarity is low but research similarity is high (transfer candidates).
- [ ] Surface cases where semantic similarity is high but research similarity is low (competing routes / conceptual divergence).
- [ ] Define quality metrics for `PaperSignature` extraction.
- [ ] Add automatic Level-2 promotion only after manual MVP quality is validated.

## Completion gate for the 2026-09-09 implementation round

- [x] `ljg-paper` is vendored/self-contained in the repo.
- [x] `AgentRunner` supports both Codex and Claude command construction.
- [x] A fake runner completes a full `DeepReadService` test and produces valid note + `PaperSignature`.
- [x] `PaperSignature` can be embedded through a fake provider and persisted.
- [x] Research-similarity edges can be generated from persisted signature embeddings.
- [x] CLI exposes deep-read/research-embedding commands.
- [x] Ruff + integration pytest + CLI smoke tests pass in GitHub Actions (run `34300574565`).
- [x] Documentation clearly separates CI-tested behavior from live CLI/Zotero behavior that still requires the user's machine.

## Errors encountered

| Error | Resolution |
|---|---|
| Upstream MKG cannot be installed directly with `pip git+https` because its flat repo layout is not packaged as one Python distribution. | Vendor the upstream source tree and import `mkg` directly from `vendor/meta-knowledge-graph`. |
| This execution environment cannot directly download the GitHub source ZIP. | Use the target repository's GitHub Actions runner to download, unzip, commit, and push upstream ZIP contents. |
| Running root-level `pytest` after vendoring also collected MKG's upstream scripts/tests, including upstream failures unrelated to this bridge. | Scope integration CI to this repository's `tests/`; preserve upstream tests untouched. |
| Ruff import formatting blocked several CI attempts before pytest. | Follow Ruff's emitted diff exactly; final run reaches and passes integration pytest. |

## Next Step

Run live Zotero + Codex/Claude validation on representative papers, then use those real `PaperSignature` results to implement Phase 12: dual-space comparison, transfer/divergence discovery, and evidence-based Level-2 promotion policy.
