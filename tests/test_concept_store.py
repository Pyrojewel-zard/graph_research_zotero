from mkg.database import Database

from graph_research_zotero.concept_store import ConceptTreeStore


def test_concept_store_writes_paper_links_and_relations(tmp_path):
    db = Database(str(tmp_path / "mkg.db"))
    db.connect()
    try:
        db.papers.add(
            {
                "doi": "zotero:user:ITEM1",
                "title": "Test paper",
                "abstract": "",
                "authors": [],
            }
        )
        store = ConceptTreeStore(db)
        hierarchy = {
            "id": "radio-frequency-integrated-circuits",
            "concept": "射频集成电路",
            "concept_en": "Radio Frequency Integrated Circuits",
            "category": "field",
            "confidence": 0.99,
            "is_anchor": True,
            "children": [
                {
                    "id": "low-noise-amplifier",
                    "concept": "低噪声放大器",
                    "concept_en": "Low Noise Amplifier",
                    "category": "direction",
                    "confidence": 0.95,
                    "is_anchor": True,
                    "children": [],
                }
            ],
        }

        count = store.save("zotero:user:ITEM1", hierarchy)
        assert count == 2
        assert db.execute_read("SELECT COUNT(*) AS n FROM paper_concepts").fetchone()["n"] == 2
        assert db.execute_read("SELECT COUNT(*) AS n FROM concept_relations").fetchone()["n"] == 1
        assert db.concepts.get_extraction("zotero:user:ITEM1") is not None
    finally:
        db.close()
