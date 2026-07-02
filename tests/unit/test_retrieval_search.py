from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.retrieval.search import _query_terms, exact_search, make_snippet


class FakeSession:
    def __init__(self, collection: object | None = None) -> None:
        self.collection = collection
        self.rows: list[tuple[object, object, int]] = []

    def scalar(self, statement: object) -> object | None:
        return self.collection

    def execute(self, statement: object) -> object:
        return SimpleNamespace(all=lambda: self.rows)


def test_exact_search_returns_source_linked_chunks() -> None:
    collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
    article = SimpleNamespace(id=uuid.uuid4(), title="Li-Nafion paper", doi="10.1000/example")
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        article_id=article.id,
        page_start=2,
        page_end=3,
        text="Conductivity of Li-Nafion in NMP depends on temperature.",
        chunk_index=0,
    )
    session = FakeSession(collection)
    session.rows = [(chunk, article, 12)]

    response = exact_search(session, "Li-Nafion", "literature", 5)  # type: ignore[arg-type]

    assert response.query == "Li-Nafion"
    assert len(response.results) == 1
    result = response.results[0]
    assert result.article_id == str(article.id)
    assert result.chunk_id == str(chunk.id)
    assert result.page_start == 2
    assert result.page_end == 3
    assert result.retrieval_method == "exact_ilike"
    assert "Li-Nafion" in result.snippet


def test_exact_search_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        exact_search(FakeSession(), "   ")  # type: ignore[arg-type]


def test_exact_search_rejects_unknown_collection() -> None:
    with pytest.raises(ValueError, match="Unknown collection"):
        exact_search(FakeSession(None), "Nafion")  # type: ignore[arg-type]


def test_make_snippet_is_derived_from_chunk_text() -> None:
    snippet = make_snippet("alpha beta gamma Nafion conductivity delta", "Nafion", radius=20)

    assert "Nafion" in snippet
    assert "conductivity" in snippet


def test_make_snippet_supports_russian_query_text() -> None:
    snippet = make_snippet("Мембраны Нафион показывают ионную проводимость после гидратации.", "ионная проводимость", radius=20)

    assert "ионную проводимость" in snippet


def test_make_snippet_falls_back_to_query_terms() -> None:
    snippet = make_snippet(
        "Li-Nafion membranes show conductivity after solvent casting.",
        "Li-Nafion in NMP: conductivity and temperature dependence",
        radius=40,
    )

    assert "Li-Nafion" in snippet
    assert "conductivity" in snippet


def test_query_terms_preserve_scientific_hyphenated_terms() -> None:
    assert _query_terms("Li-Nafion in NMP: conductivity and temperature dependence") == [
        "Li-Nafion",
        "NMP",
        "conductivity",
        "temperature",
        "dependence",
    ]


def test_make_snippet_normalizes_common_pdf_ligatures() -> None:
    snippet = make_snippet("Li-Naﬁon conductivity", "Li-Nafion", radius=20)

    assert "Li-Nafion" in snippet
