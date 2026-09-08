from graph_research_zotero.zotero_source import ZoteroPaperSource


class FakeClient:
    def __init__(self):
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "get_item_details":
            return {
                "data": {
                    "key": "ITEM1",
                    "title": "A 24 GHz LNA",
                    "creators": [
                        {"firstName": "A", "lastName": "Author", "creatorType": "author"}
                    ],
                    "abstractNote": "An abstract",
                    "DOI": "https://doi.org/10.1109/TEST.2026.1",
                    "date": "2026-01-03",
                    "publicationTitle": "IEEE TMTT",
                    "itemType": "journalArticle",
                    "tags": [{"tag": "LNA"}, {"tag": "RFIC"}],
                }
            }
        if name == "get_content":
            return "This is complete paper text. " * 30
        if name == "get_collection_items":
            return {"data": [{"key": "A"}, {"data": {"key": "B"}}]}
        if name == "search_library":
            return {"items": [{"itemKey": "A"}, {"key": "B"}]}
        if name == "find_similar":
            return {
                "data": [
                    {"itemKey": "B", "score": 0.91},
                    {"key": "C", "similarity": 0.72},
                ]
            }
        if name == "semantic_status":
            return {"ready": True}
        if name == "get_collections":
            return {"data": []}
        raise AssertionError(name)


def test_fetch_builds_normalized_paper():
    source = ZoteroPaperSource(FakeClient(), library_id=1)
    paper = source.fetch("ITEM1")
    assert paper.title == "A 24 GHz LNA"
    assert paper.authors == ["A Author"]
    assert paper.doi == "10.1109/test.2026.1"
    assert paper.year == 2026
    assert paper.venue == "IEEE TMTT"
    assert paper.tags == ["LNA", "RFIC"]
    assert len(paper.full_text) > 200


def test_enumeration_and_similarity():
    source = ZoteroPaperSource(FakeClient(), library_id=1)
    assert source.collection_item_keys("COLL") == ["A", "B"]
    assert source.library_item_keys() == ["A", "B"]
    assert source.similar_items("A") == [("B", 0.91), ("C", 0.72)]
