"""Source-bound completeness diagnostics; literal cooccurrence is not entailment."""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any

from app.evaluation.context_risks import canonical
from app.generation.block_context import full_coverage
from app.generation.compact_context_packet import validate_compact_packet
from app.records.protocol_association import PROPERTY_CUES
from app.records.schema import text_hash

VERSION = 'context_completeness_v0.1'


def pattern(value: str) -> re.Pattern[str]:
    return re.compile(value, re.IGNORECASE)


# Versioned literal inventory only. Hyphen/newline alternatives match in place;
# no selected text or original event boundary is rewritten.
FIELDS = (
    ('sample', 'sample_mention', pattern(r'\b(?:membranes?|samples?|films?|electrodes?|мембран\w*|образ(?:-\s*)?ц\w*|электрод\w*)\b')),
    ('method', 'impedance', pattern(r'\b(?:impedance\s+spectroscop\w*|EIS|импедансн\w*\s+спектроскоп\w*)\b')),
    ('method', 'dsc', pattern(r'\b(?:DSC|differential\s+scanning\s+calorimetr\w*|ДСК)\b')),
    ('condition', 'temperature', pattern(r'[+−–-]?\d+(?:[.,]\d+)?\s*(?:°\s*[CKС]|[℃K])')),
    ('condition', 'duration', pattern(r'\b\d+(?:[.,]\d+)?\s*(?:hours?|minutes?|days?|min|h|ч|мин|сут)\b')),
    ('condition', 'frequency', pattern(r'\b\d+(?:[.,]\d+)?\s*(?:[kMG]?Hz|[кМГ]?Гц)\b')),
    ('condition', 'atmosphere_mention', pattern(r'\b(?:argon|nitrogen|air|vacuum|арго(?:-\s*)?н\w*|азот\w*|воздух\w*|вакуум\w*)\b')),
)
PREPARATION = pattern(r'\b(?:prepar\w*|cast|dried|anneal\w*|soak\w*|подготовк\w*|сборк\w*|высуш\w*|пластифиц\w*)\b')


def event_audit(node: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    context = event['context']
    raw = context['text']
    inventories: dict[str, list[dict[str, Any]]] = {k: [] for k in ('property', 'sample', 'method', 'condition')}

    def hit(kind: str, match: re.Match[str]) -> dict[str, Any]:
        return {'kind': kind, 'span': {'region_id': context['region_id'], 'start': context['start'] + match.start(),
            'end': context['start'] + match.end(), 'text': match.group()}}

    for property_kind, regex in PROPERTY_CUES:
        inventories['property'].extend(hit(property_kind, m) for m in regex.finditer(raw))
    for field, kind, regex in FIELDS:
        inventories[field].extend(hit(kind, m) for m in regex.finditer(raw))
    for values in inventories.values():
        values.sort(key=lambda h: (h['span']['start'], h['span']['end'], h['kind']))
    preparation = [hit('preparation_indicator', m) for m in PREPARATION.finditer(raw)]
    families = {v['kind'] for v in inventories['property']}
    methods = {v['kind'] for v in inventories['method']}
    cue_kinds = sorted({c['kind'] for c in event['cues']})
    reasons = []
    if event['state'] != 'scope_proposal':
        reasons.append('original_event_' + event['state'])
    if event['proposed_kind'] not in ('measurement_protocol', 'measurement_setup'):
        reasons.append('measurement_scope_not_established')
    if preparation or any(k in cue_kinds for k in ('preparation_procedure', 'conditioning_procedure')):
        reasons.append('preparation_or_conditioning_not_inherited_by_measurement')
    if event['block_guards']:
        reasons.append('original_block_wide_guards_preserved')
    if event['boundary_diagnostics']:
        reasons.append('original_source_boundary_unresolved')
    for field, values in inventories.items():
        if not values:
            reasons.append('missing_literal_' + field)
    if len(families) != 1:
        reasons.append('no_unique_property_family')
    if ('conductivity' in families and 'dsc' in methods) or ('thermal_analysis' in families and 'impedance' in methods):
        reasons.append('property_method_family_conflict')
    return {'event_id': event['event_id'], 'node_ref': node['id'], 'node_id': node['node_id'],
        'page_ref': node['page_ref'], 'block_number': node['block_number'], 'context': deepcopy(context),
        'original_state': event['state'], 'scope_role': event['proposed_kind'] or 'unresolved_source_scope',
        'original_cues': deepcopy(event['cues']), 'original_guards': deepcopy(event['block_guards']),
        'original_boundary_diagnostics': deepcopy(event['boundary_diagnostics']),
        'literal_fields': inventories, 'preparation_indicators': preparation,
        'chain_state': 'not_linked' if reasons else 'source_cooccurrence_proposal', 'abstention_reasons': sorted(reasons),
        'condition_scope': event['proposed_kind'] or 'unresolved_source_scope',
        'sample_identity': 'not_established', 'own_work_origin': 'not_established',
        'scientific_support': 'not_evaluated', 'per_result_applicability': 'not_established'}


def audit_completeness(packet: dict[str, Any], diagnostics: dict[str, Any]) -> dict[str, Any]:
    validate_compact_packet(packet, diagnostics)
    wire = diagnostics['wire']
    nodes = {n['id']: n for n in wire['nodes']}
    plans = {p['parent_region_id']: p for p in diagnostics['parent']['preparation']['pages']}
    sources = {p['source']['region_id']: p['source'] for p in diagnostics['parent']['audit']['pages']}
    pages = []
    for page in wire['pages']:
        key = page['parent_region_id']
        source = sources[key]
        selected = [n for n in wire['nodes'] if n['page_ref'] == page['page_ref']]
        contexts = [c for c in wire['contexts'] if c['parent_region_id'] == key]
        seeds = {n for c in contexts for n in c['nodes']}
        core = {n for c in contexts for n in c['core_nodes']}

        def covered(ids: set[str], text: str = source['page_text']) -> bool:
            return full_coverage(text, [(nodes[n]['start'], nodes[n]['end']) for n in ids])

        union = covered({n['id'] for n in selected})
        if union != (key in packet['assembled_complete_pages']):
            raise ValueError('Completeness audit full-page union differs from immutable compact packet')
        pages.append({'page_ref': page['page_ref'], 'parent_region_id': key,
            'source': {k: deepcopy(source[k]) for k in ('article_id', 'original_pdf_path', 'original_pdf_sha256',
                'layer_pdf_path', 'layer_pdf_sha256', 'page_number', 'text_layer', 'text_layer_id', 'page_text_sha256')},
            'mapping_unproven': page['mapping_unproven'], 'registered_blocks': len(plans[key]['blocks']),
            'retained_blocks': len(selected), 'original_windows': len(contexts), 'core_union_full_page': covered(core),
            'original_window_union_full_page': covered(seeds), 'selected_union_full_page': union,
            'single_complete_window_ids': [c['context_id'] for c in contexts
                if full_coverage(source['page_text'], [(c['start'], c['end'])])],
            'added_dependency_nodes': [n['id'] for n in selected if n['id'] not in seeds],
            'retained_node_refs': [n['id'] for n in selected], 'open_boundaries': deepcopy(page['open_boundaries']),
            'parent_diagnostics': deepcopy(page['parent_diagnostics']),
            'unlocalized_diagnostics': deepcopy(page['unlocalized_diagnostics']),
            'disposition': 'full_page_block_preserved' if union else 'incomplete_scope_not_proof_of_sufficiency',
            'selection_changed': False, 'scientific_exclusion_proven': False})
    events = [event_audit(n, e) for n in wire['nodes'] for e in n['events']]
    if len({e['event_id'] for e in events}) != len(events):
        raise ValueError('Completeness audit event identities are duplicated')
    units = []
    for i, unit in enumerate(wire['co_preservation_units'], 1):
        members = [e for e in events if e['node_ref'] in unit]
        units.append({'unit_ref': i, 'nodes': deepcopy(unit), 'event_ids': [e['event_id'] for e in members],
            'property_families': sorted({v['kind'] for e in members for v in e['literal_fields']['property']}),
            'cross_event_field_inheritance': False, 'scientific_relation': 'not_established'})
    dependencies = []
    for dependency in wire['dependencies']:
        containing = [u['unit_ref'] for u in units if set(dependency['nodes']) <= set(u['nodes'])]
        if len(containing) != 1:
            raise ValueError('Completeness boundary lost its complete unique co-preservation unit')
        dependencies.append({**deepcopy(dependency), 'unit_ref': containing[0],
            'disposition': 'protected_membership_preserved_semantics_unknown' if dependency['kind'] == 'protected_source_group'
                else 'source_order_retained_boundary_unresolved', 'sentence_join_performed': False})
    summary = {'pages': len(pages), 'full_page_occurrences': sum(p['selected_union_full_page'] for p in pages),
        'original_window_full_page_occurrences': sum(p['original_window_union_full_page'] for p in pages),
        'core_full_page_occurrences': sum(p['core_union_full_page'] for p in pages),
        'single_complete_windows': sum(len(p['single_complete_window_ids']) for p in pages),
        'open_page_boundaries': sum(len(p['open_boundaries']) for p in pages), 'source_events': len(events),
        'source_cooccurrence_proposals': sum(e['chain_state'] == 'source_cooccurrence_proposal' for e in events),
        'event_scope_roles': dict(sorted(Counter(e['scope_role'] for e in events).items())),
        'dependencies': len(dependencies), 'units': len(units), 'selected_blocks': len(nodes),
        'original_windows': len(wire['contexts']), 'added_dependency_blocks': sum(len(p['added_dependency_nodes']) for p in pages)}
    return {'version': VERSION, 'compact_packet_sha256': text_hash(canonical(packet)),
        'diagnostics_sha256': text_hash(canonical(diagnostics)), 'question': wire['question'], 'summary': summary,
        'pages': pages, 'events': events, 'units': units, 'dependencies': dependencies,
        'blocking_reasons': deepcopy(packet['blocking_reasons']), 'selection_changed': False,
        'generation_performed': False, 'external_request_constructed': False, 'network_ready': False,
        'scientific_admission': 'not_evaluated', 'scientific_accuracy': None}


def validate_audit(audit: dict[str, Any], packet: dict[str, Any], diagnostics: dict[str, Any]) -> None:
    if canonical(audit_completeness(packet, diagnostics)) != canonical(audit):
        raise ValueError('Completeness audit differs from deterministic exact-source reconstruction')
