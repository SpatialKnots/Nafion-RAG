"""Synthetic geometry fixtures for source-preserving section flow."""

import pytest

from scripts.tac_experiment import STOP, digest
from scripts.tac_front_matter import exact_span
from scripts.tac_section_flow import continuation, summary_passages


def page(number, entries):
    result = {
        "page": number,
        "text": "",
        "layer": "original",
        "layer_id": f"synthetic-{number}",
        "height": 800,
        "layout_blocks": [],
        "synthetic_lines": [],
    }
    for text, box, size in entries:
        start = len(result["text"])
        result["text"] += text + "\n"
        item = {"start": start, "end": len(result["text"]), "quote": text + "\n", "bbox": box, "font_size": size, "bold": False}
        result["synthetic_lines"].append(item)
        result["layout_blocks"].append({**item, "font_names": ["Synthetic"]})
    result["text_sha256"] = digest(result["text"].encode())
    return result


@pytest.fixture(autouse=True)
def synthetic_geometry(monkeypatch):
    monkeypatch.setattr("scripts.tac_section_flow.layout_lines", lambda p: p["synthetic_lines"])


def initial(p, kind="A"):
    item = p["synthetic_lines"][0]
    return exact_span(p, kind, item["start"], item["end"], "synthetic")


def test_cross_column_abstract_keeps_full_paragraph_and_stops_at_keywords():
    p = page(
        1,
        [
            ("Measured transport shows", (40, 150, 260, 160), 10),
            ("a transi-", (40, 440, 260, 450), 10),
            ("tion with reproducible solvent dependence.", (280, 150, 500, 160), 10),
            ("Further measurements confirm the conclusion.", (280, 163, 500, 173), 10),
            ("Keywords: solvent", (280, 200, 500, 210), 10),
        ],
    )
    a = exact_span(p, "A", 0, p["synthetic_lines"][1]["end"], "synthetic")
    result = continuation([p], a, STOP)
    assert len(result) == 1
    assert result[0]["quote"] == p["text"][: p["text"].index("Keywords")]
    assert p["text"][result[0]["start"] : result[0]["end"]] == result[0]["quote"]


@pytest.mark.parametrize(
    "second,size,box",
    [
        ("Introduction", 10, (280, 150, 500, 160)),
        ("Unrelated body material.", 12, (280, 150, 500, 160)),
        ("Unrelated body material.", 10, (280, 300, 500, 310)),
        ("Unrelated body material.", 10, (560, 150, 780, 160)),
    ],
)
def test_rejects_heading_style_or_geometry_mismatch(second, size, box):
    p = page(1, [("An unfinished abstract transi-", (40, 150, 260, 450), 10), (second, box, size)])
    a = initial(p)
    assert continuation([p], a, STOP) == [a]


def test_complete_abstract_does_not_absorb_following_body():
    p = page(1, [("A complete abstract.", (40, 150, 260, 160), 10), ("Body with matching typography.", (40, 163, 260, 173), 10)])
    a = initial(p)
    assert continuation([p], a, STOP) == [a]


def test_next_page_continuation_remains_separate_exact_evidence():
    p = page(1, [("Abstract continuing across the page with transi-", (40, 700, 260, 750), 10)])
    q = page(
        2,
        [
            ("2", (40, 10, 50, 20), 10),
            ("tion measured under reproducible conditions.", (40, 60, 260, 70), 10),
            ("Introduction", (40, 120, 260, 130), 12),
        ],
    )
    result = continuation([p, q], initial(p), STOP)
    assert len(result) == 2 and result[0]["page"] == 1 and result[1]["page"] == 2
    assert result[1]["quote"] == "tion measured under reproducible conditions.\n"
    assert q["text"][result[1]["start"] : result[1]["end"]] == result[1]["quote"]


def test_mid_page_unfinished_abstract_does_not_jump_to_next_page():
    p = page(1, [("Unfinished abstract transi-", (40, 150, 260, 160), 10)])
    q = page(2, [("Unrelated opening body.", (40, 60, 260, 70), 10)])
    a = initial(p)
    assert continuation([p, q], a, STOP) == [a]


def test_summary_passage_continues_across_columns_but_excludes_methods():
    p = page(
        3,
        [
            (
                "In summary, the experimental measurements establish reproducible transport properties and "
                "consistent dependencies under all conditions studied here, providing evidence for the "
                "reported model with unfinished continu-",
                (40, 550, 260, 750),
                10,
            ),
            ("ation and independently measured limitations.", (280, 60, 500, 70), 10),
            ("Experimental section", (280, 100, 500, 110), 12),
            ("Sample preparation.", (280, 150, 500, 160), 10),
        ],
    )
    sections, diagnostics = summary_passages([page(1, []), page(2, []), p], STOP)
    assert len(sections) == 1 and sections[0]["kind"] == "C"
    assert sections[0]["quote"] == p["text"][: p["text"].index("Experimental")]
    assert any("not a separately headed" in d for d in diagnostics)


def test_early_or_inline_summary_mention_is_not_a_conclusion():
    text = "In summary, " + "Evidence from prior literature is reviewed in introductory context. " * 4
    pages = [
        page(1, [(text, (40, 60, 260, 160), 10)]),
        page(2, []),
        page(3, [("The introduction says in summary, " + text, (40, 60, 260, 160), 10)]),
    ]
    assert summary_passages(pages, STOP)[0] == []


def test_two_summary_passages_keep_separate_source_spans():
    text = "In conclusion, " + "The measurements establish reproducible properties for this material. " * 4
    p = page(3, [(text, (40, 200, 260, 260), 10), (text, (40, 400, 260, 460), 10)])
    sections, _ = summary_passages([page(1, []), page(2, []), p], STOP)
    assert len(sections) == 2 and sections[0]["end"] <= sections[1]["start"]


def test_same_page_heading_prevents_a_jump_to_following_page():
    p = page(1, [("Unfinished abstract transi-", (40, 700, 260, 750), 10), ("Introduction", (40, 760, 260, 770), 12)])
    q = page(2, [("Unrelated body prose.", (40, 60, 260, 70), 10)])
    a = initial(p)
    assert continuation([p, q], a, STOP) == [a]


def test_summary_after_references_is_excluded():
    text = "In summary, " + "A quoted prior article discusses transport in different experimental conditions. " * 4
    p = page(3, [("References", (40, 60, 260, 70), 12), (text, (40, 100, 260, 200), 10)])
    q = page(4, [(text, (40, 60, 260, 160), 10)])
    assert summary_passages([page(1, []), page(2, []), p, q], STOP)[0] == []


def test_missing_page_does_not_create_a_false_continuation():
    p = page(1, [("Abstract continuing with transi-", (40, 700, 260, 750), 10)])
    q = page(3, [("Unrelated later body.", (40, 60, 260, 70), 10)])
    a = initial(p)
    assert continuation([p, q], a, STOP) == [a]
