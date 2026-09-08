import sqlite3

from graph_research_zotero.state import IntegrationState


class SQLiteDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def execute_write(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        self.conn.commit()
        return cur

    def execute_read(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        return cur


def test_mapping_and_incremental_processing_gate():
    state = IntegrationState(SQLiteDB())

    state.upsert_mapping(
        library_id=1,
        item_key="A",
        mkg_identifier="10.1000/a",
        title="Paper A",
        content_hash="hash-a",
    )
    assert state.needs_processing(1, "A", "hash-a") is True

    state.mark_processed(1, "A", "hash-a")
    assert state.needs_processing(1, "A", "hash-a") is False
    assert state.needs_processing(1, "A", "hash-b") is True
    assert state.needs_processing(1, "A", "hash-a", force=True) is True


def test_similarity_edges_are_idempotent():
    state = IntegrationState(SQLiteDB())
    state.upsert_similarity_edge(
        library_id=1,
        source_item_key="A",
        target_item_key="B",
        source_identifier="paper-a",
        target_identifier="paper-b",
        score=0.8,
    )
    state.upsert_similarity_edge(
        library_id=1,
        source_item_key="A",
        target_item_key="B",
        source_identifier="paper-a",
        target_identifier="paper-b",
        score=0.9,
    )
    assert state.stats()["similarity_edges"] == 1
