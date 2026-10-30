"""Presentation/identity checks; no fabricated scientific acceptance or live calls."""

from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from app.generation.gigachat import GigaChatAnswerProvider
from app.generation.presentation import PRESENTATION_INSTRUCTION, capture_sources
from app.generation.providers import Evidence
from app.retrieval.search import SearchResponse, SearchResult
from app.ui import _answer_payload_panel, _citation_label, _claim_source_fragment, _linked_answer_text


def item():
    return Evidence("E1", "work-a", "chunk-a", "Название работы", None, 96, 97, "main_text",
                    "A long exact source. " * 80 + "αLi = 1.54 after the old display limit.\n<raw>&text",
                    1.0, "exact", {}, {})


def retrieved(e):
    return SearchResult(e.article_id, e.chunk_id, e.title, e.doi, e.page_start, e.page_end, e.source_type,
                        "short excerpt without number", e.score, e.retrieval_method, full_text=e.text, text_layer="original")


def citation(e):
    return {**asdict(e), "text": "short excerpt without number", "pdf_page_url": "/articles/work-a/pdf?layer=original#page=96"}


def payload(e):
    return {"query": "maximum swelling?", "status": "answered", "answer": "αLi = 1.54. [E1]",
            "claims": [{"text": "αLi = 1.54.", "citation_ids": ["E1"]}], "citations": [citation(e)], "metadata": {}}


def test_full_exact_context_survives_excerpt_limit_and_is_escaped_without_mutating_payload():
    e = item()
    sources = capture_sources(SearchResponse("q", [retrieved(e)]), [e])
    data = payload(e)
    previous = deepcopy(data)
    rendered = _answer_payload_panel(data, "q", sources)
    assert "1.54 after the old display limit." in rendered
    assert "&lt;raw&gt;&amp;text" in rendered and "<raw>" not in rendered
    assert "текстовый слой: original" in rendered
    assert "Соответствие утверждению отдельно не подтверждено" in rendered
    assert data == previous and e.text.endswith("\n<raw>&text")


def test_readable_links_in_answer_preserve_original_claim_and_page_target():
    e = item()
    raw = "αLi = 1.54. [E1]"
    rendered = _linked_answer_text(raw, [citation(e)])
    assert ">Название работы — с. 96-97</a>" in rendered
    assert "#page=96" in rendered and "data-citation-id='E1'" in rendered
    assert raw == "αLi = 1.54. [E1]"


@pytest.mark.parametrize("changes", [{"title": None}, {"page_start": None, "page_end": None},
                                    {"page_start": True, "page_end": True}])
def test_unknown_metadata_not_invented(changes):
    label = _citation_label(citation(item()) | changes)
    assert "неизвест" in label


def test_no_trace_is_explicit_and_does_not_invent_the_missing_full_text():
    rendered = _claim_source_fragment(citation(item()), None)
    assert "Полный контекст этого запроса недоступен" in rendered
    assert "short excerpt without number" in rendered
    assert "1.54 after the old display limit" not in rendered


@pytest.mark.parametrize("changes", [{"article_id": "other-work"}, {"chunk_id": "other-chunk"},
                                    {"citation_id": "E2"}, {"page_start": 95}, {"page_end": 98}])
def test_context_from_other_identity_not_attached_to_citation(changes):
    e = item()
    source = capture_sources(SearchResponse("q", [retrieved(e)]), [e])["E1"]
    rendered = _claim_source_fragment(citation(e) | changes, source)
    assert "Полный контекст этого запроса недоступен" in rendered
    assert "1.54 after the old display limit" not in rendered


def test_derived_summary_is_separate_from_original_raw_chunk():
    original = item()
    derived = replace(original, source_type="table_derived", text="System arithmetic: alphaLi > alphaH.")
    sources = capture_sources(SearchResponse("q", [retrieved(original)]), [derived])
    rendered = _claim_source_fragment(citation(derived), sources["E1"])
    assert "Вычисленная табличная сводка системы; это не цитата из PDF" in rendered
    assert "System arithmetic: alphaLi &gt; alphaH." in rendered
    assert "1.54 after the old display limit" in rendered


def test_unbound_generation_text_is_not_called_original_source():
    e = item()
    sources = capture_sources(SearchResponse("q", []), [e])
    rendered = _claim_source_fragment(citation(e), sources["E1"])
    assert "совпадение с исходным фрагментом не установлено" in rendered
    assert "Привязанный исходный фрагмент в трассе отсутствует" in rendered


def test_repeated_citation_in_one_claim_does_not_duplicate_source_context():
    e = item()
    data = payload(e)
    data["claims"][0]["citation_ids"] = ["E1", "E1"]
    rendered = _answer_payload_panel(data, "q", capture_sources(SearchResponse("q", [retrieved(e)]), [e]))
    assert rendered.count("<details class='claim-source'>") == 1


def test_multiple_works_keep_separate_titles_pages_and_text():
    a = item()
    b = replace(a, citation_id="E2", article_id="work-b", chunk_id="chunk-b", title="Вторая работа", page_start=2, page_end=2,
                text="Other source text.")
    data = payload(a)
    data["claims"][0]["citation_ids"] = ["E1", "E2"]
    data["citations"].append(citation(b) | {"pdf_page_url": "/articles/work-b/pdf?layer=original#page=2"})
    rendered = _answer_payload_panel(data, "q", capture_sources(SearchResponse("q", [retrieved(a), retrieved(b)]), [a, b]))
    assert "Вторая работа — с. 2" in rendered and "Название работы — с. 96-97" in rendered
    assert rendered.count("<details class='claim-source'>") == 2 and "Other source text." in rendered


def test_unknown_citation_remains_unlinked_instead_of_inventing_a_reference():
    rendered = _linked_answer_text("Unknown [E9] and <script>.", [citation(item())])
    assert "[E9]" in rendered and "<a " not in rendered and "&lt;script&gt;" in rendered


def test_duplicate_trace_citation_ids_rejected():
    e = item()
    with pytest.raises(ValueError, match="unique"):
        capture_sources(SearchResponse("q", [retrieved(e)]), [e, e])


def test_ui_request_observer_retains_context_only_for_that_request(monkeypatch):
    from app import ui

    e = item()
    calls = 0

    def answer(*args, trace_observer, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            trace_observer(SearchResponse("q", [retrieved(e)]), [e], {})
        return object()

    monkeypatch.setattr(ui, "answer_question", answer)
    monkeypatch.setattr(ui, "answer_response_to_dict", lambda response: payload(e))
    monkeypatch.setattr(ui, "get_settings", lambda: object())
    first = ui._answer_result_fragment(object(), "q", "literature", 5, "hybrid", "claims", "auto")
    second = ui._answer_result_fragment(object(), "q", "literature", 5, "hybrid", "claims", "auto")
    assert "1.54 after the old display limit." in first
    assert "1.54 after the old display limit." not in second
    assert "Полный контекст этого запроса недоступен" in second


@pytest.mark.parametrize("style", ["claims", "mini_review"])
def test_presentation_guidance_preserves_source_and_does_not_generate_or_change_schema(monkeypatch, style):
    from app.generation.gigachat import _Answer
    schema = deepcopy(_Answer.model_json_schema())
    monkeypatch.setattr(GigaChatAnswerProvider, "_post", lambda *a, **k: pytest.fail("No transport allowed"))
    e = item()
    active = GigaChatAnswerProvider(credentials="not-used", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                   timeout_seconds=120, max_tokens=1200)
    prompt = active._user_prompt("question", [e], answer_style=style, answer_language="ru")
    assert PRESENTATION_INSTRUCTION in prompt
    assert "Start with the direct conclusion and its scope" in prompt
    assert "Distinguish experimentally observed values, regression/model-derived parameters" in prompt
    assert "return exactly" in prompt and "claims must be empty" in prompt
    assert "Answer language: Russian." in prompt
    assert _Answer.model_json_schema() == schema
