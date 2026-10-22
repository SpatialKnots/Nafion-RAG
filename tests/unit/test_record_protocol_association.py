"""Constructed source-contract and transport cases; not scientific gold labels."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from app.records.condition_multilingual import source_events
from app.records.protocol_association import AssociationReply, local_baseline, messages, parse_reply, resolve_reply, validate_case
from app.records.protocol_association_run import MAX_CALLS, build_cases, export, guard, load, page_record, prepare, request, run
from app.records.schema import source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_condition_multilingual import source


def case(text='Conductivity was measured at 25°C.', name='a' * 64):
    region = source(text, 17)
    data = region.model_dump()
    data['page_text'] += '\nUnselected source tail.'
    data['page_text_sha256'] = text_hash(data['page_text'])
    data['region_id'] = source_identity(data)
    region = type(region).model_validate(data)
    events = source_events(region)
    sentences = [{'id': 'S' + str(i), 'span': e.context.model_dump(), 'stage27_event': e.model_dump(mode='json')}
                 for i, e in enumerate(events, 1)]
    return {'case_id': name, 'role': 'transfer_development', 'source': region.model_dump(mode='json'), 'sentences': sentences,
            'target_ids': [s['id'] for s in sentences if s['stage27_event']['cues']]}


def reply(c, kind='conductivity'):
    return AssociationReply.model_validate({'associations': [
        {'target_id': target, 'property_kind': kind, 'property_sentence_ids': ['S1'] if kind != 'unknown' else [],
         'method_sentence_ids': [], 'condition_sentence_ids': [], 'origin': 'unknown', 'diagnostic': 'Constructed proposal.'}
        for target in c['target_ids']]})


@pytest.mark.parametrize(('text', 'expected'), [
    ('Conductivity was measured at 25°C.', 'conductivity'),
    ('Электропроводность измеряли методом импедансной спектроскопии.', 'conductivity'),
    ('A DSC instrument was used. The measurements were performed under nitrogen.', 'thermal_analysis'),
    ('Conductivity and DSC were compared. Measurements were performed.', 'unknown'),
    ('Conductivity was not measured.', 'unknown'),
    ('Conductivity was measured [12].', 'unknown'),
    ('Conductivity was measured at', 'unknown'),
    ('Measurements were performed in a cell.', 'unknown'),
])
def test_baseline_is_literal_co_context_with_explicit_guarded_mixed_or_missing_abstention(text, expected):
    assert {r['property_kind'] for r in local_baseline(case(text))} == {expected}


def test_exact_unicode_sentence_restoration_and_scientific_boundary():
    c = case('Through-plane lithium conductivity was measured at 25 ◦C.')
    result, = resolve_reply(c, reply(c))
    assert result['target']['start'] == 17
    assert result['evidence']['property_sentence_ids'] == [c['sentences'][0]['span']]
    assert result['scientific_admission'] == 'not_evaluated'
    assert result['per_result_applicability'] == 'not_established'
    assert result['stage27_event'] == c['sentences'][0]['stage27_event']


@pytest.mark.parametrize('variant', ['source_text', 'lost_sentence', 'lost_target', 'duplicate_sentence', 'unsafe_id', 'foreign_span'])
def test_case_source_inventory_and_safe_identity_failures(variant):
    c = case('Conductivity was measured. Extra source sentence.')
    if variant == 'source_text':
        c['sentences'][0]['span']['text'] = 'Changed source'
    elif variant == 'lost_sentence':
        c['sentences'].pop()
    elif variant == 'lost_target':
        c['target_ids'] = []
    elif variant == 'duplicate_sentence':
        c['sentences'].append(copy.deepcopy(c['sentences'][0]))
    elif variant == 'unsafe_id':
        c['case_id'] = '../escape'
    else:
        c['sentences'][0]['span']['region_id'] = 'f' * 64
    with pytest.raises(ValueError):
        validate_case(c)


@pytest.mark.parametrize('variant', ['missing_target', 'duplicate_target', 'foreign_target', 'foreign_property',
                                     'duplicate_method', 'foreign_condition', 'known_without_evidence'])
def test_reply_requires_complete_targets_and_same_block_unique_evidence(variant):
    c = case()
    data = reply(c).model_dump(mode='json')
    a = data['associations'][0]
    if variant == 'missing_target':
        data['associations'] = []
    elif variant == 'duplicate_target':
        data['associations'].append(copy.deepcopy(a))
    elif variant == 'foreign_target':
        a['target_id'] = 'S999'
    elif variant == 'foreign_property':
        a['property_sentence_ids'] = ['S999']
    elif variant == 'duplicate_method':
        a['method_sentence_ids'] = ['S1', 'S1']
    elif variant == 'foreign_condition':
        a['condition_sentence_ids'] = ['S999']
    else:
        a['property_sentence_ids'] = []
    with pytest.raises(ValueError):
        resolve_reply(c, AssociationReply.model_validate(data))


def test_unknown_can_retain_conflicting_sources_without_scientific_admission():
    c = case('Conductivity and DSC were compared. Measurements were performed.')
    data = reply(c, 'unknown').model_dump(mode='json')
    data['associations'][0]['property_sentence_ids'] = ['S1']
    assert resolve_reply(c, AssociationReply.model_validate(data))[0]['proposal']['property_kind'] == 'unknown'


def test_duplicate_json_and_invented_property_category_are_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        parse_reply('{"associations":[],"associations":[]}')
    data = reply(case()).model_dump(mode='json')
    data['associations'][0]['property_kind'] = 'confirmed_conductivity'
    with pytest.raises(ValueError):
        AssociationReply.model_validate(data)


def test_wire_messages_are_source_only_and_request_guard_rejects_settings_or_complete_page():
    c = case()
    c['local_baseline'] = [{'private_label': 'not_sent'}]
    payload = json.loads(messages(c)[1]['content'])
    assert set(payload) == {'target_ids', 'sentences'}
    assert payload['sentences'] == [{'id': 'S1', 'text': c['source']['quote']}]
    assert 'not_sent' not in json.dumps(messages(c)) and c['source']['original_pdf_path'] not in json.dumps(messages(c))
    raw = json.dumps(request(c), ensure_ascii=False).encode()
    guard(raw, c, [page_record(validate_case(c))])
    with pytest.raises(ValueError):
        guard(raw.replace(b'medium', b'high'), c, [])
    page = page_record(validate_case(c))
    from dataclasses import replace
    with pytest.raises(ValueError):
        guard(raw, c, [replace(page, text=c['source']['quote'])])


def parent_fixture():
    c = case('Conductivity was measured at 25°C <script>constructed source</script>.')
    source_data = c['source']
    # The registered page source covers the full page; the probe unit is its exact block.
    full = dict(source_data, start=0, end=len(source_data['page_text']), quote=source_data['page_text'],
                quote_sha256=text_hash(source_data['page_text']))
    full['region_id'] = source_identity(full)
    # Use block_source to produce the same derived region identity used by the real parent.
    from app.records.condition_transfer import block_source, unit_identity
    from app.records.schema import SourceRegion
    parent = SourceRegion.model_validate(full)
    unit = {'block_number': 0, 'source': {**c['sentences'][0]['span'], 'region_id': parent.region_id},
            'text_sha256': text_hash(source_data['quote']), 'bbox': [0, 0, 100, 100]}
    unit['unit_id'] = unit_identity(parent.region_id, {'block_number': 0, 'page_start': source_data['start'],
                                                    'page_end': source_data['end']})
    derived = block_source(parent, unit)
    events = [e.model_dump(mode='json') for e in source_events(derived)]
    packet = {'inventory': {'probe_units': 1}, 'baseline_packet': {
        'inventory': {'probe_units': 1}, 'pages': [{'source': parent.model_dump(mode='json'), 'units': [unit],
        'diagnostics': ['constructed_risk']}], 'control_source': source_data}}
    report = {'results': [{'unit_id': unit['unit_id'], 'events': events}],
              'separate_control_events': [e.model_dump(mode='json') for e in source_events(validate_case(c))]}
    return packet, report


def storage(tmp_path):
    parent = tmp_path / 'parent'
    parent.mkdir()
    packet, report = parent_fixture()
    (parent / 'prepared_packet.json').write_text(json.dumps(packet), encoding='utf-8')
    (parent / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    (parent / 'manifest.json').write_text(json.dumps({'version': 'records_condition_multilingual_v0.1',
        'phase': 'executed_frozen_comparison', 'inputs': {}, 'code': {},
        'outputs': {p.name: file_hash(p) for p in parent.iterdir()}}), encoding='utf-8')
    prepared = tmp_path / 'prepared'
    with patch('app.records.protocol_association_run.execute_comparison', return_value=report):
        with patch('app.records.protocol_association_run.send_openai_request', side_effect=AssertionError('Preparation called API')):
            prepare(parent, prepared, source_root=Path.cwd())
    return prepared


def native(c):
    return json.dumps({'status': 'completed', 'model': 'constructed-model', 'id': 'constructed-response',
        'usage': {'input_tokens': 25, 'output_tokens': 20}, 'output': [{'type': 'message', 'role': 'assistant',
        'status': 'completed', 'content': [{'type': 'output_text', 'text': reply(c).model_dump_json()}]}]}).encode()


def test_all_cue_blocks_and_separate_control_are_selected_without_silent_budget_truncation():
    packet, report = parent_fixture()
    cases, pages = build_cases(packet, report)
    assert len(cases) == 2 and len(pages) == 2
    assert cases[0]['parent_page_diagnostics']['diagnostics'] == ['constructed_risk']
    assert cases[-1]['case_id'] == 'separate_control' and cases[-1]['role'] == 'separate_control'
    with patch('app.records.protocol_association_run.MAX_CALLS', 1):
        with pytest.raises(ValueError, match='budget'):
            build_cases(packet, report)


def test_native_raw_persistence_exact_replay_and_deterministic_exclusive_html_exports(tmp_path):
    prepared = storage(tmp_path)
    plan, _ = load(prepared)
    output = tmp_path / 'run'
    calls = []
    def send(payload, key, timeout):
        c = plan['cases'][len(calls)]
        assert (output / c['case_id'] / 'request.json').read_bytes() == payload
        calls.append(payload)
        return native(c), 'constructed-request'
    with patch('app.records.protocol_association_run.send_openai_request', side_effect=send):
        summary = run(prepared, output, api_key='constructed-test-key')
    assert summary['statuses'] == {'integrity_valid': 2} and len(calls) == 2 <= MAX_CALLS
    first, second = tmp_path / 'export1', tmp_path / 'export2'
    a = export(prepared, output, first)
    export(prepared, output, second)
    assert a['transfer_targets'] == a['control_targets'] == 1
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    html = (first / 'review.html').read_text(encoding='utf-8')
    assert html.count('class="case"') == 2 and '<form' not in html and 'id="q"' in html
    assert '&lt;script&gt;constructed source&lt;/script&gt;' in html
    assert '<script>constructed source</script>' not in html
    with pytest.raises(FileExistsError):
        run(prepared, output, api_key='constructed-test-key')
    with pytest.raises(FileExistsError):
        export(prepared, output, first)


@pytest.mark.parametrize('failure', ['transport', 'http', 'incomplete', 'schema', 'reference', 'root'])
def test_failure_retains_raw_diagnostics_and_stops_remaining_calls(tmp_path, failure):
    prepared = storage(tmp_path)
    output = tmp_path / 'run'
    plan, _ = load(prepared)
    c = plan['cases'][0]
    if failure == 'transport':
        response = URLError('constructed transport failure')
    elif failure == 'http':
        import io
        response = HTTPError('https://api.openai.com/v1/responses', 429, 'constructed error', {}, io.BytesIO(b'private-key'))
    else:
        raw = json.loads(native(c))
        if failure == 'incomplete':
            raw['status'] = 'incomplete'
        elif failure == 'schema':
            raw['output'][0]['content'][0]['text'] = '{}'
        elif failure == 'reference':
            data = reply(c).model_dump(mode='json')
            data['associations'][0]['method_sentence_ids'] = ['S999']
            raw['output'][0]['content'][0]['text'] = json.dumps(data)
        else:
            raw = []
        response = (json.dumps(raw).encode(), None)
    with patch('app.records.protocol_association_run.send_openai_request',
               side_effect=response if isinstance(response, Exception) else None,
               return_value=response) as send:
        summary = run(prepared, output, api_key='private-key')
    assert send.call_count == 1 and summary['statuses'] == {'failed': 1, 'unattempted': 1}
    data = json.loads((output / 'report.json').read_bytes())
    assert 'private-key' not in json.dumps(data)
    if failure not in {'transport', 'http'}:
        assert (output / c['case_id'] / 'response.json').is_file()
    if failure == 'http':
        assert (output / c['case_id'] / 'http_error_redacted.bin').read_bytes() == b'<redacted>'


def test_missing_key_prevents_directory_creation_and_network(tmp_path):
    with patch('app.records.protocol_association_run.send_openai_request') as send:
        with pytest.raises(ValueError, match='credential'):
            run(tmp_path / 'no_preparation', tmp_path / 'no_run', api_key='')
        assert not (tmp_path / 'no_run').exists() and not send.called


@pytest.mark.parametrize('variant', ['code', 'input', 'phase', 'settings', 'request', 'local_baseline'])
def test_frozen_preparation_code_and_source_drift_are_not_hidden(tmp_path, variant):
    prepared = storage(tmp_path)
    path = prepared / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    if variant == 'code':
        manifest['code'][str(Path('app/records/protocol_association.py').resolve())] = 'f' * 64
    elif variant == 'input':
        (tmp_path / 'parent' / 'report.json').write_bytes(b'changed')
    elif variant == 'phase':
        manifest['phase'] = 'run'
    else:
        plan_path = prepared / 'plan.json'
        plan = json.loads(plan_path.read_bytes())
        if variant == 'settings':
            plan['maximum_calls'] += 1
        elif variant == 'request':
            plan['cases'][0]['request']['model'] = 'unfrozen-model'
        else:
            plan['cases'][0]['local_baseline'] = []
        plan_path.write_text(json.dumps(plan), encoding='utf-8')
        manifest['outputs']['plan.json'] = file_hash(plan_path)
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        load(prepared)
