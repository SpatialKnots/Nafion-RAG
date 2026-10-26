"""Finite sample-class audit and experimental deferral; no sample identity claims."""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any

from app.evaluation.context_compaction import SourcePage, complete_pages_in_request
from app.evaluation.context_risks import canonical
from app.evaluation.query_packet import MAX_BYTES
from app.generation.block_context import full_coverage
from app.generation.query_context_selection import validate_selection
from app.records.schema import text_hash

AUDIT_VERSION = 'sample_scope_audit_v0.1'
SELECTION_VERSION = 'sample_scope_selection_v0.1'
# Literal class inventory, not mutually exclusive chemical categories. Films,
# electrodes, Nafion and generic samples alone do not establish either class.
CLASSES = (
    ('membrane', re.compile(r'\b(?:membranes?|мембран\w*)\b', re.IGNORECASE)),
    ('sei_interface', re.compile(r'\b(?:SEI|solid[ -]+electrolyte[ -]+interphas\w*|'
        r'тверд\w*\s+электролитн\w*\s+межфаз\w*)\b', re.IGNORECASE)),
)


def class_hits(text: str, offset: int = 0) -> list[dict[str, Any]]:
    return sorted(({'class': kind, 'start': offset + m.start(), 'end': offset + m.end(), 'text': m.group()}
        for kind, regex in CLASSES for m in regex.finditer(text)), key=lambda h: (h['start'], h['end'], h['class']))


def audit_scope(selection: dict[str, Any], packet: dict[str, Any], diagnostic: dict[str, Any],
                completeness: dict[str, Any]) -> dict[str, Any]:
    validate_selection(selection, packet, diagnostic, completeness)
    query_hits = class_hits(selection['wire']['question'])
    query_classes = sorted({h['class'] for h in query_hits})
    target = query_classes[0] if len(query_classes) == 1 else None
    nodes = diagnostic['wire']['nodes']
    pages = {p['page_ref']: p for p in diagnostic['wire']['pages']}
    units = []
    for ref, members in enumerate(packet['wire']['co_preservation_units'], 1):
        hits: list[dict[str, Any]] = []
        for number in members:
            n = nodes[number - 1]
            p = pages[n['page_ref']]
            hits.extend(dict(hit, node_ref=n['id'], node_id=n['node_id'], page_ref=n['page_ref'],
                article_id=p['article_id'], region_id=p['parent_region_id'], page=p['page'],
                text_layer=p['text_layer'], text_layer_id=p['text_layer_id'])
                for hit in class_hits(n['text'], n['start']))
        classes = sorted({h['class'] for h in hits})
        state = ('unsupported_or_ambiguous_query' if target is None else
            'unknown_no_class' if not classes else 'target_literal_only' if classes == [target] else
            'mixed_literal_classes' if target in classes else 'competing_literal_only')
        units.append({'unit_ref': ref, 'members': deepcopy(members), 'state': state, 'literal_classes': classes,
            'hits': hits, 'parent_selected': ref in selection['wire']['unit_refs'],
            'sample_identity': 'not_established', 'per_result_applicability': 'not_established',
            'scientific_exclusion_proven': False})
    return {'version': AUDIT_VERSION, 'parent_selection_sha256': text_hash(canonical(selection)),
        'question': selection['wire']['question'], 'query_hits': query_hits, 'query_classes': query_classes,
        'target_class': target, 'units': units, 'counts': dict(Counter(u['state'] for u in units)),
        'parent_selected_counts': dict(Counter(u['state'] for u in units if u['parent_selected'])),
        'selection_changed': False, 'network_ready': False, 'generation_performed': False,
        'external_request_constructed': False, 'scientific_loss_status': 'not_evaluated'}


def select_scope(audit: dict[str, Any], selection: dict[str, Any], packet: dict[str, Any],
                 diagnostic: dict[str, Any], completeness: dict[str, Any]) -> dict[str, Any]:
    if audit != audit_scope(selection, packet, diagnostic, completeness):
        raise ValueError('Sample scope audit differs from exact parent reconstruction')
    deferred = {u['unit_ref'] for u in audit['units'] if u['parent_selected'] and u['state'] == 'competing_literal_only'}
    retained = [ref for ref in selection['wire']['unit_refs'] if ref not in deferred]
    selected = {n for ref in retained for n in packet['wire']['co_preservation_units'][ref - 1]}
    old_selected = {b[0] for b in selection['wire']['blocks']}
    wire = deepcopy(selection['wire'])
    wire.update(version=SELECTION_VERSION, selection_policy=SELECTION_VERSION,
        parent_selection_sha256=text_hash(canonical(selection)), sample_scope_audit_sha256=text_hash(canonical(audit)))
    wire['instruction'] += (' Experimental sample-class deferral is not scientific irrelevance. '
        'Unknown and mixed classes remain; literal class mentions do not resolve sample identity or applicability.')
    wire['blocks'] = [b for b in wire['blocks'] if b[0] in selected]
    wire['contexts'] = [c for c in wire['contexts'] if set(c[1]) <= selected]
    dependencies = [(i, d) for i, d in enumerate(packet['wire']['dependencies'], 1) if selected.intersection(d[1])]
    if any(not set(d[1]) <= selected for _, d in dependencies):
        raise ValueError('Sample scope selection cuts a dependency')
    wire['dependencies'] = [d for _, d in dependencies]
    wire['dependency_refs'] = [i for i, _ in dependencies]
    wire['co_preservation_units'] = [packet['wire']['co_preservation_units'][ref - 1] for ref in retained]
    wire['unit_refs'] = retained
    nodes = diagnostic['wire']['nodes']
    by_id = {n['id']: i for i, n in enumerate(nodes, 1)}
    pages = {p['page_ref']: p for p in diagnostic['wire']['pages']}
    regions = [p['source'] for p in diagnostic['parent']['audit']['pages']]
    source_pages = [SourcePage(s['article_id'], s['region_id'], s['page_number'], s['text_layer'], s['text_layer_id'],
        s['page_text'], s['layer_pdf_path'], s['layer_pdf_sha256']) for s in regions]
    raw = canonical(wire)
    literal = complete_pages_in_request(raw, source_pages)
    decoded = complete_pages_in_request('\n'.join(n['text'] for i, n in enumerate(nodes, 1) if i in selected), source_pages)
    assembled = [s['region_id'] for s in regions for p in pages.values() if p['parent_region_id'] == s['region_id']
        if full_coverage(s['page_text'], [(n['start'], n['end']) for i, n in enumerate(nodes, 1)
            if i in selected and n['page_ref'] == p['page_ref']])]
    windows = []
    for window in diagnostic['wire']['contexts']:
        members = [by_id[n] for n in window['nodes']]
        present = [n for n in members if n in selected]
        windows.append({'context_id': window['context_id'], 'original_members': members, 'retained_members': present,
            'state': 'whole' if len(present) == len(members) else 'partial' if present else 'deferred'})
    blockers = set(selection['blocking_reasons']) | {'sample_scope_scientific_retention_not_validated'}
    if not selected:
        blockers.add('no_sample_scope_selected_context')
    if literal or decoded or assembled:
        blockers.add('sample_scope_selected_complete_page')
    if len(raw.encode('utf-8')) > MAX_BYTES:
        blockers.add('sample_scope_over_existing_byte_ceiling')
    return {'version': SELECTION_VERSION, 'wire': wire, 'wire_sha256': text_hash(raw),
        'audit_sha256': text_hash(canonical(audit)), 'deferred_unit_refs': sorted(deferred),
        'block_ledger': [{'node_ref': n['id'], 'node_id': n['node_id'],
            'state': 'selected' if i in selected else 'deferred_competing_class_proposal' if i in old_selected
                else 'previously_deferred_relevance_unknown', 'scientific_exclusion_proven': False}
            for i, n in enumerate(nodes, 1)], 'original_window_ledger': windows,
        'metrics': {'parent_selected_blocks': len(old_selected), 'selected_blocks': len(selected),
            'newly_deferred_blocks': len(old_selected - selected), 'parent_selected_units': len(selection['wire']['unit_refs']),
            'selected_units': len(retained), 'deferred_units': len(deferred),
            'parent_wire_bytes': selection['metrics']['wire_bytes'], 'wire_bytes': len(raw.encode('utf-8')),
            'parent_full_page_occurrences': selection['metrics']['selected_full_page_occurrences'],
            'selected_full_page_occurrences': len(assembled),
            'whole_windows': sum(w['state'] == 'whole' for w in windows),
            'partial_windows': sum(w['state'] == 'partial' for w in windows),
            'deferred_windows': sum(w['state'] == 'deferred' for w in windows)},
        'complete_page_matches': {'serialized': literal, 'decoded': decoded, 'assembled': assembled},
        'byte_ceiling': MAX_BYTES, 'current_byte_check_passed': len(raw.encode('utf-8')) <= MAX_BYTES,
        'blocking_reasons': sorted(blockers), 'selection_changed': True, 'scientific_loss_status': 'not_evaluated',
        'network_ready': False, 'generation_performed': False, 'external_request_constructed': False}
