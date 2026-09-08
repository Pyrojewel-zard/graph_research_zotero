from graph_research_zotero.models import ZoteroPaper


def make_paper(**overrides):
    data = {
        "item_key": "ABC123",
        "library_id": 1,
        "title": "Example",
        "authors": ["A. Author"],
        "abstract": "abstract",
        "full_text": "full text",
    }
    data.update(overrides)
    return ZoteroPaper(**data)


def test_identifier_prefers_doi():
    paper = make_paper(doi="10.1000/example", arxiv_id="2601.00001")
    assert paper.mkg_identifier == "10.1000/example"


def test_identifier_falls_back_to_arxiv():
    paper = make_paper(arxiv_id="2601.00001")
    assert paper.mkg_identifier == "arxiv:2601.00001"


def test_identifier_falls_back_to_zotero_key():
    paper = make_paper(library_id=None)
    assert paper.mkg_identifier == "zotero:user:ABC123"


def test_content_hash_changes_with_text():
    assert make_paper(full_text="a").content_hash != make_paper(full_text="b").content_hash
