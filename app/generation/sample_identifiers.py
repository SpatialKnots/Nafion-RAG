"""Article-scoped literal sample/table references; scientific identity stays open."""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any

from app.evaluation.context_risks import canonical
from app.records.schema import SourceRegion, text_hash
from app.records.table_cells import build_cell_ledger
from app.records.table_relations import relation_map

VERSION = 'sample_identifier_audit_v0.1'
TABLE = re.compile(r'\b(?:table|табл(?:ица|ице|ицу|ицы)?\.?)\s*(?P<id>\d+)\b', re.IGNORECASE)
FIGURE = re.compile(r'\b(?:fig(?:ure)?\.?|рис(?:унок|унке|унка)?\.?)\s*(?P<id>\d+)\b', re.IGNORECASE)
SAMPLE = re.compile(r'\b(?:sample|specimen|образец|образца)\s+(?P<id>\d+|[A-Z]\d*)\b'
    r'(?!\s*(?:[–—,-]|and\b|or\b|и\b|или\b)\s*\d)', re.IGNORECASE)
MULTIPLE = re.compile(r'\b(?:samples?|specimens?|образец|образца|образц(?:ы|ов|ам|ах))\s+\d+'
    r'(?:\s*(?:[–—-]|,|and|и)\s*\d+)+', re.IGNORECASE)
NUMBERING = re.compile(r'\bнумерация\s+образцов\s+в\s+табл\.?\s*(?P<id>\d+)\b|'
    r'\bsample\s+numbering\s+(?:in|follows)\s+table\s*(?P<en>\d+)\b', re.IGNORECASE)


def mentions(raw: str, offset: int = 0) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for kind, pattern in (('samples', SAMPLE), ('sample_lists_or_ranges', MULTIPLE),
            ('tables', TABLE), ('figures', FIGURE), ('numbering_anchors', NUMBERING)):
        result[kind] = [{'start': offset + m.start(), 'end': offset + m.end(), 'text': m.group(),
            **({'identifier': m.groupdict().get('id') or m.groupdict().get('en')} if kind != 'sample_lists_or_ranges' else {})}
            for m in pattern.finditer(raw)]
    return result


def build_catalog(supplement: dict[str, Any]) -> dict[str, Any]:
    tables = []
    for registered in supplement['tables']:
        source = SourceRegion.model_validate(registered['source'])
        page = registered['page']
        ledger = build_cell_ledger(page, source)
        relations = relation_map(page, ledger, source)
        group = ledger['protected_group']
        captions = [line for line in page['source_gaps']['lines'] if line['block_number'] in group['caption_blocks']]
        matches = [(line, m) for line in captions for m in TABLE.finditer(line['text'])]
        if len(matches) != 1:
            raise ValueError('Sample table caption identifier missing or ambiguous')
        line, match = matches[0]
        caption = {'start': line['page_start'], 'end': line['page_end'], 'text': line['text']}
        sample_headers = [line for line in page['source_gaps']['lines'] if line['block_number'] in group['block_numbers']
            and line['text'].strip() == '№ образца']
        if len(sample_headers) != 1:
            raise ValueError('Sample table requires exactly one printed sample header')
        header = sample_headers[0]
        rows: dict[tuple[int, int], dict[str, Any]] = {}
        for slot in ledger['slots']:
            relation = relations['cells'][slot['cell_id']]
            key = (relation['sample']['start'], relation['sample']['end'])
            row = {'identifier': relation['sample']['text'], 'sample': deepcopy(relation['sample']),
                'printed_plasticiser_composition': deepcopy(relation['composition']),
                'printed_composition_header': deepcopy(relation['plasticiser_header']),
                'printed_basis': deepcopy(relation['basis']), 'printed_group': deepcopy(relation['group']),
                'shared_block': relation['shared_block'], 'scientific_identity': 'not_established'}
            if key in rows and row != rows[key]:
                raise ValueError('Column histories disagree on the same printed sample row')
            rows[key] = row
        tables.append({'article_id': str(source.article_id), 'original_pdf_sha256': source.original_pdf_sha256,
            'source': source.model_dump(mode='json'), 'table_identifier': match.group('id'), 'caption': caption,
            'sample_header': {'start': header['page_start'], 'end': header['page_end'], 'text': header['text']},
            'rows': list(rows.values()), 'protected_group': deepcopy(group),
            'semantic_scope': 'printed_plasticiser_column_not_membrane_or_measurement_environment'})
    return {'version': VERSION, 'tables': tables, 'source_only_supplement': True,
        'historical_model_candidates_applied': False}


def validate_catalog(catalog: dict[str, Any]) -> None:
    if catalog['version'] != VERSION or catalog['historical_model_candidates_applied'] is not False:
        raise ValueError('Sample catalog version/history differs')
    for table in catalog['tables']:
        source = SourceRegion.model_validate(table['source'])
        if (table['article_id'], table['original_pdf_sha256']) != (str(source.article_id), source.original_pdf_sha256):
            raise ValueError('Sample catalog source identity differs')
        caption_ids = [m.group('id') for m in TABLE.finditer(table['caption']['text'])]
        if caption_ids != [table['table_identifier']]:
            raise ValueError('Sample catalog table identifier differs from exact caption')
        spans = [table['caption'], table['sample_header']]
        for row in table['rows']:
            if row['identifier'] != row['sample']['text']:
                raise ValueError('Sample catalog identifier differs from exact row label')
            spans.extend(row[k] for k in ('sample', 'printed_plasticiser_composition', 'printed_composition_header', 'printed_basis')
                if row[k] is not None)
            if row['printed_group']:
                spans.append(row['printed_group']['source'])
                if row['printed_group']['components']:
                    spans.append(row['printed_group']['components'])
        for span in spans:
            if not source.start <= span['start'] < span['end'] <= source.end or source.page_text[span['start']:span['end']] != span['text']:
                raise ValueError('Sample catalog span differs from exact registered source')


def audit_identifiers(applicability: dict[str, Any], origin: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    if (applicability['version'] != 'condition_applicability_audit_v0.1' or applicability['selection_changed']
            or applicability['network_ready'] or origin['version'] != 'source_origin_audit_v0.1'):
        raise ValueError('Identifier audit requires unchanged offline stage44/43 parents')
    validate_catalog(catalog)
    if [(r['node_id'], r['text'], r['selected']) for r in applicability['rows']] != [
            (r['node_id'], r['text'], r['selected']) for r in origin['rows']]:
        raise ValueError('Identifier parent block identities/text/selection differ')
    anchors = []
    for row in applicability['rows']:
        for hit in mentions(row['text'], row['start'])['numbering_anchors']:
            anchors.append({**hit, 'source': deepcopy(row['source']), 'node_id': row['node_id'],
                'node_ref': row['node_ref'], 'context': row['text'], 'scientific_support': 'not_evaluated'})
    origin_events = {e['event_id']: e for row in origin['rows'] for e in row['events']}
    rows = []
    for row in applicability['rows']:
        events = []
        for event in row['events']:
            context = event['context']
            inventory = mentions(context['text'], context['start'])
            explicit = {h['identifier'] for h in inventory['tables']}
            local_anchors = [a for a in anchors if a['source']['article_id'] == row['source']['article_id']
                and a['source']['original_pdf_sha256'] == row['source']['original_pdf_sha256']]
            scope = explicit or {a['identifier'] for a in local_anchors}
            bindings = []
            for mention in inventory['samples']:
                candidates = [{'table_index': i, 'table_identifier': table['table_identifier'], 'row': deepcopy(candidate)}
                    for i, table in enumerate(catalog['tables']) if table['article_id'] == row['source']['article_id']
                    and table['original_pdf_sha256'] == row['source']['original_pdf_sha256']
                    and table['table_identifier'] in scope for candidate in table['rows']
                    if candidate['identifier'] == mention['identifier']]
                reasons = []
                if not scope:
                    reasons.append('no_explicit_table_or_article_numbering_scope')
                if len(scope) > 1:
                    reasons.append('multiple_table_or_numbering_scopes')
                if len(candidates) != 1:
                    reasons.append('missing_or_multiple_same_article_sample_rows')
                if len(inventory['samples']) > 1 or inventory['sample_lists_or_ranges']:
                    reasons.append('multiple_samples_in_event_do_not_identify_one_measurement')
                source_event = origin_events[event['event_id']]
                if source_event['origin_state'] not in ('unknown', 'own_work_cue_proposal'):
                    reasons.append('reported_cited_or_ambiguous_origin')
                if source_event['original_guards'] or source_event['original_boundary_diagnostics']:
                    reasons.append('original_guards_or_boundaries_preserved')
                if source_event['section_kind_proposal'] == 'bibliography':
                    reasons.append('bibliography_not_current_article_sample_identity')
                if len(candidates) == 1 and (candidates[0]['row']['shared_block'] or
                        candidates[0]['row']['printed_plasticiser_composition'] is None):
                    reasons.append('sample_row_layout_or_printed_composition_unresolved')
                state = 'literal_row_identity_proposal' if not reasons else 'unresolved_with_row_candidate' if candidates else 'unresolved'
                bindings.append({'mention': deepcopy(mention), 'state': state, 'scope_basis': 'same_event_table_reference'
                    if explicit else 'article_numbering_anchor' if scope else 'unknown',
                    'explicit_table_refs': deepcopy(inventory['tables']), 'numbering_anchors': deepcopy(local_anchors),
                    'candidates': candidates, 'abstention_reasons': sorted(reasons),
                    'sample_identity': 'not_established', 'per_result_method_applicability': 'not_established',
                    'condition_transfer_performed': False, 'scientific_support': 'not_evaluated'})
            events.append({'event_id': event['event_id'], 'context': deepcopy(context), 'inventory': inventory,
                'bindings': bindings, 'original_guards': deepcopy(event['original_guards']),
                'original_boundary_diagnostics': deepcopy(event['original_boundary_diagnostics'])})
        rows.append({**{k: deepcopy(row[k]) for k in ('block_ref', 'node_ref', 'node_id', 'selected', 'source', 'source_type',
            'start', 'end', 'text', 'text_sha256')}, 'events': events})
    events = [e for row in rows for e in row['events']]
    selected = [e for row in rows if row['selected'] for e in row['events']]
    bindings = [b for e in selected for b in e['bindings']]
    return {'version': VERSION, 'question': applicability['question'], 'rows': rows, 'numbering_anchors': anchors,
        'parent_applicability_sha256': text_hash(canonical(applicability)), 'catalog_sha256': text_hash(canonical(catalog)),
        'metrics': {'blocks': len(rows), 'events': len(events), 'selected_blocks': sum(r['selected'] for r in rows),
            'selected_events': len(selected), 'selected_sample_mentions': sum(len(e['inventory']['samples']) for e in selected),
            'selected_table_refs': sum(len(e['inventory']['tables']) for e in selected),
            'selected_figure_refs': sum(len(e['inventory']['figures']) for e in selected),
            'selected_unexpanded_lists_or_ranges': sum(len(e['inventory']['sample_lists_or_ranges']) for e in selected)},
        'selected_binding_states': dict(Counter(b['state'] for b in bindings)),
        'wire_sha256_unchanged': applicability['wire_sha256_unchanged'],
        'blocking_reasons': deepcopy(applicability['blocking_reasons']), 'selection_changed': False, 'network_ready': False,
        'generation_performed': False, 'external_request_constructed': False, 'scientific_loss_status': 'not_evaluated'}
