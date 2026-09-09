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


@dataclass(frozen=True)
class DeepReadRecord:
    library_key: str
    item_key: str
    mkg_identifier: str
    source_hash: str
    runner: str
    skill_name: str
    skill_revision: str
    status: str
    note_path: str | None
    signature_path: str | None
    signature_hash: str | None
    signature_json: str | None
    last_error: str | None


class IntegrationState:
    """Additive tables stored in the same SQLite DB as MKG.

    No upstream MKG table definition is changed. This keeps Zotero bridge,
    deep-read artifacts and the two embedding spaces independently removable.
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
        self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS paper_deep_reads (
                library_key TEXT NOT NULL,
                item_key TEXT NOT NULL,
                mkg_identifier TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                runner TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                skill_revision TEXT NOT NULL,
                status TEXT NOT NULL,
                note_path TEXT,
                signature_path TEXT,
                signature_hash TEXT,
                signature_json TEXT,
                last_error TEXT,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY (library_key, item_key)
            )
            """
        )
        self.db.execute_write(
            """
            CREATE INDEX IF NOT EXISTS idx_deep_reads_identifier
            ON paper_deep_reads(mkg_identifier)
            """
        )
        self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS research_embeddings (
                mkg_identifier TEXT PRIMARY KEY,
                library_key TEXT NOT NULL,
                item_key TEXT NOT NULL,
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                vector_json TEXT NOT NULL,
                signature_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.db.execute_write(
            """
            CREATE INDEX IF NOT EXISTS idx_research_embeddings_model
            ON research_embeddings(model)
            """
        )
        self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS research_similarity_edges (
                source_mkg_identifier TEXT NOT NULL,
                target_mkg_identifier TEXT NOT NULL,
                score REAL NOT NULL,
                model TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_mkg_identifier, target_mkg_identifier, model)
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

    def get_deep_read(self, library_id: int | None, item_key: str) -> DeepReadRecord | None:
        row = self.db.execute_read(
            """
            SELECT library_key, item_key, mkg_identifier, source_hash, runner,
                   skill_name, skill_revision, status, note_path, signature_path,
                   signature_hash, signature_json, last_error
            FROM paper_deep_reads
            WHERE library_key = ? AND item_key = ?
            """,
            (library_key(library_id), item_key),
        ).fetchone()
        if not row:
            return None
        return DeepReadRecord(**dict(row))

    def start_deep_read(
        self,
        *,
        library_id: int | None,
        item_key: str,
        mkg_identifier: str,
        source_hash: str,
        runner: str,
        skill_name: str,
        skill_revision: str,
    ) -> None:
        self.db.execute_write(
            """
            INSERT INTO paper_deep_reads (
                library_key, item_key, mkg_identifier, source_hash, runner,
                skill_name, skill_revision, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'processing', ?)
            ON CONFLICT(library_key, item_key) DO UPDATE SET
                mkg_identifier = excluded.mkg_identifier,
                source_hash = excluded.source_hash,
                runner = excluded.runner,
                skill_name = excluded.skill_name,
                skill_revision = excluded.skill_revision,
                status = 'processing',
                last_error = NULL,
                updated_at = excluded.updated_at
            """,
            (
                library_key(library_id),
                item_key,
                mkg_identifier,
                source_hash,
                runner,
                skill_name,
                skill_revision,
                utcnow(),
            ),
        )

    def complete_deep_read(
        self,
        *,
        library_id: int | None,
        item_key: str,
        note_path: str,
        signature_path: str,
        signature_hash: str,
        signature: dict[str, Any],
    ) -> None:
        now = utcnow()
        self.db.execute_write(
            """
            UPDATE paper_deep_reads
            SET status = 'completed', note_path = ?, signature_path = ?,
                signature_hash = ?, signature_json = ?, last_error = NULL,
                updated_at = ?, completed_at = ?
            WHERE library_key = ? AND item_key = ?
            """,
            (
                note_path,
                signature_path,
                signature_hash,
                json.dumps(signature, ensure_ascii=False),
                now,
                now,
                library_key(library_id),
                item_key,
            ),
        )

    def fail_deep_read(self, library_id: int | None, item_key: str, error: str) -> None:
        self.db.execute_write(
            """
            UPDATE paper_deep_reads
            SET status = 'failed', last_error = ?, updated_at = ?
            WHERE library_key = ? AND item_key = ?
            """,
            (error[:4000], utcnow(), library_key(library_id), item_key),
        )

    def get_signature(self, identifier: str) -> dict[str, Any] | None:
        row = self.db.execute_read(
            """
            SELECT signature_json FROM paper_deep_reads
            WHERE mkg_identifier = ? AND status = 'completed'
            """,
            (identifier,),
        ).fetchone()
        if not row or not row["signature_json"]:
            return None
        return json.loads(row["signature_json"])

    def upsert_research_embedding(
        self,
        *,
        identifier: str,
        library_id: int | None,
        item_key: str,
        model: str,
        vector: list[float],
        signature_hash: str,
    ) -> None:
        self.db.execute_write(
            """
            INSERT INTO research_embeddings (
                mkg_identifier, library_key, item_key, model, dimensions,
                vector_json, signature_hash, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mkg_identifier) DO UPDATE SET
                library_key = excluded.library_key,
                item_key = excluded.item_key,
                model = excluded.model,
                dimensions = excluded.dimensions,
                vector_json = excluded.vector_json,
                signature_hash = excluded.signature_hash,
                updated_at = excluded.updated_at
            """,
            (
                identifier,
                library_key(library_id),
                item_key,
                model,
                len(vector),
                json.dumps(vector, separators=(",", ":")),
                signature_hash,
                utcnow(),
            ),
        )

    def get_research_embedding(self, identifier: str) -> dict[str, Any] | None:
        row = self.db.execute_read(
            "SELECT * FROM research_embeddings WHERE mkg_identifier = ?",
            (identifier,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["vector"] = [float(value) for value in json.loads(result.pop("vector_json"))]
        return result

    def list_research_embeddings(self, model: str | None = None) -> list[dict[str, Any]]:
        if model:
            cursor = self.db.execute_read(
                "SELECT * FROM research_embeddings WHERE model = ? ORDER BY mkg_identifier",
                (model,),
            )
        else:
            cursor = self.db.execute_read(
                "SELECT * FROM research_embeddings ORDER BY mkg_identifier"
            )
        rows: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            item = dict(row)
            item["vector"] = [float(value) for value in json.loads(item.pop("vector_json"))]
            rows.append(item)
        return rows

    def clear_research_similarity(self, model: str) -> None:
        self.db.execute_write(
            "DELETE FROM research_similarity_edges WHERE model = ?",
            (model,),
        )

    def upsert_research_similarity_edge(
        self,
        *,
        source_identifier: str,
        target_identifier: str,
        score: float,
        model: str,
    ) -> None:
        source, target = sorted((source_identifier, target_identifier))
        self.db.execute_write(
            """
            INSERT INTO research_similarity_edges (
                source_mkg_identifier, target_mkg_identifier, score, model, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_mkg_identifier, target_mkg_identifier, model) DO UPDATE SET
                score = excluded.score,
                updated_at = excluded.updated_at
            """,
            (source, target, score, model, utcnow()),
        )

    def list_research_similarity(self, model: str | None = None) -> list[dict[str, Any]]:
        if model:
            cursor = self.db.execute_read(
                """
                SELECT * FROM research_similarity_edges
                WHERE model = ? ORDER BY score DESC
                """,
                (model,),
            )
        else:
            cursor = self.db.execute_read(
                "SELECT * FROM research_similarity_edges ORDER BY score DESC"
            )
        return [dict(row) for row in cursor.fetchall()]

    def stats(self) -> dict[str, int]:
        mapped = self.db.execute_read("SELECT COUNT(*) AS n FROM zotero_paper_map").fetchone()["n"]
        processed = self.db.execute_read(
            "SELECT COUNT(*) AS n FROM zotero_paper_map WHERE status = 'processed'"
        ).fetchone()["n"]
        failed = self.db.execute_read(
            "SELECT COUNT(*) AS n FROM zotero_paper_map WHERE status = 'failed'"
        ).fetchone()["n"]
        edges = self.db.execute_read("SELECT COUNT(*) AS n FROM paper_similarity_edges").fetchone()["n"]
        deep_reads = self.db.execute_read(
            "SELECT COUNT(*) AS n FROM paper_deep_reads WHERE status = 'completed'"
        ).fetchone()["n"]
        research_embeddings = self.db.execute_read(
            "SELECT COUNT(*) AS n FROM research_embeddings"
        ).fetchone()["n"]
        research_edges = self.db.execute_read(
            "SELECT COUNT(*) AS n FROM research_similarity_edges"
        ).fetchone()["n"]
        return {
            "mapped_papers": int(mapped),
            "processed_papers": int(processed),
            "failed_papers": int(failed),
            "similarity_edges": int(edges),
            "deep_reads": int(deep_reads),
            "research_embeddings": int(research_embeddings),
            "research_similarity_edges": int(research_edges),
        }
