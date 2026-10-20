"""Opt-in, offline source-page compaction. Never a scientific relevance classifier.

Retained text is an exact contiguous chunk slice. Ambiguous source alignment and
bibliography classification retain the input with diagnostics. This conservative
prepass does not promise sentence-level context or permission to transmit pages.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace

from app.generation.providers import Evidence, _clean_generation_evidence_text

VERSION = "source_page_compaction_v0.1"
_REFERENCE_START = re.compile(r"(?m)^\s*(\d{1,4})[.)]\s+(?=[A-ZА-ЯЁ])")
_YEAR = re.compile(r"\b(?:18|19|20)\d{2}\b")
_HEADING = re.compile(r"(?im)^[ \t]*(?:references|bibliography|список литературы|библиографический список)[ \t]*$")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourcePage:
    article_id: str
    chunk_id: str
    page: int
    text_layer: str
    layer_id: str
    text: str
    pdf_path: str
    pdf_sha256: str


@dataclass(frozen=True)
class ContextSlice:
    citation_id: str
    input_citation_id: str
    chunk_id: str
    article_id: str
    page: int
    text_layer: str
    layer_id: str
    pdf_path: str
    pdf_sha256: str
    chunk_start: int
    chunk_end: int
    page_start: int
    page_end: int
    text_sha256: str


@dataclass(frozen=True)
class CompactionResult:
    evidence: list[Evidence]
    slices: list[ContextSlice]
    diagnostics: list[dict[str, object]]


def _bibliography_boundary(text: str) -> tuple[int | None, str]:
    heading = _HEADING.search(text)
    if heading is not None:
        return heading.start(), "explicit_reference_heading_heuristic"
    starts = list(_REFERENCE_START.finditer(text))
    if len(starts) < 3:
        return None, "bibliography_not_established"
    numbers = [int(match.group(1)) for match in starts]
    if any(right != left + 1 for left, right in zip(numbers, numbers[1:], strict=False)):
        return None, "ambiguous_numbered_blocks_retained"
    ends = [match.start() for match in starts[1:]] + [len(text)]
    blocks = [text[start.start():end] for start, end in zip(starts, ends, strict=True)]
    # Deliberately narrow dissertation-style reference grammar. Numeric tables,
    # prose citations and other reference styles must not be forced into it.
    if not all("//" in block and _YEAR.search(block) for block in blocks):
        return None, "ambiguous_numbered_blocks_retained"
    prefix = text[:starts[0].start()].strip()
    if prefix and not prefix.isdecimal() and not ("//" in prefix and _YEAR.search(prefix)):
        return None, "ambiguous_reference_prefix_retained"
    if starts[0].start() > len(text) * 0.2:
        return None, "ambiguous_reference_prefix_retained"
    return 0, "sequential_reference_page_heuristic"


def compact_source_pages(evidence: list[Evidence], pages: list[SourcePage]) -> CompactionResult:
    """Remove verified repeated pages and narrow reference heuristics, without a model.

    Alignment accepts only whitespace separators/edge trimming. Missing, duplicate
    or partial page mappings retain the original chunk and receive diagnostics.
    Output citation IDs are new development IDs; production IDs are never edited.
    """
    output: list[Evidence] = []
    slices: list[ContextSlice] = []
    diagnostics: list[dict[str, object]] = []
    seen: dict[tuple[str, str, int, str, str, str], str] = {}
    for item in evidence:
        source = sorted((page for page in pages if page.chunk_id == item.chunk_id), key=lambda page: page.page)
        ranges: list[tuple[SourcePage, int, int, int]] = []
        cursor = 0
        valid = bool(source) and item.source_type != "table_derived"
        valid = valid and [page.page for page in source] == list(range(item.page_start, item.page_end + 1))
        for page in source:
            content = page.text.strip()
            start = item.text.find(content, cursor) if content else -1
            if (page.article_id != item.article_id or not page.text_layer or not page.layer_id
                    or not page.pdf_path or not page.pdf_sha256 or start < 0 or item.text[cursor:start].strip()):
                valid = False
                break
            ranges.append((page, start, start + len(content), len(page.text) - len(page.text.lstrip())))
            cursor = start + len(content)
        valid = valid and not item.text[cursor:].strip()
        if not valid:
            output.append(replace(item, citation_id=f"C{len(output) + 1}"))
            diagnostics.append({"input_citation_id": item.citation_id, "action": "retain_unaligned_chunk",
                                "reason": "source_page_alignment_not_proven", "chunk_id": item.chunk_id})
            continue
        for page, start, end, page_start in ranges:
            original_end = end
            boundary, reason = _bibliography_boundary(item.text[start:end])
            if boundary is not None:
                end = start + boundary
                diagnostics.append({"input_citation_id": item.citation_id, "page": page.page,
                                    "action": "omit_reference_candidate", "reason": reason,
                                    "chunk_start": end, "chunk_end": original_end,
                                    "omitted_sha256": _sha(item.text[end:original_end]),
                                    "classification": "algorithm_proposal_not_confirmed"})
            else:
                diagnostics.append({"input_citation_id": item.citation_id, "page": page.page,
                                    "action": "retain_nonreference_or_unknown", "reason": reason})
            if not item.text[start:end].strip():
                continue
            key = (page.article_id, page.text_layer, page.page, _sha(item.text[start:end]), page.layer_id, page.pdf_sha256)
            if key in seen:
                diagnostics.append({"input_citation_id": item.citation_id, "page": page.page,
                                    "action": "omit_exact_duplicate_page", "retained_citation_id": seen[key],
                                    "chunk_start": start, "chunk_end": end, "omitted_sha256": key[3]})
                continue
            citation_id = f"C{len(output) + 1}"
            seen[key] = citation_id
            output.append(replace(item, citation_id=citation_id, text=item.text[start:end],
                                  page_start=page.page, page_end=page.page))
            slices.append(ContextSlice(citation_id, item.citation_id, item.chunk_id, item.article_id,
                                       page.page, page.text_layer, page.layer_id, page.pdf_path, page.pdf_sha256,
                                       start, end, page_start, page_start + end - start, key[3]))
    return CompactionResult(output, slices, diagnostics)


def complete_pages_in_request(request_user_text: str, pages: list[SourcePage]) -> list[dict[str, object]]:
    """Check the actual formatter's whitespace-normalized page text, conservatively.

    This is a literal full-page scope guard, not a claim about semantic coverage,
    leakage prevention, or a guarantee that shorter context is adequate.
    """
    submitted = _clean_generation_evidence_text(request_user_text)
    matches: dict[tuple[str, str, int, str], dict[str, object]] = {}
    for page in pages:
        normalized = _clean_generation_evidence_text(page.text)
        if normalized and normalized in submitted:
            key = (page.article_id, page.text_layer, page.page, _sha(page.text))
            matches[key] = {"article_id": page.article_id, "text_layer": page.text_layer,
                            "page": page.page, "text_sha256": key[3]}
    return list(matches.values())


def require_no_complete_pages(request_user_text: str, pages: list[SourcePage]) -> None:
    if not pages:
        raise ValueError("Full-page scope guard requires a nonempty verified source-page registry")
    matches = complete_pages_in_request(request_user_text, pages)
    if matches:
        raise ValueError(f"Full-page scope guard blocked request: {len(matches)} complete source pages; no API call permitted")
