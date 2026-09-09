import pytest

from graph_research_zotero.research_embedding import cosine_similarity


def test_cosine_similarity_basic_cases():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_requires_matching_dimensions():
    with pytest.raises(ValueError):
        cosine_similarity([1.0], [1.0, 2.0])
