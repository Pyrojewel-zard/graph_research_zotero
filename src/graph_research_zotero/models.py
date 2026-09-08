from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ZoteroPaper:
    item_key: str
    library_id: int | None
    title: str
    authors: list[str]
    abstract: str
    full_text: str
    doi: str = ""
    arxiv_id: str = ""
    year: int | None = None
    venue: str | None = None
    item_type: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.full_text.encode("utf-8", errors="ignore")).hexdigest()

    @property
    def mkg_identifier(self) -> str:
        if self.doi:
            return self.doi
        if self.arxiv_id:
            return f"arxiv:{self.arxiv_id}"
        library = self.library_id if self.library_id is not None else "user"
        return f"zotero:{library}:{self.item_key}"
