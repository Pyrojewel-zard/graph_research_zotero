# Findings — Zotero MCP × Meta Knowledge Graph

## Zotero MCP fork

Repository: `Pyrojewel-zard/zotero-mcp`

Key observations:

1. The plugin already contains a complete semantic-search subsystem and owns `zotero-mcp-vectors.sqlite`.
2. Public MCP tools are sufficient for this integration: `get_item_details`, `get_content`, `get_collections`, `get_collection_items`, `search_library`, `semantic_search`, `find_similar`, `semantic_status`, `fulltext_database`.
3. `get_content(mode=complete, format=text)` lets the graph project consume parsed text without re-opening the PDF.
4. `find_similar` already reuses the plugin's embedding/index implementation, so the graph project never needs to read raw vector BLOBs.
5. Streamable HTTP MCP normally runs at `http://127.0.0.1:23120/mcp`.

## Meta Knowledge Graph

Upstream: `Seaual/meta-knowledge-graph`

Key observations:

1. MKG's normal paper flow is `pdf_path -> PDFParser -> PaperContent -> LLMConceptExtractor`.
2. The clean integration seam is `PaperContent`: Zotero full text can be converted directly to `mkg.pdf_models.PaperContent`, then passed to `LLMConceptExtractor`.
3. MKG already provides repositories/tables for papers, concepts, paper-concept associations, concept relations, and concept extraction records.
4. MKG Stage 1 is optimized for conservative, machine-comparable contribution extraction; Stage 2 builds the `field -> direction -> ... -> method/finding/technique` hierarchy.
5. MKG's research agent already operates at the **graph level** using concept graph/research-point/recommendation tools. A new CLI-agent layer should not duplicate that responsibility.
6. Upstream MKG is not currently packaged as a directly installable Git Python dependency; vendoring avoids the flat-layout packaging failure.

## `ljg-skills` / `ljg-paper`

Repository: `Pyrojewel-zard/ljg-skills` (master branch).

Important observations:

1. `ljg-paper` is not an exhaustive literature-survey or benchmark skill; it is a deep-reading skill for one paper.
2. It focuses on a different question from MKG: what prior understanding/action/evaluation failed, what evidence forced a change, what the paper changed, and where that change stops working.
3. Its hard reading discipline includes:
   - load-bearing concepts must pass distinction / relation / case checks;
   - evidence must distinguish directly measured results, author interpretation, and explanatory inference;
   - the output should form a minimal explanatory model and expose boundary conditions.
4. Its default output is human-readable Markdown. That prose is valuable for the researcher but should **not** be re-parsed by another LLM as the machine data path.
5. Therefore the integration should add a parallel typed `PaperSignature` artifact generated in the same deep-read call.

## Processing-level decision

### ADR-006 — Three processing levels instead of all-papers agent processing

```text
L0 Indexed    -> Zotero metadata/fulltext/existing embeddings
L1 Structured -> MKG concept/citation/similarity graph
L2 Deep Read  -> CLI agent + ljg-paper + PaperSignature + research embedding
```

Only a minority of high-value papers should reach L2. This keeps cost/latency bounded and avoids repeating the same understanding work for the entire Zotero library.

## Deep-read decisions

### ADR-007 — `ljg-paper` complements MKG instead of replacing it

MKG remains the canonical machine-level taxonomy/contribution graph. `ljg-paper` supplies deeper evidence, assumptions, mechanisms, limitations, and boundary-condition analysis for selected papers.

The deep-read signature should enrich the graph with concepts such as:

```text
assumes
fails_when
changes_relation
changes_operation
changes_evaluation
supported_by
limited_by
contrasts_with
open_question
```

These are richer than raw semantic similarity and are useful for later gap/transfer analysis.

### ADR-008 — One agent call yields two artifacts

The runner should return one validated object with:

- `note_markdown`: researcher-facing note;
- `signature`: machine-facing `PaperSignature`.

The application writes files itself. This avoids a fragile `LLM -> prose -> LLM -> JSON` pipeline and avoids depending on the agent's file-editing permissions.

### ADR-009 — Codex/Claude are adapters, not the architecture

Use a small `AgentRunner` interface. Provider-specific subprocess commands stay inside `CodexRunner` and `ClaudeRunner`; deep-read logic depends only on the interface.

Codex currently supports non-interactive `codex exec`; structured output can be constrained with an output schema. Claude Code supports non-interactive print mode (`claude -p`) and JSON output. The implementation still validates the final object itself because CLI output formats and wrappers can evolve.

### ADR-010 — Treat paper text as untrusted data

The prompt must explicitly delimit paper content and say that instructions found inside the paper/full text are data, not agent instructions. This reduces prompt-injection risk when processing arbitrary PDFs.

## Research embedding decisions

### ADR-011 — Do not embed the full paper a second time

The existing Zotero embedding answers roughly: “are these papers textually/semantically similar?”

The second vector space should embed a canonicalized `PaperSignature` answering: “do these papers share problem structure, mechanism, assumptions, evidence pattern, limitations, or transferable research logic?”

This enables useful contrast cases:

- low full-text similarity + high research similarity -> cross-domain transfer candidate;
- high full-text similarity + low research similarity -> same-domain competing route / conceptual divergence.

### ADR-012 — OpenAI-compatible embedding boundary

The first implementation should expose a generic OpenAI-compatible `/embeddings` provider rather than hard-code a single hosted vendor. This makes local servers and other compatible endpoints usable while keeping the storage/query logic stable.

Research embeddings are generated only for L2 papers and are stored separately from Zotero embeddings.

## Vendoring decision

### ADR-005 — Vendor the complete MKG source tree

Ship upstream MKG at `vendor/meta-knowledge-graph/`, preserving upstream license/commit metadata. Runtime loads it directly; `MKG_SOURCE_PATH` remains only a developer override.

### ADR-013 — Vendor only `ljg-paper`, not all `ljg-skills`

For the first deep-read iteration, copy only `skills/ljg-paper` into `.agents/skills/ljg-paper/` and record its upstream commit. Do not integrate `ljg-qa`, `ljg-rank`, `ljg-structure`, etc. until a concrete need appears.

This is the main guardrail against skill-layer overengineering.

## Existing core architecture decisions

### ADR-001 — MCP boundary instead of direct SQLite access

Meta Knowledge Graph integration calls Zotero MCP tools rather than reading `zotero-mcp-vectors.sqlite`.

### ADR-002 — Zotero remains paper source of truth

MKG stores lightweight paper rows and derived knowledge, not another PDF copy. Identifier preference: normalized DOI, else `zotero:<library>:<itemKey>`.

### ADR-003 — Content hash controls incremental extraction

Skip MKG LLM extraction when mapped full-text SHA-256 is unchanged and prior processing succeeded.

### ADR-004 — Existing semantic similarity edges remain auxiliary

Zotero embedding-derived edges stay separate from MKG hierarchical `concept_relations`.

## Open verification items

These require the user's actual machine/environment:

1. Live Zotero MCP payloads and library-scale behavior.
2. Real MKG concept extraction on representative RFIC papers.
3. Installed/authenticated Codex CLI behavior with the user's model/configuration.
4. Installed/authenticated Claude Code CLI behavior with the user's model/configuration.
5. Whether Codex/Claude automatically discover the vendored project skill in the user's CLI versions; prompts should work even if they do not.
6. Real embedding endpoint/model and resulting research-signature vector quality.
7. Empirical comparison of full-text similarity vs research-signature similarity.
8. Automatic L1 -> L2 promotion policy after manual deep-read quality is validated.
