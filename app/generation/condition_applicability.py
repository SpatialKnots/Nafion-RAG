"""Exact same-event condition links; no numerical normalization or scientific admission."""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any

from app.evaluation.context_risks import canonical
from app.generation.context_completeness import FIELDS
from app.records.protocol_association import PROPERTY_CUES
from app.records.schema import text_hash

VERSION = 'condition_applicability_audit_v0.1'
NUMBER = r'[+−–-]?\d+(?:[.,]\d+)?'
UNIT = r'(?:°\s*[CСK]|℃)'
ENDPOINT = NUMBER + r'(?:\s*[.…–—-]+\s*' + NUMBER + r')?'
CONDITIONS = (
    ('temperature_range', rf'\b(?:from|от)\s+{ENDPOINT}(?:\s*{UNIT})?\s+(?:to|до)\s*{ENDPOINT}\s*{UNIT}'),
    ('temperature_step', rf'\b(?:с\s+шагом|(?:with\s+)?(?:a\s+)?steps?\s+of|in\s+steps?\s+of)\s*{NUMBER}\s*{UNIT}'),
    ('temperature_accuracy', rf'\b(?:accuracy|точност[ьи])(?:\s+поддержания\s+температу(?:-\s*)?ры)?\s*'
        rf'(?:of\s*)?[±]?\s*{NUMBER}\s*{UNIT}'),
    ('temperature_unresolved', rf'(?<![\w.])[±]?\s*{NUMBER}\s*{UNIT}'),
    ('frequency_range', rf'(?<!\w){NUMBER}\s*(?:[кМГkMG]?(?:Гц|Hz))\s*[–—-]\s*{NUMBER}\s*(?:[кМГkMG]?(?:Гц|Hz))'),
    ('frequency_unresolved', rf'(?<!\w){NUMBER}\s*(?:[кМГkMG]?(?:Гц|Hz))\b'),
    ('duration', rf'(?<!\w){NUMBER}\s*(?:hours?|minutes?|days?|min|h|ч|мин|сут)\b'),
    ('atmosphere_mention', r'\b(?:argon|nitrogen|air|vacuum|арго(?:-\s*)?н\w*|азот\w*|воздух\w*|вакуум\w*)\b'),
)
LABEL = re.compile(r'\b(?:(?:sample|specimen)\s+(?:[A-Z]\d*|\d+)|образец\s+\d+)\b', re.IGNORECASE)
MEASUREMENT = re.compile(r'\b(?:(?:conductivity|impedance\s+spectra)\s+(?:was|were)\s+measured|'
    r'we\s+measured|measurements\s+were\s+(?:performed|conducted|carried\s+out)|'
    r'электропроводность\s+измеряли|для\s+измерений\s+импеданса\s+использовали)\b', re.IGNORECASE)
PREPARATION = re.compile(r'\b(?:prepared|dried|annealed|preparation|conditioning|equilibrat\w*|'
    r'подготов\w*|сборк\w*|выдерж\w*)\b', re.IGNORECASE)


def inventory(event: dict[str, Any]) -> dict[str, Any]:
    raw, offset = event['context']['text'], event['context']['start']

    def hit(kind: str, match: re.Match[str]) -> dict[str, Any]:
        return {'kind': kind, 'start': offset + match.start(), 'end': offset + match.end(), 'text': match.group()}

    conditions: list[dict[str, Any]] = []
    for kind, pattern in CONDITIONS:
        for match in re.finditer(pattern, raw, re.IGNORECASE):
            value = hit(kind, match)
            if any(value['start'] < prior['end'] and prior['start'] < value['end'] for prior in conditions):
                continue
            conditions.append(value)
    properties = [hit(kind, m) for kind, pattern in PROPERTY_CUES for m in pattern.finditer(raw)]
    methods = [hit('conductivity' if kind == 'impedance' else 'thermal_analysis', m)
        for field, kind, pattern in FIELDS if field == 'method' for m in pattern.finditer(raw)]
    samples = [hit('generic_sample_mention', m) for field, _, pattern in FIELDS if field == 'sample'
        for m in pattern.finditer(raw)]
    labels = [hit('explicit_sample_label', m) for m in LABEL.finditer(raw)]
    coordinated = any(re.match(r'\s*(?:and|or|и|или|,|/)\s*\w', raw[h['end'] - offset:], re.IGNORECASE) for h in labels)
    identity = ('single_explicit_label_proposal' if len(labels) == 1 and not coordinated else
        'ambiguous_explicit_labels' if labels else 'generic_class_only' if samples else 'unknown')
    return {'properties': properties, 'methods': methods, 'samples': samples, 'explicit_labels': labels,
        'sample_identity_state': identity, 'conditions': sorted(conditions, key=lambda h: (h['start'], h['end'])),
        'measurement_cues': [hit('measurement_action', m) for m in MEASUREMENT.finditer(raw)],
        'preparation_cues': [hit('preparation_action', m) for m in PREPARATION.finditer(raw)]}


def link_event(event: dict[str, Any]) -> dict[str, Any]:
    fields = inventory(event)
    role = event['procedure_role']
    preparation = bool(fields['preparation_cues']) or role in ('preparation_or_conditioning_cues', 'mixed_procedure_cues')
    measurement = bool(fields['measurement_cues']) or role in ('measurement_cues', 'mixed_procedure_cues')
    reasons = []
    if preparation:
        reasons.append('preparation_or_conditioning_not_inherited_by_measurement')
    if not measurement:
        reasons.append('measurement_scope_not_established')
    if event['original_guards']:
        reasons.append('original_block_guards_preserved')
    if event['original_boundary_diagnostics']:
        reasons.append('original_boundaries_unresolved')
    if event['origin_state'] not in ('unknown', 'own_work_cue_proposal') or event['section_kind_proposal'] == 'bibliography':
        reasons.append('origin_not_eligible_for_local_measurement_proposal')
    for key in ('properties', 'methods', 'samples'):
        if not fields[key] and not (key == 'samples' and fields['explicit_labels']):
            reasons.append('missing_same_event_' + key)
    properties = {h['kind'] for h in fields['properties']}
    methods = {h['kind'] for h in fields['methods']}
    if len(properties) != 1 or methods != properties:
        reasons.append('property_method_family_not_unique_and_matching')
    if fields['sample_identity_state'] == 'ambiguous_explicit_labels':
        reasons.append('explicit_sample_labels_ambiguous')
    links = []
    for condition in fields['conditions']:
        parameter = condition['kind'] in ('temperature_step', 'temperature_accuracy')
        state = ('preparation_context_only' if preparation and not measurement else 'unresolved'
            if reasons else 'measurement_protocol_parameter_proposal' if parameter else 'same_event_measurement_context_proposal')
        links.append({'condition': deepcopy(condition), 'state': state,
            'property_spans': deepcopy(fields['properties']), 'method_spans': deepcopy(fields['methods']),
            'sample_spans': deepcopy(fields['samples']), 'explicit_sample_labels': deepcopy(fields['explicit_labels']),
            'sample_identity_state': fields['sample_identity_state'], 'abstention_reasons': sorted(reasons),
            'single_measured_temperature_asserted': False, 'cross_event_inheritance': False,
            'per_result_applicability': 'not_established', 'scientific_support': 'not_evaluated'})
    return {'event_id': event['event_id'], 'context': deepcopy(event['context']), 'inventory': fields,
        'links': links, 'origin_state': event['origin_state'], 'original_state': event['original_state'],
        'original_guards': deepcopy(event['original_guards']),
        'original_boundary_diagnostics': deepcopy(event['original_boundary_diagnostics']),
        'scientific_limitations': ['own_work_not_proven', 'sample_identity_not_proven', 'per_result_applicability_not_proven']}


def audit_applicability(origin: dict[str, Any]) -> dict[str, Any]:
    if origin['version'] != 'source_origin_audit_v0.1' or origin['selection_changed'] or origin['network_ready']:
        raise ValueError('Applicability audit requires the unchanged offline stage43 origin audit')
    rows = [{**{k: deepcopy(row[k]) for k in ('block_ref', 'node_ref', 'node_id', 'selected', 'source',
        'source_type', 'start', 'end', 'text', 'text_sha256')},
        'events': [link_event(e) for e in row['events']]} for row in origin['rows']]
    events = [e for row in rows for e in row['events']]
    selected_events = [e for row in rows if row['selected'] for e in row['events']]
    links = [link for e in selected_events for link in e['links']]
    return {'version': VERSION, 'parent_origin_sha256': text_hash(canonical(origin)), 'question': origin['question'],
        'rows': rows, 'metrics': {'blocks': len(rows), 'events': len(events),
            'selected_blocks': sum(row['selected'] for row in rows), 'selected_events': len(selected_events),
            'selected_condition_occurrences': len(links)},
        'selected_condition_roles': dict(Counter(link['condition']['kind'] for link in links)),
        'selected_link_states': dict(Counter(link['state'] for link in links)),
        'wire_sha256_unchanged': origin['wire_sha256_unchanged'], 'blocking_reasons': deepcopy(origin['blocking_reasons']),
        'selection_changed': False, 'network_ready': False, 'generation_performed': False,
        'external_request_constructed': False, 'scientific_loss_status': 'not_evaluated'}
