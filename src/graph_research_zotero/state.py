from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def library_key(library_id: int | None) -> str:
    return str(library_id) if library_id is not None else "user"


@dataclass(frozen=True)
class MappingRecord:
    library_key: str
    item_key: str
    mkg_identifier: str
    content_hash: str | None
    processed_hash: str | None
    status: str
    last_error: str | None


class IntegrationState:
    """Additive tables stored in the same SQLite DB as MKG.

    No upstream MKG table definition is changed.  This makes uninstalling the
    bridge safe and keeps the upstream package upgradeable.
    """

    def __init__(self, db: Any) -> None:
        self.db = db
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS zotero_paper_map (
                library_key TEXT NOT NULL,
                item_key TEXT NOT NULL,
                mkg_identifier TEXT NOT NULL,
                title TEXT,
                content_hash TEXT,
                processed_hash TEXT,
                status TEXT NOT NULL DEFAULT 'synced',
                last_error TEXT,
                metadata_json TEXT,
                synced_at TEXT NOT NULL,
                processed_at TEXT,
                PRIMARY KEY (library_key, item_key),
                UNIQUE (mkg_identifier)
            )
            """
        )
        self.db.execute_write(
            """
            CREATE INDEX IF NOT EXISTS idx_zotero_map_identifier
            ON zotero_paper_map(mkg_identifier)
            """
        )
        self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS paper_similarity_edges (
                library_key TEXT NOT NULL,
                source_item_key TEXT NOT NULL,
                target_item_key TEXT NOT NULL,
                source_mkg_identifier TEXT,
                target_mkg_identifier TEXT,
                score REAL NOT NULL,
                source TEXT NOT NULL DEFAULT 'zotero-mcp:find_similar',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (library_key, source_item_key, target_item_key)
            )
            """
        )
        self.db.execute_write(
            """
            CREATE INDEX IF NOT EXISTS idx_similarity_source_identifier
            ON paper_similarity_edges(source_mkg_identifier)
            """
        )
        self.db.execute_write(
            """
            CREATE INDEX IF NOT EXISTS idx_similarity_target_identifier
            ON paper_similarity_edges(target_mkg_identifier)
            """
        )
        self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS zotero_sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                scope_key TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                total INTEGER DEFAULT 0,
                synced INTEGER DEFAULT 0,
                processed INTEGER DEFAULT 0,
                skipped INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                details_json TEXT
            )
            """
        )

    def get_mapping(self, library_id: int | None, item_key: str) -> MappingRecord | None:
        row = self.db.execute_read(
            """
            SELECT library_key, item_key, mkg_identifier, content_hash,
                   processed_hash, status, last_error
            FROM zotero_paper_map
            WHERE library_key = ? AND item_key = ?
            """,
            (library_key(library_id), item_key),
        ).fetchone()
        if not row:
            return None
        return MappingRecord(
            library_key=row["library_key"],
            item_key=row["item_key"],
            mkg_identifier=row["mkg_identifier"],
            content_hash=row["content_hash"],
            processed_hash=row["processed_hash"],
            status=row["status"],
            last_error=row["last_error"],
        )

    def get_mapping_by_identifier(self, identifier: str) -> MappingRecord | None:
        row = self.db.execute_read(
            """
            SELECT library_key, item_key, mkg_identifier, content_hash,
                   processed_hash, status, last_error
            FROM zotero_paper_map
            WHERE mkg_identifier = ?
            """,
            (identifier,),
        ).fetchone()
        if not row:
            return None
        return MappingRecord(
            library_key=row["library_key"],
            item_key=row["item_key"],
            mkg_identifier=row["mkg_identifier"],
            content_hash=row["content_hash"],
            processed_hash=row["processed_hash"],
            status=row["status"],
            last_error=row["last_error"],
        )

    def upsert_mapping(
        self,
        *,
        library_id: int | None,
        item_key: str,
        mkg_identifier: str,
        title: str,
        content_hash: str,
        metadata: dict[str, Any] | None = None,
        status: str = "synced",
    ) -> None:
        self.db.execute_write(
            """
            INSERT INTO zotero_paper_map (
                library_key, item_key, mkg_identifier, title, content_hash,
                status, last_error, metadata_json, synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
            ON CONFLICT(library_key, item_key) DO UPDATE SET
                mkg_identifier = excluded.mkg_identifier,
                title = excluded.title,
                content_hash = excluded.content_hash,
                status = excluded.status,
                last_error = NULL,
                metadata_json = excluded.metadata_json,
                synced_at = excluded.synced_at
            """,
            (
                library_key(library_id),
                item_key,
                mkg_identifier,
                title,
                content_hash,
                status,
                json.dumps(metadata or {}, ensure_ascii=False),
                utcnow(),
            ),
        )

    def mark_processed(
        self,
        library_id: int | None,
        item_key: str,
        processed_hash: str,
    ) -> None:
        self.db.execute_write(
            """
            UPDATE zotero_paper_map
            SET processed_hash = ?, status = 'processed', last_error = NULL,
                processed_at = ?, synced_at = ?
            WHERE library_key = ? AND item_key = ?
            """,
            (
                processed_hash,
                utcnow(),
                utcnow(),
                library_key(library_id),
                item_key,
            ),
        )

    def mark_error(self, library_id: int | None, item_key: str, error: str) -> None:
        self.db.execute_write(
            """
            UPDATE zotero_paper_map
            SET status = 'failed', last_error = ?, synced_at = ?
            WHERE library_key = ? AND item_key = ?
            """,
            (error[:4000], utcnow(), library_key(library_id), item_key),
        )

    def needs_processing(
        self,
        library_id: int | None,
        item_key: str,
        content_hash: str,
        *,
        force: bool = False,
    ) -> bool:
        if force:
            return True
        mapping = self.get_mapping(library_id, item_key)
        if mapping is None:
            return True
        return not (
            mapping.status == "processed"
            and mapping.processed_hash
            and mapping.processed_hash == content_hash
        )

    def list_mappings(self, library_id: int | None = None) -> list[dict[str, Any]]:
        if library_id is None:
            cursor = self.db.execute_read(
                "SELECT * FROM zotero_paper_map ORDER BY synced_at DESC"
            )
        else:
            cursor = self.db.execute_read(
                "SELECT * FROM zotero_paper_map WHERE library_key = ? ORDER BY synced_at DESC",
                (library_key(library_id),),
            )
        return [dict(row) for row in cursor.fetchall()]

    def upsert_similarity_edge(
        self,
        *,
        library_id: int | None,
        source_item_key: str,
        target_item_key: str,
        score: float,
        source_identifier: str | None,
        target_identifier: str | None,
    ) -> None:
        self.db.execute_write(
            """
            INSERT INTO paper_similarity_edges (
                library_key, source_item_key, target_item_key,
                source_mkg_identifier, target_mkg_identifier,
                score, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'zotero-mcp:find_similar', ?)
            ON CONFLICT(library_key, source_item_key, target_item_key) DO UPDATE SET
                source_mkg_identifier = excluded.source_mkg_identifier,
                target_mkg_identifier = excluded.target_mkg_identifier,
                score = excluded.score,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (
                library_key(library_id),
                source_item_key,
                target_item_key,
                source_identifier,
                target_identifier,
                score,
                utcnow(),
            ),
        )

    def clear_similarity_for_source(self, library_id: int | None, source_item_key: str) -> None:
        self.db.execute_write(
            "DELETE FROM paper_similarity_edges WHERE library_key = ? AND source_item_key = ?",
            (library_key(library_id), source_item_key),
        )

    def stats(self) -> dict[str, int]:
        mapped = self.db.execute_read("SELECT COUNT(*) AS n FROM zotero_paper_map").fetchone()["n"]
        processed = self.db.execute_read(
            "SELECT COUNT(*) AS n FROM zotero_paper_map WHERE status = 'processed'"
        ).fetchone()["n"]
        failed = self.db.execute_read(
            "SELECT COUNT(*) AS n FROM zotero_paper_map WHERE status = 'failed'"
        ).fetchone()["n"]
        edges = self.db.execute_read("SELECT COUNT(*) AS n FROM paper_similarity_edges").fetchone()["n"]
        return {
            "mapped_papers": int(mapped),
            "processed_papers": int(processed),
            "failed_papers": int(failed),
            "similarity_edges": int(edges),
        }
