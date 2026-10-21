"""Constructed stage-chain, target-budget and fail-stop counterexamples; no scientific gold."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.records import table_remaining as runner
from app.records.article_windows import source_page
from app.records.multi import parse_multi_reply, resolve_multi_reply
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from app.records.table_cells import bind_reply, build_cell_ledger
from tests.unit.test_record_multi import envelope
from tests.unit.test_record_table_continuation import measurement, table_source, target


def write_fixture_json(path, value):
    """These fixtures deliberately overwrite inputs to exercise drift detection."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def constructed_parent():
    base, _ = table_source()
    text, lines = 'Hidden prefix.\n', []

    def add(value, x, y, block, width=18):
        nonlocal text
        raw = value + '\n'
        lines.append({'block_number': block, 'page_start': len(text), 'page_end': len(text) + len(raw),
                      'bbox': [x, y, x + width, y + 8], 'text': raw, 'text_sha256': text_hash(raw)})
        text += raw

    start = len(text)
    add('Table 2', 0, 0, 0)
    add('№ образца', 0, 10, 1, 40)
    for column, header in enumerate(('σ30°C,', 'σ–40°C,')):
        add(header, 100 + 100 * column, 10, 2 + column)
        add('См см–1', 100 + 100 * column, 20, 2 + column)
    for row in range(1, 22):
        block = row + 4 if row != 13 else 16  # rows 12–13 deliberately share a PDF block
        y = 40 + row * 20
        add(str(row), 10, y, block)
        add('1.0 × 10–4', 100, y, block)
        add('–' if row in {2, 15} else '1.0 × 10–4', 200, y, block)
    end = len(text)
    text += 'Hidden suffix.'
    data = base.regions[0].model_dump()
    data.update(page_text=text, page_text_sha256=text_hash(text), start=start, end=end, quote=text[start:end],
                quote_sha256=text_hash(text[start:end]))
    data['region_id'] = source_identity(data)
    table = SourceRegion.model_validate(data)
    bundle = base.model_copy(update={'regions': (table, base.regions[1])})
    page = {'article_id': str(table.article_id), 'page_number': table.page_number, 'page_text': text,
            'page_text_sha256': text_hash(text), 'text_layer_id': str(table.text_layer_id),
            'original_pdf_sha256': table.original_pdf_sha256, 'source_gaps': {'text_geometry_proven': True, 'lines': lines},
            'protected_groups': [{'kind': 'closed_ruled_table_proposal',
                                  'block_numbers': sorted({line['block_number'] for line in lines}), 'page_ranges': [[start, end]]}]}
    ledger = build_cell_ledger(page, table)
    numeric = [s for s in ledger['slots'] if s['source_state'] == 'numeric_source_proposal']
    for i, cell in enumerate(numeric[:4]):
        cell['previous_proposals'] = [f'constructed-stage20-{i}']
    for cell in ledger['slots']:
        cell.update(new_proposals=[], continuation_outcomes=[])
    for i, cell in enumerate(numeric[4:13]):
        cell['new_proposals'] = [{'record_id': f'constructed-stage21-{i}', 'case_id': 'constructed-parent', 'revisit': False}]
    numeric[0]['new_proposals'] = [{'record_id': 'constructed-revisit', 'case_id': 'constructed-parent', 'revisit': True}]
    ledger['summary'].update(previous_covered_cells=4, new_covered_cells=9, combined_covered_cells=13, remaining_numeric_cells=23)
    # A constructed 62-page registry for metadata/guard tests, with unique page addresses.
    pages = [replace(source_page(table), page=i + 1) for i in range(62)]
    return bundle, ledger, pages


def reply_for(bundle, cells, *, partial=False):
    return {'schema_version': 'records_multi_fixed_reply_v0.1',
            'coverage': 'partial' if partial else 'claimed_complete_in_context',
            'returned_measurement_count': len(cells), 'measurements': [measurement(bundle, cell) for cell in cells],
            'unresolved': [{'reason': 'incomplete_conditions', 'evidence': [target(bundle, cells[0])['sample']],
                            'note': 'Constructed source-scoped abstention.'}] if partial else [],
            'diagnostic': 'Constructed selections; scientific applicability is not established.'}


def prepared_fixture(tmp_path, monkeypatch):
    bundle, ledger, pages = constructed_parent()
    monkeypatch.setattr(runner, 'verify_parent_outputs', lambda *args: (bundle, copy.deepcopy(ledger), pages, {}))
    prepared = tmp_path / 'prepared'
    runner.prepare_remaining(tmp_path / 'old-prepared', tmp_path / 'old-run', prepared, source_root=Path.cwd())
    return prepared, bundle, ledger


def rebind_manifest(directory):
    path = directory / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    manifest['artifacts'] = {p.relative_to(directory).as_posix(): file_hash(p)
                             for p in directory.rglob('*') if p.is_file() and p != path}
    write_fixture_json(path, manifest)


def test_all_remaining_partition_and_duplicate_old_revisit_do_not_inflate_coverage():
    bundle, ledger, _ = constructed_parent()
    cases = runner.target_cases(bundle, ledger)
    ids = [t['cell_id'] for case in cases for t in case['targets']]
    assert len(ids) == len(set(ids)) == 23
    assert [len(case['targets']) for case in cases] == [3] * 7 + [2]
    assert [case['case_id'] for case in cases] == list(runner.CASE_IDS)
    counts = runner.accounting(ledger)
    assert counts['previous_covered_cells'] == 13
    assert sum(len(s['previous_proposals']) + len(s['new_proposals']) for s in ledger['slots']) == 14
    assert all(not next(s for s in ledger['slots'] if s['cell_id'] == identifier)['previous_proposals'] for identifier in ids)


@pytest.mark.parametrize('mutation', ['duplicate_cell', 'duplicate_record', 'dash_proposal', 'revisit', 'double_new',
                                     'denominator', 'too_few', 'source_order', 'prior_outcomes'])
def test_inherited_ledger_or_current_history_inconsistencies_fail(mutation):
    bundle, ledger, _ = constructed_parent()
    numeric = [s for s in ledger['slots'] if s['source_state'] == 'numeric_source_proposal']
    if mutation == 'duplicate_cell':
        ledger['slots'][-1]['cell_id'] = ledger['slots'][0]['cell_id']
    elif mutation == 'duplicate_record':
        numeric[1]['previous_proposals'] = numeric[0]['previous_proposals'][:]
    elif mutation == 'dash_proposal':
        next(s for s in ledger['slots'] if s['source_state'] == 'explicit_dash')['new_proposals'] = [
            {'record_id': 'constructed-invalid'}]
    elif mutation in {'revisit', 'double_new'}:
        cell = numeric[0] if mutation == 'revisit' else numeric[20]
        cell['stage22_proposals'] = [{'record_id': 'constructed-new-1'}]
        if mutation == 'double_new':
            cell['stage22_proposals'].append({'record_id': 'constructed-new-2'})
    elif mutation == 'denominator':
        ledger['summary']['numeric_source_proposal'] += 1
    elif mutation == 'too_few':
        numeric[4]['new_proposals'] = []
    elif mutation == 'source_order':
        ledger['slots'].reverse()
    else:
        numeric[20]['stage22_outcomes'] = [{'case_id': 'already-attempted'}]
    with pytest.raises(ValueError):
        runner.target_cases(bundle, ledger)


def test_preparation_is_deterministic_and_existing_output_is_exclusive(tmp_path, monkeypatch):
    prepared, _, _ = prepared_fixture(tmp_path, monkeypatch)
    second = tmp_path / 'second'
    result = runner.prepare_remaining(tmp_path / 'old', tmp_path / 'old-run', second, source_root=Path.cwd())
    assert result['new_model_calls'] == 0 and result['maximum_calls'] == 8
    for path in prepared.rglob('*'):
        if path.is_file():
            assert path.read_bytes() == (second / path.relative_to(prepared)).read_bytes()
    with pytest.raises(FileExistsError):
        runner.prepare_remaining(tmp_path / 'old', tmp_path / 'old-run', second, source_root=Path.cwd())
    plan, ledger, pages, _ = runner.load_remaining(prepared)
    assert len(plan['cases']) == 8 and len(pages) == 62 and ledger['stage22_summary']['remaining_numeric_cells'] == 23


@pytest.mark.parametrize('mutation', ['maximum_calls', 'timeout_seconds', 'max_output_tokens_per_call', 'model', 'endpoint',
                                     'duplicate_target', 'omitted_target', 'wrong_address', 'case_order', 'registry', 'summary'])
def test_resealed_metadata_still_cannot_override_declared_policy(tmp_path, monkeypatch, mutation):
    prepared, _, _ = prepared_fixture(tmp_path, monkeypatch)
    path = prepared / 'plan.json'
    plan = json.loads(path.read_bytes())
    if mutation in {'maximum_calls', 'timeout_seconds', 'max_output_tokens_per_call'}:
        plan[mutation] += 1
    elif mutation in {'model', 'endpoint'}:
        plan[mutation] = 'constructed-alternative'
    elif mutation == 'duplicate_target':
        plan['cases'][1]['targets'][0] = plan['cases'][0]['targets'][0]
    elif mutation == 'omitted_target':
        plan['cases'][-1]['targets'].pop()
    elif mutation == 'wrong_address':
        plan['cases'][0]['targets'][0]['sample']['start_token'] += 1
    elif mutation == 'case_order':
        plan['cases'].reverse()
    elif mutation == 'registry':
        write_fixture_json(prepared / 'page_registry.json', [])
    else:
        ledger = json.loads((prepared / 'ledger.json').read_bytes())
        ledger['stage22_summary']['combined_covered_cells'] += 1
        write_fixture_json(prepared / 'ledger.json', ledger)
    write_fixture_json(path, plan)
    rebind_manifest(prepared)
    with pytest.raises(ValueError):
        runner.load_remaining(prepared)


def install_transport(monkeypatch, bundle, ledger, *, fail_at=None, partial_at=None):
    calls = []
    cases = runner.target_cases(bundle, ledger)

    def send(payload, *args):
        index = len(calls)
        calls.append(payload)
        if index == fail_at:
            raise TimeoutError('Constructed timeout, no retry allowed')
        ids = [t['cell_id'] for t in cases[index]['targets']]
        cells = [next(s for s in ledger['slots'] if s['cell_id'] == identifier) for identifier in ids]
        data = reply_for(bundle, cells[:1] if index == partial_at else cells, partial=index == partial_at)
        return envelope(json.dumps(data)), 'constructed-request'

    monkeypatch.setattr(runner, 'send_openai_request', send)
    return calls


def test_eight_case_run_preserves_all_parent_fields_and_covers_final_two_targets(tmp_path, monkeypatch):
    prepared, bundle, parent = prepared_fixture(tmp_path, monkeypatch)
    calls = install_transport(monkeypatch, bundle, parent)
    output = tmp_path / 'live'
    report = runner.run_remaining(prepared, output, api_key='constructed-secret')
    assert report['summary']['integrity_valid'] == 8 and len(calls) == 8
    assert report['summary']['proposed_records'] == 23 and report['cases'][-1]['records'] == 2
    assert report['summary']['source_accounting']['combined_covered_cells'] == 36
    assert report['summary']['source_accounting']['remaining_numeric_cells'] == 0
    ledger = json.loads((output / 'ledger.json').read_bytes())
    assert ledger['summary'] == parent['summary']  # the old stage21 summary is historical
    for old, new in zip(parent['slots'], ledger['slots'], strict=True):
        assert all(new[key] == value for key, value in old.items())
    assert (output / 'review.html').read_text(encoding='utf-8').count('class="case"') == 8
    assert (output / 'ledger.html').read_text(encoding='utf-8').count('class="slot"') == 42
    assert 'constructed-secret' not in (output / 'report.json').read_text()


@pytest.mark.parametrize('fail_at', [0, 6, 7])
def test_early_and_late_failures_stop_remaining_calls_with_per_slot_outcomes(tmp_path, monkeypatch, fail_at):
    prepared, bundle, parent = prepared_fixture(tmp_path, monkeypatch)
    calls = install_transport(monkeypatch, bundle, parent, fail_at=fail_at)
    output = tmp_path / 'failed'
    report = runner.run_remaining(prepared, output, api_key='constructed-secret')
    assert len(calls) == fail_at + 1
    assert report['summary']['failed'] == 1 and report['summary']['unattempted'] == 7 - fail_at
    assert report['summary']['integrity_valid'] == fail_at and report['summary']['proposed_records'] == 3 * fail_at
    ledger = json.loads((output / 'ledger.json').read_bytes())
    outcomes = [o['outcome'] for s in ledger['slots'] for o in s['stage22_outcomes']]
    assert len(outcomes) == 23 and 'failed' in outcomes
    for case in report['cases'][fail_at + 1:]:
        assert not (output / case['case_id']).exists()


def test_partial_result_retains_missing_targets_without_silent_coverage_success(tmp_path, monkeypatch):
    prepared, bundle, parent = prepared_fixture(tmp_path, monkeypatch)
    calls = install_transport(monkeypatch, bundle, parent, partial_at=0)
    report = runner.run_remaining(prepared, tmp_path / 'partial', api_key='constructed-secret')
    assert len(calls) == 8 and len(report['cases'][0]['missing_targets']) == 2
    assert report['summary']['proposed_records'] == 21
    assert report['summary']['source_accounting']['remaining_numeric_cells'] == 2
    ledger = json.loads((tmp_path / 'partial/ledger.json').read_bytes())
    assert sum(o['outcome'] == 'omitted_or_abstained' for s in ledger['slots'] for o in s['stage22_outcomes']) == 2


@pytest.mark.parametrize('failure', ['false_complete', 'outside_target', 'missing_file', 'incomplete_response'])
def test_runtime_failure_is_not_a_successful_abstention_and_preserves_native_response(tmp_path, monkeypatch, failure):
    prepared, bundle, parent = prepared_fixture(tmp_path, monkeypatch)
    cases = runner.target_cases(bundle, parent)
    calls = []

    def send(*args):
        calls.append(1)
        if failure == 'incomplete_response':
            return envelope('{}', status='incomplete'), None
        if failure == 'missing_file':
            (prepared / 'ledger.json').unlink()
        ids = [t['cell_id'] for t in cases[0]['targets']]
        cells = [next(s for s in parent['slots'] if s['cell_id'] == identifier) for identifier in ids]
        if failure == 'false_complete':
            cells = cells[:1]
        elif failure == 'outside_target':
            cells[0] = next(s for s in parent['slots'] if s['previous_proposals'])
        return envelope(json.dumps(reply_for(bundle, cells))), None

    monkeypatch.setattr(runner, 'send_openai_request', send)
    output = tmp_path / 'failure'
    report = runner.run_remaining(prepared, output, api_key='constructed-secret')
    assert len(calls) == 1 and report['summary']['failed'] == 1 and report['summary']['unattempted'] == 7
    assert (output / runner.CASE_IDS[0] / 'response.json').exists()
    assert not (output / runner.CASE_IDS[0] / 'candidates.json').exists()
    if failure == 'missing_file':
        assert report['final_source_integrity']['status'] == 'failed'
        assert 'Source integrity failed' in (output / 'review.html').read_text()


def parent_artifacts(tmp_path, monkeypatch):
    bundle, ledger, pages = constructed_parent()
    numeric = [s for s in ledger['slots'] if s['source_state'] == 'numeric_source_proposal']
    parent_prepared, parent_run = tmp_path / 'old-prepared', tmp_path / 'old-live'
    parent_prepared.mkdir()
    parent_run.mkdir()
    write_fixture_json(parent_prepared / 'manifest.json', {})
    source_ledger = copy.deepcopy(ledger)
    for cell in source_ledger['slots']:
        del cell['new_proposals'], cell['continuation_outcomes']
    for cell in ledger['slots']:
        cell['new_proposals'] = []
    selections = [numeric[4:7], numeric[7:10], numeric[10:13], numeric[:1]]
    cases, rows = [], []
    for i, selected in enumerate(selections):
        case_id = f'constructed-parent-{i}'
        case = {'case_id': case_id, 'input': f'{case_id}/input.json', 'request': f'{case_id}/request.json',
                'targets': [target(bundle, cell) for cell in selected], 'revisit': i == 3}
        cases.append(case)
        for directory in (parent_prepared / case_id, parent_run / case_id):
            directory.mkdir()
            write_fixture_json(directory / 'input.json', bundle.model_dump(mode='json'))
            (directory / 'request.json').write_bytes(json.dumps(runner.build_request(bundle, case['targets']), ensure_ascii=False).encode())
        reply = parse_multi_reply(json.dumps(reply_for(bundle, selected)))
        resolved, pending = resolve_multi_reply(bundle, reply)
        ids = bind_reply(bundle, reply, ledger)
        directory = parent_run / case_id
        (directory / 'response.json').write_bytes(envelope(reply.model_dump_json()))
        write_fixture_json(directory / 'reply.json', reply.model_dump(mode='json'))
        write_fixture_json(directory / 'candidates.json', resolved.model_dump(mode='json'))
        write_fixture_json(directory / 'unresolved.json', pending)
        write_fixture_json(directory / 'cell_bindings.json', [{'cell_id': identifier, 'record_id': str(record.record_id)}
                                                    for identifier, record in zip(ids, resolved.records, strict=True)])
        for cell, record in zip(selected, resolved.records, strict=True):
            cell['new_proposals'].append({'record_id': str(record.record_id), 'case_id': case_id, 'revisit': i == 3})
        rows.append({**case, 'status': 'integrity_valid', 'bound_cells': ids})
    write_fixture_json(parent_run / 'ledger.json', ledger)
    write_fixture_json(parent_run / 'report.json', {'final_source_integrity': {'status': 'verified'}, 'cases': rows})
    write_fixture_json(parent_run / 'manifest.json', {'version': 'records_table_continuation_v0.1',
                                             'prepared_manifest_sha256': file_hash(parent_prepared / 'manifest.json'), 'artifacts': {}})
    rebind_manifest(parent_run)
    monkeypatch.setattr(runner, 'load_prepared', lambda _: ({'cases': cases}, source_ledger, pages, {}))
    return parent_prepared, parent_run


@pytest.mark.parametrize('mutation', ['none', 'history', 'source_field', 'raw_reply', 'saved_candidate', 'binding',
                                     'case_order', 'failed_parent'])
def test_parent_native_replay_and_ledger_are_reconciled_before_new_targets(tmp_path, monkeypatch, mutation):
    prepared, previous = parent_artifacts(tmp_path, monkeypatch)
    path = previous / 'ledger.json'
    ledger = json.loads(path.read_bytes())
    if mutation == 'history':
        next(s for s in ledger['slots'] if s['new_proposals'])['new_proposals'][0]['record_id'] = 'constructed-mismatch'
    elif mutation == 'source_field':
        ledger['slots'][0]['header']['text'] = 'Changed source'
    elif mutation == 'raw_reply':
        (previous / 'constructed-parent-0/response.json').write_bytes(envelope('{}'))
    elif mutation == 'saved_candidate':
        candidate_path = previous / 'constructed-parent-0/candidates.json'
        candidate = json.loads(candidate_path.read_bytes())
        candidate['records'][0]['method']['note'] = 'Changed saved explanation changes identity/content.'
        write_fixture_json(candidate_path, candidate)
    elif mutation == 'binding':
        write_fixture_json(previous / 'constructed-parent-0/cell_bindings.json', [])
    elif mutation in {'case_order', 'failed_parent'}:
        report_path = previous / 'report.json'
        report = json.loads(report_path.read_bytes())
        if mutation == 'case_order':
            report['cases'].reverse()
        else:
            report['cases'][0]['status'] = 'failed'
        write_fixture_json(report_path, report)
    write_fixture_json(path, ledger)
    rebind_manifest(previous)
    if mutation == 'none':
        _, restored, _, _ = runner.verify_parent_outputs(prepared, previous)
        assert runner.accounting(restored)['previous_covered_cells'] == 13
    else:
        with pytest.raises(ValueError):
            runner.verify_parent_outputs(prepared, previous)
