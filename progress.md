# Progress — Zotero MCP × Meta Knowledge Graph

## Session 2026-09-09 — Deep-read / research embedding extension

### Planning completed

- Re-inspected `Pyrojewel-zard/ljg-skills` and selected only `ljg-paper` for the first integration round.
- Re-inspected vendored MKG concept extraction and research-agent boundaries.
- Confirmed the responsibilities are complementary:
  - MKG = all/selected-corpus machine-comparable concept graph;
  - `ljg-paper` = deep reading for selected high-value papers;
  - Zotero embedding = full-text semantic space;
  - research embedding = typed research-signature space.
- Added the Level 0 / Level 1 / Level 2 processing model to `task_plan.md`.
- Added ADRs for `AgentRunner`, dual artifacts, prompt-injection boundary, research embeddings, and limiting the initial skill surface.

### Implementation target for this session

```text
Zotero item/fulltext
      ↓
ensure L0 mapping
      ↓
AgentRunner (Codex | Claude)
      ↓
vendored ljg-paper instruction
      ↓
DeepReadResult
  ├─ note_markdown
  └─ PaperSignature
          ↓
 canonical signature text
          ↓
 EmbeddingProvider
          ↓
 research_embeddings
          ↓
 research_similarity_edges
```

### Validation strategy

GitHub Actions cannot authenticate to the user's local Codex/Claude accounts or reach localhost Zotero. Therefore CI will validate the architecture with deterministic fakes:

- fake agent runner -> full deep-read persistence path;
- fake embedding provider -> vector persistence;
- cosine research-similarity -> edge construction;
- CLI import/smoke tests;
- Ruff and integration tests.

Real CLI/Zotero execution remains a separate live validation on the user's machine.

### Current phase

Phase 8 — vendor `ljg-paper` and define typed deep-read contract: **in progress**.

---

## Session 2026-09-08 — Base integration and MKG vendoring

### Completed

- Inspected `Pyrojewel-zard/zotero-mcp` and verified Streamable HTTP MCP, complete-text retrieval, and semantic `find_similar` path.
- Implemented MCP JSON-RPC client, Zotero normalization/full-text retrieval, collection/library enumeration, content-hash incremental state, direct MKG `PaperContent`, concept extraction/relation persistence, similarity-edge generation, CLI, and tests.
- Added GitHub Actions CI and iterated until install / Ruff / integration pytest / CLI smoke test passed.
- Vendored the complete `Seaual/meta-knowledge-graph` source into `vendor/meta-knowledge-graph/` using its GitHub source ZIP and preserved upstream metadata/license.
- Changed runtime/CI/docs to use the vendored source directly.

### Live validation still required

This GitHub-connected session cannot access the user's localhost Zotero MCP endpoint. Base live checks remain:

```bash
grz doctor
grz sync-item <ITEM_KEY> --process
grz build-similarity --top-k 8 --min-score 0.55
grz stats
```
