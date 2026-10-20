"""Development-only block windows; exact source geometry, conservative fallbacks."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from app.evaluation.context_compaction import CompactionResult, ContextSlice, SourcePage
from app.generation.evidence_adequacy import LIGATURES, term_matches_text
from app.generation.providers import Evidence

VERSION = "source_block_windows_v0.1"
MAX_ANCHOR_BLOCKS = 2
NEIGHBOR_BLOCKS = 1
_CAPTION = re.compile(r"(?im)^[ \t]*(?:table|figure|fig\.|таблица|табл\.|рис\.)\s*\d+")
_CONDITION = re.compile(
    r"(?:\d\s*[°◦]\s*[CcСсКK]|±\s*\d|"
    r"\d\s*(?:wt\.?\s*%|mass\s*%|%|S/cm|mS/cm|Hz|kHz|MHz|MPa|kPa|ml|mL|мл|МПа|кПа|См/см)(?!\w)|"
    r"\b\d+(?:[.,]\d+)?\s*(?:K|h|min|hours?|minutes?|days?|ч|мин|сут|с|сек)\b|"
    r"measur|isotherm|equilibr|triplic|gravim|weight|calorim|uncertaint|standard deviation|"
    r"sample|prepared|preparation|calculated as|defined as|"
    r"измер|температур|равновес|гравим|образц|навеск|погреш|массов|рассчитыв|определя)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextBlock:
    page_start: int
    page_end: int
    bbox: tuple[float, float, float, float]
    block_number: int


@dataclass(frozen=True)
class RegisteredBlocks:
    article_id: str
    page: int
    layer_id: str
    text_sha256: str
    selected_pdf_path: str
    selected_pdf_sha256: str
    blocks: tuple[TextBlock, ...]
    diagnostic: str | None = None


@dataclass(frozen=True)
class WindowResult:
    evidence: list[Evidence]
    slices: list[ContextSlice]
    diagnostics: list[dict[str, object]]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def read_registered_blocks(page: SourcePage, selected_pdf: Path, expected_pdf_sha256: str) -> RegisteredBlocks:
    """Read original/registered OCR PDF without changing it; never fuzzy-align text.

    File/read/PDF errors propagate. An extraction-version/layout mismatch is
    represented explicitly so the selector can retain original evidence instead.
    """
    checksum = hashlib.sha256(selected_pdf.read_bytes()).hexdigest()
    if checksum != expected_pdf_sha256:
        raise ValueError("Selected-layer PDF hash differs from frozen input")
    blocks: list[TextBlock] = []
    diagnostic = None
    with fitz.open(selected_pdf) as document:
        pdf_page = document[page.page - 1]
        cursor = 0
        if pdf_page.get_text("text") != page.text:
            diagnostic = "registered_page_text_differs_from_current_pdf_extraction"
        else:
            for block in pdf_page.get_text("blocks"):
                if block[6] == 0:
                    text = block[4]
                    if not page.text.startswith(text, cursor):
                        diagnostic = "pdf_block_order_does_not_match_registered_text"
                        break
                    blocks.append(TextBlock(cursor, cursor + len(text), tuple(block[:4]), int(block[5])))
                    cursor += len(text)
            if cursor != len(page.text) and diagnostic is None:
                diagnostic = "pdf_blocks_do_not_cover_registered_text"
    return RegisteredBlocks(page.article_id, page.page, page.layer_id, _sha(page.text), str(selected_pdf.resolve()),
                            checksum, tuple(blocks), diagnostic)


def _structural_risks(text: str) -> list[str]:
    risks = []
    if _CAPTION.search(text):
        risks.append("caption_table_or_figure_boundaries_unresolved")
    numeric_lines = 0
    for line in text.splitlines():
        line = line.strip()
        if line and len(line) <= 50:
            alnum = sum(char.isalnum() for char in line)
            if alnum and sum(char.isdigit() for char in line) / alnum >= 0.5:
                numeric_lines += 1
    if numeric_lines >= 6:
        risks.append("numeric_layout_headers_rows_or_footnotes_unresolved")
    if any((unicodedata.category(char) in {"Co", "Cc"} and char not in "\n\r\t") or char == "\ufffd" for char in text):
        risks.append("damaged_or_private_use_formula_text")
    return risks


def select_block_windows(prepass: CompactionResult, pages: list[SourcePage], maps: list[RegisteredBlocks],
                         anchor_terms: list[str], *,
                         protected_ranges: dict[tuple[str, int, str], list[tuple[int, int]]] | None = None) -> WindowResult:
    """Select exact complete blocks plus condition blocks and immediate neighbors.

    This is an experimental lexical selector. Unknown layout retains the full
    fragment; no page-scope override or scientific acceptance is inferred.
    """
    output: list[Evidence] = []
    slices: list[ContextSlice] = []
    diagnostics: list[dict[str, object]] = []
    for item in prepass.evidence:
        matches = [span for span in prepass.slices if span.citation_id == item.citation_id]
        span = matches[0] if len(matches) == 1 else None
        reasons = _structural_risks(item.text)
        source_matches = [] if span is None else [p for p in pages if p.chunk_id == span.chunk_id and p.layer_id == span.layer_id
                                                  and p.article_id == span.article_id and p.page == span.page]
        source = source_matches[0] if len(source_matches) == 1 else None
        proven_span = (span is not None and source is not None and span.article_id == item.article_id
                       and span.chunk_id == item.chunk_id and span.page == item.page_start == item.page_end
                       and 0 <= span.page_start < span.page_end <= len(source.text)
                       and span.chunk_start >= 0 and span.text_layer == source.text_layer
                       and span.pdf_path == source.pdf_path and span.pdf_sha256 == source.pdf_sha256
                       and span.chunk_end - span.chunk_start == len(item.text)
                       and _sha(item.text) == span.text_sha256
                       and item.text == source.text[span.page_start:span.page_end])
        mapping_matches = [] if source is None else [m for m in maps if m.article_id == source.article_id
                                                     and m.page == source.page and m.layer_id == source.layer_id]
        mapping = mapping_matches[0] if len(mapping_matches) == 1 else None
        protected: list[tuple[int, int]] = []
        if protected_ranges is not None and proven_span and source is not None and mapping is not None and span is not None:
            proposed = protected_ranges.get((source.article_id, source.page, source.layer_id), [])
            block_ranges = {(block.page_start, block.page_end) for block in mapping.blocks}
            if any(start < 0 or start >= end or end > len(source.text) or (start, end) not in block_ranges for start, end in proposed):
                reasons.append("protected_layout_range_not_an_exact_block")
            else:
                protected = proposed
                # Risk analysis only: outgoing source text is never masked or repaired.
                shadow = list(item.text)
                for start, end in protected:
                    first, last = max(start, span.page_start) - span.page_start, min(end, span.page_end) - span.page_start
                    if first < last:
                        shadow[first:last] = [" "] * (last - first)
                reasons = _structural_risks("".join(shadow))
        if (not proven_span or source is None or mapping is None or mapping.diagnostic is not None
                or mapping.text_sha256 != _sha(source.text)):
            reasons.append("source_geometry_not_proven" if mapping is None or mapping.diagnostic is None else mapping.diagnostic)
        units: list[tuple[int, int, TextBlock]] = []
        if not reasons and span is not None and mapping is not None and source is not None:
            cursor = 0
            for block in mapping.blocks:
                if block.page_start != cursor or block.page_end <= block.page_start or block.page_end > len(source.text):
                    reasons.append("block_registry_has_gap_overlap_or_invalid_range")
                    break
                cursor = block.page_end
                start, end = max(block.page_start, span.page_start), min(block.page_end, span.page_end)
                if start >= end:
                    continue
                if (source.text[block.page_start:start].strip() or source.text[end:block.page_end].strip()):
                    reasons.append("prepass_boundary_cuts_nonwhitespace_pdf_block")
                    break
                if source.text[start:end].strip():
                    units.append((start, end, block))
            if cursor != len(source.text):
                reasons.append("block_registry_does_not_cover_page")
        if reasons:
            citation = f"W{len(output) + 1}"
            output.append(replace(item, citation_id=citation))
            if span is not None and proven_span:
                slices.append(replace(span, citation_id=citation))
            diagnostics.append({"citation_id": citation, "prepass_citation_id": item.citation_id,
                                "action": "retain_full_fragment", "reasons": reasons,
                                "cross_page_relations": "not_resolved"})
            continue
        assert source is not None and span is not None
        hits: dict[int, list[str]] = {}
        conditions: set[int] = set()
        layout: set[int] = set()
        for index, (start, end, _) in enumerate(units):
            normalized = source.text[start:end].lower().translate(LIGATURES)
            hits[index] = sorted({term for term in anchor_terms if term.strip()
                                  and term_matches_text(term.lower().translate(LIGATURES), normalized)})
            if _CONDITION.search(source.text[start:end]):
                conditions.add(index)
            if any(left <= start and end <= right for left, right in protected):
                layout.add(index)
        anchors = sorted((index for index in hits if hits[index]), key=lambda index: (-len(hits[index]), index))[:MAX_ANCHOR_BLOCKS]
        seeds = set(anchors) | conditions | layout
        selected = {index for seed in seeds for index in range(max(0, seed - NEIGHBOR_BLOCKS),
                                                               min(len(units), seed + NEIGHBOR_BLOCKS + 1))}
        for index, (start, end, block) in enumerate(units):
            why = []
            if index in anchors:
                why.append("ranked_query_anchor")
            if index in conditions:
                why.append("measurement_or_condition_heuristic")
            if index in layout:
                why.append("protected_layout_group")
            if index in selected and index not in seeds:
                why.append("adjacent_block")
            diagnostics.append({"prepass_citation_id": item.citation_id, "action": "retain_block" if index in selected else "omit_block",
                                "page_start": start, "page_end": end, "block_number": block.block_number,
                                "bbox": list(block.bbox), "matched_terms": hits[index], "reasons": why,
                                "text_sha256": _sha(source.text[start:end]), "classification": "algorithm_proposal_not_confirmed"})
        if not selected:
            diagnostics.append({"prepass_citation_id": item.citation_id, "action": "no_window_selected",
                                "reason": "no_lexical_or_condition_anchor_not_evidence_of_absence"})
        ranges: list[tuple[int, int]] = []
        for index in sorted(selected):
            start, end, _ = units[index]
            if ranges and not source.text[ranges[-1][1]:start].strip():
                ranges[-1] = (ranges[-1][0], end)
            else:
                ranges.append((start, end))
        for start, end in ranges:
            citation = f"W{len(output) + 1}"
            chunk_start = span.chunk_start + start - span.page_start
            chunk_end = span.chunk_start + end - span.page_start
            output.append(replace(item, citation_id=citation, text=source.text[start:end]))
            slices.append(replace(span, citation_id=citation,
                                  chunk_start=chunk_start, chunk_end=chunk_end, page_start=start, page_end=end,
                                  text_sha256=_sha(source.text[start:end])))
            diagnostics.append({"citation_id": citation, "prepass_citation_id": item.citation_id, "action": "window_emitted",
                                "page_start": start, "page_end": end, "cross_page_relations": "not_resolved"})
    return WindowResult(output, slices, diagnostics)
