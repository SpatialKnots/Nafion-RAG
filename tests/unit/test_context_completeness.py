"""Completeness/association safety checks; constructed cases are not scientific gold."""

import copy
import json

import pytest

from app.evaluation.context_risks import canonical
from app.generation.compact_context_packet import build_compact_packet
from app.generation.context_completeness import audit_completeness, validate_audit
from app.generation.source_context_packet import build_source_packet
from app.records.sources import file_hash
from tests.unit.test_compact_context_packet import compact_fixture
from tests.unit.test_source_context_packet import native_two_pages, packet_fixture


def fixture(tmp_path, **kwargs):
    diagnostics, _, _ = packet_fixture(tmp_path, **kwargs)
    packet = build_compact_packet(diagnostics)
    return audit_completeness(packet, diagnostics), packet, diagnostics


def test_full_page_cause_is_original_window_union_not_diagnostic_serialization(tmp_path):
    audit, packet, diagnostics = fixture(tmp_path, blocks=['Conductivity was measured.\n'] * 3)
    assert audit['summary']['full_page_occurrences'] == len(packet['assembled_complete_pages']) == 1
    page = audit['pages'][0]
    assert page['original_window_union_full_page'] and page['selected_union_full_page']
    assert not page['added_dependency_nodes']
    assert page['retained_blocks'] == len(diagnostics['wire']['nodes'])
    assert audit['blocking_reasons'] == packet['blocking_reasons']
    assert not audit['selection_changed'] and not audit['network_ready']
    validate_audit(json.loads(canonical(audit)), packet, diagnostics)


def test_complete_literal_chain_is_only_proposal_with_exact_spans(tmp_path):
    raw = 'Conductivity was measured by EIS on membranes at 25°C.\n'
    audit, _, diagnostics = fixture(tmp_path, blocks=[raw])
    event = audit['events'][0]
    assert event['chain_state'] == 'source_cooccurrence_proposal' and not event['abstention_reasons']
    assert event['sample_identity'] == event['per_result_applicability'] == 'not_established'
    assert event['scientific_support'] == 'not_evaluated'
    original = diagnostics['wire']['nodes'][0]['events'][0]
    assert event['context'] == original['context']
    for values in event['literal_fields'].values():
        assert values
        for value in values:
            span = value['span']
            assert raw[span['start']:span['end']] == span['text']


@pytest.mark.parametrize('raw,reason', [
    ('Conductivity was not measured by EIS on membranes at 25°C.', 'original_block_wide_guards_preserved'),
    ('Conductivity was measured by EIS on membranes at 25°C [12].', 'original_block_wide_guards_preserved'),
    ('Conductivity was measured by EIS on membranes at 25°C, as previously reported.', 'original_block_wide_guards_preserved'),
    ('Conductivity was measured by EIS on membranes at 25°C and may change.', 'original_block_wide_guards_preserved'),
    ('Conductivity was measured by DSC on membranes at 25°C.', 'property_method_family_conflict'),
    ('Conductivity was measured by EIS on membranes during DSC at 25°C.', 'no_unique_property_family'),
    ('Conductivity was measured by EIS on membranes at 25°C', 'original_source_boundary_unresolved'),
    ('Conductivity was measured by EIS on samples prepared at 25°C.', 'preparation_or_conditioning_not_inherited_by_measurement'),
    ('Conductivity was measured by EIS at 25°C.', 'missing_literal_sample'),
])
def test_guarded_mixed_clipped_and_preparation_sources_never_create_links(tmp_path, raw, reason):
    audit, _, _ = fixture(tmp_path, blocks=[raw + '\n'])
    assert audit['events'][0]['chain_state'] == 'not_linked'
    assert reason in audit['events'][0]['abstention_reasons']
    assert not audit['network_ready']


def test_preparation_atmosphere_is_not_borrowed_by_same_block_measurement(tmp_path):
    raw = 'Conductivity was measured by EIS on membranes. Samples were prepared in argon at 25°C.\n'
    audit, _, _ = fixture(tmp_path, blocks=[raw])
    first, second = audit['events']
    assert not first['literal_fields']['condition']
    assert 'missing_literal_condition' in first['abstention_reasons']
    assert second['scope_role'] == second['condition_scope'] == 'preparation_procedure'
    assert any(h['kind'] == 'atmosphere_mention' for h in second['literal_fields']['condition'])
    assert first['chain_state'] == second['chain_state'] == 'not_linked'
    assert all(u['cross_event_field_inheritance'] is False for u in audit['units'])


def test_split_method_and_equilibrium_are_retained_without_sentence_repair(tmp_path):
    lines = ['Conductivity was measured by EIS on membranes after attaining\n', 'x/y\n',
        'thermal equilibrium at 25°C.\n']
    audit, _, diagnostics = fixture(tmp_path, blocks=lines)
    assert audit['summary']['selected_blocks'] == 3
    assert audit['summary']['source_cooccurrence_proposals'] == 0
    assert any(set(u['nodes']) == {n['id'] for n in diagnostics['wire']['nodes']} for u in audit['units'])
    assert all(d['sentence_join_performed'] is False for d in audit['dependencies'])
    assert audit['events'][0]['context']['text'] == lines[0].strip()
    assert audit['events'][-1]['context']['text'] == lines[-1].strip()


@pytest.mark.parametrize('mixed_layer,foreign_article', [(False, False), (True, False), (False, True)])
def test_cross_page_scope_never_transfers_fields_between_sources(tmp_path, mixed_layer, foreign_article):
    parent, pdf = native_two_pages(tmp_path, mixed_layer=mixed_layer, foreign_article=foreign_article)
    checksum = file_hash(pdf)
    diagnostics = build_source_packet(parent)
    packet = build_compact_packet(diagnostics)
    audit = audit_completeness(packet, diagnostics)
    assert bool([d for d in audit['dependencies'] if d['kind'] == 'unresolved_cross_page_boundary']) is (
        not mixed_layer and not foreign_article)
    assert all(u['cross_event_field_inheritance'] is False for u in audit['units'])
    assert file_hash(pdf) == checksum


def test_empty_selected_context_has_explicit_zero_inventory_and_old_refusal(tmp_path):
    audit, packet, diagnostics = fixture(tmp_path, question='Who are the authors?')
    assert not audit['events'] and not audit['units'] and not audit['dependencies']
    assert audit['summary']['selected_blocks'] == audit['summary']['source_cooccurrence_proposals'] == 0
    assert audit['blocking_reasons'] == packet['blocking_reasons']
    assert diagnostics['parent']['preparation']['baseline']['evidence']


@pytest.mark.parametrize('mutation', ['source', 'field', 'guard', 'boundary', 'coverage', 'unit', 'blocker', 'network'])
def test_audit_drift_has_visible_failure(tmp_path, mutation):
    audit, packet, diagnostics = fixture(tmp_path, protected=[1, 3, 5])
    changed = copy.deepcopy(audit)
    if mutation == 'source':
        changed['events'][0]['context']['text'] += ' altered'
    elif mutation == 'field':
        changed['events'][0]['literal_fields']['condition'] = []
        changed['events'][0]['chain_state'] = 'confirmed'
    elif mutation == 'guard':
        changed['events'][0]['original_guards'] = [{'reason': 'invented'}]
    elif mutation == 'boundary':
        changed['dependencies'][0]['disposition'] = 'resolved'
    elif mutation == 'coverage':
        changed['pages'][0]['selected_union_full_page'] = not changed['pages'][0]['selected_union_full_page']
    elif mutation == 'unit':
        changed['units'][0]['cross_event_field_inheritance'] = True
    elif mutation == 'blocker':
        changed['blocking_reasons'] = []
    else:
        changed['network_ready'] = True
    with pytest.raises(ValueError):
        validate_audit(changed, packet, diagnostics)


def runner_fixture(tmp_path, monkeypatch):
    from app.evaluation import context_completeness_run as runner
    from app.records.extraction import write_json

    old, prepared, _, _, pdf = compact_fixture(tmp_path, monkeypatch)
    parent = tmp_path / 'stage38'
    old.run(prepared, parent)
    checks = tmp_path / 'completeness_checks.json'
    report = json.loads((parent / 'report.json').read_bytes())
    write_json(checks, {'version': 'context_completeness_checks_v0.1',
        'origin': 'assistant_source_development_before_new_audit_outcomes', 'independent_human_confirmation': False,
        'parent_report_sha256': file_hash(parent / 'report.json'),
        'cases': [{'id': r['id'], 'task_id': r['id'], 'kind': 'unchanged_selection_and_refusal'} for r in report['results']]})
    destination = tmp_path / 'stage39_prepared'
    runner.prepare(parent, checks, destination)
    return runner, destination, parent, checks, pdf


def test_frozen_run_and_exports_preserve_full_parent_files_and_pdf(tmp_path, monkeypatch):
    runner, prepared, parent, _, pdf = runner_fixture(tmp_path, monkeypatch)
    checksum = file_hash(pdf)
    captured, first, second = [tmp_path / n for n in ('captured39', 'first39', 'second39')]
    result = runner.run(prepared, captured)
    assert result['development_checks_passed'] == result['questions'] == 4
    assert result['model_calls'] == result['retrieval_calls'] == result['network_ready'] == 0
    assert runner.export(captured, first) == runner.export(captured, second) == result
    for path in captured.rglob('*'):
        if path.is_file():
            relative = path.relative_to(captured)
            assert path.read_bytes() == (first / relative).read_bytes() == (second / relative).read_bytes()
    report = json.loads((captured / 'report.json').read_bytes())
    for row in report['results']:
        assert (captured / row['parent_packet_file']).read_bytes() == (parent / row['id'] / 'packet.json').read_bytes()
        assert (captured / row['diagnostics_file']).read_bytes() == (parent / row['id'] / 'diagnostics.json').read_bytes()
    assert file_hash(pdf) == checksum
    with pytest.raises(FileExistsError):
        runner.run(prepared, captured)


@pytest.mark.parametrize('variant', ['packet', 'checks', 'pdf', 'code'])
def test_source_or_code_drift_fails_before_creating_output(tmp_path, monkeypatch, variant):
    runner, prepared, parent, checks, pdf = runner_fixture(tmp_path, monkeypatch)
    if variant == 'code':
        monkeypatch.setattr(runner, 'CODE', (*runner.CODE, 'README.md'))
    else:
        {'packet': parent / 'method/packet.json', 'checks': checks, 'pdf': pdf}[variant].write_bytes(b'changed')
    output = tmp_path / 'rejected39'
    with pytest.raises(ValueError):
        runner.run(prepared, output)
    assert not output.exists()


def test_html_source_text_is_escaped_and_companion_table_is_linked(tmp_path):
    from app.evaluation.context_completeness_run import render

    audit, _, _ = fixture(tmp_path, blocks=['Conductivity <script>alert(1)</script> was measured.\n'])
    report = {'summary': {}, 'input_snapshot': {}, 'results': [{'id': 'case', 'audit_file': 'case/audit.json',
        'parent_packet_file': 'case/parent_packet.json', 'diagnostics_file': 'case/diagnostics.json'}]}
    page = render(report, {'case': audit})
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page and '<script>alert(1)</script>' not in page
    assert 'metadata_review.html' in page and 'type="search"' in page and '<form' not in page
