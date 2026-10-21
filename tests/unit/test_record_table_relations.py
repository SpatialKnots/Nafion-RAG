"""Constructed coordinate/cue counterexamples, not independent scientific annotations."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.records.fixed_links import FixedSpanMeasurement
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from app.records.table_cells import build_cell_ledger, token_address
from app.records.table_relations import audit_measurement, history_comparisons, relation_map
from app.records.table_relations_export import bind_run, reconcile_history, render_relations
from tests.unit.test_record_table_continuation import table_source


def source_fixture(*, header='пластификатора', duplicate_header=False, duplicate_basis=False,
                   third_group='Смеси G2/EC', tie_group=False, shared=False):
    base, _ = table_source()
    text, lines = 'Hidden prefix.\n', []

    def add(raw, x, y, block, width=35):
        nonlocal text
        value = raw + '\n'
        lines.append({'block_number': block, 'page_start': len(text), 'page_end': len(text) + len(value),
                      'bbox': [x, y, x + width, y + 8], 'text': value, 'text_sha256': text_hash(value)})
        text += value
        return lines[-1]

    start = len(text)
    add('№ образца', 0, 10, 0, 40)
    add('Состав', 125, 8, 1)
    add(header, 100, 18, 1, 85)
    basis = add('(масс. доли)', 115, 28, 2, 50)
    percent = add('мас. %', 210, 28, 3)
    for column, label in enumerate(('σ30°C,', 'σ–40°C,')):
        add(label, 300 + 100 * column, 10, 4 + column)
        add('См см–1', 300 + 100 * column, 20, 4 + column)
    if duplicate_header:
        add(header, 100, 18, 1, 85)
    if duplicate_basis:
        add('(масс. доли)', 115, 28, 2, 50)
    for row in range(1, 5):
        y = 30 + 30 * row
        block = row + 9 if not (shared and row == 3) else 11
        if row in {1, 3, 4}:
            label = 'Смеси EC/G2' if row == 1 else third_group if row == 3 else 'Индивидуальные растворители'
            add(label, 230, y - 15, block, 120)
            if row == 1 and tie_group:
                add('Смеси G2/EC', 230, y - 15, block, 120)
        add(str(row), 10, y, block, 10)
        add('SL' if row == 4 else '0.2/0.8', 130, y, block, 45)
        add('82.2', 210, y, block)
        add('1.0 × 10–4', 300, y, block)
        add('2.0 × 10–5', 400, y, block)
    end = len(text)
    text += 'Hidden suffix.'
    data = base.regions[0].model_dump()
    data.update(page_text=text, page_text_sha256=text_hash(text), start=start, end=end, quote=text[start:end],
                quote_sha256=text_hash(text[start:end]))
    data['region_id'] = source_identity(data)
    table = SourceRegion.model_validate(data)
    method_data = base.regions[1].model_dump()
    method = 'Электропроводность измеряли методом импедансной\nспектроскопии. Прибор Z-3000.'
    full = 'Hidden prefix. ' + method + ' Hidden continuation.'
    method_start = full.index(method)
    method_data.update(page_text=full, page_text_sha256=text_hash(full), start=method_start, end=method_start + len(method),
                       quote=method, quote_sha256=text_hash(method))
    method_data['region_id'] = source_identity(method_data)
    bundle = base.model_copy(update={'regions': (table, SourceRegion.model_validate(method_data))})
    page = {'article_id': str(table.article_id), 'page_number': table.page_number, 'page_text': text,
            'page_text_sha256': text_hash(text), 'text_layer_id': str(table.text_layer_id),
            'original_pdf_sha256': table.original_pdf_sha256, 'source_gaps': {'text_geometry_proven': True, 'lines': lines},
            'protected_groups': [{'kind': 'closed_ruled_table_proposal',
                                  'block_numbers': sorted({line['block_number'] for line in lines}), 'page_ranges': [[start, end]]}]}
    ledger = build_cell_ledger(page, table)
    relations = relation_map(page, ledger, table)
    return bundle, page, ledger, relations, {'percent': percent, 'basis': basis}


def address(bundle, reference):
    index, region = next((i, r) for i, r in enumerate(bundle.regions, 1) if r.region_id == reference['region_id'])
    return token_address(region, reference['start'], reference['end'], label=f'R{index}')


def measurement(bundle, cell, relations):
    expected = relations['cells'][cell['cell_id']]
    table = bundle.regions[0]
    raw = {'sample_label': expected['sample'], 'value': {**cell['value'], 'region_id': table.region_id},
           'unit': {**cell['unit'], 'region_id': table.region_id},
           'temperature': {**cell['header'], 'region_id': table.region_id,
                           'start': cell['header']['start'] + 1, 'end': cell['header']['end'] - 1},
           'property_name': {**cell['header'], 'region_id': table.region_id, 'end': cell['header']['start'] + 1},
           'medium': expected['medium_label'], 'medium_composition': expected['composition'],
           'composition_basis': {**expected['basis'], 'start': expected['basis']['start'] + 1, 'end': expected['basis']['end'] - 1}}
    method = bundle.regions[1]
    method_start = method.start + method.quote.index('импедансной')
    raw['method'] = {'region_id': method.region_id, 'start': method_start,
                     'end': method_start + len('импедансной\nспектроскопии')}
    from app.records.extraction import FIELDS

    observations = []
    for name in FIELDS:
        citations = [raw[name]] if name in raw else []
        if name == 'medium_composition':
            citations += [expected['sample'], expected['plasticiser_header'], expected['basis']]
            if expected['group']['kind'] == 'mixture':
                citations.append(expected['group']['source'])
        observations.append({'field': name, 'status': 'present' if name in raw else 'not_found_in_context',
                             'raw_span': address(bundle, raw[name]) if name in raw else None,
                             'evidence': [address(bundle, s) for s in citations], 'note': 'Constructed exact selection.'})
    roles = {'sample_value': ('sample_label', 'value'), 'property_value': ('property_name', 'value'),
             'conditions_measurement': ('temperature', 'value', 'method')}
    return FixedSpanMeasurement.model_validate({'observations': observations, 'representation': 'scalar',
        'linkage': {role: {'evidence': [address(bundle, raw[f]) for f in fields], 'note': 'Constructed association.'}
                    for role, fields in roles.items()}})


def outcome(findings, rule):
    return next(f['outcome'] for f in findings if f['rule'] == rule)


def test_exact_source_chain_does_not_grant_scientific_acceptance_or_numeric_pure_fraction():
    bundle, _, ledger, relations, _ = source_fixture()
    for cell in (ledger['slots'][0], ledger['slots'][6]):
        reply = measurement(bundle, cell, relations)
        findings = audit_measurement(bundle, reply, cell, relations)
        assert outcome(findings, 'medium_composition.source_label') == 'coordinates_match'
        assert outcome(findings, 'composition.citation_chain') == 'endpoints_covered'
        assert outcome(findings, 'method.literal_source') == 'literal_method_cue'
        assert outcome(findings, 'composition.semantic_scope') == outcome(findings, 'method.applicability') == 'unknown'
        assert all(f['scientific_support'] == 'not_evaluated' for f in findings)
    assert relations['cells'][ledger['slots'][6]['cell_id']]['composition']['text'] == 'SL'


@pytest.mark.parametrize('field,other_index', [('medium_composition', 2), ('medium_composition', 4), ('medium', 4)])
def test_identical_ratio_or_reversed_group_at_other_coordinates_is_not_substituted(field, other_index):
    bundle, _, ledger, relations, _ = source_fixture()
    cell = ledger['slots'][0]
    original = measurement(bundle, cell, relations).model_dump(mode='json')
    other = measurement(bundle, ledger['slots'][other_index], relations)
    replacement = next(o for o in other.observations if o.field == field)
    obs = next(o for o in original['observations'] if o['field'] == field)
    obs.update(raw_span=replacement.raw_span.model_dump(), evidence=[s.model_dump() for s in replacement.evidence])
    findings = audit_measurement(bundle, FixedSpanMeasurement.model_validate(original), cell, relations)
    assert outcome(findings, f'{field}.source_label') == 'different_source_coordinates'


@pytest.mark.parametrize('variation', ['mass_percent', 'partial_basis', 'broad_composition'])
def test_other_column_partial_and_broad_raw_selections_remain_diagnostics(variation):
    bundle, _, ledger, relations, extra = source_fixture()
    cell = ledger['slots'][0]
    data = measurement(bundle, cell, relations).model_dump(mode='json')
    field = 'medium_composition' if variation == 'broad_composition' else 'composition_basis'
    expected = relations['cells'][cell['cell_id']]
    if variation == 'mass_percent':
        reference = {'region_id': bundle.regions[0].region_id, 'start': extra['percent']['page_start'],
                     'end': extra['percent']['page_end'] - 1}
    elif variation == 'partial_basis':
        reference = {**expected['basis'], 'start': expected['basis']['start'] + 1, 'end': expected['basis']['start'] + 6}
    else:
        reference = {**expected['composition'], 'start': expected['sample']['start']}
    obs = next(o for o in data['observations'] if o['field'] == field)
    obs.update(raw_span=address(bundle, reference), evidence=[address(bundle, reference)])
    findings = audit_measurement(bundle, FixedSpanMeasurement.model_validate(data), cell, relations)
    assert outcome(findings, f'{field}.source_label') == 'different_source_coordinates'


@pytest.mark.parametrize('variation', ['missing_header', 'duplicate_header', 'duplicate_basis', 'unknown_group', 'tie_group', 'shared'])
def test_unsupported_source_layout_is_not_repaired_or_forced(variation):
    kwargs = {'header': 'unknown'} if variation == 'missing_header' else {
        'third_group': 'Unrecognized section'} if variation == 'unknown_group' else {variation: True}
    _, _, ledger, relations, _ = source_fixture(**kwargs)
    first = relations['cells'][ledger['slots'][0]['cell_id']]
    third = relations['cells'][ledger['slots'][4]['cell_id']]
    if variation in {'missing_header', 'duplicate_header'}:
        assert first['plasticiser_header'] is first['composition'] is None
    elif variation == 'duplicate_basis':
        assert first['basis'] is None
    elif variation == 'unknown_group':
        assert third['group'] is third['medium_label'] is None
    elif variation == 'tie_group':
        assert first['group'] is None and len(first['nearby_group_candidates']) == 2
    else:
        assert third['shared_block'] and third['composition'] is None


@pytest.mark.parametrize('field', ['medium', 'medium_composition', 'method'])
def test_missing_field_stays_missing_even_with_source_opportunity(field):
    bundle, _, ledger, relations, _ = source_fixture()
    cell = ledger['slots'][0]
    data = measurement(bundle, cell, relations).model_dump(mode='json')
    obs = next(o for o in data['observations'] if o['field'] == field)
    obs.update(status='not_found_in_context', raw_span=None, evidence=[])
    findings = audit_measurement(bundle, FixedSpanMeasurement.model_validate(data), cell, relations)
    rule = 'method.literal_source' if field == 'method' else f'{field}.source_label'
    assert outcome(findings, rule) == 'not_proposed' and obs['raw_span'] is None


@pytest.mark.parametrize('variation', ['unrelated_text', 'same_page', 'foreign_article'])
def test_method_region_or_article_membership_alone_is_not_enough(variation):
    bundle, _, ledger, relations, _ = source_fixture()
    cell = ledger['slots'][0]
    data = measurement(bundle, cell, relations).model_dump(mode='json')
    if variation == 'unrelated_text':
        method = bundle.regions[1]
        start = method.start + method.quote.index('Прибор')
        reference = {'region_id': method.region_id, 'start': start, 'end': method.end}
        obs = next(o for o in data['observations'] if o['field'] == 'method')
        obs.update(raw_span=address(bundle, reference), evidence=[address(bundle, reference)])
    else:
        source = bundle.regions[1].model_dump()
        source.update({'page_number': bundle.regions[0].page_number} if variation == 'same_page' else {'article_id': uuid4()})
        source['region_id'] = source_identity(source)
        bundle = bundle.model_copy(update={'regions': (bundle.regions[0], SourceRegion.model_validate(source))})
    findings = audit_measurement(bundle, FixedSpanMeasurement.model_validate(data), cell, relations)
    assert outcome(findings, 'method.literal_source') == 'unsupported_method_source_or_wording'


@pytest.mark.parametrize('variation', ['field_chain', 'sample_value', 'property_value', 'conditions_measurement', 'missing_role'])
def test_selected_endpoints_must_be_covered_by_that_fields_or_roles_actual_citations(variation):
    bundle, _, ledger, relations, _ = source_fixture()
    cell = ledger['slots'][0]
    data = measurement(bundle, cell, relations).model_dump(mode='json')
    if variation == 'field_chain':
        obs = next(o for o in data['observations'] if o['field'] == 'medium_composition')
        obs['evidence'] = [obs['raw_span']]
        rule = 'composition.citation_chain'
    elif variation == 'missing_role':
        data['linkage']['sample_value'] = None
        rule = 'linkage.sample_value.endpoint_coverage'
    else:
        data['linkage'][variation]['evidence'].pop()
        rule = f'linkage.{variation}.endpoint_coverage'
    findings = audit_measurement(bundle, FixedSpanMeasurement.model_validate(data), cell, relations)
    assert outcome(findings, rule) == ('not_proposed' if variation == 'missing_role' else 'citation_endpoint_not_covered')


def test_source_geometry_drift_and_changed_ledger_fields_fail():
    bundle, page, ledger, _, _ = source_fixture()
    changed = copy.deepcopy(ledger)
    changed['slots'][0]['value']['text'] = 'Changed'
    with pytest.raises(ValueError, match='geometry differs'):
        relation_map(page, changed, bundle.regions[0])
    page['source_gaps']['lines'][0]['text_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='line text/hash/geometry'):
        relation_map(page, ledger, bundle.regions[0])


def test_all_candidate_versions_are_required_and_context_change_is_not_a_conflicting_fact():
    ledger = {'slots': [{'cell_id': 'cell', 'previous_proposals': ['old'],
                         'new_proposals': [{'record_id': 'new', 'case_id': 'revisit'}], 'stage22_proposals': []}]}
    rows = [{'record_id': 'old', 'cell_id': 'cell', 'stage': 'stage20', 'case_id': 'kayumov_table', 'region_ids': ['R1'],
             'selected_fields': {'method': {'status': 'not_found_in_context', 'raw': None}}},
            {'record_id': 'new', 'cell_id': 'cell', 'stage': 'stage21', 'case_id': 'revisit', 'region_ids': ['R1', 'R2'],
             'selected_fields': {'method': {'status': 'present', 'raw': {'region': 'R2'}}}}]
    reconcile_history(ledger, rows)
    comparison = history_comparisons(rows)
    assert comparison[0]['changed_fields'] == ['method'] and len(comparison[0]['candidate_versions']) == 2
    assert 'not confirmed conflicting facts' in comparison[0]['interpretation']
    for invalid in (rows[:1], rows + rows[:1], [{**rows[0], 'cell_id': 'different'}, rows[1]]):
        with pytest.raises(ValueError):
            reconcile_history(ledger, invalid)


@pytest.mark.parametrize('variation', ['drift', 'unbound_parent', 'wrong_version', 'failed_run'])
def test_manifest_binding_or_failed_run_blocks_audit(tmp_path, variation):
    report = {'final_source_integrity': {'status': 'verified'}, 'cases': [{'status': 'integrity_valid'}]}
    if variation == 'failed_run':
        report['cases'][0]['status'] = 'failed'
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report), encoding='utf-8')
    manifest = {'version': 'constructed-version', 'artifacts': {'report.json': file_hash(path)}}
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    bindings = {str(manifest_path.resolve()): file_hash(manifest_path), str(path.resolve()): file_hash(path)}
    if variation == 'drift':
        path.write_bytes(b'changed')
    if variation == 'unbound_parent':
        bindings = {}
    with pytest.raises(ValueError):
        bind_run(tmp_path, bindings, 'other' if variation == 'wrong_version' else 'constructed-version', inherited=True)


def test_read_only_html_keeps_empty_slots_and_escapes_source_proposals():
    bundle, _, ledger, relations, _ = source_fixture()
    slot = ledger['slots'][0]
    report = {'version': 'constructed-audit', 'input_snapshot': {}, 'summary': {}, 'method_source_diagnostics': {},
              'history_comparisons': [], 'sources': {r.region_id: r.model_dump(mode='json') for r in bundle.regions},
              'slots': ledger['slots'], 'candidates': [{'cell_id': slot['cell_id'], 'record_id': 'constructed-record',
                'stage': 'stage20', 'findings': [{'outcome': 'unknown'}], 'artifacts': {'input': str(Path('/synthetic/input.json'))},
                'candidate': {'note': '<script>untrusted()</script>'}, 'previous_checks': {}, 'raw_selection': {}}]}
    rendered = render_relations(report)
    assert rendered.count('class="slot"') == 8 and rendered.count('class="candidate"') == 1
    assert '&lt;script&gt;untrusted()&lt;/script&gt;' in rendered and '<script>untrusted()' not in rendered
    assert 'Scientific support remains not evaluated' in rendered and '<form' not in rendered
    assert relations['scientific_semantics'] == 'not_evaluated'
