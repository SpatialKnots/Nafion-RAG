"""Synthetic source-geometry and scientific-context counterexamples, not gold labels."""
import hashlib
from dataclasses import replace

import fitz
import pytest

from app.evaluation.context_compaction import SourcePage, compact_source_pages, complete_pages_in_request
from app.evaluation.context_windows import RegisteredBlocks, TextBlock, read_registered_blocks, select_block_windows
from app.generation.providers import Evidence


def setup(blocks):
    text = "".join(blocks)
    source = SourcePage("article", "chunk", 1, "original", "layer", text, "/synthetic.pdf", "synthetic-pdf-sha")
    item = Evidence(citation_id="E1", article_id="article", chunk_id="chunk", title="Synthetic", doi=None,
                    page_start=1, page_end=1, source_type="body", text=text.strip(), score=1.0,
                    retrieval_method="synthetic", method_scores={}, method_ranks={})
    prepass = compact_source_pages([item], [source])
    position = 0
    spans = []
    for index, block in enumerate(blocks):
        spans.append(TextBlock(position, position + len(block), (0, float(index), 100, float(index + 1)), index))
        position += len(block)
    mapping = RegisteredBlocks("article", 1, "layer", hashlib.sha256(text.encode()).hexdigest(), "/synthetic.pdf",
                               "synthetic-pdf-sha", tuple(spans))
    return item, source, prepass, mapping


def test_query_windows_keep_neighbors_and_all_condition_blocks_with_exact_offsets():
    blocks = [f"Unrelated prose segment {chr(65 + i)}.\n" for i in range(14)]
    blocks[2] = "Target conductivity reported here.\n"
    blocks[10] = "Conditions: 65 °C, 48 h equilibration, 40 wt% additive; ±0.5 uncertainty.\n"
    original, source, prepass, mapping = setup(blocks)
    result = select_block_windows(prepass, [source], [mapping], ["conductivity"])
    assert len(result.evidence) == 2
    assert result.evidence[0].text == "".join(blocks[1:4])
    assert result.evidence[1].text == "".join(blocks[9:12])
    for span, item in zip(result.slices, result.evidence, strict=True):
        assert original.text[span.chunk_start:span.chunk_end] == item.text
        assert source.text[span.page_start:span.page_end] == item.text
        assert span.input_citation_id == "E1" and item.citation_id.startswith("W")
    assert not complete_pages_in_request("\n".join(item.text for item in result.evidence), [source])
    assert original.text == source.text.strip()


@pytest.mark.parametrize("condition", [
    "25 °C", "80 ◦C", "30°C", "48 h", "200 K", "10 kHz", "1 MPa", "5 ml", "30%", "40 wt%", "10 S/cm",
    "Samples were blotted dry", "The weight uptake was defined as", "погрешность измерений", "равновесное состояние",
    "24 ч", "30 мин", "±0.5", "5 мл",
])
def test_condition_heuristic_is_retained_far_from_query_anchor(condition):
    blocks = ["Unrelated general prose.\n"] * 12
    blocks[1] = "Target conductivity.\n"
    blocks[9] = condition + ".\n"
    _, source, prepass, mapping = setup(blocks)
    result = select_block_windows(prepass, [source], [mapping], ["conductivity"])
    assert any(condition in item.text for item in result.evidence)
    selected = next(d for d in result.diagnostics if d.get("block_number") == 9)
    assert "measurement_or_condition_heuristic" in selected["reasons"]


@pytest.mark.parametrize("danger", [
    "Table 3. Conductivity\nName T\nA 20\n* 40 °C.\n",
    "Таблица 2. Набухание\nУсловия и сноски.\n",
    "Figure 2. Results including an inset.\n",
    "Рис. 1. Схема и её подпись.\n",
    "1\n2\n3\n4\n5\n6\n",
    "Damaged formula \x01 still visible.\n",
    "Private-use formula \uf0f2 still visible.\n",
    "Replacement character \ufffd.\n",
])
def test_unresolved_tables_captions_and_damaged_formulas_keep_whole_fragment(danger):
    _, source, prepass, mapping = setup(["Leading unrelated prose.\n", danger, "Trailing source.\n"])
    result = select_block_windows(prepass, [source], [mapping], ["conductivity"])
    assert result.evidence[0].text == prepass.evidence[0].text
    assert result.diagnostics[0]["action"] == "retain_full_fragment"
    assert complete_pages_in_request(result.evidence[0].text, [source])


def test_full_page_selection_is_not_arbitrarily_clipped_to_pass_scope_guard():
    _, source, prepass, mapping = setup(["Context before.\n", "Target conductivity.\n", "Context after.\n"])
    result = select_block_windows(prepass, [source], [mapping], ["conductivity"])
    assert result.evidence[0].text == source.text.strip()
    assert complete_pages_in_request(result.evidence[0].text, [source])


@pytest.mark.parametrize("kind", ["missing", "hash", "diagnostic", "gap", "overlap", "partial", "duplicate"])
def test_unproven_geometry_retains_source_and_failure_diagnostic(kind):
    _, source, prepass, mapping = setup(["Context before.\n", "Target conductivity.\n", "Context after.\n"])
    maps = [mapping]
    if kind == "missing":
        maps = []
    elif kind == "hash":
        maps = [replace(mapping, text_sha256="wrong")]
    elif kind == "diagnostic":
        maps = [replace(mapping, diagnostic="synthetic_extraction_mismatch")]
    elif kind == "gap":
        maps = [replace(mapping, blocks=(replace(mapping.blocks[0], page_start=2), *mapping.blocks[1:]))]
    elif kind == "overlap":
        maps = [replace(mapping, blocks=(mapping.blocks[0], replace(mapping.blocks[1], page_start=0), mapping.blocks[2]))]
    elif kind == "partial":
        maps = [replace(mapping, blocks=mapping.blocks[:-1])]
    elif kind == "duplicate":
        maps *= 2
    result = select_block_windows(prepass, [source], maps, ["conductivity"])
    assert result.evidence[0].text == prepass.evidence[0].text
    assert result.diagnostics[0]["action"] == "retain_full_fragment"


def test_invalid_prepass_coordinates_are_not_emitted_as_verified_source_slices():
    _, source, prepass, mapping = setup(["Target conductivity.\n"])
    prepass.slices[0] = replace(prepass.slices[0], chunk_end=99999)
    result = select_block_windows(prepass, [source], [mapping], ["conductivity"])
    assert result.evidence[0].text == prepass.evidence[0].text
    assert not result.slices
    assert "source_geometry_not_proven" in result.diagnostics[0]["reasons"]


def test_empty_terms_are_not_anchors_and_no_match_is_unknown():
    _, source, prepass, mapping = setup(["General prose without requested topic.\n"])
    result = select_block_windows(prepass, [source], [mapping], ["", " ", "conductivity"])
    assert not result.evidence
    assert result.diagnostics[-1]["reason"] == "no_lexical_or_condition_anchor_not_evidence_of_absence"


def test_anchor_limit_ranks_by_term_count_then_original_order():
    blocks = ["Background prose.\n"] * 15
    blocks[1] = "Nafion anchor.\n"
    blocks[6] = "Nafion conductivity.\n"
    blocks[12] = "Nafion conductivity.\n"
    _, source, prepass, mapping = setup(blocks)
    result = select_block_windows(prepass, [source], [mapping], ["nafion", "conductivity"])
    seeds = [d["block_number"] for d in result.diagnostics if "ranked_query_anchor" in d.get("reasons", [])]
    assert seeds == [6, 12]
    assert not any("Nafion anchor." in item.text for item in result.evidence)


def test_pdf_blocks_require_exact_registered_text_and_frozen_file_hash(tmp_path):
    path = tmp_path / "synthetic.pdf"
    with fitz.open() as document:
        pdf_page = document.new_page()
        pdf_page.insert_text((50, 50), "Target conductivity.")
        pdf_page.insert_text((50, 100), "Measurement at 25 C.")
        document.save(path)
        text = pdf_page.get_text("text")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    source = SourcePage("article", "chunk", 1, "original", "layer", text, str(path), checksum)
    mapping = read_registered_blocks(source, path, checksum)
    assert mapping.diagnostic is None
    assert mapping.blocks[0].page_start == 0 and mapping.blocks[-1].page_end == len(text)
    assert len(mapping.blocks) == 2
    assert read_registered_blocks(replace(source, text=text + "wrong"), path, checksum).diagnostic is not None
    with pytest.raises(ValueError, match="hash differs"):
        read_registered_blocks(source, path, "wrong-hash")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum
