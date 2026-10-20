"""Exact-block layout protection proposals, never table reconstruction or gold labels."""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass

from app.evaluation.context_compaction import SourcePage
from app.evaluation.context_windows import RegisteredBlocks, TextBlock

VERSION = "source_layout_groups_v0.1"
EDGE_TOLERANCE = 3.0
MIN_PROSE_WORDS = 25
_MARKER = re.compile(r"(?im)^[ \t]*(?:table|figure|fig\.|таблица|табл\.|рис\.)\s*\d+")
_CAPTION = re.compile(r"(?i)^\s*(?:table|figure|fig\.|таблица|табл\.|рис\.)\s*\d+(?:\.\d+)*[.:](?:\s|$)")
_NOTE = re.compile(r"(?i)^\s*(?:[*†‡]|notes?\b|примечани\w*\b|[a-zа-я]\))")
_CONTINUED = re.compile(r"(?i)\b(?:continued|continuation|продолжени\w*|окончани\w*)")


@dataclass(frozen=True)
class ProtectedGroup:
    kind: str
    article_id: str
    page: int
    layer_id: str
    block_numbers: tuple[int, ...]
    caption_blocks: tuple[int, ...]
    page_ranges: tuple[tuple[int, int], ...]
    bbox: tuple[float, float, float, float]
    context_blocks: tuple[int, ...]


@dataclass(frozen=True)
class LayoutProtection:
    groups: list[ProtectedGroup]
    diagnostics: list[dict[str, object]]


def _damaged(text: str) -> bool:
    return any((unicodedata.category(char) in {"Co", "Cc"} and char not in "\r\n\t") or char == "\ufffd" for char in text)


def _prose(text: str) -> bool:
    return (len(re.findall(r"[^\W\d_]+", text)) >= MIN_PROSE_WORDS
            and text.rstrip().rstrip('"”’»').endswith((".", "!", "?"))
            and not _MARKER.search(text) and not _NOTE.match(text) and not _damaged(text))


def _overlap(a: TextBlock, b: TextBlock) -> bool:
    overlap = min(a.bbox[2], b.bbox[2]) - max(a.bbox[0], b.bbox[0])
    return overlap >= 0.5 * min(a.bbox[2] - a.bbox[0], b.bbox[2] - b.bbox[0])


def propose_layout_groups(page: SourcePage, mapping: RegisteredBlocks) -> LayoutProtection:
    """Protect spatially enclosed caption groups and complete inline-reference blocks.

    All groups are proposals. Missing/open/crossing enclosures remain diagnostics,
    never grounds to remove the existing broad source protection.
    """
    diagnostics: list[dict[str, object]] = []
    valid = (page.page >= 1 and bool(page.article_id) and bool(page.layer_id)
             and mapping.article_id == page.article_id and mapping.page == page.page and mapping.layer_id == page.layer_id
             and mapping.diagnostic is None and mapping.text_sha256 == hashlib.sha256(page.text.encode()).hexdigest())
    cursor = 0
    numbers = set()
    for block in mapping.blocks:
        valid = valid and (block.page_start == cursor and block.page_start < block.page_end <= len(page.text)
                           and all(math.isfinite(value) for value in block.bbox)
                           and block.bbox[0] < block.bbox[2] and block.bbox[1] < block.bbox[3]
                           and block.block_number not in numbers)
        cursor = block.page_end
        numbers.add(block.block_number)
    if not valid or cursor != len(page.text):
        return LayoutProtection([], [{"action": "layout_geometry_not_proven", "page": page.page,
                                      "article_id": page.article_id, "diagnostic": mapping.diagnostic}])
    text = {block.block_number: page.text[block.page_start:block.page_end] for block in mapping.blocks}
    prose = [block for block in mapping.blocks if _prose(text[block.block_number])]
    groups: dict[tuple[int, ...], ProtectedGroup] = {}
    for caption in mapping.blocks:
        content = text[caption.block_number]
        marker = _MARKER.search(content)
        if marker is None:
            continue
        prefix = content[:marker.start()].strip()
        if (prefix and not prefix.endswith((".", "!", "?", ":", ";"))
                and not _CAPTION.match(content[marker.start():])
                and len(re.findall(r"[^\W\d_]+", content)) >= MIN_PROSE_WORDS):
            group = ProtectedGroup("inline_caption_reference_proposal", page.article_id, page.page, page.layer_id,
                                   (caption.block_number,), (), ((caption.page_start, caption.page_end),), caption.bbox, ())
            groups[group.block_numbers] = group
            continue
        if not _CAPTION.match(content):
            diagnostics.append({"action": "caption_style_unresolved", "block_number": caption.block_number})
            continue
        if _CONTINUED.search(content):
            diagnostics.append({"action": "continued_caption_unresolved", "block_number": caption.block_number})
            continue
        above = [block for block in prose if block.bbox[3] <= caption.bbox[1] and _overlap(block, caption)]
        below = [block for block in prose if block.bbox[1] >= caption.bbox[3] and _overlap(block, caption)]
        if not above or not below:
            diagnostics.append({"action": "caption_enclosure_open", "block_number": caption.block_number})
            continue
        left = max(above, key=lambda block: (block.bbox[3], -block.block_number))
        right = min(below, key=lambda block: (block.bbox[1], block.block_number))
        x0, x1 = max(left.bbox[0], right.bbox[0]), min(left.bbox[2], right.bbox[2])
        y0, y1 = left.bbox[3], right.bbox[1]
        if not _overlap(left, right) or x1 <= x0 or y1 <= y0:
            diagnostics.append({"action": "caption_column_enclosure_unresolved", "block_number": caption.block_number})
            continue
        members = []
        crossing = []
        for block in mapping.blocks:
            if block.block_number in {left.block_number, right.block_number}:
                continue
            bx0, by0, bx1, by1 = block.bbox
            if bx1 <= x0 or bx0 >= x1 or by1 <= y0 or by0 >= y1:
                continue
            if (bx0 < x0 - EDGE_TOLERANCE or bx1 > x1 + EDGE_TOLERANCE or by0 < y0 - EDGE_TOLERANCE
                    or by1 > y1 + EDGE_TOLERANCE or block in prose):
                crossing.append(block.block_number)
            members.append(block)
        if crossing or caption not in members:
            diagnostics.append({"action": "caption_enclosure_ambiguous", "block_number": caption.block_number,
                                "crossing_blocks": crossing})
            continue
        # Include both complete enclosing paragraphs, not just the caption/rows.
        selected = sorted([left, *members, right], key=lambda block: block.page_start)
        numbers_tuple = tuple(block.block_number for block in selected)
        caption_numbers = tuple(block.block_number for block in members if _CAPTION.match(text[block.block_number]))
        groups[numbers_tuple] = ProtectedGroup("prose_enclosed_caption_group_proposal", page.article_id, page.page, page.layer_id,
            numbers_tuple, caption_numbers, tuple((block.page_start, block.page_end) for block in selected),
            (min(block.bbox[0] for block in selected), min(block.bbox[1] for block in selected),
             max(block.bbox[2] for block in selected), max(block.bbox[3] for block in selected)),
            (left.block_number, right.block_number))
    for group in groups.values():
        diagnostics.append({"action": "protected_layout_proposal", "kind": group.kind,
                            "block_numbers": list(group.block_numbers), "classification": "algorithm_proposal_not_confirmed",
                            "visual_content": "not_serialized", "cross_page_relations": "not_resolved"})
    return LayoutProtection(list(groups.values()), diagnostics)
