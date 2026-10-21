"""Constructed scope counterexamples; not independent scientific reference annotations."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.records.condition_scope import ConditionProjection, SourceEvent, project_conditions, source_events
from app.records.condition_scope_export import export_condition_scope, load_condition_parent
from app.records.fixed_links import FixedSpanMeasurement
from app.records.material_roles_export import export_material_roles
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_material_roles import change_selection, make_row, sources, synthetic_parent
from tests.unit.test_record_table_relations import measurement, source_fixture

TEXT = ('Электропроводность измеряли методом импедансной\nспектроскопии в режиме охлаждения с шагом\n10°C '
        '(точность ±0.1°C). (Температурный интервал определялся свойствами мембраны). '
        'Измерения прово-\nдили в симметричных ячейках Ti/образец/Ti. '
        'Подготовку электродов и сборку измерительных\nячеек проводили в сухом боксе в атмосфере арго-\nна. '
        'Перед измерениями образцы выдерживали 2 ч. '
        'Для измерений импеданса использовали прибор Z-3000; спектры записывали при постоянной температуре после достижения')


def fixture(text=TEXT):
    bundle, _, ledger, relations, _ = source_fixture()
    data = bundle.regions[1].model_dump()
    full = 'Hidden prefix. ' + text + ' Hidden continuation.'
    data.update(page_text=full, page_text_sha256=text_hash(full), quote=text, quote_sha256=text_hash(text),
                start=len('Hidden prefix. '), end=len('Hidden prefix. ') + len(text))
    data['region_id'] = source_identity(data)
    bundle = bundle.model_copy(update={'regions': (bundle.regions[0], SourceRegion.model_validate(data))})
    selected = measurement(bundle, ledger['slots'][0], relations)
    selected = select(bundle, selected, 'conditioning', 'в режиме охлаждения с шагом\n10°C')
    row = make_row(bundle, selected, ledger['slots'][0])
    return bundle, ledger['slots'][0], selected, row, source_events(bundle.regions[1])


def select(bundle, selected, field, text):
    region = next(r for r in bundle.regions if text in r.quote)
    start = region.start + region.quote.index(text)
    changed = change_selection(bundle, selected, field, {'region_id': region.region_id, 'start': start, 'end': start + len(text)})
    data = changed.model_dump(mode='json')
    next(o for o in data['observations'] if o['field'] == field)['status'] = 'present'
    return FixedSpanMeasurement.model_validate(data)


def project(bundle, cell, row, events):
    return project_conditions(row, sources(bundle), cell, bundle.regions[0].region_id, events)


def scopes(projection):
    return {s.source_field: s for s in projection.selections}


def test_catalog_retains_complete_unsupported_and_incomplete_source_with_exact_offsets():
    bundle, _, _, _, events = fixture()
    assert len(events) == 6
    assert [e.kind for e in events] == ['measurement_protocol', 'unclassified', 'measurement_setup',
                                       'preparation_procedure', 'conditioning_procedure', 'measurement_protocol']
    assert [e.state for e in events] == ['complete_clause_proposal', 'unsupported_clause', 'complete_clause_proposal',
                                        'complete_clause_proposal', 'complete_clause_proposal', 'incomplete_source']
    assert '±0.1°C' in events[0].context.text
    for event in events:
        assert bundle.regions[1].page_text[event.context.start:event.context.end] == event.context.text
        assert event.scientific_support == 'not_evaluated'


def test_cooling_in_conditioning_maps_to_measurement_protocol_without_rewriting_or_inheriting_completion():
    bundle, cell, _, row, events = fixture()
    old = copy.deepcopy(row)
    result = project(bundle, cell, row, events)
    by_field = scopes(result)
    assert by_field['conditioning'].scope == by_field['method'].scope == 'measurement_protocol'
    assert by_field['temperature'].scope == 'measurement_temperature'
    assert by_field['conditioning'].selected.text == 'в режиме охлаждения с шагом\n10°C'
    assert result.measurement_environment == result.equilibration_completion == 'unknown'
    assert result.scientific_admission == 'not_evaluated' and row == old
    assert all(s.applicability == 'not_evaluated' for s in result.selections)


@pytest.mark.parametrize('field', ['conditioning', 'preparation', 'method', 'temperature'])
def test_field_name_and_confirmation_note_do_not_establish_scope(field):
    bundle, cell, selected, _, events = fixture()
    selected = select(bundle, selected, field, 'в режиме охлаждения с шагом\n10°C')
    row = make_row(bundle, selected, cell)
    row['candidate'][field]['note'] = 'Model says conditioning is scientifically confirmed.'
    assert scopes(project(bundle, cell, row, events))[field].scope == 'measurement_protocol'


@pytest.mark.parametrize('text', ['в сухом боксе в атмосфере арго-\nна', 'в атмосфере арго-\nна'])
def test_preparation_atmosphere_never_becomes_measurement_environment(text):
    bundle, cell, selected, _, events = fixture()
    selected = select(bundle, selected, 'preparation', text)
    result = project(bundle, cell, make_row(bundle, selected, cell), events)
    assert scopes(result)['preparation'].scope == 'preparation_procedure'
    assert result.measurement_environment == 'unknown'


def test_explicit_before_measurement_clause_is_a_conditioning_proposal_only():
    bundle, cell, selected, _, events = fixture()
    selected = select(bundle, selected, 'conditioning', 'Перед измерениями образцы выдерживали 2 ч.')
    result = project(bundle, cell, make_row(bundle, selected, cell), events)
    assert scopes(result)['conditioning'].scope == 'conditioning_procedure'
    assert result.equilibration_completion == 'unknown'


@pytest.mark.parametrize('text', ['10°C', '±0.1°C', 'арго-\nна', 'Ti/образец/Ti', '0.2/0.8'])
def test_unsupported_fragments_are_retained_without_guessing_conditions(text):
    bundle, cell, selected, _, events = fixture()
    selected = select(bundle, selected, 'preparation', text)
    result = scopes(project(bundle, cell, make_row(bundle, selected, cell), events))['preparation']
    assert result.status == 'unassigned' and result.scope is None and result.selected.text == text


def test_other_conductivity_column_cannot_supply_this_cells_temperature():
    bundle, cell, selected, _, events = fixture()
    selected = select(bundle, selected, 'temperature', '–40°C')
    result = scopes(project(bundle, cell, make_row(bundle, selected, cell), events))['temperature']
    assert result.status == 'unassigned'


@pytest.mark.parametrize('text', ['после достижения', 'при постоянной температуре после достижения',
                                  'Для измерений импеданса использовали прибор Z-3000; '
                                  'спектры записывали при постоянной температуре после достижения'])
def test_clipped_tail_never_proves_equilibrium_or_completed_conditions(text):
    bundle, cell, selected, _, events = fixture()
    selected = select(bundle, selected, 'conditioning', text)
    result = project(bundle, cell, make_row(bundle, selected, cell), events)
    assert scopes(result)['conditioning'].status == 'incomplete_source'
    assert scopes(result)['conditioning'].scope is None and result.equilibration_completion == 'unknown'


def test_selection_crossing_preparation_and_conditioning_stays_ambiguous():
    bundle, cell, selected, _, events = fixture()
    text = TEXT[TEXT.index('Подготовку'):TEXT.index('Для измерений')].rstrip()
    selected = select(bundle, selected, 'preparation', text)
    result = scopes(project(bundle, cell, make_row(bundle, selected, cell), events))['preparation']
    assert result.status == 'ambiguous' and result.scope is None and len(result.event_ids) == 2


@pytest.mark.parametrize('variant', ['negated', 'reported', 'unknown_cue'])
def test_nonaffirmative_or_unknown_source_cue_does_not_create_scope(variant):
    text = TEXT.replace('Электропроводность измеряли', {'negated': 'Электропроводность измеряли не',
        'reported': 'Авторы писали: электропроводность измеряли', 'unknown_cue': 'Параметры оценивали'}[variant])
    bundle, cell, _, row, events = fixture(text)
    result = project(bundle, cell, row, events)
    assert events[0].kind == 'unclassified'
    assert scopes(result)['method'].status == scopes(result)['conditioning'].status == 'unassigned'


def test_missing_fields_stay_missing_even_when_source_contains_full_preparation_clause():
    bundle, cell, _, row, events = fixture()
    result = project(bundle, cell, row, events)
    assert result.missing_source_fields == {'preparation': 'not_found_in_context'}
    assert not any(s.scope == 'preparation_procedure' for s in result.selections)


@pytest.mark.parametrize('variant', ['candidate_id', 'cell_id', 'raw_text', 'status', 'evidence', 'unavailable_region', 'wrong_article'])
def test_candidate_and_source_drift_fail_before_projection(variant):
    bundle, cell, _, row, events = fixture()
    row = copy.deepcopy(row)
    if variant in {'candidate_id', 'cell_id'}:
        row['record_id' if variant == 'candidate_id' else 'cell_id'] = '0' * 64
    elif variant == 'raw_text':
        row['selected_fields']['method']['raw']['text'] = 'Wrong text'
    elif variant == 'status':
        row['selected_fields']['method']['status'] = 'ambiguous'
    elif variant == 'evidence':
        row['candidate']['method']['evidence'][0]['quote'] = 'Changed quotation'
    elif variant == 'unavailable_region':
        row['region_ids'] = [bundle.regions[0].region_id]
    else:
        row['candidate']['article_id'] = '00000000-0000-0000-0000-000000000000'
    with pytest.raises(ValueError):
        project(bundle, cell, row, events)


@pytest.mark.parametrize('variant', ['lost_field', 'duplicate_field', 'missing_present', 'confirmed', 'environment',
                                     'equilibrium', 'scope_missing', 'ambiguous_one_event', 'duplicate_event',
                                     'lost_context', 'outside_context', 'extra'])
def test_strict_projection_contract_rejects_lost_selections_or_unearned_claims(variant):
    bundle, cell, _, row, events = fixture()
    data = project(bundle, cell, row, events).model_dump(mode='json')
    if variant == 'lost_field':
        data['selections'].pop()
    elif variant == 'duplicate_field':
        data['selections'].append(data['selections'][0])
    elif variant == 'missing_present':
        data['missing_source_fields']['preparation'] = 'present'
    elif variant == 'confirmed':
        data['scientific_admission'] = 'confirmed'
    elif variant == 'environment':
        data['measurement_environment'] = 'argon'
    elif variant == 'equilibrium':
        data['equilibration_completion'] = 'confirmed'
    elif variant == 'scope_missing':
        data['selections'][0]['scope'] = None
    elif variant == 'ambiguous_one_event':
        data['selections'][1].update(status='ambiguous', scope=None)
    elif variant == 'duplicate_event':
        data['selections'][1]['event_ids'] *= 2
    elif variant == 'lost_context':
        data['selections'][1]['context'] = []
    elif variant == 'outside_context':
        data['selections'][1]['context'][0]['end'] = data['selections'][1]['selected']['start']
    else:
        data['selections'][0]['normalized_temperature'] = 30
    with pytest.raises(ValueError):
        ConditionProjection.model_validate(data)


@pytest.mark.parametrize('variant', ['identity', 'cue', 'science', 'false_complete'])
def test_source_event_contract_rejects_identity_and_cue_drift(variant):
    *_, events = fixture()
    data = events[0].model_dump(mode='json')
    if variant == 'identity':
        data['event_id'] = 'f' * 64
    elif variant == 'cue':
        data['cues'][0]['text'] = 'Changed cue'
    elif variant == 'science':
        data['scientific_support'] = 'confirmed'
    else:
        from app.records.condition_scope import event_identity
        from app.records.material_roles import RoleSpan

        data['state'] = 'incomplete_source'
        data['event_id'] = event_identity(RoleSpan.model_validate(data['context']), data['kind'], data['state'])
    with pytest.raises(ValueError):
        SourceEvent.model_validate(data)


def parents(tmp_path):
    relations, windows, _ = synthetic_parent(tmp_path)
    report_path, manifest_path = relations / 'report.json', relations / 'manifest.json'
    report = json.loads(report_path.read_bytes())
    native = tmp_path / 'constructed-native.json'
    native.write_text(json.dumps({'records': [report['candidates'][0]['candidate']]}, ensure_ascii=False), encoding='utf-8')
    report['candidates'][0]['artifacts'] = {'candidates.json': str(native)}
    report['method_source_diagnostics'] = {'paragraph_completeness': 'constructed_complete_fixture'}
    report_path.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    manifest = json.loads(manifest_path.read_bytes())
    manifest['inputs'][str(native.resolve())] = file_hash(native)
    manifest['outputs']['report.json'] = file_hash(report_path)
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    material = tmp_path / 'material'
    export_material_roles(relations, windows, material, source_root=Path.cwd())
    return material, relations, windows


def test_export_keeps_both_parent_reports_all_slots_and_repeat_bytes(tmp_path):
    material, relations, windows = parents(tmp_path)
    first, second = tmp_path / 'first', tmp_path / 'second'
    summary = export_condition_scope(material, relations, windows, first, source_root=Path.cwd())
    export_condition_scope(material, relations, windows, second, source_root=Path.cwd())
    assert summary['logical_slots'] == 8 and summary['candidate_versions'] == 1 and summary['new_model_calls'] == 0
    assert (first / 'parent_report.json').read_bytes() == (relations / 'report.json').read_bytes()
    assert (first / 'material_roles_report.json').read_bytes() == (material / 'report.json').read_bytes()
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    html = (first / 'review.html').read_text(encoding='utf-8')
    assert html.count('class="source-slot"') == 8 and html.count('class="projection"') == 1
    assert '<form' not in html and 'unknown' in html
    with pytest.raises(FileExistsError):
        export_condition_scope(material, relations, windows, first, source_root=Path.cwd())


@pytest.mark.parametrize('variant', ['hash_drift', 'version', 'projection', 'summary', 'parent_copy', 'lost_binding'])
def test_frozen_parent_identity_and_recomputed_roles_are_required(tmp_path, variant):
    material, relations, windows = parents(tmp_path)
    manifest_path = material / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    path = material / 'report.json'
    report = json.loads(path.read_bytes())
    if variant == 'hash_drift':
        path.write_bytes(b'changed')
    elif variant == 'version':
        manifest['version'] = 'other'
    elif variant == 'lost_binding':
        manifest['inputs'].pop(str((windows / 'report.json').resolve()))
    else:
        if variant == 'projection':
            report['projections'][0]['scientific_admission'] = 'confirmed'
        elif variant == 'summary':
            report['summary']['new_model_calls'] = 1
        else:
            (material / 'parent_report.json').write_bytes(b'changed parent')
            manifest['outputs']['parent_report.json'] = file_hash(material / 'parent_report.json')
        path.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
        manifest['outputs']['report.json'] = file_hash(path)
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        load_condition_parent(material, relations, windows)
