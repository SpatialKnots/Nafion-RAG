"""Selection integrity/loss accounting; constructed cases are not scientific gold."""

import copy
import json

import pytest

from app.evaluation.context_risks import canonical
from app.generation.compact_context_packet import build_compact_packet
from app.generation.context_completeness import audit_completeness
from app.generation.query_context_selection import expand_selected_unit, select_context, validate_selection
from app.generation.source_context_packet import build_source_packet
from app.records.sources import file_hash
from tests.unit.test_context_completeness import runner_fixture as previous_fixture
from tests.unit.test_source_context_packet import native_two_pages, packet_fixture


def fixture(tmp_path, **kwargs):
    kwargs.setdefault('question', 'How was conductivity measured?')
    diagnostic, _, _ = packet_fixture(tmp_path, **kwargs)
    packet = build_compact_packet(diagnostic)
    audit = audit_completeness(packet, diagnostic)
    return select_context(packet, diagnostic, audit), packet, diagnostic, audit


def test_sparse_whole_unit_selection_accounts_for_every_parent_block_and_window(tmp_path):
    result, packet, diagnostic, audit = fixture(tmp_path)
    before = copy.deepcopy((packet, diagnostic, audit))
    assert result['metrics']['selected_blocks'] < result['metrics']['parent_blocks']
    assert result['metrics']['selected_blocks'] + result['metrics']['deferred_blocks'] == result['metrics']['parent_blocks']
    assert len(result['block_ledger']) == result['metrics']['parent_blocks']
    assert sum(result['metrics'][k] for k in ('whole_windows_retained', 'partial_windows_local_only',
        'deferred_windows_local_only')) == result['metrics']['parent_windows']
    assert result['metrics']['partial_windows_local_only'] > 0
    nodes = diagnostic['wire']['nodes']
    for ref in result['wire']['unit_refs']:
        numbers = packet['wire']['co_preservation_units'][ref - 1]
        assert expand_selected_unit(result['wire'], ref) == [nodes[n - 1]['text'] for n in numbers]
    assert (packet, diagnostic, audit) == before
    validate_selection(json.loads(canonical(result)), packet, diagnostic, audit)


@pytest.mark.parametrize('raw', ['Conductivity was not measured [12].\n',
    'Conductivity was measured as previously reported.\n', 'Conductivity was measured and may change.\n',
    'Conductivity method notes with unknown grammar.\n', 'Conductivity was measured after attaining\n'])
def test_guards_incomplete_and_unclassified_matching_source_are_not_filtered(tmp_path, raw):
    result, _, diagnostic, _ = fixture(tmp_path, blocks=['Background.\n', raw, 'Tail.\n'])
    texts = [b[5] for b in result['wire']['blocks']]
    assert raw in texts
    original = next(n for n in diagnostic['wire']['nodes'] if n['text'] == raw)
    assert original['events']
    assert not result['network_ready'] and result['scientific_loss_status'] == 'not_evaluated'


def test_preparation_and_conditioning_blocks_are_retained_without_field_inheritance(tmp_path):
    blocks = ['Background.\n', 'Conductivity was measured by EIS on membranes.\n',
        'Samples were prepared in argon at 25°C.\n', 'Before measurements, samples were held for 2 hours.\n', 'End.\n']
    result, _, _, audit = fixture(tmp_path, blocks=blocks,
        question='How was conductivity measured after equilibration and sample preparation?')
    texts = [b[5] for b in result['wire']['blocks']]
    assert all(raw in texts for raw in blocks[1:4])
    assert any(e['scope_role'] == e['condition_scope'] == 'preparation_procedure' for e in audit['events'])
    assert all(u['cross_event_field_inheritance'] is False for u in audit['units'])
    assert 'preparation atmosphere' in result['wire']['instruction']


def test_protected_group_and_interleaved_formula_chain_cannot_be_cut(tmp_path):
    lines = ['Background.\n', 'Conductivity was measured after attaining\n', 'x/y\n',
        '= z\n', 'thermal equilibrium.\n', 'End.\n', 'Last.\n']
    result, packet, diagnostic, _ = fixture(tmp_path, blocks=lines, protected=[1, 3, 4])
    assert all(raw in [b[5] for b in result['wire']['blocks']] for raw in lines[1:5])
    selected = {b[0] for b in result['wire']['blocks']}
    for unit in packet['wire']['co_preservation_units']:
        assert not set(unit) & selected or set(unit) <= selected
    assert len(result['wire']['dependencies']) == result['metrics']['selected_dependencies']
    assert diagnostic['parent']['preparation']['baseline']['evidence']


@pytest.mark.parametrize('question', [
    'For MissingAuthor 2021, how was conductivity measured?',
    'What conductivity was reported for membranes containing Mars regolith?',
    'Who are the authors?',
])
def test_missing_article_material_or_unsupported_family_selects_no_substitute(tmp_path, question):
    result, _, _, _ = fixture(tmp_path, question=question)
    assert not result['wire']['blocks'] and not result['wire']['contexts']
    assert 'no_query_selected_context' in result['blocking_reasons']
    assert not result['network_ready']


def test_selected_union_still_blocks_full_pages_and_preserves_all_old_refusals(tmp_path):
    result, packet, _, _ = fixture(tmp_path, blocks=['Conductivity was measured.\n'] * 3)
    assert result['complete_page_matches']['assembled']
    assert result['complete_page_matches']['decoded']
    assert 'selected_complete_source_page_or_assembled_coverage' in result['blocking_reasons']
    assert set(packet['blocking_reasons']) <= set(result['blocking_reasons'])
    assert not result['network_ready']


def test_large_indivisible_source_is_not_clipped_and_raw_numeric_context_stays_exact(tmp_path):
    text = 'Conductivity was measured from -40 to +80°C with steps of 10°C and accuracy ±0.1°C. ' + 'unbroken text ' * 9000 + '\n'
    result, _, _, _ = fixture(tmp_path, blocks=[text, 'End.\n'])
    assert text in [b[5] for b in result['wire']['blocks']]
    assert not result['current_byte_check_passed'] and result['byte_ceiling'] == 100000
    assert 'selected_context_over_existing_byte_ceiling' in result['blocking_reasons']


@pytest.mark.parametrize('mixed_layer,foreign_article', [(False, False), (True, False), (False, True)])
def test_cross_page_dependencies_and_pdf_identity_are_unchanged(tmp_path, mixed_layer, foreign_article):
    parent, pdf = native_two_pages(tmp_path, mixed_layer=mixed_layer, foreign_article=foreign_article)
    checksum = file_hash(pdf)
    diagnostic = build_source_packet(parent)
    packet = build_compact_packet(diagnostic)
    audit = audit_completeness(packet, diagnostic)
    result = select_context(packet, diagnostic, audit)
    selected = {b[0] for b in result['wire']['blocks']}
    for dependency in packet['wire']['dependencies']:
        assert not selected.intersection(dependency[1]) or set(dependency[1]) <= selected
    assert file_hash(pdf) == checksum


@pytest.mark.parametrize('mutation', ['text', 'block', 'unit', 'dependency', 'losses', 'reasons', 'blocker', 'ready'])
def test_forged_selection_or_loss_ledger_fails_validation(tmp_path, mutation):
    result, packet, diagnostic, audit = fixture(tmp_path, protected=[1, 3, 5])
    if mutation == 'text':
        result['wire']['blocks'][0][5] += ' altered'
    elif mutation == 'block':
        result['wire']['blocks'].pop()
    elif mutation == 'unit':
        result['wire']['unit_refs'] = []
    elif mutation == 'dependency':
        result['wire']['dependencies'] = []
    elif mutation == 'losses':
        result['original_window_ledger'] = []
    elif mutation == 'reasons':
        result['block_ledger'][0]['state'] = 'scientifically_irrelevant'
    elif mutation == 'blocker':
        result['blocking_reasons'] = []
    else:
        result['network_ready'] = True
    with pytest.raises(ValueError):
        validate_selection(result, packet, diagnostic, audit)


@pytest.mark.parametrize('ref', [True, 0, 100000, '1'])
def test_foreign_unit_references_are_visible_errors(tmp_path, ref):
    result, _, _, _ = fixture(tmp_path)
    with pytest.raises(ValueError):
        expand_selected_unit(result['wire'], ref)


def runner_fixture(tmp_path, monkeypatch):
    from app.evaluation import query_context_selection_run as runner
    from app.records.extraction import write_json

    old, prepared, _, _, pdf = previous_fixture(tmp_path, monkeypatch)
    parent = tmp_path / 'stage39'
    old.run(prepared, parent)
    report = json.loads((parent / 'report.json').read_bytes())
    checks = tmp_path / 'selection_checks.json'
    write_json(checks, {'version': 'query_context_selection_checks_v0.1',
        'origin': 'assistant_source_development_before_new_selection_outcomes', 'independent_human_confirmation': False,
        'parent_report_sha256': file_hash(parent / 'report.json'),
        'cases': [{'id': r['id'], 'task_id': r['id'], 'kind': 'no_admission_upgrade'} for r in report['results']]})
    destination = tmp_path / 'stage40_prepared'
    runner.prepare(parent, checks, destination)
    return runner, destination, parent, checks, pdf


def test_frozen_run_export_preserves_all_parent_bytes_and_actual_wire_measurement(tmp_path, monkeypatch):
    runner, prepared, parent, _, pdf = runner_fixture(tmp_path, monkeypatch)
    checksum = file_hash(pdf)
    captured, first, second = [tmp_path / n for n in ('captured40', 'first40', 'second40')]
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
        for new, old in [('audit_file', 'audit.json'), ('parent_packet_file', 'parent_packet.json'),
                ('diagnostics_file', 'diagnostics.json')]:
            assert (captured / row[new]).read_bytes() == (parent / row['id'] / old).read_bytes()
        assert (captured / row['wire_file']).stat().st_size == row['metrics']['wire_bytes']
    assert file_hash(pdf) == checksum
    with pytest.raises(FileExistsError):
        runner.run(prepared, captured)


@pytest.mark.parametrize('variant', ['packet', 'checks', 'pdf', 'code'])
def test_frozen_drift_is_rejected_before_output(tmp_path, monkeypatch, variant):
    runner, prepared, parent, checks, pdf = runner_fixture(tmp_path, monkeypatch)
    if variant == 'code':
        monkeypatch.setattr(runner, 'CODE', (*runner.CODE, 'README.md'))
    else:
        {'packet': parent / 'method/parent_packet.json', 'checks': checks, 'pdf': pdf}[variant].write_bytes(b'drift')
    output = tmp_path / 'rejected40'
    with pytest.raises(ValueError):
        runner.run(prepared, output)
    assert not output.exists()


def test_html_keeps_escaped_full_blocks_and_local_deferred_source_links(tmp_path):
    from app.evaluation.query_context_selection_run import render

    result, packet, diagnostic, audit = fixture(tmp_path, blocks=['Conductivity <script>alert(1)</script> was measured.\n'])
    row = {'id': 'case', 'selection_file': 'case/selection.json', 'wire_file': 'case/wire.json',
        'audit_file': 'case/parent_audit.json', 'parent_packet_file': 'case/parent_packet.json',
        'diagnostics_file': 'case/diagnostics.json'}
    report = {'summary': {}, 'input_snapshot': {}, 'results': [row]}
    parents = {'case': {'audit_file': canonical(audit).encode(), 'parent_packet_file': canonical(packet).encode(),
        'diagnostics_file': canonical(diagnostic).encode()}}
    page = render(report, {'case': result}, parents)
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page and '<script>alert(1)</script>' not in page
    assert 'metadata_review.html' in page and 'type="search"' in page and '<form' not in page
    assert 'case/diagnostics.json' in page and 'file:///' in page
