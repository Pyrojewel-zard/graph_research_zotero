# graph_research_zotero

把现有的 **Zotero MCP 文献库** 与 **Meta Knowledge Graph (MKG)** 组合成一个完整仓库：

- Zotero / `Pyrojewel-zard/zotero-mcp` 继续作为论文、全文和 embedding 的唯一数据源；
- `Seaual/meta-knowledge-graph` 已完整 vendor 到 `vendor/meta-knowledge-graph/`；
- 不重新上传 PDF，不重新计算 embedding，不直接读取 `zotero-mcp-vectors.sqlite`；
- MKG 负责两阶段 concept extraction、concept hierarchy、graph 和 research-point discovery；
- Zotero MCP 的 `find_similar` 用于生成论文之间的 semantic-similarity edges。

## Architecture

```text
Zotero 7
  │
  ├─ metadata / collections / tags
  ├─ cached full text
  └─ existing embeddings
       │
       │ Streamable HTTP MCP
       ▼
Pyrojewel-zard/zotero-mcp
  │
  ├─ get_item_details
  ├─ get_content(mode=complete)
  ├─ search_library / get_collection_items
  └─ find_similar / semantic_search
       │
       ▼
graph_research_zotero
  │
  ├─ ZoteroMCPClient
  ├─ ZoteroPaperSource
  ├─ MKGBridge
  ├─ SyncState / semantic edges
  │
  └─ vendor/meta-knowledge-graph
       ├─ mkg/PaperContent
       ├─ LLMConceptExtractor
       ├─ ConceptRepository
       ├─ graph / Neo4j (optional)
       └─ Research Agent / Research Point Discovery
```

### Design rule

**Zotero owns papers; MKG owns derived knowledge.**

MKG 源码跟随本仓库分发，但它不会持有另一份论文 PDF，也不会依赖 Zotero MCP 私有向量 SQLite 的表结构。两个系统仍然只通过 Zotero MCP 的公开 tool contract 交换论文数据与语义检索结果。

## Vendored MKG

上游：`https://github.com/Seaual/meta-knowledge-graph`

源码目录：

```text
vendor/meta-knowledge-graph/
```

当前 vendoring 是通过 `.github/workflows/vendor-mkg.yml` 在 GitHub 云端完成：

```text
Download upstream main.zip
        ↓
unzip
        ↓
copy to vendor/meta-knowledge-graph
        ↓
commit + push
```

`vendor/meta-knowledge-graph/UPSTREAM_VENDOR_INFO.md` 记录具体上游 commit。上游 `LICENSE` 原样保留。

正常运行不需要再 `git clone` MKG，也不需要 `grz-bootstrap`。

## Current MVP

当前已经实现：

1. Streamable HTTP MCP JSON-RPC client；
2. Zotero metadata + 已解析全文读取；
3. Zotero 内容直接构造成 MKG `PaperContent`，绕过 MKG `PDFParser`；
4. 复用 vendored MKG 的 `LLMConceptExtractor`；
5. 保存 concept、concept hierarchy、paper-concept association；
6. 用 Zotero MCP `find_similar` 构建 `paper_similarity_edges`；
7. `zotero_paper_map` 保存 Zotero itemKey ↔ MKG identifier 和 content hash，实现增量处理；
8. GitHub Actions：install / vendor check / Ruff / pytest / CLI smoke test。

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

因为 MKG 已经在仓库内，安装后无需再下载 MKG。

## Configure

`.env`：

```env
ZOTERO_MCP_URL=http://127.0.0.1:23120/mcp
MKG_DB_PATH=./data/mkg.db

MKG_LLM_PROVIDER=openai
MKG_LLM_API_KEY=
MKG_LLM_MODEL=gpt-5-mini
MKG_LLM_BASE_URL=https://api.openai.com/v1
```

如果 MKG 数据库中已经有 LLM 配置，可不设置 `MKG_LLM_*`。

高级开发场景仍可用 `MKG_SOURCE_PATH` 临时覆盖 vendored MKG 路径，但正常使用不需要设置。

## Quick start

检查 Zotero MCP 和 semantic index：

```bash
grz doctor
```

查看 collections：

```bash
grz collections
```

同步一篇论文并执行 MKG concept extraction：

```bash
grz sync-item <ITEM_KEY> --process
```

同步一个 collection：

```bash
grz sync-collection <COLLECTION_KEY> --process
```

同步整个 library：

```bash
grz sync-library --process --limit 500
```

利用已有 embedding 构建论文相似度边：

```bash
grz build-similarity --top-k 8 --min-score 0.55
```

查看状态：

```bash
grz stats
```

## Incremental behavior

每篇论文完整文本计算 SHA-256：

```text
same itemKey + same content_hash + already processed
    → skip LLM extraction

content changed / first import / --force
    → run MKG LLMConceptExtractor
```

因此日常工作流是：

```text
Save paper to Zotero
        ↓
Zotero MCP indexes full text / embedding
        ↓
grz sync-library --process
        ↓
only new/changed papers run concept extraction
        ↓
grz build-similarity
        ↓
MKG research graph / topic exploration
```

## Integration tables

本项目对 MKG SQLite 增加 additive tables，不修改原有核心表定义：

- `zotero_paper_map`
- `paper_similarity_edges`
- `zotero_sync_runs`

MKG 自己的 `papers`, `concepts`, `concept_relations`, `paper_concepts`, `concept_extractions` 等继续由 MKG repository 管理。

## Verification status

GitHub CI 已验证：

- Python editable install；
- vendored MKG 路径存在；
- Ruff；
- pytest；
- CLI import smoke test。

仍需在实际运行 Zotero MCP 的机器上做 live E2E：

```bash
grz doctor
grz sync-item <ITEM_KEY> --process
grz build-similarity
```

## Planning files

- `task_plan.md` — phases / completion gate
- `findings.md` — architecture findings
- `progress.md` — implementation/testing log

## Upstream

- Zotero MCP fork: https://github.com/Pyrojewel-zard/zotero-mcp
- Meta Knowledge Graph: https://github.com/Seaual/meta-knowledge-graph
- planning-with-files: https://github.com/OthmanAdi/planning-with-files
