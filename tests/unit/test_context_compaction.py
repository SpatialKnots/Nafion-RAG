"""Synthetic counterexamples; these are not corpus-wide scientific labels."""
from dataclasses import replace

import pytest

from app.evaluation import answer_trace
from app.evaluation.context_compaction import (
    SourcePage,
    compact_source_pages,
    complete_pages_in_request,
    require_no_complete_pages,
)
from app.generation.providers import Evidence


def evidence(text, *, chunk="chunk", citation="E1", first=1, last=1, article="article"):
    return Evidence(citation_id=citation, article_id=article, chunk_id=chunk, title="Synthetic source", doi=None,
                    page_start=first, page_end=last, source_type="body", text=text, score=0.5,
                    retrieval_method="synthetic", method_scores={}, method_ranks={})


def page(text, *, chunk="chunk", number=1, layer="original", article="article"):
    return SourcePage(article, chunk, number, layer, f"layer-{number}-{layer}", text, "/synthetic.pdf", "synthetic-sha256")


def references():
    return "\n".join(f"{i}. Author A. Study of water // Journal. — 2020. — P. 1–5." for i in range(1, 5))


def test_overlap_removed_once_with_exact_coordinates_and_conditions_preserved():
    first = "Conditions: 25 °C, 40 wt% SL.\nTable 1. Conductivity\nEC SL\n60 40\n* measured after 24 h."
    second = "Figure 2. Caption and its uncertainty ±0.5.\n\x01 Damaged formula preserved."
    items = [evidence(first + "\n\n" + second, last=2),
             evidence(second, chunk="next", citation="E2", first=2, last=2)]
    pages = [page("  " + first + "\n"), page(second + "\n", number=2), page(second, chunk="next", number=2)]
    result = compact_source_pages(items, pages)
    assert [item.text for item in result.evidence] == [first, second]
    assert [item.citation_id for item in items] == ["E1", "E2"]
    assert len(result.slices) == 2
    for fragment in result.slices:
        original = next(item for item in items if item.chunk_id == fragment.chunk_id)
        source = next(p for p in pages if p.chunk_id == fragment.chunk_id and p.page == fragment.page)
        emitted = next(item for item in result.evidence if item.citation_id == fragment.citation_id)
        assert emitted.text == original.text[fragment.chunk_start:fragment.chunk_end]
        assert emitted.text == source.text[fragment.page_start:fragment.page_end]
    assert any(d["action"] == "omit_exact_duplicate_page" for d in result.diagnostics)


def test_reference_page_is_proposal_and_source_kept_immutable():
    text = "154\n" + references()
    item = evidence(text)
    result = compact_source_pages([item], [page(text)])
    assert result.evidence == []
    assert result.diagnostics[0]["classification"] == "algorithm_proposal_not_confirmed"
    assert item.text == text


def test_explicit_reference_suffix_retains_body_exactly():
    text = "Measured at 80 °C.\nTable 2. 82.2% mass gain.\nReferences\n" + references()
    result = compact_source_pages([evidence(text)], [page(text)])
    assert result.evidence[0].text == text[:text.index("References")]
    assert result.slices[0].page_end == text.index("References")


@pytest.mark.parametrize("text", [
    "1. Sample A 2020\n2. Sample B 2021\n3. Sample C 2022",
    "Introduction: these are scientific observations.\n" + references(),
    references().replace("2. Author", "7. Author"),
    "In references we discuss results. Table 1: 25 °C.",
    references().replace("3. Author A. Study of water // Journal. — 2020. — P. 1–5.", "3. Numerical result: 2020 mV."),
])
def test_ambiguous_numbered_body_and_tables_are_retained(text):
    result = compact_source_pages([evidence(text)], [page(text)])
    assert [item.text for item in result.evidence] == [text]


@pytest.mark.parametrize("kind", ["missing", "wrong_article", "duplicate_page", "nonwhitespace_gap", "partial", "derived"])
def test_unproven_alignment_is_retained_and_diagnosed(kind):
    item = evidence("Exact source.")
    sources = [page(item.text)]
    if kind == "missing":
        sources = []
    elif kind == "wrong_article":
        sources = [replace(sources[0], article_id="other")]
    elif kind == "duplicate_page":
        sources *= 2
    elif kind == "nonwhitespace_gap":
        sources = [page("source.")]
    elif kind == "partial":
        sources = [page(item.text + " Missing tail.")]
    elif kind == "derived":
        item = replace(item, source_type="table_derived")
    result = compact_source_pages([item], sources)
    assert result.evidence[0].text == item.text and not result.slices
    assert result.diagnostics[0]["action"] == "retain_unaligned_chunk"


@pytest.mark.parametrize("different", ["article", "layer", "layer_id", "pdf_sha256"])
def test_equal_text_different_article_or_layer_is_not_deduplicated(different):
    text = "Same reported measurement."
    other_article = "other" if different == "article" else "article"
    items = [evidence(text), evidence(text, chunk="other", citation="E2", article=other_article)]
    sources = [page(text), page(text, chunk="other", article=other_article, layer="ocr" if different == "layer" else "original")]
    if different == "layer_id":
        sources[1] = replace(sources[1], layer_id="other-layer-id")
    if different == "pdf_sha256":
        sources[1] = replace(sources[1], pdf_sha256="other-pdf-hash")
    result = compact_source_pages(items, sources)
    assert len(result.evidence) == 2 and len(result.slices) == 2


def test_scope_guard_checks_submitted_whitespace_and_empty_registry_fails_closed():
    pages = [page("Measured\n at 25 °C.\n")]
    assert len(complete_pages_in_request("Source: Measured at 25 °C.", pages)) == 1
    with pytest.raises(ValueError, match="complete source pages"):
        require_no_complete_pages("Measured at 25 °C.", pages)
    with pytest.raises(ValueError, match="nonempty verified"):
        require_no_complete_pages("Any request", [])
    require_no_complete_pages("Measured at 25 °C.", [page("Measured at 25 °C. More source context.")])


def test_scope_guard_blocks_provider_before_network_and_attempt_directory(tmp_path, monkeypatch):
    text = "Measured\nat 25 °C."
    monkeypatch.setattr(answer_trace, "send_openai_request", lambda *a: pytest.fail("Full pages must not be sent"))
    provider = answer_trace.TraceResponsesProvider(model="synthetic", api_key="synthetic", output=tmp_path / "attempt",
                                                  source_pages=[page(text)])
    with pytest.raises(ValueError, match="Full-page scope guard blocked"):
        provider.generate("Question", [evidence(text)])
    assert provider.prepared_request is None and not (tmp_path / "attempt").exists()


def test_shorter_exact_slice_can_be_prepared_without_disclosing_registry_paths():
    text = "Measured at 25 °C. Additional exact source context."
    provider = answer_trace.TraceResponsesProvider(model="synthetic", api_key="synthetic", source_pages=[page(text)])
    with pytest.raises(answer_trace.PreparationComplete):
        provider.generate("Question", [evidence(text[:17])])
    assert provider.prepared_request is not None
    assert b"/synthetic.pdf" not in provider.prepared_request


def test_empty_source_page_registry_blocks_before_preparation():
    provider = answer_trace.TraceResponsesProvider(model="synthetic", api_key="synthetic", source_pages=[])
    with pytest.raises(ValueError, match="nonempty verified"):
        provider.generate("Question", [evidence("Exact text.")])
    assert provider.prepared_request is None
