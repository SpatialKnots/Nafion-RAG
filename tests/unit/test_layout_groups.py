"""Synthetic layout counterexamples; group proposals are not scientific gold."""
import hashlib
from dataclasses import replace

import pytest

from app.evaluation.context_compaction import SourcePage, compact_source_pages, complete_pages_in_request
from app.evaluation.context_windows import RegisteredBlocks, TextBlock, select_block_windows
from app.evaluation.layout_groups import propose_layout_groups
from app.generation.providers import Evidence

PROSE = " ".join(["Ordinary explanatory background discusses a different topic without quantitative statements"] * 3) + ".\n"


def fixture(*, caption="Table 1. Source measurements.\n", note=None, rows="10\n20\n30\n40\n50\n60\n70\n80\n"):
    texts = [PROSE] * 4 + [caption, rows,
        note or "* This note explains the entire convention used in the table.\n"] + [PROSE] * 4
    cursor = 0
    blocks = []
    for number, text in enumerate(texts):
        blocks.append(TextBlock(cursor, cursor + len(text), (50.0, float(number * 40), 300.0, float(number * 40 + 20)), number))
        cursor += len(text)
    text = "".join(texts)
    source = SourcePage("article", "chunk", 1, "original", "layer", text, "/synthetic.pdf", "synthetic-pdf-sha")
    item = Evidence(citation_id="E1", article_id="article", chunk_id="chunk", title="Synthetic", doi=None,
        page_start=1, page_end=1, source_type="body", text=text.strip(), score=1,
        retrieval_method="synthetic", method_scores={}, method_ranks={})
    prepass = compact_source_pages([item], [source])
    mapping = RegisteredBlocks("article", 1, "layer", hashlib.sha256(text.encode()).hexdigest(),
                               "/synthetic.pdf", "synthetic-pdf-sha", tuple(blocks))
    return texts, source, prepass, mapping


def select(source, prepass, mapping, protection):
    ranges = [pair for group in protection.groups for pair in group.page_ranges]
    return select_block_windows(prepass, [source], [mapping], ["zirconium"],
                                protected_ranges={(source.article_id, source.page, source.layer_id): ranges})


def test_caption_numeric_rows_long_footnote_and_both_context_paragraphs_stay_together():
    note = "* " + PROSE * 2
    texts, source, prepass, mapping = fixture(note=note)
    protection = propose_layout_groups(source, mapping)
    assert len(protection.groups) == 1
    group = protection.groups[0]
    assert group.kind == "prose_enclosed_caption_group_proposal"
    assert group.block_numbers == (3, 4, 5, 6, 7)
    assert group.context_blocks == (3, 7)
    result = select(source, prepass, mapping, protection)
    assert len(result.evidence) == 1
    assert result.evidence[0].text == "".join(texts[2:9])
    assert note in result.evidence[0].text
    assert not complete_pages_in_request(result.evidence[0].text, [source])
    span = result.slices[0]
    assert result.evidence[0].text == source.text[span.page_start:span.page_end]
    assert result.evidence[0].text == prepass.evidence[0].text[span.chunk_start:span.chunk_end]
    assert all(d["classification"] == "algorithm_proposal_not_confirmed" for d in protection.diagnostics)


@pytest.mark.parametrize("note", ["Notes: " + PROSE, "Примечание. " + PROSE, "a) " + PROSE, "† " + PROSE])
def test_explicit_long_notes_cannot_become_prose_barriers(note):
    _, source, _, mapping = fixture(note=note)
    group = propose_layout_groups(source, mapping).groups[0]
    assert group.context_blocks == (3, 7) and 6 in group.block_numbers


@pytest.mark.parametrize("caption", ["Figure 2. Caption.\n", "Рис. 2. Подпись.\n", "Таблица 1. Значения.\n", "Fig. 1. Diagram.\n"])
def test_supported_caption_labels_are_whole_group_proposals(caption):
    _, source, _, mapping = fixture(caption=caption)
    assert propose_layout_groups(source, mapping).groups[0].caption_blocks == (4,)


@pytest.mark.parametrize("kind", ["above", "below", "cross_column", "crossing_block", "bad_bbox", "wrong_layer", "gap"])
def test_open_crossing_or_unproven_geometry_does_not_override_full_protection(kind):
    _, source, prepass, mapping = fixture()
    blocks = list(mapping.blocks)
    if kind == "above":
        blocks = [replace(b, bbox=(50, 500 + b.block_number * 40, 300, 520 + b.block_number * 40))
                  if b.block_number < 4 else b for b in blocks]
    elif kind == "below":
        blocks = [replace(b, bbox=(50, -500 + b.block_number * 10, 300, -480 + b.block_number * 10))
                  if b.block_number > 6 else b for b in blocks]
    elif kind == "cross_column":
        blocks = [replace(b, bbox=(400, b.bbox[1], 650, b.bbox[3])) if b.block_number > 6 else b for b in blocks]
    elif kind == "crossing_block":
        blocks[5] = replace(blocks[5], bbox=(30, blocks[5].bbox[1], 500, blocks[5].bbox[3]))
    elif kind == "bad_bbox":
        blocks[5] = replace(blocks[5], bbox=(float("nan"), 200, 300, 220))
    elif kind == "wrong_layer":
        mapping = replace(mapping, layer_id="other")
    elif kind == "gap":
        blocks[5] = replace(blocks[5], page_start=blocks[5].page_start + 2)
    mapping = replace(mapping, blocks=tuple(blocks))
    protection = propose_layout_groups(source, mapping)
    assert not protection.groups
    result = select(source, prepass, mapping, protection)
    assert result.evidence[0].text == prepass.evidence[0].text
    assert result.diagnostics[0]["action"] == "retain_full_fragment"


@pytest.mark.parametrize("caption", ["Table 1. Continued.\n", "Таблица 1. Продолжение.\n", "Table 1\nData\n"])
def test_continued_or_unrecognized_captions_stay_unresolved(caption):
    _, source, prepass, mapping = fixture(caption=caption)
    protection = propose_layout_groups(source, mapping)
    assert not protection.groups
    assert select(source, prepass, mapping, protection).evidence[0].text == prepass.evidence[0].text


def test_damaged_formula_inside_protected_group_is_preserved_without_repair():
    _, source, prepass, mapping = fixture(rows="Formula \uf0f2\x01 and numerical labels unchanged.\n")
    protection = propose_layout_groups(source, mapping)
    result = select(source, prepass, mapping, protection)
    assert "\uf0f2\x01" in result.evidence[0].text
    assert not any(d["action"] == "retain_full_fragment" for d in result.diagnostics)


def test_damage_outside_group_keeps_full_fragment():
    texts, source, prepass, mapping = fixture()
    text = source.text.replace(texts[0], texts[0].replace("Ordinary", "Ordin\x01ry", 1), 1)
    source = replace(source, text=text)
    mapping = replace(mapping, text_sha256=hashlib.sha256(text.encode()).hexdigest())
    item = replace(prepass.evidence[0], text=text.strip(), citation_id="E1")
    prepass = compact_source_pages([item], [source])
    result = select(source, prepass, mapping, propose_layout_groups(source, mapping))
    assert result.evidence[0].text == text.strip()
    assert "damaged_or_private_use_formula_text" in result.diagnostics[0]["reasons"]


def test_unfinished_inline_reference_protects_entire_block_without_fake_caption_group():
    caption = PROSE.rstrip(".\n") + "\nFig. 2 shows the observations in context.\n"
    _, source, _, mapping = fixture(caption=caption, rows="Diagram label.\n")
    protection = propose_layout_groups(source, mapping)
    assert len(protection.groups) == 1
    assert protection.groups[0].kind == "inline_caption_reference_proposal"
    assert protection.groups[0].block_numbers == (4,)


def test_actual_caption_merged_after_prose_is_not_forced_to_inline_reference():
    _, source, prepass, mapping = fixture(caption=PROSE + "Fig. 2. A separate caption.\n")
    protection = propose_layout_groups(source, mapping)
    assert not protection.groups
    assert select(source, prepass, mapping, protection).evidence[0].text == prepass.evidence[0].text


def test_partial_block_override_is_rejected_and_old_default_is_unchanged():
    _, source, prepass, mapping = fixture()
    baseline = select_block_windows(prepass, [source], [mapping], ["zirconium"])
    assert select_block_windows(prepass, [source], [mapping], ["zirconium"], protected_ranges={}) == baseline
    result = select_block_windows(prepass, [source], [mapping], ["zirconium"], protected_ranges={
        (source.article_id, source.page, source.layer_id): [(mapping.blocks[4].page_start + 1, mapping.blocks[4].page_end)]})
    assert result.evidence[0].text == prepass.evidence[0].text
    assert "protected_layout_range_not_an_exact_block" in result.diagnostics[0]["reasons"]
