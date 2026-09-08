from __future__ import annotations

from typing import Any, Iterable

from .mcp_client import ZoteroMCPClient
from .models import ZoteroPaper
from .normalize import (
    extract_item_key,
    extract_item_keys,
    field,
    normalize_authors,
    normalize_doi,
    normalize_tags,
    normalize_year,
    unwrap_singleton,
)


class ZoteroPaperSource:
    """Paper-oriented adapter over the public tools exposed by zotero-mcp."""

    def __init__(self, client: ZoteroMCPClient, library_id: int | None = None) -> None:
        self.client = client
        self.library_id = library_id

    def _with_library(self, args: dict[str, Any]) -> dict[str, Any]:
        if self.library_id is None:
            return args
        return {"libraryID": self.library_id, **args}

    def semantic_status(self) -> dict[str, Any]:
        result = self.client.call_tool("semantic_status", {})
        return result if isinstance(result, dict) else {"raw": result}

    def get_collections(self) -> Any:
        return self.client.call_tool(
            "get_collections",
            self._with_library({"recursive": True, "mode": "complete"}),
        )

    def collection_item_keys(
        self,
        collection_key: str,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[str]:
        result = self.client.call_tool(
            "get_collection_items",
            self._with_library(
                {
                    "collectionKey": collection_key,
                    "mode": "complete",
                    "limit": limit,
                    "offset": offset,
                }
            ),
        )
        return extract_item_keys(result)

    def library_item_keys(self, *, limit: int = 500, offset: int = 0) -> list[str]:
        result = self.client.call_tool(
            "search_library",
            self._with_library(
                {
                    "mode": "complete",
                    "limit": limit,
                    "offset": offset,
                    "includeAttachments": "false",
                }
            ),
        )
        return extract_item_keys(result)

    def fetch(self, item_key: str, *, include_full_text: bool = True) -> ZoteroPaper:
        details_raw = self.client.call_tool(
            "get_item_details",
            self._with_library({"itemKey": item_key, "mode": "complete"}),
        )
        details = unwrap_singleton(details_raw)
        if not isinstance(details, dict):
            raise ValueError(
                f"Unexpected get_item_details response for {item_key}: {type(details).__name__}"
            )

        full_text = ""
        if include_full_text:
            content = self.client.call_tool(
                "get_content",
                self._with_library(
                    {
                        "itemKey": item_key,
                        "mode": "complete",
                        "format": "text",
                        "include": {
                            "pdf": True,
                            "attachments": True,
                            "notes": False,
                            "abstract": False,
                            "webpage": False,
                        },
                        "contentControl": {
                            "preserveOriginal": True,
                            "allowExtended": True,
                            "prioritizeCompleteness": True,
                        },
                    }
                ),
            )
            if isinstance(content, str):
                full_text = content
            elif isinstance(content, dict):
                # Defensive fallback for clients/plugin versions that ignore format=text.
                full_text = str(
                    content.get("content")
                    or content.get("text")
                    or content.get("fullText")
                    or ""
                )
            elif content is not None:
                full_text = str(content)

        creators = field(details, "creators", "authors", default=[])
        date_value = field(details, "date", "published", "publicationDate")
        arxiv_id = str(field(details, "arXiv", "arxiv", "arxivId", default="")).strip()

        title = str(field(details, "title", default=f"Zotero item {item_key}")).strip()
        if not title:
            title = f"Zotero item {item_key}"

        return ZoteroPaper(
            item_key=item_key,
            library_id=self.library_id,
            title=title,
            authors=normalize_authors(creators),
            abstract=str(field(details, "abstractNote", "abstract", default="") or ""),
            full_text=full_text,
            doi=normalize_doi(field(details, "DOI", "doi", default="")),
            arxiv_id=arxiv_id,
            year=normalize_year(date_value),
            venue=field(
                details,
                "publicationTitle",
                "conferenceName",
                "proceedingsTitle",
                "journalAbbreviation",
                "publisher",
            ),
            item_type=field(details, "itemType", "type"),
            tags=normalize_tags(field(details, "tags", default=[])),
            metadata=details,
        )

    def fetch_many(
        self,
        item_keys: Iterable[str],
        *,
        include_full_text: bool = True,
    ) -> Iterable[ZoteroPaper]:
        for item_key in item_keys:
            yield self.fetch(item_key, include_full_text=include_full_text)

    def similar_items(
        self,
        item_key: str,
        *,
        top_k: int = 8,
        min_score: float = 0.55,
    ) -> list[tuple[str, float]]:
        result = self.client.call_tool(
            "find_similar",
            {"itemKey": item_key, "topK": top_k, "minScore": min_score},
        )
        data = result.get("data", []) if isinstance(result, dict) else result
        if not isinstance(data, list):
            return []

        normalized: list[tuple[str, float]] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            target = extract_item_key(row)
            score = row.get("score", row.get("similarity", row.get("maxScore")))
            if not target or target == item_key or score is None:
                continue
            try:
                normalized.append((target, float(score)))
            except (TypeError, ValueError):
                continue
        return normalized
