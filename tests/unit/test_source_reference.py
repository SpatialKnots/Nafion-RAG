"""Synthetic reference resolution and SQL-scope controls, without database I/O."""

from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from app.retrieval import search
from app.retrieval.source_reference import rank_context, reference, resolve


@pytest.mark.parametrize("question", ["Smith (2021)", "Smith и Jones (2021)", "Smith and Jones (2021)",
                                     "Smith et al. (2021)", "Smith и соавторы (2021)"])
def test_parse_and_resolve_registered_reference(question):
    citation = reference(question)
    assert citation.surname == "Smith" and citation.year == "2021"
    assert resolve(citation, {"a": {"title": "Smith 2021", "authors": None, "year": None}}) == ["a"]


def test_ambiguity_and_surname_boundaries():
    citation = reference("Smith (2021)")
    assert resolve(citation, {"a": {"title": "Blacksmith 2021"}}) == []
    assert resolve(citation, {"a": {"title": "Smith 2020"}}) == []
    assert resolve(citation, {"a": {"title": "Smith 2021"}, "b": {"title": "Smith 2021"}}) == ["a", "b"]
    assert reference("Smith (2021), Jones (2020)") is None


def test_inactive_question_does_not_access_session():
    assert search._source_reference_search(None, "Nafion conductivity?", "literature", search.SearchFilters(), 5) == (None, None)


def test_inventory_and_chunk_lookup_preserve_all_sql_filters():
    statements = []
    article_id, library_id = UUID(int=1), UUID(int=9)
    article = SimpleNamespace(id=article_id, title="Smith 2021", authors=None, year=2021, journal="Journal", doi=None)
    chunk = SimpleNamespace(id=UUID(int=2), page_start=2, page_end=3, source_type="body", text_layer="original", text="Raw source.")

    class Session:
        def scalars(self, statement):
            statements.append(statement)
            return SimpleNamespace(unique=lambda: [article])

        def execute(self, statement):
            statements.append(statement)
            return [(chunk, article)]

    filters = search.SearchFilters.normalize(article_id=article_id, library_source_id=library_id, year=2021,
                                              tag_type="keyword", tag_value="synthetic", source_type="body", text_layer="original")
    selected, metadata = search._source_reference_search(Session(), "Smith (2021)", "synthetic_collection", filters, 5)
    assert metadata["resolved"] is True and len(selected) == 1
    assert selected[0].full_text == "Raw source." and selected[0].page_end == 3
    assert len(statements) == 2
    for statement in statements:
        compiled = statement.compile(dialect=postgresql.dialect())
        sql, values = str(compiled), list(compiled.params.values())
        assert "synthetic_collection" in values and library_id in values and article_id in values
        assert 2021 in values and "synthetic" in values and "keyword" in values
        assert "original" in values and "body" in values
        assert "library_source_files" in sql and "article_tags" in sql and "collections.name" in sql


def test_empty_or_ambiguous_work_preserves_baseline(monkeypatch):
    monkeypatch.setattr(search, "_source_reference_inventory", lambda *a: {"a": {"title": "Smith 2021"},
                                                                          "b": {"title": "Smith 2021"}})
    monkeypatch.setattr(search, "_source_reference_chunks", lambda *a: pytest.fail("Ambiguous work must not be loaded"))
    rows, metadata = search._source_reference_search(None, "Smith (2021)", "c", search.SearchFilters(), 5)
    assert rows is None and metadata["reason"] == "ambiguous_metadata"


def test_role_reservation_precedes_first_page_and_respects_small_budget():
    def item(number, body):
        return SimpleNamespace(chunk_id=str(number), article_id="a", full_text=body, snippet=body)
    first = item(0, "Nafion introductory paragraph.")
    method = item(1, "Nafion ethanol-free dispersion: azeotropic distillation.")
    table = item(2, "Table 1. XYZ conductivity for a Nafion sample.")
    question = "How to prepare Nafion dispersion and compare conductivity XYZ?"
    rows, metadata = rank_context(question, [first, method, table], top_k=2)
    assert rows == [method, table] and metadata["missing_roles"] == []
    rows, metadata = rank_context(question, [first, method, table], top_k=1)
    assert len(rows) == 1 and metadata["missing_roles"] == ["conductivity_table"]
