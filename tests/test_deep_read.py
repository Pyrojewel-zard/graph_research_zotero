import json
import sqlite3
from types import SimpleNamespace

from graph_research_zotero.deep_read import DeepReadService
from graph_research_zotero.models import ZoteroPaper
from graph_research_zotero.skill_loader import SkillBundle
from graph_research_zotero.state import IntegrationState


class FakePapers:
    def get(self, identifier):
        return {"title": identifier, "status": "processed", "contributions": ["graph transfer"]}


class FakeDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.papers = FakePapers()

    def execute_write(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        self.conn.commit()
        return cur

    def execute_read(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        return cur


class FakeSource:
    library_id = 1

    def __init__(self, paper):
        self.paper = paper

    def fetch(self, item_key, include_full_text=True):
        assert item_key == self.paper.item_key
        assert include_full_text is True
        return self.paper


class FakeBridge:
    def __init__(self):
        self.db = FakeDB()
        self.state = IntegrationState(self.db)

    def sync_paper(self, paper, process=False, force=False):
        assert process is False
        self.state.upsert_mapping(
            library_id=paper.library_id,
            item_key=paper.item_key,
            mkg_identifier=paper.mkg_identifier,
            title=paper.title,
            content_hash=paper.content_hash,
        )
        return SimpleNamespace(identifier=paper.mkg_identifier)


class FakeRunner:
    name = "fake"

    def available(self):
        return True

    def run(self, prompt, *, output_schema=None, cwd=None):
        assert "trusted skill" in prompt
        assert "paper_data_json" in prompt
        assert output_schema["type"] == "object"
        payload = {
            "note_markdown": "# Deep note\n\nThe old assumption fails, then the graph representation fixes it.",
            "signature": {
                "paper_id": "will-be-normalized",
                "title": "will-be-normalized",
                "research_problem": "Transfer circuit optimization across topologies.",
                "prior_assumption": "A fixed-size vector represents every topology.",
                "prior_failure": "Topology changes break that representation.",
                "main_contribution": "Use graph structure for transferable prediction.",
                "change_type": "relation",
                "change_description": "Connectivity becomes part of the representation.",
                "mechanism_steps": ["encode netlist", "message passing", "predict metrics"],
                "evidence": [
                    {
                        "claim": "Transfer works on held-out structures.",
                        "evidence": "Held-out topology experiment.",
                        "strength": "direct",
                        "locator": "Table 2",
                    }
                ],
                "limitations": ["No post-layout validation."],
                "boundary_conditions": ["One technology node."],
                "load_bearing_concepts": [
                    {
                        "concept": "topology graph",
                        "distinguishes": "connectivity from flat vectors",
                        "depends_on": ["netlist"],
                        "affects": ["transferability"],
                        "example": "Different LNA stages produce different graphs.",
                        "boundary": "Encoding must preserve relevant device relations.",
                    }
                ],
                "open_questions": ["Does it transfer after layout?"],
                "transfer_candidates": ["layout-aware optimization"],
                "confidence": 0.9,
            },
        }
        return json.dumps(payload)


class FakeEmbeddingProvider:
    model = "fake-research-embed"

    def embed(self, text):
        assert "No post-layout validation" in text
        return [1.0, 0.5, 0.25]


def test_deep_read_persists_note_signature_and_embedding(tmp_path):
    paper = ZoteroPaper(
        item_key="ITEM1",
        library_id=1,
        title="Graph Transfer for RF Circuits",
        authors=["A. Author"],
        abstract="A test abstract.",
        full_text="paper body " * 100,
        doi="10.1000/test",
    )
    source = FakeSource(paper)
    bridge = FakeBridge()
    settings = SimpleNamespace(deep_read_dir=tmp_path)
    skill = SkillBundle(name="ljg-paper", revision="skill-rev", text="trusted skill", root=tmp_path)
    service = DeepReadService(
        settings,
        source,
        bridge,
        FakeRunner(),
        embedding_provider=FakeEmbeddingProvider(),
        skill=skill,
    )

    result = service.deep_read("ITEM1", embed=True)
    assert result.status == "completed"
    assert result.embedded is True
    assert result.note_path and result.signature_path

    note = (tmp_path / "1" / "ITEM1" / "note.md").read_text(encoding="utf-8")
    signature = json.loads(
        (tmp_path / "1" / "ITEM1" / "signature.json").read_text(encoding="utf-8")
    )
    assert "# Deep note" in note
    assert signature["paper_id"] == "10.1000/test"
    assert signature["title"] == paper.title

    stored = bridge.state.get_research_embedding("10.1000/test")
    assert stored["model"] == "fake-research-embed"
    assert stored["vector"] == [1.0, 0.5, 0.25]
    assert bridge.state.stats()["deep_reads"] == 1
    assert bridge.state.stats()["research_embeddings"] == 1

    unchanged = service.deep_read("ITEM1", embed=True)
    assert unchanged.status == "unchanged"
    assert unchanged.embedded is False


def test_research_similarity_uses_signature_vectors(tmp_path):
    paper = ZoteroPaper(
        item_key="ITEM1",
        library_id=1,
        title="Paper",
        authors=[],
        abstract="",
        full_text="paper body " * 100,
        doi="10.1000/a",
    )
    bridge = FakeBridge()
    source = FakeSource(paper)
    settings = SimpleNamespace(deep_read_dir=tmp_path)
    skill = SkillBundle(name="ljg-paper", revision="skill-rev", text="trusted skill", root=tmp_path)
    service = DeepReadService(settings, source, bridge, FakeRunner(), skill=skill)

    bridge.state.upsert_research_embedding(
        identifier="paper-a",
        library_id=1,
        item_key="A",
        model="m",
        vector=[1.0, 0.0],
        signature_hash="a",
    )
    bridge.state.upsert_research_embedding(
        identifier="paper-b",
        library_id=1,
        item_key="B",
        model="m",
        vector=[0.9, 0.1],
        signature_hash="b",
    )
    bridge.state.upsert_research_embedding(
        identifier="paper-c",
        library_id=1,
        item_key="C",
        model="m",
        vector=[0.0, 1.0],
        signature_hash="c",
    )

    result = service.build_research_similarity(model="m", top_k=1, min_score=0.5)
    assert result["papers"] == 3
    assert result["edges"] == 1
    edges = bridge.state.list_research_similarity("m")
    assert edges[0]["source_mkg_identifier"] == "paper-a"
    assert edges[0]["target_mkg_identifier"] == "paper-b"
