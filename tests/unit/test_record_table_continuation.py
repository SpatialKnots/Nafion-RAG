"""Constructed source geometry and adversarial coordinates, not scientific reference data."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from urllib.error import URLError
from uuid import uuid4

import pytest

from app.records import table_continuation as runner
from app.records.article_windows import source_page
from app.records.extraction import FIELDS
from app.records.multi import parse_multi_reply, resolve_multi_reply
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from app.records.spans import TokenSpan
from app.records.table_cells import absolute_span, bind_reply, build_cell_ledger, token_address
from tests.unit.test_record_multi import envelope
from tests.unit.test_record_spans import source


def table_source(*, shared=False, dash=False, unknown=False):
    lines = []
    text = 'Hidden prefix.\n'

    def line(value, x, y, block, width=18):
        nonlocal text
        raw = value + '\n'
        lines.append({'block_number': block, 'page_start': len(text), 'page_end': len(text) + len(raw),
                      'bbox': [x, y, x + width, y + 8], 'text': raw, 'text_sha256': text_hash(raw)})
        text += raw

    start = len(text)
    line('Table 2', 0, 0, 0)
    line('№ образца', 0, 10, 1, 40)
    line('σ30°C,', 100, 10, 2)
    line('См см–1', 100, 20, 2)
    line('σ–40°C,', 200, 10, 3)
    line('См см–1', 200, 20, 3)
    line('1', 10, 40, 4)
    line('1.0 × 10–4', 100, 40, 4)
    line('1.0 × 10–4', 200, 40, 4)
    line('2', 10, 60, 4 if shared else 5)
    line('unreadable?' if unknown else '1.0 × 10–4', 100, 60, 4 if shared else 5)
    line('–' if dash else '2.0 × 10–5', 200, 60, 4 if shared else 5)
    end = len(text)
    text += 'Hidden suffix.'
    base = source()
    data = base.regions[0].model_dump()
    data.update(page_text=text, page_text_sha256=text_hash(text), start=start, end=end, quote=text[start:end],
                quote_sha256=text_hash(text[start:end]))
    data['region_id'] = source_identity(data)
    region = SourceRegion.model_validate(data)
    data2 = region.model_dump()
    method_text = 'Hidden prefix. Method impedance spectroscopy. Continuation excluded. Hidden suffix.'
    method_start, method_end = method_text.index('Method'), method_text.index(' Continuation')
    data2.update(page_number=2, text_layer_id=uuid4(), page_text=method_text, page_text_sha256=text_hash(method_text),
                 start=method_start, end=method_end, quote=method_text[method_start:method_end],
                 quote_sha256=text_hash(method_text[method_start:method_end]))
    data2['region_id'] = source_identity(data2)
    method = SourceRegion.model_validate(data2)
    bundle = base.model_copy(update={'regions': (region, method)})
    page = {'article_id': str(region.article_id), 'page_number': 1, 'page_text': text, 'page_text_sha256': text_hash(text),
            'text_layer_id': str(region.text_layer_id), 'original_pdf_sha256': region.original_pdf_sha256,
            'source_gaps': {'text_geometry_proven': True, 'lines': lines},
            'protected_groups': [{'kind': 'closed_ruled_table_proposal', 'block_numbers': sorted({v['block_number'] for v in lines}),
                                  'page_ranges': [[start, end]]}]}
    return bundle, page


def target(bundle, cell):
    region = bundle.regions[0]
    return {'cell_id': cell['cell_id'], 'sample': token_address(region, cell['sample']['start'], cell['sample']['end']),
            'column': token_address(region, cell['header']['start'], cell['header']['end'])}


def measurement(bundle, cell, *, method=True):
    r = bundle.regions[0]
    addresses = {field: token_address(r, cell[key]['start'], cell[key]['end'])
                 for field, key in [('sample_label', 'sample'), ('value', 'value'), ('unit', 'unit')]}
    # Exclude sigma and comma, preserving all printed temperature characters.
    header = cell['header']
    addresses['temperature'] = token_address(r, header['start'] + 1, header['end'] - 1)
    if method:
        m = bundle.regions[1]
        addresses['method'] = token_address(m, m.start, m.end, label='R2')
    observations = [{'field': f, 'status': 'present' if f in addresses else 'not_found_in_context',
                     'raw_span': addresses.get(f), 'evidence': [addresses[f]] if f in addresses else [],
                     'note': 'Constructed exact source selection, association not independently evaluated.'} for f in FIELDS]
    return {'observations': observations, 'representation': 'scalar',
            'linkage': {'sample_value': None, 'property_value': None, 'conditions_measurement': {
                'evidence': [addresses['value'], addresses['method']], 'note': 'Constructed association.'} if method else None}}


def reply(bundle, cell, *, method=True):
    return {'schema_version': 'records_multi_fixed_reply_v0.1', 'coverage': 'claimed_complete_in_context',
            'returned_measurement_count': 1, 'measurements': [measurement(bundle, cell, method=method)],
            'unresolved': [], 'diagnostic': 'Constructed fixture, no scientific accuracy claim.'}


def test_conservation_identical_lexemes_keep_distinct_coordinate_identities():
    bundle, page = table_source()
    ledger = build_cell_ledger(page, bundle.regions[0])
    assert ledger['summary']['logical_slots'] == ledger['summary']['numeric_source_proposal'] == 4
    assert len({s['cell_id'] for s in ledger['slots']}) == 4
    for cell in ledger['slots']:
        parsed = parse_multi_reply(json.dumps(reply(bundle, cell)))
        assert bind_reply(bundle, parsed, ledger, targets=[cell['cell_id']], require_method_region=True) == [cell['cell_id']]
        resolved, _ = resolve_multi_reply(bundle, parsed)
        assert resolved.records[0].method.raw_text == bundle.regions[1].quote
        assert resolved.records[0].review_state == 'needs_review'


@pytest.mark.parametrize('field,other', [('sample_label', 2), ('temperature', 1), ('unit', 1), ('value', 2)])
def test_same_lexeme_at_wrong_row_column_coordinates_fails(field, other):
    bundle, page = table_source()
    ledger = build_cell_ledger(page, bundle.regions[0])
    data = reply(bundle, ledger['slots'][0])
    foreign = next(o for o in measurement(bundle, ledger['slots'][other])['observations'] if o['field'] == field)
    actual = next(o for o in data['measurements'][0]['observations'] if o['field'] == field)
    actual.update(raw_span=foreign['raw_span'], evidence=foreign['evidence'])
    with pytest.raises(ValueError, match='row/column|declared unambiguous'):
        bind_reply(bundle, parse_multi_reply(json.dumps(data)), ledger, targets=[ledger['slots'][0]['cell_id']])


@pytest.mark.parametrize('kind', ['shared', 'dash', 'unknown', 'missing', 'multiple'])
def test_uncertain_slots_conserve_denominator_and_never_become_numeric_zero(kind):
    bundle, page = table_source(shared=kind == 'shared', dash=kind == 'dash', unknown=kind == 'unknown')
    if kind in {'missing', 'multiple'}:
        chosen = next(v for v in page['source_gaps']['lines'] if v['block_number'] == 5 and v['bbox'][0] == 100)
        if kind == 'missing':
            page['source_gaps']['lines'].remove(chosen)
        else:
            page['source_gaps']['lines'].append(copy.deepcopy(chosen))
    ledger = build_cell_ledger(page, bundle.regions[0])
    summary = ledger['summary']
    assert summary['logical_slots'] == 4
    assert sum(v for k, v in summary.items() if k not in {'logical_slots', 'rows', 'columns'}) == 4
    if kind == 'shared':
        assert summary['unresolved_shared_block'] == 4
        assert all(s['value'] is None for s in ledger['slots'])
    elif kind == 'dash':
        assert summary['explicit_dash'] == 1 and ledger['slots'][-1]['value']['text'] == '–'
    else:
        assert any(s['source_state'].startswith('unresolved') for s in ledger['slots'])


@pytest.mark.parametrize('mutation', ['text', 'hash', 'bbox', 'identity', 'clipped', 'unproven', 'row_labels', 'unit'])
def test_source_drift_and_unsupported_geometry_fail(mutation):
    bundle, page = table_source()
    if mutation == 'text':
        page['source_gaps']['lines'][0]['text'] = 'Changed'
    elif mutation == 'hash':
        page['source_gaps']['lines'][0]['text_sha256'] = 'f' * 64
    elif mutation == 'bbox':
        page['source_gaps']['lines'][0]['bbox'][0] = float('nan')
    elif mutation == 'identity':
        page['text_layer_id'] = str(uuid4())
    elif mutation == 'clipped':
        page['protected_groups'][0]['page_ranges'][0][0] -= 1
    elif mutation == 'unproven':
        page['source_gaps']['text_geometry_proven'] = False
    elif mutation == 'row_labels':
        page['source_gaps']['lines'] = [v for v in page['source_gaps']['lines'] if v['text'] != '1\n']
    else:
        page['source_gaps']['lines'] = [v for v in page['source_gaps']['lines'] if v['text'] != 'См см–1\n']
    with pytest.raises(ValueError):
        build_cell_ledger(page, bundle.regions[0])


@pytest.mark.parametrize('mutation', ['duplicate_target', 'duplicate_cell', 'out_of_target', 'wrong_method',
                                     'missing_link', 'one_region_link'])
def test_targets_and_present_method_provenance_are_required(mutation):
    bundle, page = table_source()
    ledger = build_cell_ledger(page, bundle.regions[0])
    cell = ledger['slots'][0]
    data, targets = reply(bundle, cell), [cell['cell_id']]
    if mutation == 'duplicate_target':
        targets *= 2
    elif mutation == 'duplicate_cell':
        data['measurements'] *= 2
        data['returned_measurement_count'] = 2
    elif mutation == 'out_of_target':
        targets = [ledger['slots'][1]['cell_id']]
    elif mutation == 'wrong_method':
        obs = next(o for o in data['measurements'][0]['observations'] if o['field'] == 'method')
        obs['raw_span'] = data['measurements'][0]['observations'][0]['raw_span']
    elif mutation == 'missing_link':
        data['measurements'][0]['linkage']['conditions_measurement'] = None
    else:
        data['measurements'][0]['linkage']['conditions_measurement']['evidence'].pop()
    with pytest.raises(ValueError):
        bind_reply(bundle, parse_multi_reply(json.dumps(data)), ledger, targets=targets, require_method_region=True)


def test_missing_method_is_retained_not_filled_or_admitted():
    bundle, page = table_source()
    ledger = build_cell_ledger(page, bundle.regions[0])
    parsed = parse_multi_reply(json.dumps(reply(bundle, ledger['slots'][0], method=False)))
    bind_reply(bundle, parsed, ledger, require_method_region=True)
    resolved, _ = resolve_multi_reply(bundle, parsed)
    assert resolved.records[0].method.status == 'not_found_in_context'


def test_request_scope_includes_both_regions_and_only_addresses_not_numeric_reference_answers():
    bundle, page = table_source()
    ledger = build_cell_ledger(page, bundle.regions[0])
    targets = [target(bundle, ledger['slots'][0])]
    request = runner.build_request(bundle, targets)
    pages = [source_page(r) for r in bundle.regions]
    runner.guard_request(request, bundle, targets, pages)
    user = json.loads(request['input'][1]['content'])
    assert len(user['context']) == 2 and '1.0 ×' not in user['task']
    assert all('Hidden' not in r['source'] for r in user['context'])
    combined = replace(pages[0], text=bundle.regions[0].quote + '\n' + bundle.regions[1].quote)
    with pytest.raises(ValueError, match='Full-page scope guard'):
        runner.guard_request(request, bundle, targets, [combined])
    request['max_output_tokens'] += 1
    with pytest.raises(ValueError, match='frozen'):
        runner.guard_request(request, bundle, targets, pages)


def fake_prepared(tmp_path, monkeypatch):
    bundle, page = table_source()
    ledger = build_cell_ledger(page, bundle.regions[0])
    ledger['slots'][0]['previous_proposals'] = ['synthetic-previous-record']
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    rows = []
    for i, case_id in enumerate(runner.CASE_IDS):
        # Three different new cells followed by one deliberate old-cell revisit.
        cell = ledger['slots'][(i + 1) % 4]
        targets = [target(bundle, cell)]
        directory = prepared / case_id
        directory.mkdir()
        (directory / 'input.json').write_text(bundle.model_dump_json(), encoding='utf-8')
        (directory / 'request.json').write_text(json.dumps(runner.build_request(bundle, targets), ensure_ascii=False), encoding='utf-8')
        rows.append({'case_id': case_id, 'input': f'{case_id}/input.json', 'request': f'{case_id}/request.json',
                     'targets': targets, 'revisit': i == 3})
    (prepared / 'manifest.json').write_text('{}', encoding='utf-8')
    bindings = {str(p.resolve()): file_hash(p) for p in prepared.rglob('*') if p.is_file()}
    monkeypatch.setattr(runner, 'load_prepared', lambda _: ({'cases': rows}, ledger, [source_page(r) for r in bundle.regions], bindings))
    return prepared, bundle, ledger


def test_mocked_run_separates_old_new_and_revisit_and_replays_exactly(tmp_path, monkeypatch):
    prepared, bundle, ledger = fake_prepared(tmp_path, monkeypatch)
    calls = []

    def send(payload, *args):
        calls.append(payload)
        cell = ledger['slots'][len(calls) % 4]
        return envelope(json.dumps(reply(bundle, cell))), 'constructed-request'

    monkeypatch.setattr(runner, 'send_openai_request', send)
    out = tmp_path / 'run'
    report = runner.run_continuation(prepared, out, api_key='synthetic-secret')
    assert report['summary']['integrity_valid'] == 4 and len(calls) == 4
    counts = report['summary']['source_accounting']
    assert counts['previous_covered_cells'] == 1 and counts['new_covered_cells'] == 3
    assert counts['combined_covered_cells'] == 4 and counts['remaining_numeric_cells'] == 0
    assert report['summary']['proposed_records'] == 4  # includes one revisit
    assert (out / 'ledger.html').read_text(encoding='utf-8').count('class="slot"') == 4
    assert (out / 'review.html').read_text(encoding='utf-8').count('class="case"') == 4
    assert 'synthetic-secret' not in (out / 'report.json').read_text()
    for case in runner.CASE_IDS:
        parsed = parse_multi_reply((out / case / 'reply.json').read_text())
        resolved, _ = resolve_multi_reply(bundle, parsed)
        saved = json.loads((out / case / 'candidates.json').read_bytes())
        assert [r.model_dump(mode='json') for r in resolved.records] == saved['records']


@pytest.mark.parametrize('failure', ['timeout', 'transport', 'incomplete', 'source_cell', 'changed_source', 'false_complete'])
def test_failure_stops_remaining_calls_preserves_raw_and_omits_success_candidates(tmp_path, monkeypatch, failure):
    prepared, bundle, ledger = fake_prepared(tmp_path, monkeypatch)
    calls = []
    if failure == 'changed_source':
        (prepared / runner.CASE_IDS[0] / 'input.json').write_bytes(b'changed')

    def send(*args):
        calls.append(1)
        if failure == 'timeout':
            raise TimeoutError('Constructed timeout')
        if failure == 'transport':
            raise URLError('Constructed transport error')
        if failure == 'incomplete':
            return envelope('{}', status='incomplete'), None
        selected = ledger['slots'][0 if failure == 'source_cell' else 1]
        if failure == 'false_complete':
            # A target count mismatch can be integrity-valid source but is not complete.
            row = runner.load_prepared(prepared)[0]['cases'][0]
            row['targets'].append(target(bundle, ledger['slots'][2]))
            (prepared / row['request']).write_text(
                json.dumps(runner.build_request(bundle, row['targets']), ensure_ascii=False), encoding='utf-8')
        return envelope(json.dumps(reply(bundle, selected))), None

    monkeypatch.setattr(runner, 'send_openai_request', send)
    out = tmp_path / 'failed'
    report = runner.run_continuation(prepared, out, api_key='synthetic-secret')
    assert report['summary']['failed'] == 1 and report['summary']['unattempted'] == 3
    assert len(calls) == (0 if failure == 'changed_source' else 1)
    assert not (out / runner.CASE_IDS[0] / 'candidates.json').exists()
    if failure not in {'changed_source', 'transport', 'timeout'}:
        assert (out / runner.CASE_IDS[0] / 'response.json').exists()


def test_absolute_coordinates_resolve_selected_occurrence_not_string_search():
    bundle, page = table_source()
    ledger = build_cell_ledger(page, bundle.regions[0])
    cell = ledger['slots'][2]
    span = TokenSpan.model_validate(token_address(bundle.regions[0], cell['value']['start'], cell['value']['end']))
    assert absolute_span(bundle, span)['start'] == cell['value']['start']
    assert absolute_span(bundle, span)['start'] != ledger['slots'][0]['value']['start']
