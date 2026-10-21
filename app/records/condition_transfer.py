"""Prospective full-scope probe units for the unchanged stage25 literal event rules."""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any, Final

from app.records.condition_scope import SourceEvent, source_events
from app.records.material_roles import RoleSpan, checked_span
from app.records.schema import SourceRegion, source_identity, text_hash

VERSION: Final = 'records_condition_transfer_v0.1'


def unit_identity(parent_id: str, block: dict[str, Any]) -> str:
    return text_hash(json.dumps([parent_id, block['block_number'], block['page_start'], block['page_end']], separators=(',', ':')))


def registered_units(page: dict[str, Any], source: SourceRegion) -> tuple[list[dict[str, Any]], list[str]]:
    """Never create units from a registry which cannot prove exact whole-page coverage."""
    mapping = page.get('mapping')
    if not mapping:
        return [], ['missing_registered_mapping']
    if (mapping['article_id'], mapping['page'], mapping['layer_id'], mapping['text_sha256'], mapping['selected_pdf_sha256']) != (
            str(source.article_id), source.page_number, str(source.text_layer_id), source.page_text_sha256, source.layer_pdf_sha256):
        raise ValueError('Transfer block registry differs from the exact source page identity')
    if mapping['diagnostic']:
        return [], ['unproven_registered_mapping', mapping['diagnostic']]
    cursor, seen = 0, set()
    for block in mapping['blocks']:
        start, end, number = block['page_start'], block['page_end'], block['block_number']
        if (type(start) is not int or type(end) is not int or type(number) is not int or number < 0
                or start != cursor or not cursor < end <= len(source.page_text) or number in seen):
            return [], ['registry_gap_overlap_duplicate_or_invalid_range']
        bbox = block['bbox']
        if (len(bbox) != 4 or not all(type(v) in {float, int} and math.isfinite(v) for v in bbox)
                or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]):
            return [], ['unproven_block_geometry']
        cursor = end
        seen.add(number)
    if cursor != len(source.page_text):
        return [], ['registry_does_not_cover_whole_page']
    units = []
    for block in mapping['blocks']:
        span = RoleSpan(region_id=source.region_id, start=block['page_start'], end=block['page_end'],
                        text=source.page_text[block['page_start']:block['page_end']])
        units.append({'unit_id': unit_identity(source.region_id, block), 'block_number': block['block_number'],
                      'bbox': block['bbox'], 'source': span.model_dump(), 'text_sha256': text_hash(span.text)})
    return units, []


def packet_inventory(packet: dict[str, Any]) -> dict[str, Any]:
    pages = packet['pages']
    identifiers = [(p['article_id'], p['page_number']) for p in pages]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError('Transfer page inventory contains duplicate source pages')
    expected = {(d['article_id'], number) for d in packet['documents'] for number in d['declared_pages']}
    if len({d['article_id'] for d in packet['documents']}) != len(packet['documents']) or set(identifiers) != expected:
        raise ValueError('Transfer pages differ from all declared source documents/pages')
    if any(p['task_id'] in packet['excluded_task_ids'] for p in pages):
        raise ValueError('Development control task leaked into transfer denominators')
    units = [u['unit_id'] for p in pages for u in p['units']]
    if len(units) != len(set(units)):
        raise ValueError('Transfer unit inventory contains duplicate block identities')
    if any((p['probe_diagnostics'] and p['units']) or (not p['probe_diagnostics']
            and len(p['units']) != p['declared_block_count']) for p in pages):
        raise ValueError('Transfer units differ from their proven/deferred registry accounting')
    return {'primary_task_groups': len({d['task_id'] for d in packet['documents']}), 'source_documents': len(packet['documents']),
            'source_pages': len(pages), 'registered_blocks': sum(p['declared_block_count'] for p in pages),
            'probe_units': len(units), 'deferred_mapping_pages': sum(bool(p['probe_diagnostics']) for p in pages),
            'historically_deferred_layout_pages': sum(p['planning_state'] == 'deferred_page' for p in pages),
            'document_roles': dict(Counter(d['role'] for d in packet['documents']))}


def build_packet(scope: dict[str, Any], windows: dict[str, Any], page_sources: dict[tuple[str, int], SourceRegion],
                 control: SourceRegion, control_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Prepare only: neither inspect event outcomes nor execute the frozen rules here."""
    excluded = [t['task_id'] for t in scope['tasks'] if any(d['article_id'] == str(control.article_id) for d in t['documents'])]
    if len(excluded) != 1:
        raise ValueError('Exactly one development task must contain the stage25 control source')
    metadata = {d['article_id']: d for d in scope['documents']}
    declarations = [(t, d) for t in scope['tasks'] if t['task_id'] not in excluded for d in t['documents']]
    documents = [{'article_id': d['article_id'], 'task_id': t['task_id'], 'role': d['role'],
                  'title': metadata[d['article_id']]['title'], 'exposure': t['exposure'],
                  'declared_pages': [p['page_number'] for p in d['pages']],
                  'original_pdf_path': d['original_pdf_path'], 'original_pdf_sha256': d['original_pdf_sha256']}
                 for t, d in declarations]
    keys = {(d['article_id'], number) for d in documents for number in d['declared_pages']}
    page_map = {(p['article_id'], p['page_number']): p for p in windows['pages']}
    if len(page_map) != len(windows['pages']) or any(key not in page_map for key in keys):
        raise ValueError('Frozen windows lack a unique page for the declared transfer scope')
    pages = []
    units: list[dict[str, Any]]
    for document in documents:
        for number in document['declared_pages']:
            key = (document['article_id'], number)
            page, source = page_map[key], page_sources.get(key)
            if source is None:
                if page.get('page_text') is not None:
                    raise ValueError('Transfer source registry lost a nonempty page')
                units, diagnostics = [], ['missing_or_empty_source_page']
            else:
                if (source.start != 0 or source.end != len(source.page_text) or page['parent_region_id'] != source.region_id
                        or page['page_text'] != source.page_text or page['task_id'] != document['task_id']
                        or source.original_pdf_sha256 != document['original_pdf_sha256']):
                    raise ValueError('Transfer full-page source differs from frozen declaration/geometry')
                units, diagnostics = registered_units(page, source)
            pages.append({'article_id': key[0], 'page_number': number, 'task_id': document['task_id'],
                'document_role': document['role'], 'planning_state': page['planning_state'], 'diagnostics': page['diagnostics'],
                'layout_diagnostics': page.get('layout_diagnostics', []), 'table_diagnostics': page.get('table_diagnostics', []),
                'source_gaps': page.get('source_gaps'), 'declared_block_count': len(page.get('mapping', {}).get('blocks', [])),
                'probe_diagnostics': diagnostics, 'source': source.model_dump(mode='json') if source else None, 'units': units,
                'paragraph_adequacy': 'not_established', 'per_result_applicability': 'not_established'})
    packet = {'version': VERSION, 'excluded_task_ids': excluded, 'documents': documents, 'pages': pages,
              'control_source': control.model_dump(mode='json'), 'expected_control_events': control_events,
              'exposure': 'development_exposed; frozen-rule transfer probe, not independent gold',
              'scope': 'Every declared other-task page and proven registered block; source-event policy only.',
              'scientific_admission': 'not_evaluated', 'new_model_calls': 0}
    packet['inventory'] = packet_inventory(packet)
    return packet


def block_source(parent: SourceRegion, unit: dict[str, Any]) -> SourceRegion:
    span = checked_span(unit['source'], {parent.region_id: parent}, parent.article_id)
    if unit['text_sha256'] != text_hash(span.text) or unit['unit_id'] != unit_identity(parent.region_id, {
            'block_number': unit['block_number'], 'page_start': span.start, 'page_end': span.end}):
        raise ValueError('Transfer unit text or block identity changed after preparation')
    data = parent.model_dump()
    data.update(start=span.start, end=span.end, quote=span.text, quote_sha256=unit['text_sha256'],
                selection_basis='manual_development',
                selection_note='Frozen complete registered block for local transfer probe; scope not validated.')
    data['region_id'] = source_identity(data)
    return SourceRegion.model_validate(data)


def execute_packet(packet: dict[str, Any]) -> dict[str, Any]:
    if packet['version'] != VERSION or packet_inventory(packet) != packet['inventory']:
        raise ValueError('Transfer packet version/inventory changed after preparation')
    control = SourceRegion.model_validate(packet['control_source'])
    actual = [e.model_dump(mode='json') for e in source_events(control)]
    expected = [SourceEvent.model_validate(e).model_dump(mode='json') for e in packet['expected_control_events']]
    if actual != expected:
        raise ValueError('Frozen stage25 source-event control replay differs')
    results: list[dict[str, Any]] = []
    all_events: list[SourceEvent] = []
    for page in packet['pages']:
        if page['source'] is None:
            if page['units']:
                raise ValueError('Missing transfer source cannot contain probe units')
            continue
        parent = SourceRegion.model_validate(page['source'])
        if str(parent.article_id) != page['article_id'] or parent.page_number != page['page_number']:
            raise ValueError('Transfer page source/article identity changed')
        for unit in page['units']:
            source = block_source(parent, unit)
            events = source_events(source)
            recognized = any(e.kind != 'unclassified' for e in events)
            results.append({'unit_id': unit['unit_id'], 'article_id': page['article_id'], 'page_number': page['page_number'],
                'block_region_id': source.region_id, 'outcome': 'literal_cue_observed' if recognized else 'no_literal_cue',
                'events': [e.model_dump(mode='json') for e in events], 'scientific_support': 'not_evaluated',
                'diagnostic': 'Unchanged raw rule output only; no cue does not mean experimental conditions are absent.'})
            all_events.extend(events)
    summary = {**packet['inventory'], 'executed_units': len(results),
        'unit_outcomes': dict(Counter(r['outcome'] for r in results)),
        'event_states': dict(Counter(e.state for e in all_events)), 'event_kinds': dict(Counter(e.kind for e in all_events)),
        'source_events': len(all_events), 'separate_control_events': len(actual), 'control_replay_exact': True,
        'new_measurement_records': 0, 'new_model_calls': 0, 'scientific_precision': None, 'scientific_recall': None,
        'scientific_admission': 'not_evaluated'}
    return {'version': VERSION, 'summary': summary, 'results': results, 'separate_control_events': actual}
