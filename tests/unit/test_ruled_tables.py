"""Synthetic closed-table and marker-closure counterexamples; no corpus gold."""
import hashlib
from dataclasses import replace

import fitz
import pytest

from app.evaluation.context_compaction import SourcePage, compact_source_pages
from app.evaluation.context_windows import RegisteredBlocks, TextBlock, read_registered_blocks, select_block_windows
from app.evaluation.ruled_tables import HorizontalRule, RegisteredRules, propose_ruled_tables, read_registered_rules
from app.generation.providers import Evidence


def fixture(caption="Table 1\nExperimental values\n", note="* Measured at 30 °C.\n** Measured at 40 °C.\n", star_markers=True):
    texts = [caption, "Name\nValue\n", "A\n1.25*\n2.5\n" if star_markers else "A\n1.25\n2.5\n",
             "B\n3.75**\n4.0\n" if star_markers else "B\n3.75\n4.0\n", note]
    boxes = [(50, 40, 400, 60), (50, 72, 400, 85), (50, 100, 400, 115), (50, 125, 400, 140), (50, 155, 250, 175)]
    blocks = []
    cursor = 0
    for index, (text, box) in enumerate(zip(texts, boxes, strict=True)):
        blocks.append(TextBlock(cursor, cursor+len(text), tuple(map(float, box)), index))
        cursor += len(text)
    text = "".join(texts)
    source = SourcePage("article", "chunk", 1, "original", "layer", text, "/synthetic.pdf", "synthetic-hash")
    mapping = RegisteredBlocks("article", 1, "layer", hashlib.sha256(text.encode()).hexdigest(), "/synthetic.pdf",
                               "synthetic-hash", tuple(blocks))
    rules = RegisteredRules("article", 1, "layer", mapping.text_sha256, "synthetic-hash",
                            (HorizontalRule(50, 400, 70, 0), HorizontalRule(50, 400, 90, 1), HorizontalRule(50, 400, 150, 2)))
    return source, mapping, rules


def test_closed_table_header_rows_and_matching_notes_are_one_exact_protected_group():
    source, mapping, rules = fixture()
    result = propose_ruled_tables(source, mapping, rules)
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.kind == "closed_ruled_table_proposal" and group.block_numbers == (0, 1, 2, 3, 4)
    assert result.diagnostics[0]["note_blocks"] == [4]
    item = Evidence(citation_id="E1", article_id="article", chunk_id="chunk", title="Synthetic", doi=None,
        page_start=1, page_end=1, source_type="body", text=source.text.strip(), score=1,
        retrieval_method="synthetic", method_scores={}, method_ranks={})
    prepass = compact_source_pages([item], [source])
    selected = select_block_windows(prepass, [source], [mapping], ["zirconium"], protected_ranges={
        (source.article_id, source.page, source.layer_id): list(group.page_ranges)})
    assert selected.evidence[0].text == source.text.strip()
    assert "1.25*" in selected.evidence[0].text and "30 °C" in selected.evidence[0].text


@pytest.mark.parametrize("kind", ["no_bottom", "endpoints", "caption_gap", "crossing", "no_notes", "missing_marker", "note_gap",
                                  "continued", "figure", "wrong_source", "invalid_rule", "gap", "duplicate_block"])
def test_unresolved_tables_do_not_produce_closed_table_overrides(kind):
    source, mapping, rules = fixture()
    if kind == "no_bottom":
        rules = replace(rules, rules=rules.rules[:1])
    elif kind == "endpoints":
        rules = replace(rules, rules=(rules.rules[0], replace(rules.rules[1], x1=390), replace(rules.rules[2], x1=390)))
    elif kind == "caption_gap":
        mapping = replace(mapping, blocks=(replace(mapping.blocks[0], bbox=(50, 10, 400, 20)), *mapping.blocks[1:]))
    elif kind == "crossing":
        mapping = replace(mapping, blocks=(mapping.blocks[0], mapping.blocks[1],
            replace(mapping.blocks[2], bbox=(20, 100, 500, 115)), *mapping.blocks[3:]))
    elif kind == "no_notes":
        source, mapping, rules = fixture(note="Unmarked body text.\n")
    elif kind == "missing_marker":
        source, mapping, rules = fixture(note="* Only one of two markers is defined.\n")
    elif kind == "note_gap":
        mapping = replace(mapping, blocks=(*mapping.blocks[:4], replace(mapping.blocks[4], bbox=(50, 170, 250, 190))))
    elif kind == "continued":
        source, mapping, rules = fixture(caption="Table 1. Continued.\n")
    elif kind == "figure":
        source, mapping, rules = fixture(caption="Figure 1. Graph.\n")
    elif kind == "wrong_source":
        rules = replace(rules, layer_id="other")
    elif kind == "invalid_rule":
        rules = replace(rules, rules=(HorizontalRule(float("nan"), 400, 70, 0), *rules.rules[1:]))
    elif kind == "gap":
        mapping = replace(mapping, blocks=(replace(mapping.blocks[0], page_start=2), *mapping.blocks[1:]))
    elif kind == "duplicate_block":
        mapping = replace(mapping, blocks=(*mapping.blocks[:4], replace(mapping.blocks[4], block_number=3)))
    assert not any(group.kind == "closed_ruled_table_proposal" for group in propose_ruled_tables(source, mapping, rules).groups)


@pytest.mark.parametrize("prefix", ["Table 2 summarises", "Table 2 shows", "Figure 2 presents", "Таблица 2 содержит"])
def test_leading_prose_reference_is_protected_without_claiming_a_table(prefix):
    content = prefix + " " + "ordinary explanatory prose discusses a different topic without numeric statements " * 4 + ".\n"
    source, mapping, rules = fixture(caption=content)
    result = propose_ruled_tables(source, mapping, rules)
    assert result.groups[0].kind == "leading_reference_paragraph_proposal"
    assert result.groups[0].block_numbers == (0,)


def test_read_actual_pdf_vector_rules_and_preserve_file_hash(tmp_path):
    path = tmp_path / "synthetic_table.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 50), "Table 1. Values")
        page.insert_text((50, 80), "Name       Value")
        page.insert_text((50, 110), "A          1.25    2.5")
        page.insert_text((50, 140), "B          3.75    4.0")
        for y in (65, 90, 150):
            page.draw_line((50, y), (400, y), width=0.5)
        doc.save(path)
        text = page.get_text("text")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    source = SourcePage("article", "chunk", 1, "original", "layer", text, str(path), checksum)
    mapping = read_registered_blocks(source, path, checksum)
    rules = read_registered_rules(source, mapping)
    assert len(rules.rules) == 3
    assert propose_ruled_tables(source, mapping, rules).groups[0].kind == "closed_ruled_table_proposal"
    with pytest.raises(ValueError, match="exact registered"):
        read_registered_rules(source, replace(mapping, selected_pdf_sha256="wrong"))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum


@pytest.mark.parametrize("tail", ["C\n5.0\n6.0\n", "a The notation refers to the source material.\n"])
def test_unclassified_close_tail_prevents_partial_table_admission(tail):
    source, mapping, rules = fixture(note=tail, star_markers=False)
    result = propose_ruled_tables(source, mapping, rules)
    assert not any(group.kind == "closed_ruled_table_proposal" for group in result.groups)
    assert any(d["action"] == "table_tail_unresolved" for d in result.diagnostics)
