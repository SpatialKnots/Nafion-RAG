"""Source scope integrity and unknown retention; constructed cases are not gold."""

import copy
import json

import pytest

from app.evaluation.context_risks import canonical
from app.generation.sample_scope import audit_scope, class_hits, select_scope
from app.records.sources import file_hash
from tests.unit.test_query_context_selection import fixture
from tests.unit.test_query_context_selection import runner_fixture as previous_fixture


def build(tmp_path, text, question='How was membrane conductivity measured?', **kwargs):
    values = fixture(tmp_path, blocks=['Background.\n', text, 'Tail.\n'], question=question, **kwargs)
    return values, audit_scope(*values)


@pytest.mark.parametrize('question,text,state,retained', [
    ('How was membrane conductivity measured?', 'SEI conductivity was measured by EIS.\n', 'competing_literal_only', False),
    ('Как измеряли проводимость мембран?', 'SEI conductivity was measured by EIS.\n', 'competing_literal_only', False),
    ('How was SEI conductivity measured?', 'Membrane conductivity was measured by EIS.\n', 'competing_literal_only', False),
    ('How was membrane conductivity measured?', 'Membrane conductivity was not measured [12].\n', 'target_literal_only', True),
    ('How was membrane conductivity measured?', 'Membrane and SEI conductivity were compared by EIS.\n', 'mixed_literal_classes', True),
    ('How was membrane conductivity measured?', 'Film conductivity was measured by EIS.\n', 'unknown_no_class', True),
    ('How was membrane conductivity measured?', 'Electrode conductivity was measured by EIS.\n', 'unknown_no_class', True),
    ('How was membrane conductivity measured?', 'Nafion conductivity was measured by EIS.\n', 'unknown_no_class', True),
    ('How was conductivity measured?', 'SEI conductivity was measured by EIS.\n', 'unsupported_or_ambiguous_query', True),
    ('Compare membrane and SEI conductivity methods.', 'SEI conductivity was measured by EIS.\n', 'unsupported_or_ambiguous_query', True),
])
def test_finite_classes_mixed_unknown_and_unsupported_queries(tmp_path, question, text, state, retained):
    values, audit = build(tmp_path, text, question)
    before = copy.deepcopy(values)
    unit = next(u for u in audit['units'] if any(h['text'].lower() in ('sei', 'membrane') for h in u['hits'])
        and u['parent_selected']) if state not in ('unknown_no_class',) else next(u for u in audit['units'] if u['parent_selected'])
    assert unit['state'] == state
    result = select_scope(audit, *values)
    assert (text in [b[5] for b in result['wire']['blocks']]) is retained
    assert values == before
    assert result['network_ready'] is False
    assert set(values[0]['blocking_reasons']) <= set(result['blocking_reasons'])
    assert all(u['sample_identity'] == 'not_established' and not u['scientific_exclusion_proven'] for u in audit['units'])


def test_exact_unicode_spans_are_not_normalized_or_repaired():
    text = 'α Мембраны; SEI; solid-electrolyte interphase; mem-\nbrane; films.'
    hits = class_hits(text, 17)
    assert {h['class'] for h in hits} == {'membrane', 'sei_interface'}
    assert all(text[h['start'] - 17:h['end'] - 17] == h['text'] for h in hits)
    assert not any(h['text'] in ('mem-\nbrane', 'films') for h in hits)


def test_target_in_protected_unit_prevents_competing_only_deferral(tmp_path):
    blocks = ['Background.\n', 'SEI conductivity was measured after attaining\n', 'x/y\n',
        '= z\n', 'thermal equilibrium of membranes.\n', 'Tail.\n']
    values = fixture(tmp_path, blocks=blocks, question='How was membrane conductivity measured?', protected=[1, 3, 4])
    audit = audit_scope(*values)
    result = select_scope(audit, *values)
    assert all(t in [b[5] for b in result['wire']['blocks']] for t in blocks[1:5])
    assert any(u['state'] == 'mixed_literal_classes' for u in audit['units'])
    assert result['wire']['dependencies'] == values[0]['wire']['dependencies']


def test_preparation_unknown_retained_without_article_class_inheritance(tmp_path):
    values = fixture(tmp_path, question='How was membrane conductivity measured after sample preparation?',
        blocks=['Background.\n', 'Membrane conductivity was measured by EIS.\n',
            'Samples were prepared in argon at 25°C.\n', 'Tail.\n'])
    audit = audit_scope(*values)
    result = select_scope(audit, *values)
    assert 'Samples were prepared in argon at 25°C.\n' in [b[5] for b in result['wire']['blocks']]
    assert all(u['per_result_applicability'] == 'not_established' for u in audit['units'])


def test_retained_complete_page_and_oversized_unit_keep_guards(tmp_path):
    text = 'Membrane conductivity was measured by EIS. ' + 'source ' * 16000 + '\n'
    values, audit = build(tmp_path, text)
    result = select_scope(audit, *values)
    assert text in [b[5] for b in result['wire']['blocks']]
    assert not result['current_byte_check_passed'] and result['byte_ceiling'] == 100000
    assert not result['network_ready']


@pytest.mark.parametrize('mutation', ['hits', 'state', 'membership', 'query', 'hash'])
def test_forged_scope_audit_is_rejected(tmp_path, mutation):
    values, audit = build(tmp_path, 'SEI conductivity was measured by EIS.\n')
    if mutation == 'query':
        audit['target_class'] = 'sei_interface'
    elif mutation == 'hash':
        audit['parent_selection_sha256'] = 'foreign'
    else:
        unit = next(u for u in audit['units'] if u['hits'])
        unit[{'hits': 'hits', 'state': 'state', 'membership': 'members'}[mutation]] = []
    with pytest.raises(ValueError, match='exact parent reconstruction'):
        select_scope(audit, *values)


def runner_fixture(tmp_path, monkeypatch):
    from app.evaluation import sample_scope_run as runner
    from app.records.extraction import write_json

    previous, prepared, _, _, pdf = previous_fixture(tmp_path, monkeypatch)
    parent = tmp_path / 'stage40'
    previous.run(prepared, parent)
    report = json.loads((parent / 'report.json').read_bytes())
    checks = tmp_path / 'scope_checks.json'
    write_json(checks, {'version': 'sample_scope_checks_v0.1',
        'origin': 'assistant_source_development_before_new_scope_outcomes', 'independent_human_confirmation': False,
        'parent_report_sha256': file_hash(parent / 'report.json'),
        'cases': [{'id': r['id'], 'task_id': r['id'], 'kind': 'no_admission_upgrade'} for r in report['results']]})
    destination = tmp_path / 'scope_prepared'
    runner.prepare(parent, checks, destination)
    return runner, destination, parent, checks, pdf


def test_frozen_audit_selection_and_exports_are_identical_and_preserve_parent_bytes(tmp_path, monkeypatch):
    runner, prepared, parent, _, pdf = runner_fixture(tmp_path, monkeypatch)
    checksum = file_hash(pdf)
    audit, selected = tmp_path / 'audit', tmp_path / 'selected'
    runner.execute(prepared, audit)
    result = runner.execute(audit, selected, select=True)
    assert result['checks_passed'] == result['questions'] == 4
    assert result['network_ready'] == result['retrieval_calls'] == result['model_calls'] == 0
    for original, is_selected in ((audit, False), (selected, True)):
        a, b = [tmp_path / (original.name + suffix) for suffix in ('_a', '_b')]
        assert runner.export(original, a, select=is_selected) == runner.export(original, b, select=is_selected)
        for p in original.rglob('*'):
            if p.is_file():
                assert p.read_bytes() == (a / p.relative_to(original)).read_bytes() == (b / p.relative_to(original)).read_bytes()
    old, new = [json.loads((p / 'report.json').read_bytes()) for p in (parent, selected)]
    for r, row in zip(old['results'], new['results'], strict=True):
        for k in runner.PARENTS:
            assert (parent / r[k]).read_bytes() == (selected / row[k]).read_bytes()
        assert (selected / row['wire_file']).stat().st_size == row['metrics']['wire_bytes']
    assert file_hash(pdf) == checksum
    with pytest.raises(FileExistsError):
        runner.execute(prepared, audit)


@pytest.mark.parametrize('mutation', ['code', 'checks', 'pdf', 'source'])
def test_frozen_drift_fails_before_output(tmp_path, monkeypatch, mutation):
    runner, prepared, parent, checks, pdf = runner_fixture(tmp_path, monkeypatch)
    if mutation == 'code':
        monkeypatch.setattr(runner, 'CODE', (*runner.CODE, 'README.md'))
    else:
        path = {'checks': checks, 'pdf': pdf, 'source': parent / 'method/selection.json'}[mutation]
        path.write_bytes(b'drift')
    output = tmp_path / 'rejected'
    with pytest.raises(ValueError):
        runner.execute(prepared, output)
    assert not output.exists()


def test_html_escapes_source_and_retains_all_units_and_pdf_links(tmp_path):
    from app.evaluation.sample_scope_run import PARENTS, render

    values, audit = build(tmp_path, 'SEI conductivity <script>alert(1)</script> was measured.\n')
    selection, packet, diagnostic, completeness = values
    row = {'id': 'q', **{k: 'q/' + k + '.json' for k in PARENTS}, 'scope_audit_file': 'q/scope_audit.json'}
    parents = {'q': {k: canonical(v).encode('utf-8') for k, v in zip(PARENTS,
        (selection, packet, completeness, diagnostic), strict=True)}}
    page = render({'version': 'test', 'summary': {}, 'input_snapshot': {}, 'results': [row]}, {'q': audit}, parents, {})
    assert '<script>alert(1)</script>' not in page and '&lt;script&gt;alert(1)&lt;/script&gt;' in page
    assert page.count('<tr data-unit>') == len(audit['units'])
    assert 'file:///' in page and 'metadata_review.html' in page and '<form' not in page


def test_prospective_source_unit_checks_are_validated_before_execution(tmp_path, monkeypatch):
    from app.records.extraction import write_json

    runner, _, parent, checks_path, _ = runner_fixture(tmp_path, monkeypatch)
    checks = json.loads(checks_path.read_bytes())
    report = json.loads((parent / 'report.json').read_bytes())
    row = next(r for r in report['results'] if r['id'] == 'method')
    selection, packet, diagnostic, _ = runner.parent_values(parent, row)
    ref = selection['wire']['unit_refs'][0]
    numbers = packet['wire']['co_preservation_units'][ref - 1]
    nodes = [{k: diagnostic['wire']['nodes'][n - 1][k] for k in ('node_id', 'text', 'start', 'end', 'text_sha256')}
        for n in numbers]
    checks['cases'].append({'id': 'source_unit', 'task_id': 'method', 'kind': 'unit_state', 'nodes': nodes,
        'expected_state': 'unsupported_or_ambiguous_query'})
    checks_path = tmp_path / 'checks_with_unit.json'
    write_json(checks_path, checks)
    prepared = tmp_path / 'with_unit_check'
    assert runner.prepare(parent, checks_path, prepared)['new_scope_outcomes'] == 0
    captured = tmp_path / 'unit_audit'
    result = runner.execute(prepared, captured)
    assert result['checks_passed'] == result['checks'] == 5
    checks['cases'][-1]['nodes'][0]['text'] += 'forged'
    checks_path = tmp_path / 'checks_with_forged_node.json'
    write_json(checks_path, checks)
    with pytest.raises(ValueError, match='exact source block'):
        runner.prepare(parent, checks_path, tmp_path / 'bad_unit_check')
