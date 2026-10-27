"""Finite condition-link and offline preservation checks; no independent gold."""

import copy
import json
import socket
import subprocess
import sys

import pytest

from app.evaluation.context_risks import canonical
from app.generation.condition_applicability import audit_applicability, inventory, link_event
from app.generation.source_origin import origin_event
from app.records.sources import file_hash
from tests.unit.test_source_origin import event, inputs
from tests.unit.test_source_origin import runner_fixture as previous_fixture


def clause(text, *, roles=('measurement_protocol',), guarded=False, incomplete=False):
    return origin_event(event(text, roles=roles, guarded=guarded, incomplete=incomplete), {'kind': 'unknown'})


def test_nested_range_step_and_accuracy_remain_whole_exact_spans():
    text = ('Электропроводность измеряли в направлении мембраны методом импедансной спектроскопии '
        'в интервале температур от –60…–40 до +70…+80°C с шагом 10°C '
        '(точность поддержания температу-\nры ±0.1°C).')
    original = clause(text)
    result = link_event(original)
    conditions = result['inventory']['conditions']
    assert [h['kind'] for h in conditions] == ['temperature_range', 'temperature_step', 'temperature_accuracy']
    assert conditions[0]['text'] == 'от –60…–40 до +70…+80°C'
    assert conditions[1]['text'] == 'с шагом 10°C'
    assert conditions[2]['text'] == 'точность поддержания температу-\nры ±0.1°C'
    assert [link['state'] for link in result['links']] == ['same_event_measurement_context_proposal',
        'measurement_protocol_parameter_proposal', 'measurement_protocol_parameter_proposal']
    assert result['inventory']['sample_identity_state'] == 'generic_class_only'
    assert all(not link['single_measured_temperature_asserted'] for link in result['links'])
    assert all(text[h['start'] - 19:h['end'] - 19] == h['text'] for h in conditions)


@pytest.mark.parametrize('sample,state,link_state', [
    ('sample A', 'single_explicit_label_proposal', 'same_event_measurement_context_proposal'),
    ('sample 2', 'single_explicit_label_proposal', 'same_event_measurement_context_proposal'),
    ('sample A and B', 'ambiguous_explicit_labels', 'unresolved'),
    ('sample A and sample B', 'ambiguous_explicit_labels', 'unresolved'),
    ('membranes', 'generic_class_only', 'same_event_measurement_context_proposal'),
])
def test_explicit_and_ambiguous_sample_labels_remain_local_proposals(sample, state, link_state):
    result = link_event(clause(f'Conductivity was measured for {sample} by EIS at 25°C.'))
    assert result['inventory']['sample_identity_state'] == state
    assert result['links'][0]['state'] == link_state
    assert result['links'][0]['per_result_applicability'] == 'not_established'


@pytest.mark.parametrize('kwargs', [{'guarded': True}, {'incomplete': True}])
def test_guards_and_boundaries_block_local_measurement_proposals(kwargs):
    original = clause('Conductivity was measured for sample A by EIS at 25°C.', **kwargs)
    before = copy.deepcopy(original)
    result = link_event(original)
    assert result['links'][0]['state'] == 'unresolved' and result['links'][0]['abstention_reasons']
    assert result['original_guards'] == original['original_guards'] and original == before


def test_preparation_argon_is_never_inherited_by_separate_measurement():
    preparation = link_event(clause('Samples were prepared in argon at 25°C.', roles=('preparation_procedure',)))
    measurement = link_event(clause('Conductivity was measured by EIS on membranes.'))
    assert {link['state'] for link in preparation['links']} == {'preparation_context_only'}
    assert not measurement['links']
    assert all(not link['cross_event_inheritance'] for link in preparation['links'])


@pytest.mark.parametrize('text,roles', [
    ('Conductivity was measured by DSC for membranes at 25°C.', ('measurement_protocol',)),
    ('Conductivity was measured by EIS at 25°C.', ('measurement_protocol',)),
    ('Conductivity of membranes by EIS at 25°C was discussed.', ()),
    ('Conductivity was measured by EIS for membranes according to previous work at 25°C.', ('measurement_protocol',)),
    ('Conductivity was measured by EIS for membranes [12] at 25°C.', ('measurement_protocol',)),
    ('Conductivity was measured and samples prepared by EIS at 25°C.', ('measurement_protocol', 'preparation_procedure')),
])
def test_missing_components_conflicts_reported_and_mixed_procedures_abstain(text, roles):
    result = link_event(clause(text, roles=roles))
    assert result['links'] and all(link['state'] == 'unresolved' for link in result['links'])


def test_frequency_duration_and_atmosphere_spans_are_not_numerically_normalized():
    raw = 'Membranes: frequency 1 Гц–3 МГц; duration 2 hours; argon; 30°C.'
    result = inventory(clause(raw))
    assert {h['kind'] for h in result['conditions']} == {'frequency_range', 'duration', 'atmosphere_mention',
        'temperature_unresolved'}
    assert all(raw[h['start'] - 19:h['end'] - 19] == h['text'] for h in result['conditions'])
    assert not any('value' in h for h in result['conditions'])


def test_all_events_source_and_wire_are_preserved(tmp_path):
    from app.generation.source_origin import audit_origin

    origin = audit_origin(*inputs(tmp_path))
    before = copy.deepcopy(origin)
    result = audit_applicability(origin)
    assert origin == before and result['wire_sha256_unchanged'] == origin['wire_sha256_unchanged']
    assert result['blocking_reasons'] == origin['blocking_reasons']
    assert result['metrics']['events'] == origin['metrics']['events']
    assert not result['network_ready'] and not result['selection_changed']
    for old, new in zip(origin['rows'], result['rows'], strict=True):
        assert old['text'] == new['text'] and old['selected'] == new['selected']
        for a, b in zip(old['events'], new['events'], strict=True):
            assert a['context'] == b['context'] and a['original_guards'] == b['original_guards']


def runner_fixture(tmp_path, monkeypatch):
    from app.evaluation import condition_applicability_run as runner
    from app.records.extraction import write_json

    previous, prepared, _, _, pdf = previous_fixture(tmp_path, monkeypatch)
    parent = tmp_path / 'stage43'
    previous.run(prepared, parent)
    report = json.loads((parent / 'report.json').read_bytes())
    checks = tmp_path / 'applicability_checks.json'
    write_json(checks, {'version': 'condition_applicability_checks_v0.1',
        'origin': 'assistant_source_development_before_new_applicability_outcomes', 'independent_human_confirmation': False,
        'parent_report_sha256': file_hash(parent / 'report.json'),
        'cases': [{'id': row['id'], 'task_id': row['id'], 'kind': 'unchanged_source_and_refusals'} for row in report['results']]})
    destination = tmp_path / 'applicability_prepared'
    runner.prepare(parent, checks, destination)
    return runner, destination, parent, checks, pdf


def test_run_and_exports_with_connections_forbidden_preserve_all_parent_bytes(tmp_path, monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append('connection')
        raise AssertionError('Applicability tests forbid network connections')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    runner, prepared, parent, _, pdf = runner_fixture(tmp_path, monkeypatch)
    checksum = file_hash(pdf)
    captured, first, second = [tmp_path / n for n in ('run', 'review', 'repeat')]
    result = runner.run(prepared, captured)
    assert result['checks_passed'] == result['questions'] == 4
    assert runner.export(captured, first) == runner.export(captured, second) == result
    for p in captured.rglob('*'):
        if p.is_file():
            assert p.read_bytes() == (first / p.relative_to(captured)).read_bytes() == (second / p.relative_to(captured)).read_bytes()
    old, new = [json.loads((p / 'report.json').read_bytes()) for p in (parent, captured)]
    for a, b in zip(old['results'], new['results'], strict=True):
        for key in runner.FILES:
            assert (parent / a[key]).read_bytes() == (captured / b[key]).read_bytes()
    assert not attempts and file_hash(pdf) == checksum
    with pytest.raises(FileExistsError):
        runner.run(prepared, captured)
    # Exercise the actual guarded CLI in a fresh process; hooks cannot be removed.
    evidence, cli_review = tmp_path / 'network.json', tmp_path / 'cli_review'
    proc = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'scripts.condition_applicability',
        '--network-evidence', str(evidence), 'export', '--captured', str(captured), '--output-dir', str(cli_review)],
        capture_output=True, text=True, encoding='utf-8', check=False)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(evidence.read_bytes())['blocked_socket_or_dns_attempts'] == []
    assert (cli_review / 'report.json').read_bytes() == (captured / 'report.json').read_bytes()


@pytest.mark.parametrize('variant', ['code', 'event', 'checks', 'pdf'])
def test_frozen_drift_fails_before_output(tmp_path, monkeypatch, variant):
    runner, prepared, parent, checks, pdf = runner_fixture(tmp_path, monkeypatch)
    if variant == 'code':
        monkeypatch.setattr(runner, 'CODE', (*runner.CODE, 'README.md'))
    else:
        report = json.loads((parent / 'report.json').read_bytes())
        row = next(r for r in report['results'] if r['id'] == 'method')
        target = {'event': parent / row['origin_file'], 'checks': checks, 'pdf': pdf}[variant]
        assert target.is_file()
        target.write_bytes(b'drift')
    out = tmp_path / 'rejected'
    with pytest.raises(ValueError):
        runner.run(prepared, out)
    assert not out.exists()


def test_html_escaping_and_read_only_source_filter(tmp_path):
    from app.evaluation.condition_applicability_run import FILES, render
    from app.generation.source_origin import audit_origin

    args = inputs(tmp_path)
    audit = audit_applicability(audit_origin(*args))
    audit['rows'][0]['text'] = '<script>alert(1)</script>'
    row = {'id': 'q', **{k: 'q/' + k + '.json' for k in FILES}, 'applicability_file': 'q/applicability.json'}
    page = render({'version': 'test', 'summary': {}, 'input_snapshot': {}, 'results': [row]}, {'q': audit},
        {'q': {'diagnostics_file': canonical(args[4]).encode('utf-8')}})
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page and '<script>alert(1)</script>' not in page
    assert 'file:///' in page and 'metadata_review.html' in page and '<form' not in page
