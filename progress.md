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

### Implemented

#### Vendored skill

- Added `.github/workflows/vendor-ljg-paper.yml`.
- Vendored only `skills/ljg-paper` into `.agents/skills/ljg-paper/`.
- Recorded upstream `Pyrojewel-zard/ljg-skills` `master` commit:
  `2f867dcb5ad0fcf4158bcdbef2b4d16d944bc29d`.

#### Typed deep-read contract

Added `src/graph_research_zotero/paper_signature.py`:

- `EvidenceItem` with `direct | author_interpretation | inference` strength;
- `LoadBearingConcept` with distinction / dependency / effect / example / boundary fields;
- strict `PaperSignature`;
- `DeepReadResult = note_markdown + signature`;
- deterministic `PaperSignature.embedding_text()`;
- parser for direct JSON and Claude-style JSON wrappers.

#### AgentRunner

Added `src/graph_research_zotero/agent_runner.py`:

- `AgentRunner` protocol;
- `CodexRunner` using non-interactive `codex exec`, stdin prompt, read-only sandbox, output schema, last-message file;
- `ClaudeRunner` using non-interactive print/JSON mode;
- configurable executable/model/timeout;
- executable/version diagnostics exposed through `grz doctor`.

#### Deep-read orchestration

Added `src/graph_research_zotero/deep_read.py`:

```text
Zotero full text
      ↓
ensure L0 mapping
      ↓
trusted vendored ljg-paper + untrusted paper/MKG data
      ↓
AgentRunner
      ↓
DeepReadResult
  ├─ note.md
  └─ signature.json
      ↓
optional research embedding
```

Important behavior:

- refuses unusably short full text;
- source hash includes paper content, `ljg-paper` revision, runner, and contract version;
- unchanged successful reads skip agent execution unless forced;
- paper content/MKG context are explicitly delimited as untrusted data to reduce prompt-injection risk;
- the application, not the CLI agent, writes artifacts;
- output signature paper id/title are normalized to the real Zotero/MKG identity.

#### Research-signature embedding

Added `src/graph_research_zotero/research_embedding.py`:

- `EmbeddingProvider` protocol;
- OpenAI-compatible `/embeddings` client;
- cosine similarity;
- embeds only canonical `PaperSignature`, never the full paper again.

Extended additive SQLite state with:

```text
paper_deep_reads
research_embeddings
research_similarity_edges
```

Added persistence/skip/build methods and extended stats.

#### CLI

Added:

```bash
grz deep-read <ITEM_KEY> --runner codex|claude
grz embed-research <ITEM_KEY>
grz build-research-similarity
grz stats
```

`grz doctor` now also reports:

- vendored `ljg-paper` revision;
- Codex CLI availability/version;
- Claude CLI availability/version;
- research embedding configuration.

#### Configuration / docs

- Extended `.env.example` with agent and research-embedding settings.
- Rewrote README around the three-level processing architecture and two vector spaces.
- Updated `task_plan.md` completion gate and phase states.

### Automated execution performed

GitHub Actions run **34300574565** executed the current implementation on Python 3.11 with deterministic fakes.

Final result:

```text
Install                     ✅
Verify vendored MKG         ✅
Verify vendored ljg-paper   ✅
Ruff                        ✅
Pytest integration package ✅
CLI import smoke test       ✅
```

The tests exercise more than imports:

- direct + Claude-wrapped `DeepReadResult` parsing;
- Codex / Claude CLI command construction;
- fake runner -> full `DeepReadService` -> persisted note/signature;
- source-hash skip on unchanged second run;
- fake embedding provider -> persisted research vector;
- cosine similarity -> persisted `research_similarity_edges`;
- stats for deep reads and research vectors.

### CI issues found and resolved

1. Vendored MKG previously caused root-level pytest to collect upstream scripts/tests; integration CI is intentionally scoped to this project's `tests/`.
2. Several CI attempts were blocked only by Ruff import formatting in `tests/test_paper_signature.py`; Ruff's exact emitted diff was applied, after which the full test chain passed.

### Not executed in GitHub Actions

GitHub-hosted runners cannot reach the user's running Zotero MCP on localhost and do not inherit the user's authenticated Codex/Claude CLI sessions. Therefore the following remain **live-machine validation**, not claimed as CI-tested:

```bash
grz doctor
grz sync-item <ITEM_KEY> --process
grz deep-read <ITEM_KEY> --runner codex
grz deep-read <ANOTHER_ITEM_KEY> --runner claude
# once an embedding endpoint/model is configured
grz embed-research <ITEM_KEY>
grz build-research-similarity
grz stats
```

### Current phase

Phases 8–11: **MVP implementation complete and CI-tested**.

Phase 12: **pending real-data evaluation** — compare Zotero full-text similarity with research-signature similarity, identify transfer/divergence cases, then define an evidence-based automatic Level-2 promotion policy.

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
