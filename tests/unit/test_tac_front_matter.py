import json
import textwrap
from pathlib import Path

import pytest

from scripts.tac_experiment import ABSTRACT, STOP, TITLE_NOISE, add_layout_blocks, digest, extract, heading_spans
from scripts.tac_front_matter import exact_span, geometry_abstract, geometry_title, layout_lines


def make_pdf(tmp_path: Path, entries):
    import fitz

    file = tmp_path / "synthetic_front.pdf"
    pages = []
    with fitz.open() as document:
        for number, page_entries in enumerate(entries, 1):
            p = document.new_page()
            for x, y, text, size in page_entries:
                wrapped = textwrap.wrap(text, 90) if len(text) > 95 else [text]
                for index, line in enumerate(wrapped):
                    p.insert_text((x, y + index * size * 1.4), line, fontsize=size)
            raw = p.get_text("text")
            pages.append(
                {
                    "page": number,
                    "text": raw,
                    "text_sha256": digest(raw.encode()),
                    "layer": "original",
                    "layer_id": f"synthetic-{number}",
                    "layer_pdf_path": str(file),
                }
            )
        document.save(file)
    return file, [add_layout_blocks(p) for p in pages]


def title(page):
    return geometry_title(page, TITLE_NOISE, ABSTRACT, STOP)[0]


def test_short_title_continuations_are_merged_before_word_filter(tmp_path):
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 80, "Transport properties of experimental membranes", 17),
                (80, 108, "in liquids", 17),
                (40, 150, "Alice Smith and Bob Jones", 11),
                (40, 185, "ABSTRACT: Short source summary.", 10),
            ]
        ],
    )
    result = title(pages[0])
    assert result["quote"] == "Transport properties of experimental membranes\nin liquids\n"


def test_other_column_does_not_interrupt_wrapped_title(tmp_path):
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 80, "Transport properties of experimental membranes", 13),
                (70, 105, "in liquids", 13),
                (400, 90, "A separate table caption", 13),
                (40, 150, "Alice Smith and Bob Jones", 11),
                (40, 200, "Introduction", 12),
            ]
        ],
    )
    result = title(pages[0])
    assert "in liquids" in result["quote"] and "caption" not in result["quote"]


def test_body_extracted_before_title_does_not_hide_front_matter(tmp_path):
    abstract = "Measured transport depends on solvent conditions. Our experiments establish these dependencies. " * 3
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 400, "Introduction", 12),
                (40, 430, "Detailed body text.", 10),
                (40, 80, "Transport properties of experimental membranes", 17),
                (40, 125, "Alice Smith and Bob Jones", 11),
                (40, 180, abstract, 10),
            ]
        ],
    )
    p = pages[0]
    t = title(p)
    a, _diagnostic = geometry_abstract(p, t, STOP)
    assert t["quote"].startswith("Transport")
    assert a is not None and " ".join(a["quote"].split()) == " ".join(abstract.split())
    assert p["text"][a["start"] : a["end"]] == a["quote"]


def test_title_below_abstract_is_supported_by_byline(tmp_path):
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 80, "ABSTRACT: A publisher places this summary before the title.", 10),
                (40, 400, "Transport properties of experimental membranes", 17),
                (40, 440, "Alice Smith and Bob Jones", 11),
            ]
        ],
    )
    assert title(pages[0])["quote"].startswith("Transport")


def test_formula_after_abstract_without_byline_is_not_a_title(tmp_path):
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 80, "Transport properties of experimental membranes", 17),
                (40, 150, "ABSTRACT: A source summary.", 10),
                (40, 250, "H2O Li2O Example Formula Block", 30),
            ]
        ],
    )
    assert title(pages[0])["quote"].startswith("Transport")


def test_word_fragments_on_same_visual_row_form_full_title(tmp_path):
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 80, "Transport", 17),
                (118, 80, "properties", 17),
                (200, 80, "of membranes", 17),
                (40, 150, "Alice Smith and Bob Jones", 11),
                (40, 190, "Introduction", 12),
            ]
        ],
    )
    result = title(pages[0])
    assert all(word in result["quote"] for word in ("Transport", "properties", "membranes"))


def test_explicit_abstract_on_page_after_cover_and_title_is_complete(tmp_path):
    first = "The roles of experimental solvents are examined under controlled conditions."
    second = "Measurements establish a reproducible dependence and identify limitations."
    _file, pages = make_pdf(tmp_path, [[], [], [(40, 80, "ABSTRACT: " + first, 10), (40, 105, second, 10), (40, 160, "Introduction", 12)]])
    # Old absolute page <= 2 limit must not discard the abstract after a manuscript cover.
    sections, _ = heading_spans(pages, front_start=2)
    a = [s for s in sections if s.kind == "A"]
    assert len(a) == 1 and first in a[0].quote and second in a[0].quote
    assert "Introduction" not in a[0].quote


def test_unlabelled_opening_body_without_layout_boundary_is_excluded(tmp_path):
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 80, "Transport properties of experimental membranes", 17),
                (40, 125, "Alice Smith and Bob Jones", 11),
                (40, 180, "An opening paragraph describing experimental properties and conditions. " * 4, 10),
            ]
        ],
    )
    assert geometry_abstract(pages[0], title(pages[0]), STOP)[0] is None


def test_corresponding_property_is_not_deleted_as_author_metadata(tmp_path):
    sentence = "The corresponding transport property varies with the solvent and experimental conditions. "
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 80, "Transport properties of experimental membranes", 17),
                (40, 125, "Alice Smith and Bob Jones", 11),
                (40, 180, sentence * 3, 10),
                (40, 260, "Introduction", 12),
            ]
        ],
    )
    a, _ = geometry_abstract(pages[0], title(pages[0]), STOP)
    assert a and " ".join(a["quote"].split()) == " ".join((sentence * 3).split())


def test_manuscript_cover_is_skipped_in_frozen_extraction(tmp_path):
    file, pages = make_pdf(
        tmp_path,
        [
            [(40, 80, "This is an Accepted Manuscript", 12)],
            [
                (40, 80, "Transport properties of experimental membranes", 17),
                (40, 125, "Alice Smith and Bob Jones", 11),
                (40, 170, "Introduction", 12),
            ],
        ],
    )
    sha = digest(file.read_bytes())
    snapshot = {
        "pdf_hashes": {str(file): sha},
        "articles": [
            {
                "article_id": "synthetic",
                "title": "Filename is not evidence",
                "doi": None,
                "original_pdf_path": str(file),
                "original_pdf_sha256": sha,
                "pages": pages,
                "chunks": [],
            }
        ],
    }
    source, output = tmp_path / "snapshot.json", tmp_path / "profiles.json"
    source.write_text(json.dumps(snapshot), encoding="utf-8")
    extract(source, output)
    p = json.loads(output.read_bytes())["profiles"][0]
    assert p["front_page"] == 2 and p["sections"][0]["page"] == 2
    assert "Transport properties" in p["sections"][0]["quote"]


def test_source_checksum_mismatch_is_not_hidden():
    p = {"text": "Exact source", "text_sha256": "incorrect"}
    with pytest.raises(ValueError, match="frozen source"):
        exact_span(p, "A", 0, len(p["text"]), "synthetic")


def test_as_received_material_does_not_end_explicit_abstract(tmp_path):
    first = "The as-received material exhibits experimentally measured transport properties in different solvents. "
    _file, pages = make_pdf(tmp_path, [[(40, 80, "ABSTRACT: " + first * 3, 10), (40, 180, "Introduction", 12)]])
    sections, _ = heading_spans(pages)
    assert " ".join(sections[0].quote.split()) == " ".join((first * 3).split())


def test_keywords_in_other_column_do_not_cut_off_unlabelled_abstract(tmp_path):
    sentence = "Measured transport depends on solvent conditions and reproducible experimental measurements. "
    _file, pages = make_pdf(
        tmp_path,
        [
            [
                (40, 80, "Transport properties of experimental membranes", 17),
                (40, 125, "Alice Smith and Bob Jones", 11),
                (180, 180, sentence * 4, 8),
                (40, 210, "Keywords: solvent", 9),
                (40, 340, "Introduction", 12),
            ]
        ],
    )
    a, _ = geometry_abstract(pages[0], title(pages[0]), STOP)
    assert a and " ".join(a["quote"].split()) == " ".join((sentence * 4).split())


def test_repeated_fragment_in_separate_block_maps_only_with_adjacent_anchor(monkeypatch):
    from unittest.mock import MagicMock

    import fitz

    def block(text, x, y):
        return {'lines': [{'bbox': (x, y, x + 40, y + 10),
                           'spans': [{'text': text, 'size': 10, 'flags': 0}]}]}
    document = MagicMock()
    document.__enter__.return_value = document
    document.__getitem__.return_value.get_text.return_value = {
        'blocks': [block('electrolyte.', 40, 80), block('CAR-1', 40, 100),
                   block(' electrolyte.', 80, 100), block(' electrolyte.', 400, 400)]}
    monkeypatch.setattr(fitz, 'open', lambda _path: document)
    raw = 'electrolyte.\nCAR-1\n electrolyte.\n electrolyte.\n'
    p = {'page': 1, 'layer_pdf_path': 'synthetic', 'text': raw}
    lines = layout_lines(p)
    mapped = [line for line in lines if line['quote'] == ' electrolyte.\n']
    assert len(mapped) == 1 and mapped[0]['start'] == raw.index(' electrolyte.')
