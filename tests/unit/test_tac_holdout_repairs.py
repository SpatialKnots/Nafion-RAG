"""Structural counterexamples from stage19; fixtures are synthetic, not scientific gold."""
import pytest

from scripts.tac_experiment import ABSTRACT, STOP, TITLE_NOISE, digest, heading_spans
from scripts.tac_front_matter import exact_span, geometry_abstract, geometry_title, join_lines
from scripts.tac_section_cleanup import clean_conclusions


def page(number, entries):
    p = dict(page=number, text="", layer="original", layer_id=f"fixture-{number}", height=800,
             layout_blocks=[], synthetic_lines=[])
    for text, box, size, bold in entries:
        start = len(p["text"])
        p["text"] += text + "\n"
        line = dict(start=start, end=len(p["text"]), quote=text + "\n", bbox=box, font_size=size, bold=bold)
        p["synthetic_lines"].append(line)
        p["layout_blocks"].append({**line, "font_names": ["Synthetic"]})
    p["text_sha256"] = digest(p["text"].encode())
    return p


@pytest.fixture(autouse=True)
def geometry(monkeypatch):
    for module in ("tac_front_matter", "tac_section_cleanup"):
        monkeypatch.setattr(f"scripts.{module}.layout_lines", lambda p: p["synthetic_lines"])


@pytest.mark.parametrize("heading", ["4. Discussion and conclusions", "Обсуждение и выводы"])
def test_combined_conclusion_heading_is_complete_and_source_exact(heading):
    p = page(1, [(heading, (40, 100, 500, 120), 12, True),
                 ("The complete scientific conclusion.", (40, 140, 500, 160), 10, False),
                 ("Supporting Information", (40, 200, 500, 220), 12, True)])
    sections, _ = heading_spans([p])
    assert [s.quote for s in sections] == ["The complete scientific conclusion.\n"]
    assert p["text"][sections[0].start:sections[0].end] == sections[0].quote


def test_inline_combined_heading_words_do_not_create_a_conclusion():
    p = page(1, [("Discussion and conclusions indicate important transport dependencies.", (40, 100, 500, 120), 10, False)])
    assert heading_spans([p])[0] == []


@pytest.mark.parametrize("boundary", ["СПИСОК ЛИТЕРАТУРЫ / REFERENCES", "БЛАГОДАРНОСТЬ"])
def test_bilingual_bibliography_and_singular_acknowledgment_stop_later_pages(boundary):
    p = page(1, [("Conclusions", (40, 100, 500, 120), 12, True),
                 ("A scientific result.", (40, 140, 500, 160), 10, False)])
    q = page(2, [(boundary, (40, 100, 500, 120), 12, True),
                 ("Bibliography or administrative text.", (40, 140, 500, 160), 10, False)])
    r = page(3, [("More bibliography.", (40, 100, 500, 120), 10, False)])
    assert [s.quote for s in heading_spans([p, q, r])[0]] == ["A scientific result.\n"]


def test_primary_supported_abstract_excludes_a_secondary_language_variant():
    text = "Аннотация: Первый полный итог.\nКлючевые слова: полимер\nAbstract: Second complete summary.\nKeywords: polymer\n"
    p = dict(page=1, text=text, text_sha256=digest(text.encode()), layer="original", layer_id="fixture")
    sections, notes = heading_spans([p])
    assert [s.quote for s in sections] == ["Первый полный итог.\n"]
    assert any("secondary abstract" in n for n in notes)


def test_first_line_indent_does_not_truncate_an_explicit_abstract():
    p = page(1, [("A scientific paragraph starts with an indent and", (58, 100, 500, 110), 10, False),
                 ("continues with exactly the same typography.", (40, 122, 500, 132), 10, False)])
    result = join_lines(p, p["synthetic_lines"], title=False)
    assert len(result) == 1 and result[0]["quote"] == p["text"]


@pytest.mark.parametrize("box,size", [((280, 122, 500, 132), 10), ((40, 180, 500, 190), 10), ((40, 122, 500, 132), 12)])
def test_new_indent_tolerance_preserves_column_gap_and_font_boundaries(box, size):
    p = page(1, [("A first body row.", (58, 100, 260, 110), 10, False),
                 ("Unrelated following text.", box, size, False)])
    assert len(join_lines(p, p["synthetic_lines"], title=False)) == 2


def test_bibliographic_header_and_initialled_byline_are_not_the_title(monkeypatch):
    monkeypatch.setattr("scripts.tac_metadata.author_blocks", lambda p: [])
    p = page(1, [("Example Journal, 2024, vol. 12, pp. 1-8", (40, 40, 500, 56), 16, False),
                 ("Transport properties of polymer electrolyte membranes", (40, 120, 500, 130), 10, True),
                 ("A. B. Smith, C. D. JonesB", (40, 140, 500, 150), 10, True)])
    title, _ = geometry_title(p, TITLE_NOISE, ABSTRACT, STOP)
    assert title["quote"] == "Transport properties of polymer electrolyte membranes\n"


def test_year_without_bibliographic_volume_is_retained_in_a_title(monkeypatch):
    monkeypatch.setattr("scripts.tac_metadata.author_blocks", lambda p: [])
    p = page(1, [("Polymer research progress from 2020 to 2024", (40, 120, 500, 140), 16, False)])
    assert geometry_title(p, TITLE_NOISE, ABSTRACT, STOP)[0]["quote"] == p["text"]


@pytest.mark.parametrize("affiliation_boundary", [True, False])
def test_tac_byline_matching_is_bounded_and_does_not_repair_source(monkeypatch, affiliation_boundary):
    prose = "Measured transport properties depend on experimental conditions. " * 4
    p = page(1, [("Transport properties of polymer membranes", (40, 80, 500, 100), 16, True),
                 (prose, (40, 180, 500, 240), 10, False),
                 ("© 2024 The authors. Published by the journal.", (40, 252, 500, 262), 10, False),
                 ("Introduction", (40, 300, 260, 312), 12, True)])
    monkeypatch.setattr("scripts.tac_metadata.author_blocks", lambda _: [
        dict(cleaned="Alice Smith, z\nBob Jones and Andrea-A. Rivas", bbox=(40, 110, 500, 122),
             last_bbox=(40, 130, 500, 142), affiliation_boundary=affiliation_boundary)])
    title = exact_span(p, "T", 0, p["synthetic_lines"][0]["end"], "fixture")
    abstract, note = geometry_abstract(p, title, STOP)
    if affiliation_boundary:
        assert abstract["quote"] == prose + "\n"
        assert p["text"][abstract["start"]:abstract["end"]] == abstract["quote"]
        assert "© 2024" in p["text"]
    else:
        assert abstract is None and "byline" in note


def test_assignment_statement_in_separate_paragraph_is_excluded():
    p = page(1, [("The complete scientific conclusion.", (40, 200, 500, 220), 10, False),
                 ("Свойства материала\nизучались в рамках государственного задания института.", (40, 240, 500, 280), 10, False)])
    result, notes = clean_conclusions([p], [exact_span(p, "C", 0, len(p["text"]), "fixture")])
    assert result[0]["quote"] == "The complete scientific conclusion.\n"
    assert any("government-assignment paragraph" in n for n in notes)


def test_property_statement_without_assignment_is_not_removed():
    p = page(1, [("Свойства материала изучались в рамках температурного диапазона 200-300 K.", (40, 200, 500, 220), 10, False)])
    source = exact_span(p, "C", 0, len(p["text"]), "fixture")
    assert clean_conclusions([p], [source])[0] == [source]


def test_relative_top_margin_removes_repeated_header_but_retains_body():
    entries = [("Repeated manuscript identifier", (40, 55, 500, 65), 10, True),
               ("The scientific body remains exact.", (40, 85, 500, 100), 10, False)]
    p, q = page(1, entries), page(2, entries)
    result, _ = clean_conclusions([p,q], [exact_span(q, "C", 0, len(q["text"]), "fixture")])
    assert result[0]["quote"] == "The scientific body remains exact.\n"
