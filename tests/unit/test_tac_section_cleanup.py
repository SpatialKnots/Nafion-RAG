"""Counterexamples for layout-backed exclusions; all retained slices stay exact."""

import pytest

from scripts.tac_experiment import STOP, digest
from scripts.tac_front_matter import exact_span
from scripts.tac_section_cleanup import clean_conclusions, title_without_footnote
from scripts.tac_section_flow import summary_passages


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
    for module in ("tac_section_cleanup", "tac_section_flow"):
        monkeypatch.setattr(f"scripts.{module}.layout_lines", lambda p: p["synthetic_lines"])


def proposal(p, start=0, kind="C", method="fixture"):
    return exact_span(p, kind, start, len(p["text"]), method)


def test_backward_figure_tail_excluded_with_caption_evidence():
    p = page(1, [("Figure 2. Measurements.", (40, 300, 500, 320), 10, False),
                 ("The measurements support this conclusion.", (40, 400, 260, 420), 10, False),
                 ("(a)", (40, 100, 60, 110), 12, False), ("0", (40, 200, 50, 210), 9, False)])
    start = p["synthetic_lines"][1]["start"]
    result, notes = clean_conclusions([p], [proposal(p, start)])
    assert result[0]["quote"] == "The measurements support this conclusion.\n"
    assert p["text"][result[0]["start"]:result[0]["end"]] == result[0]["quote"]
    assert any("above preceding figure caption" in n for n in notes)


@pytest.mark.parametrize("caption,tail,size", [(False, "(a)", 12), (True, "A scientific continuation in the next column.", 10)])
def test_missing_caption_or_matching_body_prose_remains(caption, tail, size):
    entries = [("Figure 2. Measurements." if caption else "Earlier body text.", (40, 300, 500, 320), 10, False),
               ("Unfinished conclusion with", (40, 700, 260, 720), 10, False),
               (tail, (280, 100, 500, 120), size, False)]
    p = page(1, entries)
    source = proposal(p, p["synthetic_lines"][1]["start"])
    assert clean_conclusions([p], [source])[0] == [source]


def test_repeated_multi_line_header_and_marginal_page_number_removed():
    entries = [("Articles", (40, 20, 80, 30), 18, True), ("Journal", (90, 25, 150, 35), 12, True),
               ("Science body contains 100 units.", (40, 80, 500, 100), 10, False),
               ("100", (40, 760, 60, 780), 10, False)]
    p, q = page(1, entries), page(2, entries)
    # PDF blocks may merge the two mapped running-header lines.
    p["layout_blocks"][:2] = [{**p["layout_blocks"][0], "end": p["synthetic_lines"][1]["end"]}]
    q["layout_blocks"][:2] = [{**q["layout_blocks"][0], "end": q["synthetic_lines"][1]["end"]}]
    result, _ = clean_conclusions([p, q], [proposal(p)])
    assert result[0]["quote"] == "Science body contains 100 units.\n"


def test_numeric_body_and_unique_header_retained():
    p = page(1, [("Unique heading", (40, 20, 200, 30), 10, False),
                 ("100", (40, 150, 80, 160), 10, False)])
    source = proposal(p)
    assert clean_conclusions([p], [source])[0] == [source]


def test_marginal_only_fragment_excluded():
    p = page(1, [("138", (40, 760, 80, 780), 10, False)])
    result, notes = clean_conclusions([p], [proposal(p)])
    assert result == [] and any("empty/marginal-only" in n for n in notes)


@pytest.mark.parametrize("boundary", ["Авторы выражают благодарность коллегам.",
                                     "Работа выполнена при поддержке фонда.",
                                     "Рекомендации и перспективы дальнейшей разработки темы"])
def test_administrative_or_bold_subsection_boundary_stops_continuation(boundary):
    p = page(1, [("Научный итог.", (40, 200, 500, 220), 10, False),
                 (boundary, (40, 230, 500, 250), 10, True),
                 ("Following text.", (40, 260, 500, 280), 10, False)])
    q = page(2, [("Later continuation.", (40, 100, 500, 120), 10, False)])
    result, _ = clean_conclusions([p, q], [proposal(p), proposal(q)])
    assert len(result) == 1 and result[0]["quote"] == "Научный итог.\n"


@pytest.mark.parametrize("text", ["Полученные рекомендации и перспективы дальнейшей разработки темы обсуждены.",
                                 "Рекомендации и перспективы дальнейшей разработки темы",
                                 "Научная работа выполнена при поддержке температуры 300 K."])
def test_inline_mentions_and_unbold_recommendations_remain(text):
    p = page(1, [(text, (40, 200, 500, 220), 10, False)])
    source = proposal(p)
    assert clean_conclusions([p], [source])[0] == [source]


def test_dagger_removed_only_with_unique_smaller_lower_matching_note():
    p = page(1, [("Scientific title†", (40, 100, 500, 120), 16, False),
                 ("† Electronic supplementary information.", (40, 700, 500, 720), 7, False)])
    title = exact_span(p, "T", 0, p["synthetic_lines"][0]["end"], "fixture")
    result, _ = title_without_footnote(p, title)
    assert result["quote"] == "Scientific title"
    assert p["text"][result["start"]:result["end"]] == result["quote"]


@pytest.mark.parametrize("notes", [[], [("† A note.", (40, 700, 500, 720), 16, False)],
                                  [("† A note.", (40, 700, 500, 720), 7, False),
                                   ("† Another note.", (40, 730, 500, 750), 7, False)]])
def test_unsupported_or_ambiguous_dagger_retained_with_diagnostic(notes):
    p = page(1, [("Scientific title†", (40, 100, 500, 120), 16, False), *notes])
    title = exact_span(p, "T", 0, p["synthetic_lines"][0]["end"], "fixture")
    result, diagnostics = title_without_footnote(p, title)
    assert result == title and diagnostics


def test_russian_summary_excludes_unheaded_funding_paragraph():
    summary = "Таким образом, " + "измерения показывают устойчивое изменение свойств материала в исследованных условиях. " * 4
    funding = "Работа выполнена при поддержке фонда."
    p = page(3, [(summary + "\n" + funding, (40, 200, 500, 400), 10, False)])
    sections, notes = summary_passages([page(1, []), page(2, []), p], STOP)
    assert len(sections) == 1 and sections[0]["quote"] == summary + "\n"
    assert any("not a separately headed" in n for n in notes)


def test_summary_cleanup_does_not_discard_separate_later_summary():
    p = page(1, [("First scientific summary.", (40, 200, 500, 220), 10, False),
                 ("Работа выполнена при поддержке фонда.", (40, 230, 500, 250), 10, False)])
    q = page(2, [("Second independently delimited summary.", (40, 200, 500, 220), 10, False)])
    result, _ = clean_conclusions([p, q], [proposal(p, method="proposed_implicit_summary_passage"),
                                         proposal(q, method="proposed_implicit_summary_passage")])
    assert len(result) == 2 and result[1]["quote"] == q["text"]
