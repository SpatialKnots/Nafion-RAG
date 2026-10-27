"""Offline source diagnostics and preservation checks; no independent scientific gold."""

import copy
import json
import socket

import pytest

from app.evaluation.context_risks import canonical
from app.generation.sample_scope import audit_scope, select_scope
from app.generation.source_origin import audit_origin, heading_lines, origin_event, section_hint
from app.records.sources import file_hash
from tests.unit.test_query_context_selection import fixture
from tests.unit.test_sample_scope import runner_fixture as previous_fixture


def event(text, *, guarded=False, incomplete=False, roles=()):
    return {'event_id': 'test', 'context': {'region_id': 'r', 'start': 19, 'end': 19 + len(text), 'text': text},
        'state': 'guarded_source' if guarded else 'incomplete_source' if incomplete else 'unsupported_clause',
        'proposed_kind': None, 'cues': [{'kind': role} for role in roles],
        'block_guards': [{'reason': 'original_guard'}] if guarded else [],
        'boundary_diagnostics': ['original_boundary'] if incomplete else []}


@pytest.mark.parametrize('text,guarded,incomplete,state', [
    ('We measured conductivity.', False, False, 'own_work_cue_proposal'),
    ('В данной работе измеряли проводимость.', False, False, 'own_work_cue_proposal'),
    ('Conductivity was measured according to previous work [12].', False, False, 'reported_work_cue_proposal'),
    ('We measured conductivity according to previous work [12].', False, False, 'mixed_origin_cues'),
    ('We measured conductivity.', True, False, 'guarded_origin_cues'),
    ('We measured conductivity after attaining', False, True, 'guarded_origin_cues'),
    ('Conductivity was measured [12].', False, False, 'citation_only_origin_unknown'),
    ('Conductivity was measured.', False, False, 'unknown'),
])
def test_explicit_cues_citations_guards_and_unknown_own_work(text, guarded, incomplete, state):
    original = event(text, guarded=guarded, incomplete=incomplete)
    before = copy.deepcopy(original)
    result = origin_event(original, {'kind': 'methods'})
    assert result['origin_state'] == state
    assert result['own_work_origin'] == result['sample_identity'] == result['per_result_applicability'] == 'not_established'
    assert result['original_guards'] == original['block_guards'] and original == before
    assert all(text[h['start'] - 19:h['end'] - 19] == h['text'] for h in result['origin_hits'])


def test_methods_heading_does_not_establish_own_work_or_transfer_preparation_atmosphere():
    original = event('Samples were prepared in argon.', roles=('preparation_procedure',))
    result = origin_event(original, {'kind': 'methods'})
    assert result['origin_state'] == 'unknown'
    assert result['procedure_role'] == 'preparation_or_conditioning_cues'
    assert result['cross_event_field_inheritance'] is False
    assert origin_event(event('We used samples.', roles=('preparation_procedure', 'measurement_protocol')),
        {'kind': 'unknown'})['procedure_role'] == 'mixed_procedure_cues'


def test_exact_complete_heading_lines_not_substrings_or_hyphen_repairs():
    raw = 'Methods are described elsewhere.\n2. Methods\nРЕЗУЛЬТАТЫ И\u00a0ОБСУЖДЕНИЕ\nRef-\nerences\n'
    hits = heading_lines(raw, 7)
    assert [h['kind'] for h in hits] == ['methods', 'results_discussion']
    assert all(raw[h['start'] - 7:h['end'] - 7] == h['text'] for h in hits)


def plan_and_node(heading='Methods\n', *, cross_column=False, below=False, diagnostic=None):
    text = heading + 'Conductivity was measured.\n'
    start = len(heading)
    return ({'block_number': 1, 'start': start, 'text': text[start:]},
        {'page_text': text, 'mapping': {'diagnostic': diagnostic, 'blocks': [
            {'block_number': 0, 'page_start': 0, 'page_end': start,
                'bbox': [120 if cross_column else 10, 5, 150 if cross_column else 50, 15]},
            {'block_number': 1, 'page_start': start, 'page_end': len(text), 'bbox': [0, 0 if below else 20, 100, 50]}]}})


@pytest.mark.parametrize('heading,kind', [('Methods\n', 'methods'), ('References\n', 'bibliography'),
    ('ВВЕДЕНИЕ\n', 'introduction'), ('4. Conclusions\n', 'conclusions')])
def test_same_page_geometry_gives_only_section_proposals(heading, kind):
    node, plan = plan_and_node(heading)
    result = section_hint(node, plan)
    assert result['kind'] == kind and result['state'] == 'same_page_column_heading_proposal'
    assert result['scientific_section_proven'] is False


@pytest.mark.parametrize('kwargs', [{'cross_column': True}, {'below': True}, {'diagnostic': 'unproven_mapping'}])
def test_cross_column_later_or_unproven_geometry_cannot_inherit_section(kwargs):
    node, plan = plan_and_node(**kwargs)
    assert section_hint(node, plan)['kind'] == 'unknown'


def test_heading_embedded_in_own_block_is_not_applied_to_prior_body_text():
    node, plan = plan_and_node()
    node.update(block_number=0, start=0, text='Methods\n')
    assert section_hint(node, plan)['state'] == 'leading_heading_proposal'
    node['text'] = 'Earlier discussion.\nMethods\n'
    assert section_hint(node, plan)['kind'] == 'unknown'


def inputs(tmp_path):
    old, packet, diagnostic, completeness = fixture(tmp_path,
        blocks=['Background.\n', 'Methods\n', 'Conductivity was measured after attaining\n',
            'x/y\n', 'thermal equilibrium.\n', 'Samples were prepared in argon.\n', 'Tail.\n'],
        question='How was conductivity measured after sample preparation?')
    scope = audit_scope(old, packet, diagnostic, completeness)
    selection = select_scope(scope, old, packet, diagnostic, completeness)
    return selection, scope, old, packet, diagnostic, completeness


def test_all_blocks_events_and_wire_remain_exact_and_cross_page_state_is_not_inherited(tmp_path):
    values = inputs(tmp_path)
    before = copy.deepcopy(values)
    result = audit_origin(*values)
    nodes = values[4]['wire']['nodes']
    assert result['metrics']['blocks'] == len(nodes)
    assert result['metrics']['events'] == sum(len(n['events']) for n in nodes)
    assert result['wire_sha256_unchanged'] == values[0]['wire_sha256']
    assert values == before and result['blocking_reasons'] == values[0]['blocking_reasons']
    assert not result['selection_changed'] and not result['network_ready']
    for node, row in zip(nodes, result['rows'], strict=True):
        assert row['text'] == node['text'] and len(row['events']) == len(node['events'])
        for original, new in zip(node['events'], row['events'], strict=True):
            assert original['context'] == new['context']
            assert original['block_guards'] == new['original_guards']


def runner_fixture(tmp_path, monkeypatch):
    from app.evaluation import source_origin_run as runner
    from app.records.extraction import write_json

    previous, prepared, _, _, pdf = previous_fixture(tmp_path, monkeypatch)
    stage41, parent = tmp_path / 'stage41', tmp_path / 'stage42'
    previous.execute(prepared, stage41)
    previous.execute(stage41, parent, select=True)
    report = json.loads((parent / 'report.json').read_bytes())
    checks = tmp_path / 'origin_checks.json'
    write_json(checks, {'version': 'source_origin_checks_v0.1',
        'origin': 'assistant_source_development_before_new_origin_outcomes', 'independent_human_confirmation': False,
        'parent_report_sha256': file_hash(parent / 'report.json'),
        'cases': [{'id': r['id'], 'task_id': r['id'], 'kind': 'unchanged_selection_and_refusals'} for r in report['results']]})
    destination = tmp_path / 'origin_prepared'
    runner.prepare(parent, checks, destination)
    return runner, destination, parent, checks, pdf


def test_offline_run_export_with_connections_forbidden_preserves_all_parent_files(tmp_path, monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append('connection_attempt')
        raise AssertionError('Offline source origin must not open network connections')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    runner, prepared, parent, _, pdf = runner_fixture(tmp_path, monkeypatch)
    checksum = file_hash(pdf)
    captured, first, second = [tmp_path / p for p in ('origin_run', 'origin_review', 'origin_repeat')]
    result = runner.run(prepared, captured)
    assert result['checks_passed'] == result['questions'] == 4
    assert result['network_ready'] == result['model_calls'] == result['embedding_calls'] == result['retrieval_calls'] == 0
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


@pytest.mark.parametrize('variant', ['code', 'source', 'checks', 'pdf'])
def test_frozen_drift_fails_before_output(tmp_path, monkeypatch, variant):
    runner, prepared, parent, checks, pdf = runner_fixture(tmp_path, monkeypatch)
    if variant == 'code':
        monkeypatch.setattr(runner, 'CODE', (*runner.CODE, 'README.md'))
    else:
        report = json.loads((parent / 'report.json').read_bytes())
        row = next(r for r in report['results'] if r['id'] == 'method')
        target = {'source': parent / row['scope_selection_file'], 'checks': checks, 'pdf': pdf}[variant]
        assert target.is_file()
        target.write_bytes(b'drift')
    destination = tmp_path / 'rejected'
    with pytest.raises(ValueError):
        runner.run(prepared, destination)
    assert not destination.exists()


def test_html_escapes_source_and_exposes_read_only_selected_filter(tmp_path):
    from app.evaluation.source_origin_run import FILES, render

    values = inputs(tmp_path)
    audit = audit_origin(*values)
    audit['rows'][0]['text'] = '<script>alert(1)</script>'
    row = {'id': 'q', **{k: 'q/' + k + '.json' for k in FILES}, 'origin_file': 'q/origin.json'}
    parents = {'q': {'diagnostics_file': canonical(values[4]).encode('utf-8')}}
    page = render({'version': 'test', 'summary': {}, 'input_snapshot': {}, 'results': [row]}, {'q': audit}, parents)
    assert '<script>alert(1)</script>' not in page and '&lt;script&gt;alert(1)&lt;/script&gt;' in page
    assert 'id="selected"' in page and 'file:///' in page and 'metadata_review.html' in page
    assert '<form' not in page and page.count('<tr data-block ') == len(audit['rows'])
