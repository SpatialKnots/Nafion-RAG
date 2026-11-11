"""Recover raw information lost by approximate deduplication on refused preparations."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from app.generation.providers import Evidence
from app.retrieval.source_reference import reference

VERSION = 'retrieved_raw_preservation_v0.1'


def _text(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip()


def recover(question: str, pool: Sequence[Evidence], display_pool: Sequence[Evidence],
            kept: Sequence[Evidence], display_kept: Sequence[Evidence], *,
            layers: Mapping[str, str], reference_metadata: object) -> tuple[list[Evidence], list[Evidence], dict[str, Any]] | None:
    """Preserve old admission: only sources already in the request-local retrieval pool."""
    citation = reference(question)
    if citation is None or not isinstance(reference_metadata, Mapping):
        return None
    article_id = reference_metadata.get('article_id')
    if (reference_metadata.get('resolved') is not True or reference_metadata.get('matching_article_ids') != [article_id]
            or reference_metadata.get('surname') != citation.surname or str(reference_metadata.get('year')) != citation.year
            or not pool or not kept or any(e.article_id != article_id for e in (*pool, *kept))):
        return None
    if re.fullmatch(re.escape(citation.surname) + r'\s*\(' + citation.year + r'\)',
                    question[citation.start:citation.end]) is None:
        return None
    if len(pool) != len(display_pool) or len(kept) != len(display_kept):
        raise ValueError('Raw/display evidence pairing differs')
    originals = {}
    for item, display in zip(pool, display_pool, strict=True):
        if (item.article_id, item.chunk_id) != (display.article_id, display.chunk_id):
            raise ValueError('Raw/display evidence identity differs')
        if item.chunk_id in originals:
            raise ValueError('Conflicting or repeated input chunk identity')
        originals[item.chunk_id] = item
    if any(e.chunk_id not in originals or e.text != originals[e.chunk_id].text for e in kept):
        return None
    if any(not layers.get(e.chunk_id) for e in pool):
        return None
    result, displays, restored, redundant = list(kept), list(display_kept), [], []
    present = {e.chunk_id for e in kept}
    for item, display in zip(pool, display_pool, strict=True):
        if item.chunk_id in present:
            continue
        compatible = [e for e in result if e.article_id == item.article_id and e.source_type == item.source_type
                      and layers[e.chunk_id] == layers[item.chunk_id]
                      and e.page_start <= item.page_end and e.page_end >= item.page_start]
        ordered = sorted(compatible, key=lambda e: (e.page_start, e.page_end, e.chunk_id))
        pages = {p for e in ordered for p in range(e.page_start, e.page_end + 1)}
        target_pages = set(range(item.page_start, item.page_end + 1))
        covered = bool(_text(item.text)) and target_pages <= pages and _text(item.text) in _text('\n'.join(e.text for e in ordered))
        if covered:
            redundant.append({'chunk_id': item.chunk_id, 'reason': 'literal_text_and_page_coverage_already_preserved'})
            continue
        result.append(item)
        displays.append(display)
        present.add(item.chunk_id)
        restored.append({'chunk_id': item.chunk_id, 'article_id': item.article_id,
            'page_start': item.page_start, 'page_end': item.page_end, 'source_type': item.source_type,
            'text_layer': layers[item.chunk_id], 'raw_text_sha256': hashlib.sha256(item.text.encode()).hexdigest(),
            'reason': 'full_literal_information_not_proven_redundant'})
    if not restored:
        return None
    if len(result) > len(pool) or sum(len(e.text) for e in result) > sum(len(e.text) for e in pool):
        raise ValueError('Recovered evidence exceeds existing pre-deduplication pool budget')
    return ([replace(e, citation_id=f'E{i}') for i, e in enumerate(result, 1)],
            [replace(e, citation_id=f'E{i}') for i, e in enumerate(displays, 1)],
            {'version': VERSION, 'original_pool_count': len(pool), 'previous_kept_count': len(kept),
             'final_kept_count': len(result), 'original_pool_chars': sum(len(e.text) for e in pool),
             'final_kept_chars': sum(len(e.text) for e in result), 'restored': restored, 'proven_redundant': redundant,
             'baseline_admission_chunk_ids': [e.chunk_id for e in kept], 'automatic_reassessment': False,
             'new_retrieval_executed': False, 'admission_changed': False, 'scientific_support': 'not_evaluated'})
