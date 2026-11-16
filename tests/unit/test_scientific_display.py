"""Bounded local math display: preserve values, escape content, reject ambiguity."""

from copy import deepcopy

import pytest

from app.generation.scientific_display import scientific_text
from app.ui import _linked_answer_text


@pytest.mark.parametrize("raw,expected", [
    (r"$6.3 \times 10^{-6}$", "6.3 × 10<sup>-6</sup>"),
    (r"$6.9 \cdot 10^{−4}$", "6.9 · 10<sup>−4</sup>"),
    (r"$\mathrm{S\cdot cm^{-1}}$", "S· cm<sup>-1</sup>"),
    (r"$25^{\circ}C$", "25<sup>°</sup>C"),
    (r"\(\sigma_{Li}=1.2\times10^{-3}\) مل", "σ<sub>Li</sub>=1.2×10<sup>-3</sup>"),
    (r"$\frac{S}{cm}$", '<span class="math-fraction"><span>S</span><span>cm</span></span>'),
    (r"$$H_{2}O$$", "H<sub>2</sub>O"),
])
def test_valid_formulas_are_rendered_without_changing_values(raw, expected):
    rendered = scientific_text(raw)
    assert expected in rendered and "scientific-math" in rendered
    assert "math-unparsed" not in rendered


@pytest.mark.parametrize("raw", [r"$\unknown{10}$", r"$10^{-6$", r"$10^-6$", r"$\input{secret}$",
                                 r"$\href{javascript:evil}{link}$", "$6.3 \times 10^{-6}$", "$" + "{" * 20 + "x" + "}" * 20 + "$"])
def test_unknown_or_malformed_markup_is_retained_not_silently_repaired(raw):
    rendered = scientific_text(raw)
    assert "math-unparsed" in rendered
    assert "<a " not in rendered and "<script" not in rendered


def test_plain_text_currency_and_html_remain_escaped():
    assert scientific_text("cost $12 and $15") == "cost $12 and $15"
    assert scientific_text("<img src=x onerror=evil> & αLi=1.54") == "&lt;img src=x onerror=evil&gt; &amp; αLi=1.54"
    assert "<script" not in scientific_text(r"$\text{<script>alert(1)</script>}$")


def test_formula_display_keeps_readable_citation_links_and_input_unchanged():
    raw = r"Conductivity $6.3 \times 10^{-6}$ S/cm. [E1]"
    citations = [{"citation_id": "E1", "title": "Source", "page_start": 12, "page_end": 13,
                  "pdf_page_url": "/articles/a/pdf?layer=original#page=12"}]
    original = deepcopy(citations)
    rendered = _linked_answer_text(raw, citations)
    assert "6.3 × 10<sup>-6</sup>" in rendered
    assert "Source — с. 12-13</a>" in rendered
    assert citations == original and raw.endswith("[E1]")
