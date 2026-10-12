import json
from pathlib import Path

import pytest

from app.retrieval.search import SearchResponse, SearchResult
from scripts.tac_experiment import (
    abstract_layout_end,
    digest,
    dissertation_title,
    heading_spans,
    implicit_russian_abstract,
    lexical_score,
    span,
    staged_replay,
    unlabelled_abstract,
    validate_snapshot,
    write_new,
)


def page(text: str, number: int = 1, **extra):
    return {"page": number, "text": text, "text_sha256": digest(text.encode()), "layer": "original", "layer_id": "synthetic-layer", **extra}


def test_inline_abstract_keeps_exact_unicode_and_excludes_introduction():
    text = "Abstract: Li-Naﬁon at 20 °C.\n1. Introduction\nUnrelated body.\n"
    sections, _ = heading_spans([page(text)])
    assert len(sections) == 1
    assert sections[0].quote == "Li-Naﬁon at 20 °C.\n"
    assert text[sections[0].start : sections[0].end] == sections[0].quote


def test_abstracted_word_does_not_start_section():
    sections, diagnostics = heading_spans([page("Abstracted data are discussed.\nIntroduction\nBody\n")])
    assert not sections
    assert any("A:" in item for item in diagnostics)


def test_abstract_without_end_does_not_absorb_article():
    sections, diagnostics = heading_spans([page("Abstract\nOpening paragraph.\nUnlabelled body.\n"), page("More body", 2)])
    assert not sections
    assert any("excluded rather than absorbing" in item for item in diagnostics)


def test_layout_boundary_limits_abstract_without_introduction_heading():
    text = "ABSTRACT: Short abstract.\nBody without heading.\n"
    boundary = text.index("Body")
    sections, _ = heading_spans([page(text, layout_blocks=[{"start": 0, "end": boundary}])])
    assert [item.quote for item in sections] == ["Short abstract.\n"]


def test_separate_abstract_heading_uses_next_exact_layout_paragraph():
    text = "Abstract\nOne paragraph.\nBody text.\n"
    end = text.index("Body")
    sections, _ = heading_spans([page(text, layout_blocks=[{"start": 0, "end": 9}, {"start": 9, "end": end}])])
    assert [item.quote for item in sections] == ["One paragraph.\n"]


def test_conclusion_cross_page_stops_before_methods():
    sections, _ = heading_spans([page("4. Conclusions\nFirst result.\n"), page("Second result.\nMethods\nNo longer conclusions.\n", 2)])
    assert [(item.kind, item.page, item.quote) for item in sections] == [
        ("C", 1, "First result.\n"),
        ("C", 2, "Second result.\n"),
    ]


@pytest.mark.parametrize("stop", ["■ REFERENCES AND NOTES", "Funding: This study was funded.", "БЛАГОДАРНОСТИ"])
def test_conclusion_excludes_reference_or_funding_material(stop):
    sections, _ = heading_spans([page(f"Conclusions\nResult.\n{stop}\nOther text.\n")])
    assert [item.quote for item in sections] == ["Result.\n"]


def test_mention_of_conclusions_is_not_a_heading():
    sections, _ = heading_spans([page("Our conclusions were consistent with previous work.\n")])
    assert not sections


def test_russian_implicit_abstract_preserves_source_and_excludes_keywords():
    text = "Принята к публикации 01.02.2021 г.\nТочный текст аннотации.\nКлючевые слова: пример\nВВЕДЕНИЕ\n"
    result = implicit_russian_abstract([page(text)])
    assert result is not None
    assert result.quote == "Точный текст аннотации.\n"
    assert result.method.startswith("proposed_")


def test_tampered_text_and_invalid_offsets_fail():
    source = page("Some text")
    source["text"] = "changed"
    with pytest.raises(ValueError, match="checksum"):
        span(source, "A", 0, 4, "synthetic")
    with pytest.raises(ValueError, match="outside"):
        span(page("Some text"), "A", 0, 100, "synthetic")


def result(article: str, chunk: str) -> SearchResult:
    return SearchResult(article, chunk, "Synthetic article", None, 1, 1, "paragraph", "synthetic evidence", 1.0, "synthetic")


def test_replay_rescue_preserves_original_source_objects_and_no_duplicate_chunks():
    a, b, c = result("a", "1"), result("b", "2"), result("a", "3")
    response = SearchResponse("query", [a, b, c])
    strict = staged_replay(response, {"b"}, top_k=3, rescue=False)
    rescue = staged_replay(response, {"b"}, top_k=3, rescue=True)
    assert strict.results == [b]
    assert rescue.results == [b, a, c]
    assert all(any(item is original for original in response.results) for item in rescue.results)
    assert rescue.metadata["rescue_count"] == 2


def test_empty_shortlist_rescue_falls_back_without_gold_information():
    response = SearchResponse("query", [result("a", "1"), result("b", "2")])
    assert staged_replay(response, set(), top_k=2, rescue=True).results == response.results


def test_shortlist_does_not_require_all_query_words_in_same_article():
    assert lexical_score("NMC-111 vs LFP in EC", "LFP electrolyte in EC") > 0
    assert lexical_score("EC", "electronic") == 0


def test_snapshot_duplicate_article_and_tampering_fail():
    article = {"article_id": "synthetic", "pages": [page("text")], "chunks": []}
    with pytest.raises(ValueError, match="Duplicate source article"):
        validate_snapshot({"articles": [article, article]})
    article["pages"][0]["text"] = "tampered"
    with pytest.raises(ValueError, match="checksum"):
        validate_snapshot({"articles": [article]})


def test_artifact_refuses_overwrite(tmp_path: Path):
    destination = tmp_path / "report.json"
    write_new(destination, {"diagnostic": "original"})
    with pytest.raises(FileExistsError):
        write_new(destination, {"diagnostic": "replacement"})
    assert json.loads(destination.read_bytes()) == {"diagnostic": "original"}


@pytest.mark.parametrize("stop", ["Acknowledgment. We thank colleagues.", "ФИНАНСИРОВАНИЕ РАБОТЫ", "КОНФЛИКТ ИНТЕРЕСОВ"])
def test_new_conclusion_stop_variants_exclude_non_results(stop):
    sections, _ = heading_spans([page(f"Conclusions\nMeasured result.\n{stop}\nNot a scientific result.\n")])
    assert [item.quote for item in sections] == ["Measured result.\n"]


def test_full_paper_summary_is_bounded_by_exact_layout_not_surrounding_body():
    text = "Introduction\nBody precedes summary in extraction order.\nFull Paper: Summary.\nFooter.\n"
    begin = text.index("Full Paper")
    end = text.index("Footer")
    sections, _ = heading_spans([page(text, layout_blocks=[{"start": begin, "end": end}])])
    assert [item.quote for item in sections] == ["Summary.\n"]


def test_dissertation_title_uses_author_specialty_zone_and_preserves_raw_text():
    text = "University\nИВАНОВ ИВАН ИВАНОВИЧ\n\nExact title\ncontinued title\nСпециальность 1.4.4\nДиссертация на соискание степени\n"
    proposed = dissertation_title(page(text))
    assert proposed is not None
    assert proposed.quote.strip() == "Exact title\ncontinued title"
    assert text[proposed.start : proposed.end] == proposed.quote


def test_dissertation_title_without_author_anchor_abstains():
    assert dissertation_title(page("University\nTopic\nСпециальность 1.4.4\nДиссертация на соискание степени")) is None


def block(start, end, bbox, font=12, names=None):
    return {"start": start, "end": end, "bbox": bbox, "font_size": font, "font_names": names or ["BodyFont"]}


def test_fragmented_abstract_joins_same_style_and_stops_at_different_column():
    text = "Abstract\nFirst line.\nSecond line.\nBody text.\n"
    b1, b2, b3 = text.index("First"), text.index("Second"), text.index("Body")
    source = page(
        text,
        layout_blocks=[
            block(0, b1, (0, 0, 100, 12)),
            block(b1, b2, (0, 15, 200, 27)),
            block(b2, b3, (0, 30, 200, 42)),
            block(b3, len(text), (220, 30, 420, 42)),
        ],
    )
    end = abstract_layout_end(source, 0, b1)
    assert end == b3
    assert text[b1:end] == "First line.\nSecond line.\n"


def test_fragmented_abstract_does_not_join_changed_font():
    text = "Abstract\nSummary.\nBody.\n"
    b1, b2 = text.index("Summary"), text.index("Body")
    source = page(
        text,
        layout_blocks=[block(0, b1, (0, 0, 100, 12)), block(b1, b2, (0, 15, 200, 27)), block(b2, len(text), (0, 30, 200, 42), font=10)],
    )
    assert abstract_layout_end(source, 0, b1) == b2


def test_unlabelled_front_matter_requires_layout_transition():
    title_text = "Experimental study title\n"
    abstract = "Here we report a measured property and discuss its dependence on conditions. " * 3 + "\n"
    body = "Body paragraph that contains detailed experimental context. " * 4
    text = title_text + abstract + body
    b1, b2 = len(title_text), len(title_text) + len(abstract)
    source = page(
        text,
        layout_blocks=[
            block(0, b1, (0, 10, 450, 30), font=20),
            block(b1, b2, (0, 50, 450, 180)),
            block(b2, len(text), (0, 220, 200, 400), font=10),
        ],
    )
    title = span(source, "T", 0, b1, "synthetic")
    proposed, _ = unlabelled_abstract(source, title)
    assert proposed is not None and proposed.quote == abstract
    source["layout_blocks"][-1]["bbox"] = (0, 220, 450, 400)
    assert unlabelled_abstract(source, title)[0] is None


def test_unlabelled_multiple_candidates_remain_ambiguous():
    title_text = "Experimental study title\n"
    paragraph = "Here we report results for this study. " * 5 + "\n"
    body = "Body context. " * 20
    text = title_text + paragraph + paragraph + body
    b1, b2, b3 = len(title_text), len(title_text) + len(paragraph), len(title_text) + 2 * len(paragraph)
    source = page(
        text,
        layout_blocks=[
            block(0, b1, (0, 10, 450, 30)),
            block(b1, b2, (0, 50, 450, 120)),
            block(b2, b3, (0, 150, 450, 220)),
            block(b3, len(text), (0, 250, 200, 500)),
        ],
    )
    proposed, diagnostic = unlabelled_abstract(source, span(source, "T", 0, b1, "synthetic"))
    assert proposed is None and "candidates=2" in diagnostic


def test_unlabelled_abstract_joins_prior_fragments_before_prose_anchor():
    title_text = "Experimental study title\n"
    first = "A general description of the scientific background. " * 4 + "\n"
    second = "Further background that contains no narrative trigger. " * 3 + "\n"
    last = "This work provides an experimental result for a measured property. " * 3 + "\n"
    body = "Detailed body context. " * 20
    text = title_text + first + second + last + body
    b1, b2, b3, b4 = [len(title_text + value) for value in ("", first, first + second, first + second + last)]
    source = page(text, layout_blocks=[
        block(0, b1, (0, 10, 450, 30), font=20),
        block(b1, b2, (0, 50, 450, 100)),
        block(b2, b3, (0, 103, 450, 140)),
        block(b3, b4, (0, 143, 450, 190)),
        block(b4, len(text), (0, 220, 200, 450), font=10),
    ])
    proposed, _ = unlabelled_abstract(source, span(source, "T", 0, b1, "synthetic"))
    assert proposed is not None and proposed.quote == first + second + last
    assert source["text"][proposed.start:proposed.end] == proposed.quote
