# graph_research_zotero

把现有的 **Zotero MCP 文献库**、**Meta Knowledge Graph (MKG)**、**ljg-paper** 和可切换的 **Codex / Claude Code CLI** 组合成一个分层的研究发现系统。

核心原则不是“每篇论文多跑几遍 AI”，而是：

- Zotero / `Pyrojewel-zard/zotero-mcp` 继续作为论文、全文和现有 embedding 的唯一数据源；
- MKG 负责全局可比较的结构化知识、concept graph 和 research-point discovery；
- `ljg-paper` 只对值得深读的关键论文做 Level-2 深度分析；
- 第二 embedding 只编码机器可比较的 `PaperSignature`，**不重新 embedding 全文**；
- Codex / Claude Code 只是一层 `AgentRunner`，不是核心数据模型。

## Three processing levels

```text
LEVEL 0 — Indexed                         通常覆盖 100% library
────────────────────────────────────
Zotero metadata
Zotero parsed full text
Zotero MCP existing full-text embedding

LEVEL 1 — Structured                      研究 collection / corpus
────────────────────────────────────
MKG Stage 1 contribution extraction
MKG Stage 2 concept hierarchy
citation / concept / semantic-similarity graph

LEVEL 2 — Deep Read                       只处理少量高价值论文
────────────────────────────────────
Codex CLI or Claude Code CLI
        + vendored ljg-paper
                 ↓
          DeepReadResult
           ├─ note.md                给研究者阅读
           └─ PaperSignature JSON    给机器比较
                       ↓
             research embedding
                       ↓
           research-similarity graph
```

不要把 Level 2 当成默认 ingest。当前设计预期只对少量高价值论文使用，后续才会根据 bridge / PageRank / cluster representative / novelty / uncertainty / gap-neighbor 等信号自动升级。

## Architecture

```text
Zotero 7
  ├─ metadata / collections / tags
  ├─ cached full text
  └─ existing embeddings
          │
          │ Streamable HTTP MCP
          ▼
Pyrojewel-zard/zotero-mcp
  ├─ get_item_details
  ├─ get_content(mode=complete)
  ├─ search_library / get_collection_items
  └─ find_similar / semantic_search
          │
          ├─────────────────────────────────┐
          ▼                                 ▼
   Level 0 / Level 1                    Level 2 selected papers
          │                                 │
      MKGBridge                       AgentRunner
          │                         ┌───────┴───────┐
          ▼                       Codex          Claude
vendored Meta Knowledge Graph        │             │
  ├─ LLMConceptExtractor             └──────┬──────┘
  ├─ concept hierarchy                      │
  ├─ citation / graph                 vendored ljg-paper
  └─ Research Agent                         │
          │                                 ▼
          │                         note + PaperSignature
          │                                 │
          │                         research embedding
          │                                 │
          └────────────────┬────────────────┘
                           ▼
                    enriched research graph
```

### Design rule

**Zotero owns papers; MKG owns global derived knowledge; ljg-paper owns selected-paper deep understanding.**

本项目不会：

- 复制另一份 PDF；
- 直接读取 `zotero-mcp-vectors.sqlite` 的私有表结构；
- 对全文做第二遍 embedding；
- 默认对整个 library 执行 Codex / Claude 深读；
- 用 CLI Agent 再实现一套与 MKG 重复的 whole-graph gap finder。

## Vendored upstreams

### Meta Knowledge Graph

```text
vendor/meta-knowledge-graph/
```

`.github/workflows/vendor-mkg.yml` 下载上游 source ZIP、解压、复制并记录精确 commit。正常运行无需额外 clone MKG。

### ljg-paper

只 vendor `Pyrojewel-zard/ljg-skills` 中的：

```text
.agents/skills/ljg-paper/
```

`.github/workflows/vendor-ljg-paper.yml` 下载 `ljg-skills` 的 `master.zip`，只复制 `skills/ljg-paper`，并在：

```text
.agents/skills/ljg-paper/UPSTREAM_VENDOR_INFO.md
```

记录上游 commit。

当前第一版**没有接入** `ljg-qa / ljg-rank / ljg-structure / ...`，这是刻意的范围控制。

## What is implemented

### Zotero / MKG bridge

- Streamable HTTP MCP JSON-RPC client；
- Zotero metadata + 已解析全文读取；
- Zotero 内容直接构造成 MKG `PaperContent`，绕过 MKG `PDFParser`；
- 复用 vendored MKG `LLMConceptExtractor`；
- concept / hierarchy / paper-concept association persistence；
- content-hash 增量处理；
- 复用 Zotero MCP `find_similar` 构建全文语义相似边。

### Level-2 deep read

- `AgentRunner` interface；
- `CodexRunner`：non-interactive `codex exec`、stdin paper context、read-only sandbox、structured output schema；
- `ClaudeRunner`：non-interactive print/JSON mode；
- prompt trust boundary：论文全文与 MKG context 被明确视为 untrusted data；
- vendored `ljg-paper` instructions + ReadingGuide + template；
- 单次 agent call 同时产生：
  - `note_markdown`；
  - strict Pydantic `PaperSignature`。

### PaperSignature

当前机器结构包含：

```text
research_problem
prior_assumption
prior_failure
main_contribution
change_type / change_description
mechanism_steps
evidence[]
limitations[]
boundary_conditions[]
load_bearing_concepts[]
open_questions[]
transfer_candidates[]
confidence
```

Evidence 明确区分：

```text
direct
| author_interpretation
| inference
```

### Research embedding

第二向量空间只使用 canonical `PaperSignature.embedding_text()`：

```text
full-text embedding       Zotero MCP 已有
        │
        └─ 文本/主题语义相似

research embedding        本项目新增
        │
        └─ 问题结构 / 机制 / 假设 / 证据 / 局限 / 迁移逻辑相似
```

首版支持 OpenAI-compatible `/embeddings` endpoint，因此可接 hosted 或 local compatible embedding server。

## Install

```bash
git clone https://github.com/Pyrojewel-zard/graph_research_zotero.git
cd graph_research_zotero

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

pip install -e .
cp .env.example .env
```

因为 MKG 和 `ljg-paper` 都已经在仓库内，无需额外下载它们。

## Configure

基础：

```env
ZOTERO_MCP_URL=http://127.0.0.1:23120/mcp
MKG_DB_PATH=./data/mkg.db

MKG_LLM_PROVIDER=openai
MKG_LLM_API_KEY=
MKG_LLM_MODEL=gpt-5-mini
MKG_LLM_BASE_URL=https://api.openai.com/v1
```

Deep read：

```env
DEEP_READ_AGENT=codex
DEEP_READ_AGENT_TIMEOUT_SECONDS=900
DEEP_READ_DIR=./data/deep_reads

CODEX_BINARY=codex
CODEX_MODEL=

CLAUDE_BINARY=claude
CLAUDE_MODEL=
```

Codex / Claude 使用你机器上 CLI 已有的登录/鉴权状态。本项目不保存它们的账号凭据。

Research embedding 可选配置：

```env
RESEARCH_EMBEDDING_BASE_URL=http://127.0.0.1:8000/v1
RESEARCH_EMBEDDING_API_KEY=
RESEARCH_EMBEDDING_MODEL=<your-embedding-model>
RESEARCH_EMBEDDING_TIMEOUT_SECONDS=120
```

不配置 embedding endpoint 也可以正常生成 `note.md + signature.json`。

## Quick start

### 1. 基础检查

```bash
grz doctor
```

除了 Zotero MCP / semantic index / MKG DB，现在还会显示：

- vendored `ljg-paper` revision；
- Codex CLI 是否可用及版本；
- Claude CLI 是否可用及版本；
- research embedding 是否配置。

### 2. Level 1 — MKG structure

```bash
grz sync-item <ITEM_KEY> --process
```

或：

```bash
grz sync-collection <COLLECTION_KEY> --process
grz sync-library --process --limit 500
```

已有 Zotero embedding 的全文语义边：

```bash
grz build-similarity --top-k 8 --min-score 0.55
```

### 3. Level 2 — deep read

默认 runner：

```bash
grz deep-read <ITEM_KEY>
```

指定 Codex：

```bash
grz deep-read <ITEM_KEY> --runner codex
```

指定 Claude Code：

```bash
grz deep-read <ITEM_KEY> --runner claude
```

只生成深读，不立即 embedding：

```bash
grz deep-read <ITEM_KEY> --no-embed
```

强制重跑：

```bash
grz deep-read <ITEM_KEY> --force
```

输出路径：

```text
data/deep_reads/<library>/<itemKey>/
├── note.md
└── signature.json
```

source hash 同时包含 paper content hash、`ljg-paper` revision、runner 和 signature contract version，因此论文或 skill 更新后可以安全重新处理。

### 4. Research signature embedding

单篇：

```bash
grz embed-research <ITEM_KEY>
```

构建 Level-2 子集的 research similarity：

```bash
grz build-research-similarity --top-k 8 --min-score 0.55
```

如果数据库中存在多个 research embedding model，需要显式指定：

```bash
grz build-research-similarity --model <model-name>
```

### 5. Status

```bash
grz stats
```

包括：

```text
mapped_papers
processed_papers
similarity_edges
deep_reads
research_embeddings
research_similarity_edges
```

## Incremental behavior

### MKG Level 1

```text
same itemKey + same content_hash + processed
    → skip MKG LLM extraction
```

### Deep Read Level 2

```text
same paper content
+ same ljg-paper revision
+ same runner
+ same PaperSignature contract
+ existing artifacts
    → skip agent deep read
```

### Research embedding

```text
same signature hash + same embedding model
    → skip embedding
```

## Integration tables

本项目仅增加 additive tables，不改 MKG 核心 schema：

```text
zotero_paper_map
paper_similarity_edges
zotero_sync_runs
paper_deep_reads
research_embeddings
research_similarity_edges
```

MKG 自己的 `papers / concepts / concept_relations / paper_concepts / concept_extractions` 继续由 MKG repository 管理。

## Why two vector spaces?

一个典型的后续发现任务：

```text
full-text similarity LOW
research similarity HIGH
        ↓
可能是跨领域但问题结构/方法机制相似
        ↓
Transfer candidate
```

相反：

```text
full-text similarity HIGH
research similarity LOW
        ↓
同一个主题里采取不同机制或不同假设
        ↓
Competing route / conceptual divergence
```

这也是第二 embedding 层存在的理由；它不是 Zotero embedding 的重复品。

## Verification status

GitHub CI 使用 deterministic fakes，不需要真实 Zotero / Codex / Claude 账号，验证：

- editable install；
- vendored MKG；
- vendored `ljg-paper`；
- Ruff；
- integration pytest；
- `PaperSignature` parsing；
- Codex/Claude command construction；
- fake runner deep-read persistence；
- fake embedding persistence；
- research cosine similarity construction；
- CLI import smoke test。

真实环境仍需在运行 Zotero MCP 且已登录 CLI 的机器上验证：

```bash
grz doctor
grz sync-item <ITEM_KEY> --process
grz deep-read <ITEM_KEY> --runner codex
grz deep-read <ANOTHER_ITEM_KEY> --runner claude
grz build-similarity
grz build-research-similarity
grz stats
```

## Planning files

- `task_plan.md` — phases / completion gate
- `findings.md` — architecture findings / ADRs
- `progress.md` — implementation/testing log

## Upstream

- Zotero MCP fork: https://github.com/Pyrojewel-zard/zotero-mcp
- Meta Knowledge Graph: https://github.com/Seaual/meta-knowledge-graph
- ljg-skills: https://github.com/Pyrojewel-zard/ljg-skills
- planning-with-files: https://github.com/OthmanAdi/planning-with-files
