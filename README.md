# graph_research_zotero

将现有的 **Zotero MCP 文献库** 与 **Meta Knowledge Graph (MKG)** 联合起来：

- Zotero / `Pyrojewel-zard/zotero-mcp` 继续作为唯一文献数据源；
- 复用 Zotero MCP 已经完成的 PDF 全文提取与 embedding；
- 不重新上传 PDF，不重新做 embedding，不直接读取 `zotero-mcp-vectors.sqlite`；
- Meta Knowledge Graph 继续负责 LLM concept extraction、concept hierarchy、dedup、graph 与 research-point discovery；
- 通过 MCP 的 `find_similar` 把已有 embedding 变成论文之间的 semantic-similarity edges。

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
  └─ SyncState / semantic edges
       │
       ▼
Seaual/meta-knowledge-graph
  │
  ├─ PaperContent
  ├─ LLMConceptExtractor
  ├─ ConceptRepository
  ├─ citation graph / Neo4j (optional)
  └─ Research Agent / Research Point Discovery
```

### Design rule

**Zotero owns papers; MKG owns derived knowledge.**

MKG 中不保存另一份 PDF，也不访问 Zotero MCP 私有的向量数据库格式。两者只通过稳定的 MCP tool contract 连接，避免以后 Zotero 插件升级或向量存储格式改变时把 MKG 一起改坏。

## Current MVP

当前代码实现：

1. Python Streamable-HTTP MCP client；
2. 从 Zotero 获取 item metadata + 已解析全文；
3. 将 Zotero 内容直接构造成 MKG `PaperContent`，绕过 MKG 的 `PDFParser`；
4. 复用 MKG `LLMConceptExtractor`；
5. 将概念、层级关系、paper-concept association 写入 MKG 数据库；
6. 用 Zotero MCP `find_similar` 构建 `paper_similarity_edges`；
7. 用 `zotero_paper_map` 保存 Zotero itemKey ↔ MKG paper DOI 映射和 content hash，实现增量处理。

## Prerequisites

- Zotero 7
- 已安装并运行 `Pyrojewel-zard/zotero-mcp`
- Zotero MCP Streamable HTTP server 已启用（默认 `http://127.0.0.1:23120/mcp`）
- Zotero MCP semantic index 已完成
- Python 3.11+
- 一个可用的 OpenAI-compatible 或 Anthropic-compatible LLM API，供 MKG concept extraction 使用

## Install

```bash
git clone https://github.com/Pyrojewel-zard/graph_research_zotero.git
cd graph_research_zotero
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
cp .env.example .env
```

`pyproject.toml` 会直接从 GitHub 安装 `Seaual/meta-knowledge-graph`，因此本项目不复制上游 MKG 源码。

## Configure

`.env`：

```env
ZOTERO_MCP_URL=http://127.0.0.1:23120/mcp
MKG_DB_PATH=./data/mkg.db

# 如果 MKG DB 内没有配置 LLM，则使用下面这一组
MKG_LLM_PROVIDER=openai
MKG_LLM_API_KEY=
MKG_LLM_MODEL=gpt-5-mini
MKG_LLM_BASE_URL=https://api.openai.com/v1
```

如果你已经通过 MKG 自己的设置页面写入了 LLM 配置，可以不设置 `MKG_LLM_*`。

## Quick start

先检查 Zotero MCP 与 semantic index：

```bash
grz doctor
```

查看 Zotero collections：

```bash
grz collections
```

同步一个 collection 的元数据，不做 LLM extraction：

```bash
grz sync-collection <COLLECTION_KEY>
```

同步并构建 MKG concepts：

```bash
grz sync-collection <COLLECTION_KEY> --process
```

同步整个 Zotero library：

```bash
grz sync-library --process --limit 500
```

仅处理单篇论文：

```bash
grz sync-item <ITEM_KEY> --process
```

利用 Zotero 已有 embedding 构建论文相似度边：

```bash
grz build-similarity --top-k 8 --min-score 0.55
```

查看状态：

```bash
grz stats
```

## Incremental behavior

每次 `--process` 时会计算 Zotero 完整文本的 SHA-256：

```text
same itemKey + same content_hash + already processed
    → skip LLM extraction

content changed / first import / --force
    → run MKG LLMConceptExtractor
```

因此日常工作流可以是：

```text
Save paper to Zotero
        ↓
Zotero MCP automatically indexes it
        ↓
grz sync-library --process
        ↓
only new/changed papers are extracted
        ↓
grz build-similarity
        ↓
MKG graph / research discovery
```

## Data added to MKG SQLite

本项目只额外建立三个 additive tables，不修改上游 MKG 表定义：

- `zotero_paper_map` — Zotero itemKey ↔ MKG paper DOI + content hash
- `paper_similarity_edges` — 复用 Zotero embeddings 得到的 paper-to-paper similarity
- `zotero_sync_runs` — 同步记录

MKG 自己的 `papers`, `concepts`, `concept_relations`, `paper_concepts`, `concept_extractions` 等表仍由 MKG 原生 repository 管理。

## Important limitations of this first version

- 已完成代码级适配，但尚未在你的实际 Zotero 23120 服务上做端到端运行测试；见 `task_plan.md` Phase 3。
- `find_similar` 的返回结构在插件升级后若变化，只需要改 `ZoteroPaperSource.similar_items()` 的 normalization，不需要改 MKG。
- 当前 similarity edge 是辅助边，不替代 MKG concept graph。
- citation graph 仍沿用 MKG / Semantic Scholar；下一阶段可用 Zotero DOI 作为优先 identifier 做增量 citation enrichment。

## Planning files

本仓库按 `OthmanAdi/planning-with-files` 的三文件模式维护：

- `task_plan.md` — phases / completion gate
- `findings.md` — 架构调查与技术结论
- `progress.md` — 实际执行与测试日志

后续让 Codex / Claude Code / OpenCode 接着做时，优先让它读取这三个文件。

## Upstream

- Zotero MCP fork: https://github.com/Pyrojewel-zard/zotero-mcp
- Meta Knowledge Graph: https://github.com/Seaual/meta-knowledge-graph
- planning-with-files: https://github.com/OthmanAdi/planning-with-files
