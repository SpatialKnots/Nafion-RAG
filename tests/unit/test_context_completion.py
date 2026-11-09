"""Constructed attachment controls and actual service/native evidence checks."""

from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.generation import context_completion as context
from app.retrieval.search import SearchFilters, SearchResult

QUESTION = "Каковы равновесная степень набухания и энтальпия набухания Li-Nafion?"
TABLE = "Таблица 1. Равновесная степень набухания сухих мембран Li-Nafion αравн (%) и энтальпия ΔH, Дж/г"
METHODS = (
    "ЭКСПЕРИМЕНТАЛЬНАЯ ЧАСТЬ\nОбъекты исследования\n"
    "Объектом исследования являлась коммерческая мембрана Nafion 999. "
    "Замена протона на ион Li+ осуществлялась выдержкой в LiOH. "
    "Поглощение растворителя\nРавновесную степень набухания мембран Li-Nafion "
    "определяли гравиметрическим методом до постоянной массы. "
    "Согласно данным производителя, исходное содержание воды в растворителе 0.07 мас. %. "
    "Специального обезвоживания не проводили."
)


def row(text, **kwargs):
    values = dict(article_id="00000000-0000-0000-0000-000000000001", chunk_id=str(uuid4()),
                  title="Constructed source", doi=None, page_start=3, page_end=4, source_type="pdf_text",
                  text_layer="original", snippet=text, full_text=text, score=0.7, retrieval_method="hybrid")
    return SearchResult(**(values | kwargs))


def run(candidates, selected=None, **kwargs):
    selected = selected or [row(TABLE)]
    with patch.object(context, "load_context_rows", return_value=candidates) as loader:
        result, metadata = context.complete_context(None, QUESTION, "test", SearchFilters(), selected, **kwargs)
    return result, metadata, loader


def test_appends_one_raw_context_without_reordering_or_score_changes():
    table, method = row(TABLE), row(METHODS, page_start=2, page_end=2)
    result, meta, loader = run([method], [table])
    assert result == [table, method] and result[0] is table and result[1] is method
    assert loader.call_count == 1
    assert meta["reason"] == "bounded_methods_context_added"
    support = meta["supports"][0]
    assert method.full_text[support["start"]:support["end"]] == support["text"]
    assert "0.07" in support["text"]
    assert meta["scientific_ownership_verified"] is False and meta["values_propagated"] is False


@pytest.mark.parametrize("text", [
    METHODS.replace("ЭКСПЕРИМЕНТАЛЬНАЯ ЧАСТЬ", "Введение"),
    METHODS.replace("Объекты исследования", "Литература"),
    METHODS.replace("мембрана Nafion 999", "порошок LiCl"),
    METHODS.replace("Замена протона на ион Li+", "Обработка раствора"),
    METHODS.replace("осуществлялась", "не осуществлялась"),
    METHODS.replace("мембран Li-Nafion", "мембран Na-Nafion"),
    METHODS.replace("определяли гравиметрическим", "не определяли гравиметрическим"),
    METHODS.replace("определяли гравиметрическим", "будут определять гравиметрическим"),
    METHODS.replace("исходное содержание воды", "отсутствуют данные о воде"),
    METHODS.replace("до постоянной массы", "для H-Nafion до постоянной массы"),
    METHODS.replace("до постоянной массы", "для PVDF до постоянной массы"),
    "Специального обезвоживания не проводили. " + METHODS.split("Специального")[0],
])
def test_unrelated_negative_future_missing_and_wrong_operation_contexts_refuse(text):
    result, meta, _ = run([row(text, page_start=2, page_end=2)])
    assert len(result) == 1 and meta["reason"] == "methods_not_resolved"


@pytest.mark.parametrize("changes", [
    {"article_id": str(uuid4())}, {"text_layer": "ocr"}, {"source_type": "translated"},
    {"page_start": 0, "page_end": 2}, {"page_start": 3, "page_end": 4},
    {"page_start": 2, "page_end": 1},
])
def test_loader_scope_is_rechecked(changes):
    result, meta, _ = run([replace(row(METHODS, page_start=2, page_end=2), **changes)])
    assert len(result) == 1 and meta["reason"] == "loader_scope_violation"


def test_overlapping_identical_methods_choose_smallest_chunk():
    small = row(METHODS, page_start=2, page_end=2)
    big = row("Introduction. " + METHODS, page_start=1, page_end=2)
    result, meta, _ = run([big, small])
    assert result[-1] is small and len(meta["supports"]) == 1


def test_distinct_methods_are_not_resolved_by_shortest_chunk():
    result, meta, _ = run([row(METHODS, page_start=2, page_end=2),
                           row(METHODS.replace("0.07", "0.09"), page_start=2, page_end=2)])
    assert len(result) == 1 and meta["reason"] == "ambiguous_methods"


def test_overflow_fails_closed():
    result, meta, _ = run([row(METHODS, page_start=2, page_end=2) for _ in range(13)])
    assert len(result) == 1 and meta["reason"] == "candidate_overflow"


def test_existing_methods_need_no_fetch_or_duplicate():
    selected = [row(TABLE), row(METHODS, page_start=2, page_end=2)]
    result, meta, loader = run([], selected)
    assert result is selected and meta["reason"] == "context_already_present"
    loader.assert_not_called()


def test_ambiguous_table_work_needs_no_fetch():
    selected = [row(TABLE), row(TABLE, article_id=str(uuid4()))]
    result, meta, loader = run([], selected)
    assert result is selected and meta["reason"] == "ambiguous_table_scope"
    loader.assert_not_called()


@pytest.mark.parametrize("question,body", [("Что такое Nafion?", TABLE), (QUESTION, "Li-Nafion")])
def test_outside_finite_scope_has_no_io_or_metadata(question, body):
    selected = [row(body)]
    with patch.object(context, "load_context_rows", side_effect=AssertionError("No IO")):
        assert context.complete_context(None, question, "test", SearchFilters(), selected) == (selected, None)


def test_sql_keeps_collection_library_and_all_search_filters():
    statements = []

    class Session:
        def execute(self, statement):
            statements.append(statement)
            return []

    article, library = uuid4(), uuid4()
    filters = SearchFilters.normalize(article_id=article, library_source_id=library, doi="10/test",
        year_from=2001, year_to=2026, journal="Journal", source_type="pdf_text", text_layer="original",
        tag_type="topic", tag_value="membranes")
    context.load_context_rows(Session(), QUESTION, "restricted", filters, row(TABLE, article_id=str(article)))
    sql = str(statements[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    for token in ["restricted", str(article), str(library), "10/test", "2001", "2026", "journal",
                  "pdf_text", "original", "topic", "membranes", "LIMIT 13", "chunks.page_end <= 3"]:
        assert token in sql


def test_raw_hyphenation_is_preserved_in_support():
    text = METHODS.replace("мембран", "мем-\nбран").replace("исходное", "исход\u00adное")
    support = context.methods_support(row(text))[0]
    assert "мем-\nбран" in support["text"] and "исход\u00adное" in support["text"]
    assert text[support["start"]:support["end"]] == support["text"]


def test_soft_hyphen_newline_recognition_is_opt_in_and_raw_addresses_survive():
    from app.generation.fact_types import SourceView
    from app.generation.providers import Evidence

    text = METHODS.replace("мембран", "мем\u00ad\nбран").replace("методом", "ме\u00ad\nтодом")
    text = text.replace("обезвоживания", "обезво\u00ad\nживания")
    support = context.methods_support(row(text))[0]
    assert text[support["start"]:support["end"]] == support["text"]
    source = Evidence("E1", "a", "c", None, None, 1, 1, "test", "ме\u00ad\nтод", 0, "test", {}, {})
    assert SourceView(source).text == "ме тод"
    assert SourceView(source, join_soft_hyphen_lines=True).text == "метод"
