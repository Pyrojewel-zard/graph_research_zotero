from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from mkg.concept_extractor import LLMConceptExtractor
from mkg.database import Database
from mkg.llm import get_llm, init_llm, init_llm_from_db
from mkg.pdf_models import PaperContent

from .concept_store import ConceptTreeStore
from .config import Settings
from .models import ZoteroPaper
from .state import IntegrationState
from .zotero_source import ZoteroPaperSource


@dataclass(frozen=True)
class SyncResult:
    item_key: str
    identifier: str
    status: str
    processed: bool = False
    skipped: bool = False
    concepts_count: int = 0
    error: str | None = None


class MKGBridge:
    def __init__(self, settings: Settings, source: ZoteroPaperSource) -> None:
        self.settings = settings
        self.source = source
        self.db = Database(str(settings.mkg_db_path))
        self.db.connect()
        self.state = IntegrationState(self.db)
        self.concepts = ConceptTreeStore(self.db)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> MKGBridge:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _ensure_llm(self) -> None:
        if get_llm() is not None:
            return
        configured = init_llm_from_db(self.db)
        if configured is not None:
            return
        if not self.settings.llm_api_key:
            raise RuntimeError(
                "MKG LLM is not configured. Configure it in the MKG database or set MKG_LLM_API_KEY."
            )
        init_llm(
            provider=self.settings.llm_provider,
            api_key=self.settings.llm_api_key,
            model=self.settings.llm_model,
            base_url=self.settings.llm_base_url,
        )

    def _existing_concepts_context(self, limit: int = 250) -> str:
        rows = self.db.concepts.get_all()[:limit]
        if not rows:
            return ""
        lines: list[str] = []
        for row in rows:
            text = row.get("text") or ""
            text_en = row.get("text_en") or ""
            category = row.get("category") or "unknown"
            count = row.get("paper_count") or 0
            if text_en and text_en != text:
                label = f"{text_en} / {text}"
            else:
                label = str(text or text_en)
            if label:
                lines.append(f"- [{category}] {label} (papers={count})")
        return "\n".join(lines)

    @staticmethod
    def _to_paper_content(paper: ZoteroPaper) -> PaperContent:
        return PaperContent(
            title=paper.title,
            authors=paper.authors,
            abstract=paper.abstract,
            full_text=paper.full_text,
            sections={},
            metadata={
                "source": "zotero-mcp",
                "zotero_item_key": paper.item_key,
                "zotero_library_id": paper.library_id,
                "venue": paper.venue,
                "year": paper.year,
                "item_type": paper.item_type,
                "tags": paper.tags,
            },
            doi=paper.doi,
            arxiv_id=paper.arxiv_id,
        )

    def _upsert_mkg_paper(self, paper: ZoteroPaper, identifier: str) -> None:
        existing = self.db.papers.get(identifier)
        metadata = {
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors,
            "venue": paper.venue,
            "year": paper.year,
        }
        if existing:
            self.db.papers.update_metadata(identifier, metadata)
            return

        self.db.papers.add(
            {
                "doi": identifier,
                "arxiv_id": paper.arxiv_id or None,
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": paper.authors,
                "venue": paper.venue,
                "year": paper.year,
                "pdf_path": None,
            }
        )

    def sync_paper(
        self,
        paper: ZoteroPaper,
        *,
        process: bool = False,
        force: bool = False,
    ) -> SyncResult:
        existing_map = self.state.get_mapping(paper.library_id, paper.item_key)
        identifier = existing_map.mkg_identifier if existing_map else paper.mkg_identifier
        current_hash = paper.content_hash
        previous_status = existing_map.status if existing_map else "synced"

        self._upsert_mkg_paper(paper, identifier)
        self.state.upsert_mapping(
            library_id=paper.library_id,
            item_key=paper.item_key,
            mkg_identifier=identifier,
            title=paper.title,
            content_hash=current_hash,
            metadata={
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
                "year": paper.year,
                "venue": paper.venue,
                "item_type": paper.item_type,
                "tags": paper.tags,
            },
            status=previous_status,
        )

        if not process:
            return SyncResult(paper.item_key, identifier, "synced")

        needs_processing = force or not (
            existing_map
            and existing_map.status == "processed"
            and existing_map.processed_hash == current_hash
        )
        if not needs_processing:
            return SyncResult(
                paper.item_key,
                identifier,
                "unchanged",
                skipped=True,
            )

        if len(paper.full_text.strip()) < 200:
            message = "Zotero MCP returned no usable full text; refusing to run concept extraction."
            self.db.papers.update_status(identifier, "failed", message)
            self.state.mark_error(paper.library_id, paper.item_key, message)
            return SyncResult(
                paper.item_key,
                identifier,
                "failed",
                error=message,
            )

        try:
            self._ensure_llm()
            self.db.papers.update_status(identifier, "processing")

            paper_content = self._to_paper_content(paper)
            extractor = LLMConceptExtractor()
            extracted = extractor.extract(
                paper_content,
                existing_concepts=self._existing_concepts_context(),
            )
            hierarchy = extracted.concept_tree.to_dict() if extracted.concept_tree else None

            self.concepts.replace_paper_associations(identifier)
            concepts_count = self.concepts.save(
                identifier,
                hierarchy,
                raw_response=extracted.raw_response or "",
            )
            self.db.papers.update_metadata(
                identifier,
                {
                    "keywords": paper.tags,
                    "contributions": extracted.contributions,
                },
            )
            self.db.papers.update_status(identifier, "processed")
            self.state.mark_processed(paper.library_id, paper.item_key, current_hash)

            return SyncResult(
                paper.item_key,
                identifier,
                "processed",
                processed=True,
                concepts_count=concepts_count,
            )
        except Exception as exc:
            message = str(exc)
            self.db.papers.update_status(identifier, "failed", message)
            self.state.mark_error(paper.library_id, paper.item_key, message)
            return SyncResult(
                paper.item_key,
                identifier,
                "failed",
                error=message,
            )

    def sync_item(
        self,
        item_key: str,
        *,
        process: bool = False,
        force: bool = False,
    ) -> SyncResult:
        paper = self.source.fetch(item_key, include_full_text=process)
        return self.sync_paper(paper, process=process, force=force)

    def sync_items(
        self,
        item_keys: Iterable[str],
        *,
        process: bool = False,
        force: bool = False,
    ) -> list[SyncResult]:
        return [
            self.sync_item(item_key, process=process, force=force)
            for item_key in item_keys
        ]

    def build_similarity(
        self,
        *,
        top_k: int = 8,
        min_score: float = 0.55,
    ) -> dict[str, int]:
        mappings = self.state.list_mappings(self.source.library_id)
        by_item = {row["item_key"]: row["mkg_identifier"] for row in mappings}
        edge_count = 0
        sources = 0

        for row in mappings:
            source_key = row["item_key"]
            source_identifier = row["mkg_identifier"]
            self.state.clear_similarity_for_source(self.source.library_id, source_key)
            similar = self.source.similar_items(
                source_key,
                top_k=top_k,
                min_score=min_score,
            )
            sources += 1
            for target_key, score in similar:
                self.state.upsert_similarity_edge(
                    library_id=self.source.library_id,
                    source_item_key=source_key,
                    target_item_key=target_key,
                    source_identifier=source_identifier,
                    target_identifier=by_item.get(target_key),
                    score=score,
                )
                edge_count += 1

        return {"sources": sources, "edges": edge_count}

    def stats(self) -> dict[str, Any]:
        result: dict[str, Any] = self.state.stats()
        result["mkg_papers"] = len(self.db.papers.get_all())
        result["mkg_concepts"] = self.db.concepts.get_count()
        return result
