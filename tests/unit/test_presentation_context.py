"""Display excerpts/scope notices do not establish scientific support or change raw."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from app.generation.presentation import capture_sources
from app.generation.presentation_context import display_excerpt, mixture_scope_notes
from app.generation.providers import Evidence
from app.retrieval.search import SearchResponse, SearchResult
from app.ui import _answer_payload_panel

QUESTION = "Li-Nafion conductivity in EC"
CLAIM = r"Проводимость в смеси EC/SL от $6.3 \times 10^{-6}$ до $6.9 \times 10^{-4}$ при $-40^{\circ}C$–$80^{\circ}C$."
QUOTE = ("The best sample was saturated with the EC/SL mixture containing 40 wt.% sulfolane. "
         "Its conductivity from -40 to 80 C varied from 6.3 × 10 −6 to 6.9 × 10 −4 S cm −1.")
SOURCE = "Background on other polymers and unrelated discussion. " * 80 + "\n\n" + QUOTE + "\n\nReferences. " * 30


def test_numerical_quote_after_the_old_prefix_limit_is_an_exact_slice():
    excerpt = display_excerpt(SOURCE, CLAIM, QUESTION)
    assert excerpt.start > 520
    assert "6.3" in excerpt.text and "6.9" in excerpt.text and "EC/SL" in excerpt.text
    assert SOURCE[excerpt.start:excerpt.end] == excerpt.text
    assert len(excerpt.text) <= 1100 and {"6.3", "6.9"} <= set(excerpt.matched_numbers)


def test_same_numbers_for_other_material_do_not_become_semantic_confirmation():
    raw = "An unrelated material measured 1.54."
    excerpt = display_excerpt(raw, "Nafion has 1.54.", "Nafion swelling")
    assert excerpt.text == raw and "1.54" in excerpt.matched_numbers
    assert "support" not in asdict(excerpt)


def test_scope_warning_requires_both_claim_and_cited_context_mixture():
    notes = mixture_scope_notes(QUESTION, CLAIM, QUOTE)
    assert len(notes) == 1 and "смесь EC/SL" in notes[0] and "чистого EC" in notes[0]
    assert not mixture_scope_notes(QUESTION, CLAIM, "EC has a conductivity of1.2. SL is used elsewhere.")
    assert not mixture_scope_notes(QUESTION, "EC conductivity is1.2.", QUOTE)


@pytest.mark.parametrize("question", ["Li-Nafion conductivity in EC/SL", "Проводимость в смеси EC", "EC SL conductivity"])
def test_explicit_mixture_or_both_components_does_not_trigger_pure_solvent_notice(question):
    assert not mixture_scope_notes(question, CLAIM, QUOTE)


def test_unknown_pairs_do_not_invent_chemical_identity_or_scope():
    assert not mixture_scope_notes("ABC conductivity", "ABC/DEF mixture", "ABC/DEF mixture")


def example():
    evidence = Evidence("E1", "work", "chunk", "Registered source", None, 12, 13, "table", SOURCE, 1.0, "offline", {}, {})
    row = SearchResult(evidence.article_id, evidence.chunk_id, evidence.title, None, 12, 13, "table", "old prefix", 1, "offline",
                       full_text=SOURCE, text_layer="original")
    sources = capture_sources(SearchResponse(QUESTION, [row]), [evidence])
    data = {"query": QUESTION, "status": "answered", "answer": CLAIM + " [E1]", "metadata": {},
            "claims": [{"text": CLAIM, "citation_ids": ["E1"]}],
            "citations": [{**asdict(evidence), "text": "old unrelated prefix", "pdf_page_url": "/articles/work/pdf#page=12"}]}
    return data, sources


def test_ui_shows_readable_formula_relevant_quote_scope_and_original_without_mutation():
    data, sources = example()
    before = deepcopy(data)
    rendered = _answer_payload_panel(data, QUESTION, sources)
    assert "6.3 × 10<sup>-6</sup>" in rendered
    assert QUOTE in rendered and "Границы ответа" in rendered and "чистого EC" in rendered
    assert "Текст ответа до оформления" in rendered and r"\times" in rendered
    assert "Научная корректность и полнота не установлены" in rendered
    assert "Фрагмент по совпадению чисел и терминов" in rendered
    assert data == before


def test_wrong_request_source_is_not_used_for_excerpt_or_warning():
    data, sources = example()
    data["citations"][0]["article_id"] = "other-work"
    rendered = _answer_payload_panel(data, QUESTION, sources)
    assert "Границы ответа" not in rendered and QUOTE not in rendered
    assert "Полный контекст этого запроса недоступен" in rendered


def test_real_sanginov_page_quote_selected_without_a_new_model_call():
    path = Path("output/current_answer_screenshot_20261116/aec95165-f993-4576-9dba-0ec4bb8ecee1_pdf12.txt")
    if not path.exists():
        pytest.skip("Optional inspected local PDF excerpt is unavailable")
    raw = path.read_text(encoding="utf-8")
    excerpt = display_excerpt(raw, CLAIM, QUESTION)
    assert raw[excerpt.start:excerpt.end] == excerpt.text
    assert all(value in excerpt.text for value in ["6.3", "6.9", "EC/SL", "40 wt.%"])
    assert mixture_scope_notes(QUESTION, CLAIM, raw)
