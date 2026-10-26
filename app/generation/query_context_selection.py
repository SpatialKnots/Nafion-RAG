"""Versioned whole-unit candidate selection; no scientific exclusion or admission."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from app.evaluation.context_compaction import SourcePage, complete_pages_in_request
from app.evaluation.context_risks import canonical
from app.evaluation.query_packet import MAX_BYTES
from app.generation.block_context import full_coverage
from app.generation.context_completeness import PREPARATION, validate_audit
from app.generation.providers import Evidence
from app.generation.query_qualifiers import METHOD_ALIASES, assess_query_qualifiers, occurrences
from app.records.protocol_association import PROPERTY_CUES
from app.records.schema import text_hash

VERSION = 'query_context_selection_v0.1'
METHOD = re.compile(r'\b(?:measur\w*|impedance|spectroscop\w*|method\w*|protocol\w*|conditions?|programme|program|'
    r'измер\w*|метод\w*|импеданс\w*|спектроскоп\w*|услови\w*)\b', re.IGNORECASE)
PREP_QUERY = re.compile(r'\b(?:prepar\w*|atmospher\w*|equilibrat\w*|conditioning|before\s+measur\w*|'
    r'подготов\w*|атмосфер\w*|уравновеш\w*|равновес\w*|перед\s+измер\w*)\b', re.IGNORECASE)
CONDITIONING = re.compile(r'\b(?:equilibrat\w*|before\s+measur\w*|conditioned|термического\s+равновесия|'
    r'перед\s+измер\w*|выдерж\w*)\b', re.IGNORECASE)
METHOD_FAMILIES = (
    ('conductivity', re.compile(r'\b(?:impedance|EIS|импеданс\w*)\b', re.IGNORECASE)),
    ('thermal_analysis', re.compile(r'\b(?:DSC|differential\s+scanning\s+calorimetr\w*|ДСК)\b', re.IGNORECASE)),
)


def family_hits(text: str) -> list[dict[str, Any]]:
    hits = [dict(family=family, start=m.start(), end=m.end(), text=m.group())
        for family, regex in PROPERTY_CUES for m in regex.finditer(text)]
    for family, aliases in (('conductivity', METHOD_ALIASES['conductivity']),
            ('thermal_analysis', METHOD_ALIASES['differential_scanning_calorimetry'])):
        hits.extend(dict(family=family, **hit) for alias in aliases for hit in occurrences(text, alias))
    unique = {(h['family'], h['start'], h['end']): h for h in hits}
    return [unique[k] for k in sorted(unique)]


def seed_hit(offset: int, reason: str, start: int, end: int, text: str) -> dict[str, Any]:
    return {'reason': reason, 'start': offset + start, 'end': offset + end, 'text': text}


def select_context(packet: dict[str, Any], diagnostics: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    validate_audit(audit, packet, diagnostics)
    parent = diagnostics['wire']
    nodes = parent['nodes']
    pages = {p['page_ref']: p for p in parent['pages']}
    baseline = diagnostics['parent']['preparation']['baseline']
    question = parent['question']
    query_hits = family_hits(question)
    families = {h['family'] for h in query_hits}
    protocol = bool(METHOD.search(question))
    preparation = bool(PREP_QUERY.search(question))
    check = assess_query_qualifiers(question, [Evidence(**e) for e in baseline['evidence']],
        baseline_allowed=baseline['baseline_allowed'], article_metadata=baseline['article_metadata'])
    restrictions = []
    for article in check['articles']:
        required = [c for c in article['checks'] if c['qualifier']['kind'] in ('article', 'material_literal')]
        restrictions.append({'article_id': article['article_id'], 'required_checks': required,
            'eligible_by_necessary_mentions_only': not check['parse_warnings'] and all(c['state'] == 'mentioned' for c in required)})
    eligible = {r['article_id'] for r in restrictions if r['eligible_by_necessary_mentions_only']}
    hits_by_node = {n['id']: [h for h in family_hits(n['text']) if h['family'] in families] for n in nodes}
    anchored = {pages[n['page_ref']]['article_id'] for n in nodes if hits_by_node[n['id']]}
    seeds: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        article = pages[node['page_ref']]['article_id']
        if not families or article not in eligible or article not in anchored:
            continue
        reasons = []

        if hits_by_node[node['id']] and (not protocol or METHOD.search(node['text'])):
            for hit in hits_by_node[node['id']]:
                reasons.append(seed_hit(node['start'],
                    'literal_query_family_in_method_context' if protocol else 'literal_query_family',
                    hit['start'], hit['end'], hit['text']))
        if protocol:
            for family, regex in METHOD_FAMILIES:
                if family in families:
                    for match in regex.finditer(node['text']):
                        reasons.append(seed_hit(node['start'], 'compatible_method_family_in_anchored_article',
                            match.start(), match.end(), match.group()))
        if preparation:
            for regex in (PREPARATION, CONDITIONING):
                for match in regex.finditer(node['text']):
                    reasons.append(seed_hit(node['start'], 'requested_preparation_or_conditioning_indicator',
                        match.start(), match.end(), match.group()))
            for event in node['events']:
                for cue in event['cues']:
                    if cue['kind'] in ('preparation_procedure', 'conditioning_procedure'):
                        s = cue['span']
                        reasons.append({'reason': 'requested_original_scope_cue', **{k: s[k] for k in ('start', 'end', 'text')}})
        if reasons:
            seeds[node['id']] = reasons
    selected_units = [i for i, u in enumerate(parent['co_preservation_units'], 1) if set(u) & seeds.keys()]
    selected = {n for i in selected_units for n in parent['co_preservation_units'][i - 1]}
    dependencies = [(i, d) for i, d in enumerate(parent['dependencies'], 1) if selected.intersection(d['nodes'])]
    if any(not set(d['nodes']) <= selected for _, d in dependencies):
        raise ValueError('Query selection cuts a protected or unresolved dependency')
    number = {n['id']: i for i, n in enumerate(nodes, 1)}
    wire = deepcopy(packet['wire'])
    wire.update(version=VERSION, parent_compact_packet_sha256=text_hash(canonical(packet)),
        selection_policy=VERSION, selection_changed=True,
        reference_contract='Sparse integer block/context references retain their original parent positions. '
            'dependency_refs and unit_refs identify original positions of the corresponding filtered lists. '
            'Read entire co-preservation units; retained original contexts are complete. Omitted source remains local.',
        instruction=wire['instruction'] + ' This is a query-selected proposal, not lossless parent coverage. '
            'Deferred source relevance is unknown. Do not inherit preparation atmosphere or resolve scientific '
            'sample/condition applicability from proximity. All original refusals remain in force.')
    wire['blocks'] = [b for b in wire['blocks'] if b[0] in {number[n] for n in selected}]
    wire['contexts'] = [c for c in wire['contexts'] if set(c[1]) <= {number[n] for n in selected}]
    wire['dependencies'] = [packet['wire']['dependencies'][i - 1] for i, _ in dependencies]
    wire['dependency_refs'] = [i for i, _ in dependencies]
    wire['co_preservation_units'] = [packet['wire']['co_preservation_units'][i - 1] for i in selected_units]
    wire['unit_refs'] = selected_units
    ledger = [{'node_ref': n['id'], 'node_id': n['node_id'], 'page_ref': n['page_ref'],
        'block_number': n['block_number'], 'state': 'selected_seed' if n['id'] in seeds else 'selected_unit_closure'
            if n['id'] in selected else 'deferred_locally_relevance_unknown',
        'seed_hits': deepcopy(seeds.get(n['id'], [])), 'scientific_exclusion_proven': False} for n in nodes]
    windows = []
    for c in parent['contexts']:
        retained = [n for n in c['nodes'] if n in selected]
        windows.append({'context_id': c['context_id'], 'original_nodes': deepcopy(c['nodes']), 'retained_nodes': retained,
            'state': 'whole_original_window_retained' if len(retained) == len(c['nodes']) else 'partial_original_window_local_only'
                if retained else 'deferred_original_window_local_only'})
    regions = [p['source'] for p in diagnostics['parent']['audit']['pages']]
    source_pages = [SourcePage(s['article_id'], s['region_id'], s['page_number'], s['text_layer'], s['text_layer_id'],
        s['page_text'], s['layer_pdf_path'], s['layer_pdf_sha256']) for s in regions]
    raw = canonical(wire)
    literal = complete_pages_in_request(raw, source_pages)
    decoded = complete_pages_in_request('\n'.join(n['text'] for n in nodes if n['id'] in selected), source_pages)
    assembled = [s['region_id'] for s in regions for p in pages.values() if p['parent_region_id'] == s['region_id']
        if full_coverage(s['page_text'], [(n['start'], n['end']) for n in nodes
            if n['id'] in selected and n['page_ref'] == p['page_ref']])]
    blockers = set(packet['blocking_reasons']) | {'query_selection_scientific_retention_not_validated'}
    if not selected:
        blockers.add('no_query_selected_context')
    if literal or decoded or assembled:
        blockers.add('selected_complete_source_page_or_assembled_coverage')
    if len(raw.encode('utf-8')) > MAX_BYTES:
        blockers.add('selected_context_over_existing_byte_ceiling')
    metrics = {'parent_blocks': len(nodes), 'selected_blocks': len(selected), 'seed_blocks': len(seeds),
        'deferred_blocks': len(nodes) - len(selected), 'parent_units': len(parent['co_preservation_units']),
        'selected_units': len(selected_units), 'selected_dependencies': len(dependencies),
        'parent_source_text_bytes': packet['source_text_bytes'],
        'selected_source_text_bytes': sum(len(n['text'].encode('utf-8')) for n in nodes if n['id'] in selected),
        'parent_wire_bytes': packet['wire_bytes'], 'wire_bytes': len(raw.encode('utf-8')),
        'parent_windows': len(windows), 'whole_windows_retained': sum(w['state'] == 'whole_original_window_retained' for w in windows),
        'partial_windows_local_only': sum(w['state'] == 'partial_original_window_local_only' for w in windows),
        'deferred_windows_local_only': sum(w['state'] == 'deferred_original_window_local_only' for w in windows),
        'parent_event_occurrences': len(audit['events']),
        'selected_event_occurrences': sum(len(n['events']) for n in nodes if n['id'] in selected),
        'parent_full_page_occurrences': len(packet['assembled_complete_pages']), 'selected_full_page_occurrences': len(assembled)}
    return {'version': VERSION, 'wire': wire, 'wire_sha256': text_hash(raw), 'metrics': metrics,
        'parent_audit_sha256': text_hash(canonical(audit)), 'byte_ceiling': MAX_BYTES,
        'current_byte_check_passed': len(raw.encode('utf-8')) <= MAX_BYTES, 'query_family_hits': query_hits,
        'query_intent': {'protocol': protocol, 'preparation_or_conditioning': preparation},
        'article_restrictions': restrictions, 'query_parse_warnings': check['parse_warnings'],
        'block_ledger': ledger, 'original_window_ledger': windows,
        'complete_page_matches': {'serialized': literal, 'decoded': decoded, 'assembled': assembled},
        'blocking_reasons': sorted(blockers), 'selection_changed': True, 'scientific_loss_status': 'not_evaluated',
        'generation_performed': False, 'external_request_constructed': False, 'network_ready': False,
        'scientific_admission': 'not_evaluated'}


def validate_selection(result: dict[str, Any], packet: dict[str, Any], diagnostics: dict[str, Any], audit: dict[str, Any]) -> None:
    if canonical(select_context(packet, diagnostics, audit)) != canonical(result):
        raise ValueError('Query context selection differs from exact frozen whole-unit reconstruction')


def expand_selected_unit(wire: dict[str, Any], unit_ref: int) -> list[str]:
    """Return separate exact blocks; do not reconstruct a cross-block sentence."""
    if wire['version'] != VERSION or type(unit_ref) is not int or wire['unit_refs'].count(unit_ref) != 1:
        raise ValueError('Selected unit reference absent, duplicated or foreign')
    blocks = {b[0]: b for b in wire['blocks']}
    unit = wire['co_preservation_units'][wire['unit_refs'].index(unit_ref)]
    if len(blocks) != len(wire['blocks']) or not unit or len(unit) != len(set(unit)) or any(n not in blocks for n in unit):
        raise ValueError('Selected unit contains duplicate or missing block references')
    return [blocks[n][5] for n in unit]
