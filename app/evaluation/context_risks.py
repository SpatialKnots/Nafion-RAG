"""Diagnostic spatial relations for whole-block contexts; never an admission gate."""

from __future__ import annotations

import json
from typing import Any

from app.evaluation.context_windows import RegisteredBlocks, TextBlock, _structural_risks
from app.evaluation.layout_groups import _NOTE, ProtectedGroup
from app.evaluation.source_gaps import VERSION as VISUAL_VERSION
from app.evaluation.source_gaps import _intersects, _valid
from app.generation.block_context import VERSION as PARENT_VERSION
from app.generation.block_context import build_block_context, full_coverage
from app.records.article_windows import MAX_CONTEXT_CHARS, protected_intervals
from app.records.schema import SourceRegion, text_hash

VERSION = 'query_context_risks_v0.1'


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _windows(mapping: RegisteredBlocks, groups: list[ProtectedGroup], retained: set[int]) -> list[dict[str, Any]]:
    """Same whole-core, one-neighbor and protected closure as the existing planner.

    Unlike the planner, these windows also describe deferred pages. They are
    diagnostic scopes only; no candidate evidence or replacement plan is made.
    """
    protected = protected_intervals(mapping, groups)
    starts = dict(protected)
    windows: dict[tuple[int, int], dict[str, Any]] = {}
    first = 0
    while first < len(mapping.blocks):
        core_first = first
        last = starts.get(first, first)
        core = mapping.blocks[first:last + 1]
        first = last + 1
        if not any(b.block_number in retained for b in core):
            continue
        left, right = max(0, core_first - 1), min(len(mapping.blocks) - 1, last + 1)
        while True:
            before = left, right
            for begin, finish in protected:
                if begin <= right and finish >= left:
                    left, right = min(left, begin), max(right, finish)
            if before == (left, right):
                break
        key = left, right
        if key not in windows:
            windows[key] = {'start': mapping.blocks[left].page_start, 'end': mapping.blocks[right].page_end,
                            'block_numbers': [b.block_number for b in mapping.blocks[left:right + 1]], 'core_blocks': []}
        windows[key]['core_blocks'].extend(b.block_number for b in core)
    return list(windows.values())


def _visual_identity(raw: dict[str, Any], region: SourceRegion) -> bool:
    if not raw:
        return False
    expected = {'version': VISUAL_VERSION, 'article_id': str(region.article_id), 'page': region.page_number,
                'layer_id': str(region.text_layer_id), 'text_layer': region.text_layer,
                'text_sha256': region.page_text_sha256, 'original_pdf_path': region.layer_pdf_path,
                'original_pdf_sha256': region.layer_pdf_sha256, 'selected_pdf_path': region.layer_pdf_path,
                'selected_pdf_sha256': region.layer_pdf_sha256,
                'coordinate_system': 'unrotated_selected_pdf_pymupdf_points'}
    if any(raw.get(k) != v for k, v in expected.items()):
        raise ValueError('Context risk visual registry differs from exact selected source identity')
    return bool(raw['text_geometry_proven']) and not raw['diagnostics']


def audit_context_risks(parent: dict[str, Any]) -> dict[str, Any]:
    """Localize observed triggers/geometry without declaring distant evidence irrelevant.

    Input registries must be hash-bound by the runner; live PDF registration is
    separately compared there. A trigger location never establishes its semantic
    extent, and geometry disjointness never grants scientific exclusion.
    """
    if parent['version'] != PARENT_VERSION or any(parent[k] for k in (
            'generation_performed', 'external_request_constructed', 'network_ready')):
        raise ValueError('Context risk audit requires preserved no-generation block preparation')
    plans = {p['parent_region_id']: p['plan'] for p in parent['pages']}
    replay = build_block_context(parent['baseline'], plans)
    if canonical(replay) != canonical(parent):
        raise ValueError('Context risk parent differs from deterministic block replay')
    regions = {r['region_id']: SourceRegion.model_validate(r) for r in parent['baseline']['sources']['pages'].values()}
    anchored = {p['article_id'] for p in parent['pages'] if any(b['anchor_hits'] for b in p['blocks'])}
    pages = []
    for page in parent['pages']:
        region = regions[page['parent_region_id']]
        plan = page['plan']
        raw = plan['mapping']
        mapping = RegisteredBlocks(raw['article_id'], raw['page'], raw['layer_id'], raw['text_sha256'],
            raw['selected_pdf_path'], raw['selected_pdf_sha256'], tuple(TextBlock(**b) for b in raw['blocks']), raw.get('diagnostic'))
        groups = [ProtectedGroup(**{**g, 'block_numbers': tuple(g['block_numbers']),
            'caption_blocks': tuple(g['caption_blocks']), 'context_blocks': tuple(g['context_blocks']),
            'page_ranges': tuple(tuple(r) for r in g['page_ranges']), 'bbox': tuple(g['bbox'])})
            for g in plan['protected_groups']]
        visual = plan.get('source_gaps', {})
        visual_proven = _visual_identity(visual, region)
        mapping_unproven = bool(mapping.diagnostic) or any(d in plan['diagnostics'] for d in (
            'block_registry_gap_overlap_or_invalid_range', 'invalid_block_geometry', 'block_registry_does_not_cover_page_exactly'))
        triggers = []
        for b in mapping.blocks:
            quote = region.page_text[b.page_start:b.page_end]
            kinds = _structural_risks(quote)
            if _NOTE.match(quote):
                kinds.append('note_or_footnote_lexical_trigger')
            for kind in kinds:
                triggers.append({'kind': kind, 'block_number': b.block_number, 'start': b.page_start, 'end': b.page_end,
                                 'quote': quote, 'quote_sha256': text_hash(quote), 'extent': 'trigger_block_only_semantic_extent_unknown'})
        retained = {b['block_number'] for b in page['blocks'] if b['retention_reasons']} if page['article_id'] in anchored else set()
        windows = [] if mapping_unproven else _windows(mapping, groups, retained)
        by_number = {b.block_number: b for b in mapping.blocks}
        for window in windows:
            start, end = window['start'], window['end']
            numbers = set(window['block_numbers'])
            selected_groups = [g for g in groups if numbers.intersection((*g.block_numbers, *g.context_blocks))]
            boxes = [by_number[n].bbox for n in numbers] + [g.bbox for g in selected_groups]
            relations = []
            for asset in visual.get('assets', []):
                box = tuple(asset['bbox'])
                if not visual_proven or not asset['geometry_valid'] or not _valid(box):
                    relation = 'unknown_geometry'
                elif any(_intersects(box, b) for b in boxes):
                    relation = 'intersects_selected_or_protected_geometry'
                else:
                    relation = 'outside_selected_geometry_relevance_unknown'
                relations.append({'asset_id': asset['asset_id'], 'relation': relation})
            quote = region.page_text[start:end]
            window.update(context_id=text_hash(canonical([VERSION, region.region_id, start, end])),
                quote=quote, quote_sha256=text_hash(quote), state='diagnostic_window_not_candidate',
                protected_groups=[g.kind for g in selected_groups], asset_relations=relations,
                trigger_relations=[{'trigger_index': i, 'relation': 'intersects_selected_text' if
                    max(start, t['start']) < min(end, t['end']) else 'outside_selected_text_extent_unknown'}
                    for i, t in enumerate(triggers)],
                complete_page_coverage=full_coverage(region.page_text, [(start, end)]),
                exceeds_existing_character_ceiling=len(quote) > MAX_CONTEXT_CHARS,
                scientific_relevance='not_evaluated')
        located_kinds = {t['kind'] for t in triggers}
        # Page-level counts and unresolved boundaries cannot be converted into
        # absence merely because no individual block reproduces the detector.
        unlocalized = [d for d in page['diagnostics'] if d not in located_kinds]
        pages.append({'source': region.model_dump(mode='json'), 'parent_diagnostics': page['diagnostics'],
            'unlocalized_page_diagnostics': unlocalized, 'mapping_unproven': mapping_unproven,
            'visual_geometry_proven': visual_proven, 'retained_core_block_numbers': sorted(retained),
            'text_triggers': triggers, 'visual_registry': visual, 'windows': windows,
            'diagnostic_windows_assemble_complete_page': full_coverage(region.page_text,
                [(w['start'], w['end']) for w in windows]), 'scientific_exclusion_proven': False})
    return {'version': VERSION, 'parent_sha256': text_hash(canonical(parent)),
        'question': parent['baseline']['question'], 'parent_blocking_reasons': parent['blocking_reasons'],
        'parent_assembled_complete_pages': parent['assembled_complete_pages'], 'pages': pages,
        'selection_changed': False, 'admission_changed': False, 'scientific_exclusion_proven': False,
        'generation_performed': False, 'external_request_constructed': False, 'network_ready': False}
