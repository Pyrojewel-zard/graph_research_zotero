from graph_research_zotero.normalize import (
    extract_item_keys,
    normalize_authors,
    normalize_doi,
    normalize_tags,
    normalize_year,
)


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1109/TMTT.2026.123") == "10.1109/tmtt.2026.123"
    assert normalize_doi("DOI: 10.1234/ABC") == "10.1234/abc"


def test_normalize_authors_supports_zotero_creator_shapes():
    creators = [
        {"firstName": "Ada", "lastName": "Lovelace", "creatorType": "author"},
        {"name": "OpenAI Research", "creatorType": "author"},
    ]
    assert normalize_authors(creators) == ["Ada Lovelace", "OpenAI Research"]


def test_normalize_tags():
    assert normalize_tags([{"tag": "RFIC"}, "LNA", {"tag": ""}]) == ["RFIC", "LNA"]


def test_normalize_year():
    assert normalize_year("2026-09-08") == 2026
    assert normalize_year(None) is None


def test_extract_item_keys_from_nested_payloads():
    payload = {
        "data": {
            "items": [
                {"key": "AAA111"},
                {"data": {"key": "BBB222"}},
                {"itemKey": "AAA111"},
            ]
        }
    }
    assert extract_item_keys(payload) == ["AAA111", "BBB222"]
