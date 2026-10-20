"""Closed vector-rule table proposals; no scientific cell assignment or OCR."""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from app.evaluation.context_compaction import SourcePage
from app.evaluation.context_windows import RegisteredBlocks
from app.evaluation.layout_groups import _CONTINUED, _NOTE, LayoutProtection, ProtectedGroup, _prose

VERSION = "source_ruled_tables_v0.2"
_TABLE = re.compile(r"(?i)^\s*(?:table|таблица|табл\.)\s*\d+(?:\.\d+)*(?:[.:]|\s|$)")
_REFERENCE = re.compile(
    r"(?i)^\s*(?:table|figure|fig\.|таблица|табл\.|рис\.)\s*\d+\s+"
    r"(?:shows?\b|presents?\b|lists?\b|summari[sz]es?\b|демонстр\w*|представ\w*|показ\w*|содерж\w*|суммир\w*)")


@dataclass(frozen=True)
class HorizontalRule:
    x0: float
    x1: float
    y: float
    drawing_index: int


@dataclass(frozen=True)
class RegisteredRules:
    article_id: str
    page: int
    layer_id: str
    text_sha256: str
    pdf_sha256: str
    rules: tuple[HorizontalRule, ...]


def read_registered_rules(page: SourcePage, mapping: RegisteredBlocks) -> RegisteredRules:
    path = Path(mapping.selected_pdf_path)
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    if (page.page < 1 or mapping.diagnostic is not None or checksum != mapping.selected_pdf_sha256
            or mapping.article_id != page.article_id or mapping.page != page.page or mapping.layer_id != page.layer_id
            or mapping.text_sha256 != hashlib.sha256(page.text.encode()).hexdigest()):
        raise ValueError("Vector-rule registry requires the exact registered PDF/page/text")
    rules = []
    with fitz.open(path) as doc:
        pdf_page = doc[page.page - 1]
        if pdf_page.get_text("text") != page.text:
            raise ValueError("Vector-rule page text differs from registered text")
        for index, drawing in enumerate(pdf_page.get_drawings()):
            rect = drawing["rect"]
            if (all(math.isfinite(value) for value in rect) and rect.width >= 120 and 0 <= rect.height <= 1
                    and drawing["items"] and all(item[0] in {"l", "re"} for item in drawing["items"])):
                rules.append(HorizontalRule(rect.x0, rect.x1, (rect.y0 + rect.y1) / 2, index))
    return RegisteredRules(page.article_id, page.page, page.layer_id, mapping.text_sha256, checksum, tuple(rules))


def propose_ruled_tables(page: SourcePage, mapping: RegisteredBlocks, registry: RegisteredRules) -> LayoutProtection:
    valid = (mapping.diagnostic is None and page.page >= 1 and mapping.article_id == registry.article_id == page.article_id
             and mapping.page == registry.page == page.page and mapping.layer_id == registry.layer_id == page.layer_id
             and mapping.text_sha256 == registry.text_sha256 == hashlib.sha256(page.text.encode()).hexdigest()
             and registry.pdf_sha256 == mapping.selected_pdf_sha256)
    cursor = 0
    seen = set()
    for block in mapping.blocks:
        valid = valid and (block.page_start == cursor and block.page_start < block.page_end <= len(page.text)
                           and all(math.isfinite(value) for value in block.bbox)
                           and block.bbox[0] < block.bbox[2] and block.bbox[1] < block.bbox[3]
                           and block.block_number not in seen)
        cursor = block.page_end
        seen.add(block.block_number)
    if not valid or cursor != len(page.text) or any(not all(math.isfinite(v) for v in (r.x0, r.x1, r.y))
                                                  or r.x1 - r.x0 < 120 for r in registry.rules):
        return LayoutProtection([], [{"action": "table_rule_geometry_not_proven"}])
    texts = {block.block_number: page.text[block.page_start:block.page_end] for block in mapping.blocks}
    groups = []
    diagnostics = []
    rules = sorted(registry.rules, key=lambda rule: (rule.y, rule.drawing_index))
    for caption in mapping.blocks:
        content = texts[caption.block_number]
        reference = _REFERENCE.match(content)
        if reference is not None and _prose(content[reference.end():]):
            groups.append(ProtectedGroup("leading_reference_paragraph_proposal", page.article_id, page.page, page.layer_id,
                (caption.block_number,), (), ((caption.page_start, caption.page_end),), caption.bbox, ()))
            continue
        if not _TABLE.match(content):
            continue
        if _CONTINUED.search(content):
            diagnostics.append({"action": "continued_table_unresolved", "caption_block": caption.block_number})
            continue
        tops = [r for r in rules if 0 <= r.y - caption.bbox[3] <= 16
                and r.x0 - 3 <= caption.bbox[0] and caption.bbox[2] <= r.x1 + 3]
        if not tops:
            diagnostics.append({"action": "table_opening_rule_missing", "caption_block": caption.block_number})
            continue
        top = tops[0]
        barriers = [b.bbox[1] for b in mapping.blocks if b.bbox[1] > top.y and b.bbox[2] > top.x0 and b.bbox[0] < top.x1
                    and (_prose(texts[b.block_number]) or _TABLE.match(texts[b.block_number]))]
        limit = min(barriers, default=float("inf"))
        bottoms = [r for r in rules if top.y < r.y <= limit + 3 and abs(r.x0 - top.x0) <= 3 and abs(r.x1 - top.x1) <= 3]
        if not bottoms:
            diagnostics.append({"action": "table_closing_rule_missing", "caption_block": caption.block_number})
            continue
        bottom = bottoms[-1]
        members = []
        crossing = []
        for block in mapping.blocks:
            x0, y0, x1, y1 = block.bbox
            if y1 <= top.y or y0 >= bottom.y or x1 <= top.x0 or x0 >= top.x1:
                continue
            if x0 < top.x0 - 3 or x1 > top.x1 + 3 or y0 < top.y - 3 or y1 > bottom.y + 3:
                crossing.append(block.block_number)
            members.append(block)
        if crossing or len(members) < 2 or sum(len(re.findall(r"\d+(?:[.,]\d+)?", texts[b.block_number])) for b in members) < 4:
            diagnostics.append({"action": "table_band_ambiguous", "caption_block": caption.block_number, "crossing": crossing})
            continue
        notes = []
        tail_unresolved = None
        edge = bottom.y
        after = sorted((b for b in mapping.blocks if b.bbox[1] >= bottom.y and b.bbox[2] > top.x0 and b.bbox[0] < top.x1),
                       key=lambda b: (b.bbox[1], b.block_number))
        for block in after:
            if block.bbox[1] - edge > 12:
                break
            if not _NOTE.match(texts[block.block_number]):
                tail_unresolved = block.block_number
                break
            if block.bbox[0] < top.x0 - 3 or block.bbox[2] > top.x1 + 3:
                crossing.append(block.block_number)
                break
            notes.append(block)
            edge = block.bbox[3]
        if tail_unresolved is not None:
            diagnostics.append({"action": "table_tail_unresolved", "caption_block": caption.block_number,
                                "tail_block": tail_unresolved})
            continue
        markers = {m for b in members for m in re.findall(r"\*+|†|‡", texts[b.block_number])}
        definitions = {m for b in notes for m in re.findall(r"(?m)^\s*(\*+|†|‡)", texts[b.block_number])}
        if crossing or not markers <= definitions:
            diagnostics.append({"action": "table_notes_unresolved", "caption_block": caption.block_number,
                                "undefined_markers": sorted(markers - definitions)})
            continue
        selected = sorted([caption, *members, *notes], key=lambda b: b.page_start)
        groups.append(ProtectedGroup("closed_ruled_table_proposal", page.article_id, page.page, page.layer_id,
            tuple(b.block_number for b in selected), (caption.block_number,), tuple((b.page_start, b.page_end) for b in selected),
            (min(b.bbox[0] for b in selected), min(b.bbox[1] for b in selected),
             max(b.bbox[2] for b in selected), max(b.bbox[3] for b in selected)), ()))
        diagnostics.append({"action": "closed_ruled_table_proposal", "caption_block": caption.block_number,
            "opening_rule": top.drawing_index, "closing_rule": bottom.drawing_index,
            "note_blocks": [b.block_number for b in notes], "classification": "algorithm_proposal_not_confirmed"})
    return LayoutProtection(groups, diagnostics)
