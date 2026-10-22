"""Whole registered PDF-block proposals with explicit omissions and no generation."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from app.evaluation.context_compaction import SourcePage, complete_pages_in_request
from app.evaluation.context_windows import _CONDITION, RegisteredBlocks, TextBlock, read_registered_blocks
from app.evaluation.layout_groups import ProtectedGroup, propose_layout_groups
from app.evaluation.query_packet import MAX_BYTES, aligned_pages
from app.evaluation.ruled_tables import propose_ruled_tables, read_registered_rules
from app.evaluation.source_gaps import read_source_gaps
from app.generation.preparation import VERSION as BASELINE_VERSION
from app.generation.providers import Evidence
from app.generation.query_qualifiers import assess_query_qualifiers, extract_qualifiers, occurrences
from app.records.article_windows import plan_page
from app.records.condition_multilingual import source_events
from app.records.schema import SourceRegion, source_identity, text_hash

VERSION = 'query_block_context_v0.1'


def full_coverage(text: str, intervals: list[tuple[int, int]]) -> bool:
    """Union coverage includes overlaps; whitespace-only gaps do not evade page scope."""
    cursor = 0
    for start, end in sorted(intervals):
        if not 0 <= start < end <= len(text):
            raise ValueError('Block context interval outside registered source page')
        if start > cursor and text[cursor:start].strip():
            return False
        cursor = max(cursor, end)
    return bool(intervals) and not text[cursor:].strip()


def page_plan(region: SourceRegion) -> dict[str, Any]:
    page = SourcePage(str(region.article_id), region.region_id, region.page_number, region.text_layer,
                      str(region.text_layer_id), region.page_text, region.layer_pdf_path, region.layer_pdf_sha256)
    mapping = read_registered_blocks(page, Path(region.layer_pdf_path), region.layer_pdf_sha256)
    layout = propose_layout_groups(page, mapping)
    groups = list(layout.groups)
    table_diagnostics: list[dict[str, object]] = []
    if mapping.diagnostic is None:
        tables = propose_ruled_tables(page, mapping, read_registered_rules(page, mapping))
        groups.extend(tables.groups)
        table_diagnostics = tables.diagnostics
    planned = plan_page(region, mapping, groups)
    planned.update(layout_diagnostics=layout.diagnostics, table_diagnostics=table_diagnostics,
                   source_gaps=asdict(read_source_gaps(page, mapping)))
    return planned


def _region(parent: SourceRegion, start: int, end: int) -> SourceRegion:
    raw = parent.model_dump()
    raw.update(start=start, end=end, quote=parent.page_text[start:end], quote_sha256=text_hash(parent.page_text[start:end]),
               selection_basis='retrieval', selection_note=f'{VERSION}: whole block proposal; scientific adequacy not established.')
    raw['region_id'] = source_identity(raw)
    return SourceRegion.model_validate(raw)


def build_block_context(baseline: dict[str, Any], plans: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Keep baseline intact; propose exact whole-block windows without semantic repairs.

    Plans may be supplied only for frozen offline replay/tests. Live callers use
    current registered PDF geometry and its source hashes. All deferred pages and
    unselected block ranges remain in local accounting, never labelled irrelevant.
    """
    if baseline['version'] != BASELINE_VERSION or baseline['generation_performed'] or baseline['external_request_constructed']:
        raise ValueError('Block context requires an explicit no-generation preparation baseline')
    evidence = [Evidence(**e) for e in baseline['evidence']]
    regions = [SourceRegion.model_validate(r) for r in baseline['sources']['pages'].values()]
    if len({r.region_id for r in regions}) != len(regions):
        raise ValueError('Block context source pages must be unique')
    if plans is not None and set(plans) != {r.region_id for r in regions}:
        raise ValueError('Block context supplied plan inventory differs from registered pages')
    qualifiers, _ = extract_qualifiers(baseline['question'])
    aliases = sorted({alias for q in qualifiers if q.kind != 'article' for alias in q.aliases})
    pages: list[dict[str, Any]] = []
    candidate: list[Evidence] = []
    proposals: list[dict[str, Any]] = []
    all_intervals: dict[str, list[tuple[int, int]]] = {}
    bound = {e.chunk_id: aligned_pages(e, [r for r in regions if str(r.article_id) == e.article_id
        and e.page_start <= r.page_number <= e.page_end and r.text_layer == baseline['sources']['chunk_layers'].get(e.chunk_id)],
        baseline['sources']['chunk_layers'].get(e.chunk_id)) for e in evidence}
    pending: list[tuple[SourceRegion, list[Evidence], dict[str, Any]]] = []
    for parent in regions:
        planned = page_plan(parent) if plans is None else plans[parent.region_id]
        # Re-validate supplied plan geometry and source identities, not just quoted text.
        raw = planned['mapping']
        mapping = RegisteredBlocks(raw['article_id'], raw['page'], raw['layer_id'], raw['text_sha256'],
            raw['selected_pdf_path'], raw['selected_pdf_sha256'], tuple(TextBlock(**b) for b in raw['blocks']), raw.get('diagnostic'))
        if (mapping.article_id, mapping.page, mapping.layer_id, mapping.text_sha256,
                mapping.selected_pdf_sha256, Path(mapping.selected_pdf_path).resolve()) != (
                str(parent.article_id), parent.page_number, str(parent.text_layer_id), parent.page_text_sha256,
                parent.layer_pdf_sha256, Path(parent.layer_pdf_path).resolve()):
            raise ValueError('Block plan differs from exact registered page/layer/PDF identity')
        groups = [ProtectedGroup(**{**g, 'block_numbers': tuple(g['block_numbers']),
            'caption_blocks': tuple(g['caption_blocks']), 'context_blocks': tuple(g['context_blocks']),
            'page_ranges': tuple(tuple(r) for r in g['page_ranges']), 'bbox': tuple(g['bbox'])})
            for g in planned['protected_groups']]
        expected_plan = plan_page(parent, mapping, groups)
        if any(json.dumps(planned.get(key), sort_keys=True) != json.dumps(value, sort_keys=True)
               for key, value in expected_plan.items()):
            raise ValueError('Block plan differs from deterministic whole-block planner')
        coverage = []
        seeds = []
        for item in evidence:
            for r, offset, left in bound[item.chunk_id]:
                if r.region_id == parent.region_id:
                    length = min(len(item.text) - offset, len(r.page_text) - left)
                    coverage.append((left, left + length))
                    seeds.append(item)
        diagnostics = list(planned['diagnostics'])
        if not full_coverage(parent.page_text, coverage):
            diagnostics.append('complete_baseline_page_alignment_not_proven')
        if planned.get('source_gaps', {}).get('assets'):
            diagnostics.append('non_text_source_assets_not_interpreted')
        if planned.get('source_gaps', {}).get('diagnostics'):
            diagnostics.append('source_visual_registry_diagnostics')
        blocks: list[dict[str, Any]] = []
        for b in mapping.blocks:
            source = _region(parent, b.page_start, b.page_end)
            events = [e.model_dump(mode='json') for e in source_events(source)]
            anchor_hits = [{'alias': alias, **hit, 'start': source.start + hit['start'], 'end': source.start + hit['end']}
                           for alias in aliases for hit in occurrences(source.quote, alias)]
            reasons = []
            if anchor_hits:
                reasons.append('literal_query_mention')
            if _CONDITION.search(source.quote):
                reasons.append('finite_condition_or_method_cue')
            if any(e['block_guards'] for e in events):
                reasons.append('negation_reported_work_or_modality_guard')
            if any(e['boundary_diagnostics'] for e in events):
                reasons.append('unproven_sentence_boundary')
            blocks.append({'block_number': b.block_number, 'start': b.page_start, 'end': b.page_end,
                'text_sha256': text_hash(source.quote), 'anchor_hits': anchor_hits,
                'retention_reasons': reasons, 'events': events, 'state': 'not_selected_retained_in_baseline'})
        page: dict[str, Any] = {'parent_region_id': parent.region_id, 'article_id': str(parent.article_id), 'page': parent.page_number,
                'plan': planned, 'blocks': blocks, 'diagnostics': sorted(set(diagnostics))}
        pages.append(page)
        pending.append((parent, seeds, page))
    anchored_articles = {p['article_id'] for p in pages if any(b['anchor_hits'] for b in p['blocks'])}
    for parent, seeds, page in pending:
        if page['diagnostics'] or not seeds:
            for b in page['blocks']:
                b['state'] = 'deferred_page_retained_in_baseline'
            continue
        if page['article_id'] not in anchored_articles:
            continue
        selected_blocks = [b for b in page['blocks'] if b['retention_reasons']]
        for context in page['plan']['contexts']:
            # Context core must contain a retained block. Neighbors/protected groups
            # are already included by the existing complete-block planner.
            retained = [b for b in selected_blocks if any(core['start'] <= b['start'] and b['end'] <= core['end']
                                                        for core in context['core_units'])]
            if not retained:
                continue
            start, end = context['start'], context['end']
            source = _region(parent, start, end)
            if context['quote'] != source.quote or context['quote_sha256'] != source.quote_sha256:
                raise ValueError('Proposed block context differs from exact source text')
            if not any(b['start'] == start for b in page['blocks']) or not any(b['end'] == end for b in page['blocks']):
                raise ValueError('Proposed block context cuts a registered PDF block')
            citation_id = f'B{len(candidate) + 1}'
            candidate.append(replace(seeds[0], citation_id=citation_id, text=source.quote,
                page_start=source.page_number, page_end=source.page_number, retrieval_method='registered_block_context_proposal'))
            proposals.append({'citation_id': citation_id, 'source': source.model_dump(mode='json'),
                'parent_region_id': parent.region_id, 'context': context,
                'seed_citation_ids': [e.citation_id for e in seeds],
                'source_type_basis': 'Inherited seed chunk type; independent block semantics not established.'})
            all_intervals.setdefault(parent.region_id, []).append((start, end))
            for b in page['blocks']:
                if start <= b['start'] and b['end'] <= end:
                    b['state'] = 'included_in_candidate'
                    b.setdefault('candidate_citation_ids', []).append(citation_id)
    source_pages = [SourcePage(str(r.article_id), r.region_id, r.page_number, r.text_layer, str(r.text_layer_id),
                               r.page_text, r.layer_pdf_path, r.layer_pdf_sha256) for r in regions]
    complete = complete_pages_in_request('\n'.join(e.text for e in candidate), source_pages)
    assembled = [r.region_id for r in regions if full_coverage(r.page_text, all_intervals.get(r.region_id, []))]
    wire = {'version': VERSION, 'question': baseline['question'], 'evidence': [asdict(e) for e in candidate],
            'scientific_admission': 'not_evaluated',
            'limitations': ['whole_pdf_blocks_do_not_prove_paragraph_or_relation_completeness',
                            'unknown_and_unselected_source_remains_in_local_baseline']}
    serialized = json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    check = assess_query_qualifiers(baseline['question'], candidate, baseline_allowed=baseline['baseline_allowed'],
                                   article_metadata=baseline['article_metadata'])
    blockers = [r for r in baseline['blocking_reasons'] if r not in {'complete_source_pages_retained', 'evidence_bundle_over_budget'}]
    if not candidate:
        blockers.append('no_supported_block_context')
    if not aliases:
        blockers.append('no_supported_query_anchor')
    if any(p['diagnostics'] for p in pages):
        blockers.append('unresolved_source_pages')
    if any(p['context']['state'] != 'bounded_context_proposal' for p in proposals):
        blockers.append('deferred_block_contexts')
    if complete or assembled:
        blockers.append('complete_source_page_or_assembled_coverage')
    if not check['candidate_allowed']:
        blockers.append('candidate_query_qualifier_check_failed')
    if len(serialized.encode('utf-8')) > MAX_BYTES:
        blockers.append('candidate_over_byte_budget')
    return {'version': VERSION, 'baseline': baseline, 'pages': pages, 'proposals': proposals, 'wire': wire,
        'wire_bytes': len(serialized.encode('utf-8')), 'wire_sha256': text_hash(serialized), 'byte_ceiling': MAX_BYTES,
        'query_qualifiers': check, 'complete_page_matches': complete, 'assembled_complete_pages': assembled,
        'blocking_reasons': sorted(set(blockers)), 'technical_checks_passed': not blockers,
        'generation_performed': False, 'network_ready': False, 'external_request_constructed': False,
        'scientific_admission': 'not_evaluated'}
