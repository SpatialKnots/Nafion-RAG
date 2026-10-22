"""Constructed policy/integrity cases, never an independent scientific gold set."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.records.condition_multilingual import MultilingualEvent, identity, source_events
from app.records.condition_multilingual_export import (
    execute_comparison,
    prepare_comparison,
    run_comparison,
)
from app.records.condition_transfer import execute_packet
from app.records.condition_transfer_export import prepare_transfer, run_transfer
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_condition_transfer import packet, storage_parents


def source(text: str, offset: int = 0) -> SourceRegion:
    data = packet()['control_source']
    full = 'X' * offset + text
    data.update(page_text=full, page_text_sha256=text_hash(full), start=offset, end=len(full),
                quote=text, quote_sha256=text_hash(text))
    data['region_id'] = source_identity(data)
    return SourceRegion.model_validate(data)


@pytest.mark.parametrize(('text', 'kind'), [
    ('Электропроводность измеряли методом импедансной спектроскопии.', 'measurement_protocol'),
    ('Подготовку электродов и сборку измерительных ячеек проводили в боксе.', 'preparation_procedure'),
    ('Перед измерениями образцы выдерживали при 25°C.', 'conditioning_procedure'),
    ('Измерения прово-\nдили в симметричных ячейках.', 'measurement_setup'),
    ('Для измерений импеданса использовали анализатор.', 'measurement_protocol'),
    ('AC conductivity was measured at 25 °C.', 'measurement_protocol'),
    ('Through-plane lithium conductivity was measured at 25 ◦C.', 'measurement_protocol'),
    ('The ionic conductivity was measured at 25°C.', 'measurement_protocol'),
    ('Measurements were carried out in cooling mode.', 'measurement_protocol'),
    ('The measurements were performed in a cell.', 'measurement_protocol'),
    ('Impedance\nspectra were recorded at a fixed temperature.', 'measurement_protocol'),
    ('The membrane samples were dried at 80°C.', 'preparation_procedure'),
    ('Membranes were cast on a plate.', 'preparation_procedure'),
    ('The membrane samples were equilibrated for 24 h at 25 ◦C before measurement.', 'conditioning_procedure'),
    ('The cells were equilibrat- \ning under isothermal conditions.', 'conditioning_procedure'),
    ('Before measurement, the samples were held at 25°C.', 'conditioning_procedure'),
])
def test_literal_language_and_scope_proposals_keep_absolute_unicode_source(text, kind):
    region = source(text, 17)
    event, = source_events(region)
    assert event.state == 'scope_proposal' and event.proposed_kind == kind
    assert event.context.text == text and event.context.start == 17
    assert event.context.end == 17 + len(text)
    assert event.scientific_support == 'not_evaluated' and event.per_result_applicability == 'not_established'
    for cue in event.cues:
        assert cue.span.text == region.page_text[cue.span.start:cue.span.end]
        assert cue.span.region_id == region.region_id


@pytest.mark.parametrize(('text', 'reason'), [
    ('Conductivity was not measured.', 'negation_in_block'),
    ('Электропроводность не измеряли.', 'negation_in_block'),
    ('Ionic conductivity was measured without electrodes.', 'negation_in_block'),
    ("The samples weren't stable. Conductivity was measured.", 'negation_in_block'),
    ('No preparation was required. Conductivity was measured.', 'negation_in_block'),
    ('Previous work is discussed. Conductivity was measured.', 'reported_work_or_citation_in_block'),
    ('Conductivity was measured [12, 14–16].', 'reported_work_or_citation_in_block'),
    ('Conductivity was measured as reported by Smith.', 'reported_work_or_citation_in_block'),
    ('Ранее обсуждали образцы. Электропроводность измеряли.', 'reported_work_or_citation_in_block'),
    ('According to Smith et al., the method is established. Conductivity was measured.', 'reported_work_or_citation_in_block'),
    ('Conductivity was measured. A new run will follow.', 'modal_or_future_in_block'),
    ('Conductivity was measured. Такой метод может работать.', 'modal_or_future_in_block'),
])
def test_block_wide_guards_withhold_all_proposals_even_in_other_sentences(text, reason):
    region = source(text, 9)
    events = source_events(region)
    assert any(e.cues for e in events)
    assert not any(e.proposed_kind for e in events)
    assert all(e.state in {'guarded_source', 'incomplete_source'} for e in events)
    for event in events:
        assert reason in {g.reason for g in event.block_guards}
        for guard in event.block_guards:
            assert region.page_text[guard.span.start:guard.span.end] == guard.span.text


def test_simultaneous_measurement_and_equilibration_are_ambiguous_not_forced():
    event, = source_events(source('Impedance spectra were recorded after equilibrat-\ning the cells.'))
    assert event.state == 'ambiguous_scope' and event.proposed_kind is None
    assert {c.kind for c in event.cues} == {'measurement_protocol', 'conditioning_procedure'}


@pytest.mark.parametrize(('text', 'diagnostic'), [
    ('Conductivity was measured at', 'terminal_sentence_boundary_unproven'),
    ('conductivity was measured at 25°C.', 'initial_sentence_boundary_unproven'),
    ('Conductivity was measured as in Fig.', 'terminal_sentence_boundary_unproven'),
])
def test_clipped_boundaries_preserve_cues_without_scoping(text, diagnostic):
    event, = source_events(source(text))
    assert event.cues and event.state == 'incomplete_source' and event.proposed_kind is None
    assert diagnostic in event.boundary_diagnostics


def test_guards_survive_precedence_and_do_not_hide_mixed_roles_or_clipping():
    event, = source_events(source('Impedance spectra were not recorded after equilibrating'))
    assert event.state == 'incomplete_source' and len(event.cues) == 2 and event.block_guards


def test_abbreviations_decimals_and_all_unsupported_clauses_are_preserved():
    events = source_events(source('Conductivity was measured at 0.1 V as in Fig. 2. The value is 0.2. Unsupported tail'))
    assert [e.context.text for e in events] == [
        'Conductivity was measured at 0.1 V as in Fig. 2.', 'The value is 0.2.', 'Unsupported tail']
    assert [e.state for e in events] == ['scope_proposal', 'unsupported_clause', 'incomplete_source']


@pytest.mark.parametrize('text', [
    'Conductivity is an important material property.',
    'The word equilibratedness does not match a literal cue.',
    'The conductivity was calcu-\nlated from a fitted resistance.',
    'Электропроводность приведена на рисунке.',
])
def test_unknown_wording_is_retained_without_forced_cues(text):
    event, = source_events(source(text))
    assert event.context.text == text and not event.cues and event.proposed_kind is None


@pytest.mark.parametrize('variant', ['kind', 'guard', 'cue_span', 'identity', 'state'])
def test_event_assertion_and_identity_tampering_are_rejected(variant):
    event, = source_events(source('Conductivity was measured.'))
    data = event.model_dump()
    if variant == 'kind':
        data['proposed_kind'] = 'conditioning_procedure'
    elif variant == 'guard':
        data['block_guards'] = [{'reason': 'negation_in_block', 'span': data['context']}]
    elif variant == 'cue_span':
        data['cues'][0]['span']['text'] = 'Foreign source'
    elif variant == 'identity':
        data['diagnostic'] = 'Changed diagnostic'
    else:
        data['state'] = 'unsupported_clause'
    if variant != 'identity':
        data['event_id'] = identity({k: v for k, v in data.items() if k != 'event_id'})
    with pytest.raises(ValueError):
        MultilingualEvent.model_validate(data)


def comparison_packet():
    parent = packet()
    return {'version': 'records_condition_multilingual_v0.1', 'baseline_packet': parent,
            'baseline_report': execute_packet(parent), 'inventory': parent['inventory']}


def test_all_blocks_baseline_and_separate_control_are_accounted_without_scientific_metrics():
    result = execute_comparison(comparison_packet())
    assert result['summary']['executed_units'] == 5
    assert result['summary']['unit_outcomes'] == {'scope_proposal_observed': 3, 'no_literal_cue': 2}
    assert result['summary']['unit_transitions'] == {
        'no_literal_cue -> scope_proposal_observed': 2, 'no_literal_cue -> no_literal_cue': 2,
        'literal_cue_observed -> scope_proposal_observed': 1}
    assert result['summary']['separate_control_events'] == 1
    assert result['summary']['baseline_replay_exact']
    assert result['summary']['scientific_precision'] is result['summary']['scientific_recall'] is None
    assert result['summary']['new_model_calls'] == result['summary']['new_measurement_records'] == 0


@pytest.mark.parametrize('variant', ['baseline_result', 'baseline_control', 'baseline_summary', 'unit', 'inventory', 'version'])
def test_comparison_fails_on_baseline_source_control_or_inventory_drift(variant):
    data = comparison_packet()
    if variant == 'baseline_result':
        data['baseline_report']['results'][0]['outcome'] = 'changed'
    elif variant == 'baseline_control':
        data['baseline_report']['separate_control_events'] = []
    elif variant == 'baseline_summary':
        data['baseline_report']['summary']['executed_units'] -= 1
    elif variant == 'unit':
        data['baseline_packet']['pages'][0]['units'][0]['source']['text'] = 'changed'
    elif variant == 'inventory':
        data['inventory'] = {**data['inventory'], 'probe_units': 0}
    else:
        data['version'] = 'other'
    with pytest.raises(ValueError):
        execute_comparison(data)


def baseline_storage(tmp_path):
    stage18, stage19, stage25 = storage_parents(tmp_path)
    prepared, baseline = tmp_path / 'parent_prepared', tmp_path / 'baseline'
    prepare_transfer(stage18, stage19, stage25, prepared, source_root=Path.cwd())
    run_transfer(prepared, baseline)
    return baseline


def test_preparation_runs_neither_policy_and_export_is_complete_deterministic_exclusive_and_escaped(tmp_path):
    baseline = baseline_storage(tmp_path)
    prepared = tmp_path / 'prepared'
    with (patch('app.records.condition_multilingual_export.source_events', side_effect=AssertionError('New policy ran')),
          patch('app.records.condition_transfer.source_events', side_effect=AssertionError('Old policy ran'))):
        result = prepare_comparison(baseline, prepared, source_root=Path.cwd())
    assert result['probe_units'] == 5
    first, second = tmp_path / 'first', tmp_path / 'second'
    run_comparison(prepared, first)
    run_comparison(prepared, second)
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    assert (first / 'prepared_packet.json').read_bytes() == (prepared / 'packet.json').read_bytes()
    review = (first / 'review.html').read_text(encoding='utf-8')
    assert review.count('class="page"') == 2 and review.count('class="unit"') == 5
    assert '&lt;script&gt;' in review and 'Constructed <script>' not in review
    assert '<form' not in review and 'id="q"' in review and 'file:///' in review and '#page=1' in review
    with pytest.raises(FileExistsError):
        run_comparison(prepared, first)
    with pytest.raises(FileExistsError):
        prepare_comparison(baseline, prepared, source_root=Path.cwd())


@pytest.mark.parametrize('variant', ['output_drift', 'code_drift', 'phase', 'missing_output', 'pdf_drift'])
def test_preparation_rejects_changed_frozen_baseline_or_inputs(tmp_path, variant):
    baseline = baseline_storage(tmp_path)
    path = baseline / 'manifest.json'
    data = json.loads(path.read_bytes())
    if variant == 'output_drift':
        (baseline / 'report.json').write_text('{}', encoding='utf-8')
    elif variant == 'code_drift':
        data['code'][str(Path('app/records/condition_transfer.py').resolve())] = 'f' * 64
    elif variant == 'phase':
        data['phase'] = 'prepared'
    elif variant == 'missing_output':
        del data['outputs']['report.json']
    else:
        (tmp_path / 'constructed-storage.pdf').write_bytes(b'drifted source')
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        prepare_comparison(baseline, tmp_path / 'prepared', source_root=Path.cwd())


@pytest.mark.parametrize('variant', ['packet_drift', 'code_drift', 'phase', 'policy', 'missing_code', 'baseline_drift'])
def test_execution_rejects_changed_preparation_and_policy(tmp_path, variant):
    baseline = baseline_storage(tmp_path)
    prepared = tmp_path / 'prepared'
    prepare_comparison(baseline, prepared, source_root=Path.cwd())
    path = prepared / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    if variant == 'packet_drift':
        (prepared / 'packet.json').write_text('{}', encoding='utf-8')
    elif variant == 'code_drift':
        manifest['code'][str(Path('app/records/condition_multilingual.py').resolve())] = 'f' * 64
    elif variant == 'phase':
        manifest['phase'] = 'run'
    elif variant == 'missing_code':
        manifest['code'] = {}
    else:
        packet_path = prepared / 'packet.json'
        data = json.loads(packet_path.read_bytes())
        if variant == 'policy':
            data['policy']['version'] = 'other'
        else:
            data['baseline_report']['summary']['source_events'] -= 1
        packet_path.write_text(json.dumps(data), encoding='utf-8')
        manifest['outputs']['packet.json'] = file_hash(packet_path)
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        run_comparison(prepared, tmp_path / 'run')


def test_exact_span_validator_rejects_foreign_guard_context_even_if_event_identity_is_rebuilt():
    from app.records.condition_multilingual_export import evaluate_source

    region = source('Conductivity was measured. No further data.')
    event = source_events(region)[0]
    data = copy.deepcopy(event.model_dump())
    data['block_guards'][0]['span']['text'] = 'Foreign guard'
    data['event_id'] = identity({k: v for k, v in data.items() if k != 'event_id'})
    altered = MultilingualEvent.model_validate(data)
    with patch('app.records.condition_multilingual_export.source_events', return_value=(altered,)):
        with pytest.raises(ValueError, match='differs from exact block source'):
            evaluate_source(region)
