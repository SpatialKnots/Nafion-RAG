"""Local source-origin diagnostics; no selection, attribution or condition admission."""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any

from app.evaluation.context_risks import canonical
from app.generation.sample_scope import audit_scope, select_scope
from app.records.schema import text_hash

VERSION = 'source_origin_audit_v0.1'
HEADINGS = (
    ('bibliography', r'references|bibliography|литература|список\s+литературы|список\s+использованной\s+литературы'),
    ('methods', r'methods|experimental(?:\s+section)?|materials\s+and\s+methods|методы|экспериментальная\s+часть'),
    ('materials', r'materials|материалы'),
    ('introduction', r'introduction|введение'),
    ('results_discussion', r'results(?:\s+and\s+discussion)?|discussion|результаты(?:\s+и\s+обсуждение)?|обсуждение'),
    ('conclusions', r'conclusions?|заключение|выводы'),
    ('abstract', r'abstract|аннотация'),
)
CUES = (
    ('own_work', re.compile(r'\b(?:we\s+(?:measured|prepared|used|investigated|studied)|'
        r'in\s+(?:this|the\s+present)\s+(?:work|study)|в\s+(?:данной|настоящей|этой)\s+работе)\b', re.IGNORECASE)),
    ('reported_work', re.compile(r'\b(?:according\s+to|previous(?:ly)?|reported\s+by|literature|ранее|согласно|'
        r'по\s+данным|описан\w*\s+в\s+работ\w*)\b', re.IGNORECASE)),
    ('citation', re.compile(r'\[\s*\d+(?:\s*[,;–—-]\s*\d+)*\s*\]')),
)


def heading_lines(text: str, start: int = 0) -> list[dict[str, Any]]:
    hits = []
    offset = start
    for line in text.splitlines(keepends=True):
        for kind, phrase in HEADINGS:
            if re.fullmatch(r'\s*(?:\d+(?:\.\d+)*\.?\s+)?(?:' + phrase + r')\s*[:.]?\s*', line, re.IGNORECASE):
                left, right = len(line) - len(line.lstrip()), len(line.rstrip())
                hits.append({'kind': kind, 'start': offset + left, 'end': offset + right, 'text': line[left:right]})
        offset += len(line)
    return hits


def section_hint(node: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    mapping = plan['mapping']
    blocks = mapping['blocks']
    geometry = next(b for b in blocks if b['block_number'] == node['block_number'])
    candidates: list[tuple[float, int, dict[str, Any]]] = []
    local = heading_lines(node['text'], node['start'])
    # A heading embedded after body text cannot label the entire block.
    leading = [h for h in local if not node['text'][:h['start'] - node['start']].strip()]
    if leading:
        return {'state': 'leading_heading_proposal', 'kind': leading[0]['kind'], 'heading': leading[0],
            'scientific_section_proven': False}
    if mapping['diagnostic'] is not None:
        return {'state': 'unknown_mapping', 'kind': 'unknown', 'heading': None, 'scientific_section_proven': False}
    for block in blocks:
        if block['page_end'] > node['start']:
            continue
        box, target = block['bbox'], geometry['bbox']
        # Only a geometrically preceding heading centered inside this block's
        # horizontal span. No cross-page or cross-column state propagation.
        if box[3] > target[1] or not target[0] <= (box[0] + box[2]) / 2 <= target[2]:
            continue
        raw = plan['page_text'][block['page_start']:block['page_end']]
        hits = heading_lines(raw, block['page_start'])
        candidates.extend((box[3], h['start'], h) for h in hits)
    if not candidates:
        return {'state': 'unknown_no_same_page_heading', 'kind': 'unknown', 'heading': None,
            'scientific_section_proven': False}
    heading = max(candidates, key=lambda item: (item[0], item[1]))[2]
    return {'state': 'same_page_column_heading_proposal', 'kind': heading['kind'], 'heading': heading,
        'scientific_section_proven': False}


def origin_event(event: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
    context = event['context']
    raw = context['text']
    hits = [{'kind': kind, 'region_id': context['region_id'], 'start': context['start'] + m.start(),
        'end': context['start'] + m.end(), 'text': m.group()}
        for kind, pattern in CUES for m in pattern.finditer(raw)]
    kinds = {h['kind'] for h in hits}
    guarded = bool(event['block_guards'] or event['boundary_diagnostics'])
    origin = ('mixed_origin_cues' if {'own_work', 'reported_work'} <= kinds else
        'guarded_origin_cues' if guarded and kinds & {'own_work', 'reported_work'} else
        'reported_work_cue_proposal' if 'reported_work' in kinds else
        'own_work_cue_proposal' if 'own_work' in kinds else
        'citation_only_origin_unknown' if 'citation' in kinds else 'unknown')
    roles = {c['kind'] for c in event['cues']}
    preparation = bool(roles & {'preparation_procedure', 'conditioning_procedure'})
    measurement = bool(roles & {'measurement_protocol', 'measurement_setup'})
    role = ('mixed_procedure_cues' if preparation and measurement else 'preparation_or_conditioning_cues'
        if preparation else 'measurement_cues' if measurement else 'unknown')
    return {'event_id': event['event_id'], 'context': deepcopy(context), 'origin_state': origin,
        'origin_hits': sorted(hits, key=lambda h: (h['start'], h['end'], h['kind'])),
        'procedure_role': role, 'original_state': event['state'], 'original_proposed_kind': event['proposed_kind'],
        'original_cues': deepcopy(event['cues']), 'original_guards': deepcopy(event['block_guards']),
        'original_boundary_diagnostics': deepcopy(event['boundary_diagnostics']),
        'section_kind_proposal': section['kind'], 'own_work_origin': 'not_established',
        'sample_identity': 'not_established', 'per_result_applicability': 'not_established',
        'cross_event_field_inheritance': False, 'scientific_support': 'not_evaluated'}


def audit_origin(selection: dict[str, Any], scope_audit: dict[str, Any], old_selection: dict[str, Any],
                 packet: dict[str, Any], diagnostic: dict[str, Any], completeness: dict[str, Any]) -> dict[str, Any]:
    if scope_audit != audit_scope(old_selection, packet, diagnostic, completeness):
        raise ValueError('Origin audit parent scope differs from exact reconstruction')
    if selection != select_scope(scope_audit, old_selection, packet, diagnostic, completeness):
        raise ValueError('Origin audit requires the exact frozen stage42 selection')
    selected = {b[0] for b in selection['wire']['blocks']}
    plans = {p['parent_region_id']: p['plan'] for p in diagnostic['parent']['preparation']['pages']}
    pages = {p['page_ref']: p for p in diagnostic['wire']['pages']}
    rows = []
    for number, node in enumerate(diagnostic['wire']['nodes'], 1):
        page = pages[node['page_ref']]
        section = section_hint(node, plans[page['parent_region_id']])
        rows.append({'block_ref': number, 'node_ref': node['id'], 'node_id': node['node_id'],
            'selected': number in selected, 'source': {k: page[k] for k in
                ('article_id', 'page', 'text_layer', 'text_layer_id', 'parent_region_id', 'original_pdf_sha256')},
            'source_type': page['source_type'], 'start': node['start'], 'end': node['end'],
            'text': node['text'], 'text_sha256': node['text_sha256'], 'section_hint': section,
            'events': [origin_event(e, section) for e in node['events']], 'scientific_exclusion_proven': False})
    events = [e for row in rows for e in row['events']]
    retained = [e for row in rows if row['selected'] for e in row['events']]
    return {'version': VERSION, 'question': selection['wire']['question'],
        'parent_selection_sha256': text_hash(canonical(selection)), 'rows': rows,
        'metrics': {'blocks': len(rows), 'selected_blocks': len(selected), 'events': len(events),
            'selected_events': len(retained)},
        'selected_section_hints': dict(Counter(r['section_hint']['kind'] for r in rows if r['selected'])),
        'selected_origin_states': dict(Counter(e['origin_state'] for e in retained)),
        'selected_procedure_roles': dict(Counter(e['procedure_role'] for e in retained)),
        'wire_sha256_unchanged': selection['wire_sha256'], 'selection_changed': False,
        'blocking_reasons': deepcopy(selection['blocking_reasons']), 'network_ready': False,
        'generation_performed': False, 'external_request_constructed': False,
        'scientific_loss_status': 'not_evaluated'}
