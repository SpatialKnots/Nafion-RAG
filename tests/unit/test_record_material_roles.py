"""Constructed source-role counterexamples; no independent chemical reference labels."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.records.fixed_links import FixedSpanMeasurement
from app.records.material_roles import ROLE_NAMES, RoleProjection, RoleSpan, candidate_hash, project_roles
from app.records.material_roles_export import export_material_roles, load_role_parent, role_summary
from app.records.multi import MultiReply, resolve_multi_reply
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from app.records.table_cells import absolute_span, build_cell_ledger
from app.records.table_relations import relation_map
from tests.unit.test_record_table_relations import address, measurement, source_fixture


def make_row(bundle, selected, cell):
    reply = MultiReply(schema_version='records_multi_fixed_reply_v0.1', coverage='claimed_complete_in_context',
                      returned_measurement_count=1, measurements=(selected,), unresolved=(), diagnostic='Constructed role fixture.')
    resolved, _ = resolve_multi_reply(bundle, reply)
    record = resolved.records[0]
    return {'record_id': str(record.record_id), 'cell_id': cell['cell_id'], 'candidate': record.model_dump(mode='json'),
            'selected_fields': {str(o.field): {'status': o.status, 'raw': absolute_span(bundle, o.raw_span) if o.raw_span else None}
                                for o in selected.observations},
            'region_ids': [r.region_id for r in bundle.regions], 'stage': 'stage20', 'case_id': 'kayumov_table', 'artifacts': {}}


def fixture(index=0):
    bundle, page, ledger, relations, extra = source_fixture()
    cell = ledger['slots'][index]
    selected = measurement(bundle, cell, relations)
    row = make_row(bundle, selected, cell)
    return bundle, page, ledger, relations, extra, selected, row


def sources(bundle):
    return {r.region_id: r for r in bundle.regions}


def roles(projection):
    return {r.role: r for r in projection.roles}


def change_selection(bundle, selected, field, reference):
    data = selected.model_dump(mode='json')
    obs = next(o for o in data['observations'] if o['field'] == field)
    obs.update(raw_span=address(bundle, reference), evidence=[address(bundle, reference)])
    return FixedSpanMeasurement.model_validate(data)


def test_exact_role_projection_is_additive_and_keeps_scientific_unknowns():
    bundle, _, ledger, relations, _, _, row = fixture()
    original = copy.deepcopy(row)
    projected = project_roles(row, sources(bundle), relations['cells'][ledger['slots'][0]['cell_id']])
    by_role = roles(projected)
    assert by_role['plasticiser_components'].bindings[0].selected.text == 'EC/G2'
    assert by_role['plasticiser_composition'].bindings[0].selected.text == '0.2/0.8'
    assert by_role['plasticiser_basis'].bindings[0].selected.text == 'масс. доли'
    for name in ('membrane_composition', 'measurement_environment'):
        assert by_role[name].status == 'unknown' and not by_role[name].bindings
    assert projected.original_candidate_sha256 == candidate_hash(original['candidate']) and row == original
    assert projected.scientific_admission == 'not_evaluated'
    assert all(r.scientific_support == 'not_evaluated' for r in projected.roles)


def test_pure_code_never_becomes_fraction_one_and_two_legacy_fields_are_not_merged():
    bundle, _, ledger, relations, _, _, row = fixture(6)
    projected = project_roles(row, sources(bundle), relations['cells'][ledger['slots'][6]['cell_id']])
    by_role = roles(projected)
    assert [b.selected.text for b in by_role['plasticiser_components'].bindings] == ['SL', 'SL']
    assert {b.source_field for b in by_role['plasticiser_components'].bindings} == {'medium', 'medium_composition'}
    assert by_role['plasticiser_composition'].status == 'unknown' and not by_role['plasticiser_composition'].bindings
    assert role_summary([projected])['candidate_versions'] == role_summary([projected])['unique_candidate_cells'] == 1


def test_field_names_do_not_override_source_role():
    bundle, _, ledger, relations, _, selected, _ = fixture()
    data = selected.model_dump(mode='json')
    medium = next(o for o in data['observations'] if o['field'] == 'medium')
    composition = next(o for o in data['observations'] if o['field'] == 'medium_composition')
    medium['raw_span'], composition['raw_span'] = composition['raw_span'], medium['raw_span']
    medium['evidence'], composition['evidence'] = composition['evidence'], medium['evidence']
    row = make_row(bundle, FixedSpanMeasurement.model_validate(data), ledger['slots'][0])
    projected = project_roles(row, sources(bundle), relations['cells'][row['cell_id']])
    assert roles(projected)['plasticiser_components'].bindings[0].source_field == 'medium_composition'
    assert roles(projected)['plasticiser_composition'].bindings[0].source_field == 'medium'


@pytest.mark.parametrize('variant', ['complete_heading', 'parenthesized_basis'])
def test_explicit_boundary_variants_keep_original_text_and_separate_reference(variant):
    bundle, _, ledger, relations, _, selected, _ = fixture()
    context = relations['cells'][ledger['slots'][0]['cell_id']]
    field = 'medium' if variant == 'complete_heading' else 'composition_basis'
    reference = context['group']['source'] if variant == 'complete_heading' else context['basis']
    row = make_row(bundle, change_selection(bundle, selected, field, reference), ledger['slots'][0])
    projected = project_roles(row, sources(bundle), context)
    binding = roles(projected)['plasticiser_components' if variant == 'complete_heading' else 'plasticiser_basis'].bindings[0]
    assert binding.match_kind == ('complete_group_heading' if variant == 'complete_heading' else 'basis_boundary_variant')
    assert binding.selected.text == reference['text'] and binding.selected.start < binding.reference.start
    assert row['candidate'][field]['raw_text'] == reference['text']


@pytest.mark.parametrize('variant', ['other_row_ratio', 'other_group_order', 'mass_percent', 'partial_basis', 'outside_table'])
def test_unqualified_occurrences_are_retained_unassigned_without_environment_inference(variant):
    bundle, _, ledger, relations, extra, selected, _ = fixture()
    context = relations['cells'][ledger['slots'][0]['cell_id']]
    if variant == 'other_row_ratio':
        field, reference = 'medium_composition', relations['cells'][ledger['slots'][2]['cell_id']]['composition']
    elif variant == 'other_group_order':
        field, reference = 'medium', relations['cells'][ledger['slots'][4]['cell_id']]['medium_label']
    elif variant == 'mass_percent':
        field = 'composition_basis'
        reference = {'region_id': bundle.regions[0].region_id, 'start': extra['percent']['page_start'],
                     'end': extra['percent']['page_end'] - 1}
    elif variant == 'partial_basis':
        field = 'composition_basis'
        reference = {**context['basis'], 'start': context['basis']['start'] + 1, 'end': context['basis']['start'] + 6}
    else:
        field = 'medium'
        method = bundle.regions[1]
        reference = {'region_id': method.region_id, 'start': method.start, 'end': method.end}
    row = make_row(bundle, change_selection(bundle, selected, field, reference), ledger['slots'][0])
    projected = project_roles(row, sources(bundle), context)
    assert len(projected.unassigned_selections) == 1 and projected.unassigned_selections[0].source_field == field
    assert roles(projected)['measurement_environment'].status == 'unknown'


def test_preparation_argon_and_model_confirmation_note_do_not_establish_measurement_environment():
    bundle, _, ledger, relations, _, _, _ = fixture()
    source = bundle.regions[1].model_dump()
    quote = source['quote'] + ' Сборку ячеек проводили в атмосфере аргона.'
    full = source['page_text'][:source['start']] + quote + ' Hidden continuation.'
    source.update(page_text=full, page_text_sha256=text_hash(full), end=source['start'] + len(quote),
                  quote=quote, quote_sha256=text_hash(quote))
    source['region_id'] = source_identity(source)
    bundle = bundle.model_copy(update={'regions': (bundle.regions[0], SourceRegion.model_validate(source))})
    selected = measurement(bundle, ledger['slots'][0], relations)
    region = bundle.regions[1]
    reference = {'region_id': region.region_id, 'start': region.start + region.quote.index('Сборку'), 'end': region.end}
    row = make_row(bundle, change_selection(bundle, selected, 'medium', reference), ledger['slots'][0])
    row['candidate']['medium']['note'] = 'Model claims measurement environment is confirmed.'
    projected = project_roles(row, sources(bundle), relations['cells'][row['cell_id']])
    assert roles(projected)['measurement_environment'].status == 'unknown'
    assert projected.unassigned_selections[0].selected.text == reference_text(bundle, reference)


def reference_text(bundle, reference):
    region = next(r for r in bundle.regions if r.region_id == reference['region_id'])
    return region.page_text[reference['start']:reference['end']]


def test_missing_composition_is_not_filled_from_available_ratio():
    bundle, _, ledger, relations, _, selected, _ = fixture()
    data = selected.model_dump(mode='json')
    obs = next(o for o in data['observations'] if o['field'] == 'medium_composition')
    obs.update(status='ambiguous', raw_span=None, evidence=[])
    row = make_row(bundle, FixedSpanMeasurement.model_validate(data), ledger['slots'][0])
    projected = project_roles(row, sources(bundle), relations['cells'][row['cell_id']])
    assert projected.missing_source_fields == {'medium_composition': 'ambiguous'}
    assert not roles(projected)['plasticiser_composition'].bindings


@pytest.mark.parametrize('variant', ['missing_header', 'shared_block', 'missing_basis', 'unknown_group'])
def test_unsupported_role_context_does_not_force_a_source_role(variant):
    bundle, _, ledger, relations, _, _, row = fixture()
    context = copy.deepcopy(relations['cells'][row['cell_id']])
    if variant == 'missing_header':
        context['plasticiser_header'] = None
    elif variant == 'shared_block':
        context['shared_block'] = True
    elif variant == 'missing_basis':
        context['basis'] = None
    else:
        context['group'] = None
    projected = project_roles(row, sources(bundle), context)
    assert not roles(projected)['plasticiser_composition'].bindings
    if variant in {'missing_header', 'shared_block', 'unknown_group'}:
        assert not roles(projected)['plasticiser_components'].bindings


@pytest.mark.parametrize('variant', ['wrong_text', 'outside_span', 'foreign_region', 'status_drift', 'candidate_id', 'evidence_drift'])
def test_source_or_legacy_candidate_drift_fails_before_projection(variant):
    bundle, _, _, relations, _, _, row = fixture()
    row = copy.deepcopy(row)
    if variant == 'wrong_text':
        row['selected_fields']['medium']['raw']['text'] = 'Wrong text'
    elif variant == 'outside_span':
        row['selected_fields']['medium']['raw']['end'] += 99999
    elif variant == 'foreign_region':
        row['selected_fields']['medium']['raw']['region_id'] = 'f' * 64
    elif variant == 'status_drift':
        row['selected_fields']['medium']['status'] = 'unsupported'
    elif variant == 'candidate_id':
        row['record_id'] = '00000000-0000-0000-0000-000000000000'
    else:
        row['candidate']['medium']['evidence'][0]['quote'] = 'EC/G2 changed'
    with pytest.raises(ValueError):
        project_roles(row, sources(bundle), relations['cells'][row['cell_id']])


@pytest.mark.parametrize('variant', ['duplicate_role', 'unknown_with_bindings', 'environment_proposal', 'scientific_confirmation',
                                     'extra_key', 'duplicate_field', 'missing_status_present', 'unaccounted_selection'])
def test_strict_projection_contract_rejects_unsupported_states_and_lost_selections(variant):
    bundle, _, _, relations, _, _, row = fixture()
    data = project_roles(row, sources(bundle), relations['cells'][row['cell_id']]).model_dump(mode='json')
    if variant == 'duplicate_role':
        data['roles'][-1] = data['roles'][0]
    elif variant == 'unknown_with_bindings':
        data['roles'][0]['status'] = 'unknown'
    elif variant == 'environment_proposal':
        data['roles'][-1].update(status='source_label_proposal', bindings=data['roles'][0]['bindings'])
    elif variant == 'scientific_confirmation':
        data['scientific_admission'] = 'confirmed'
    elif variant == 'extra_key':
        data['roles'][0]['bindings'][0]['selected']['normalized_value'] = 1
    elif variant == 'duplicate_field':
        data['roles'][1]['bindings'][0]['source_field'] = 'medium'
    elif variant == 'missing_status_present':
        data['roles'][0].update(status='unknown', bindings=[])
        data['missing_source_fields'] = {'medium': 'present'}
    else:
        data['roles'][0].update(status='unknown', bindings=[])
    with pytest.raises(ValueError):
        RoleProjection.model_validate(data)


def synthetic_parent(tmp_path):
    bundle, page, _, _, extra = source_fixture()
    pdf = tmp_path / 'constructed-storage.pdf'
    pdf.write_bytes(b'Constructed storage-checksum fixture, not experimental PDF evidence.')
    rebound = []
    for source in bundle.regions:
        data = source.model_dump()
        data.update(original_pdf_path=str(pdf), layer_pdf_path=str(pdf),
                    original_pdf_sha256=file_hash(pdf), layer_pdf_sha256=file_hash(pdf))
        data['region_id'] = source_identity(data)
        rebound.append(SourceRegion.model_validate(data))
    bundle = bundle.model_copy(update={'regions': tuple(rebound)})
    page['original_pdf_sha256'] = file_hash(pdf)
    ledger = build_cell_ledger(page, bundle.regions[0])
    relations = relation_map(page, ledger, bundle.regions[0])
    row = make_row(bundle, measurement(bundle, ledger['slots'][0], relations), ledger['slots'][0])
    for cell in ledger['slots']:
        cell.update(new_proposals=[], stage22_proposals=[])
    ledger['slots'][0]['previous_proposals'] = [row['record_id']]
    parent = {'version': 'records_table_relations_v0.1', 'summary': {'logical_slots': 8, 'candidate_versions': 1},
              'slots': ledger['slots'], 'candidates': [row], 'sources': {r.region_id: r.model_dump(mode='json') for r in bundle.regions},
              'relation_map': relations}
    windows = tmp_path / 'windows'
    windows.mkdir()
    window_report = windows / 'report.json'
    window_report.write_text(json.dumps({'pages': [page]}, ensure_ascii=False), encoding='utf-8')
    directory = tmp_path / 'parent'
    directory.mkdir()
    raw = json.dumps(parent, ensure_ascii=False).encode('utf-8')
    (directory / 'report.json').write_bytes(raw)
    manifest = {'version': 'records_table_relations_v0.1', 'inputs': {str(pdf.resolve()): file_hash(pdf),
                str(window_report.resolve()): file_hash(window_report)}, 'code': {},
                'outputs': {'report.json': file_hash(directory / 'report.json')}}
    (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return directory, windows, raw


def test_export_is_deterministic_keeps_parent_bytes_and_has_all_roles_and_slots(tmp_path):
    directory, windows, raw = synthetic_parent(tmp_path)
    first, second = tmp_path / 'first', tmp_path / 'second'
    result = export_material_roles(directory, windows, first, source_root=Path.cwd())
    export_material_roles(directory, windows, second, source_root=Path.cwd())
    assert result['candidate_versions'] == 1 and result['logical_slots'] == 8
    assert result['new_model_calls'] == 0
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    assert (first / 'parent_report.json').read_bytes() == raw
    rendered = (first / 'review.html').read_text(encoding='utf-8')
    assert rendered.count('class="source-slot"') == 8 and rendered.count('class="role"') == len(ROLE_NAMES)
    assert '<form' not in rendered
    assert RoleSpan.model_json_schema()['additionalProperties'] is False
    with pytest.raises(FileExistsError):
        export_material_roles(directory, windows, first, source_root=Path.cwd())


@pytest.mark.parametrize('variant', ['report_drift', 'pdf_drift', 'wrong_version', 'lost_history', 'relation_drift', 'unbound_pdf'])
def test_parent_integrity_and_regenerated_context_are_required(tmp_path, variant):
    directory, windows, _ = synthetic_parent(tmp_path)
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    report_path = directory / 'report.json'
    parent = json.loads(report_path.read_bytes())
    if variant == 'report_drift':
        report_path.write_bytes(b'changed')
    elif variant == 'pdf_drift':
        (tmp_path / 'constructed-storage.pdf').write_bytes(b'changed')
    else:
        if variant == 'wrong_version':
            manifest['version'] = 'other'
        elif variant == 'lost_history':
            parent['candidates'] = []
            parent['summary']['candidate_versions'] = 0
        elif variant == 'relation_drift':
            next(iter(parent['relation_map']['cells'].values()))['composition']['text'] = 'Changed source relation'
        else:
            del manifest['inputs'][str((tmp_path / 'constructed-storage.pdf').resolve())]
        report_path.write_text(json.dumps(parent, ensure_ascii=False), encoding='utf-8')
        manifest['outputs']['report.json'] = file_hash(report_path)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        load_role_parent(directory, windows)
