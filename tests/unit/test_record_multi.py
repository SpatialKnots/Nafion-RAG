"""Constructed multi-record/source/coverage counterexamples; no independent scientific gold."""

from __future__ import annotations

import copy
import json
from urllib.error import URLError

import pytest

from app.records import multi_run as runner
from app.records.checks import check_bundle
from app.records.extraction import FIELDS
from app.records.fixed_links import FixedSpanReply, parse_fixed_reply
from app.records.multi import MAX_RECORDS, build_multi_messages, parse_multi_reply, resolve_multi_reply
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_fixed_links import selection, source


def multi_source():
    base = source()
    quote = ('Sample L conductivity 1 S/cm at 20 °C. Method EIS.\n'
             'Sample M conductivity 2 S/cm at 30 °C. Method DC.\n'
             'Table note: Sample M at 30 °C, not 20 °C.\n'
             'Prior work reports Sample N conductivity 3–4 S/cm at 40 °C.\n')
    data = base.regions[0].model_dump()
    full = 'Hidden unsent page prefix.\n' + quote + 'Hidden unsent page suffix.'
    data.update(page_text=full, page_text_sha256=text_hash(full), start=full.index(quote),
                end=full.index(quote) + len(quote), quote=quote, quote_sha256=text_hash(quote))
    data['region_id'] = source_identity(data)
    return base.model_copy(update={'regions': (SourceRegion.model_validate(data),)})


def measurement(bundle, label, value, temperature, *, representation='scalar', extra=None):
    raw = {'sample_label': label, 'property_name': 'conductivity', 'value': value, 'unit': 'S/cm', 'temperature': temperature}
    raw.update(extra or {})
    # Locate repeated property/unit lexemes inside the declared sample's sentence.
    text = bundle.regions[0].quote
    first = text.index(label)
    last = text.index('.', first) + 1
    from app.records.spans import token_offsets

    offsets = token_offsets(text)

    def span(word):
        start = text.index(word, first)
        end = start + len(word)
        return {'region': 'R1', 'start_token': next(i for i, pair in enumerate(offsets) if pair[0] == start),
                'end_token': next(i for i, pair in enumerate(offsets) if pair[1] == end)}

    evidence = span(text[first:last])
    observations = [{'field': name, 'status': 'present' if name in raw else 'not_found_in_context',
                     'raw_span': span(raw[name]) if name in raw else None,
                     'evidence': [evidence] if name in raw else [], 'note': 'Constructed exact source observation.'}
                    for name in FIELDS]
    return {'observations': observations, 'representation': representation,
            'linkage': {role: {'evidence': [evidence], 'note': 'Constructed link, not independently assessed.'}
                        for role in ('sample_value', 'property_value', 'conditions_measurement')}}


def reply_data(bundle):
    return {'schema_version': 'records_multi_fixed_reply_v0.1', 'coverage': 'claimed_complete_in_context',
            'returned_measurement_count': 2,
            'measurements': [measurement(bundle, 'Sample L', '1', '20 °C'), measurement(bundle, 'Sample M', '2', '30 °C')],
            'unresolved': [], 'diagnostic': 'Constructed observations only; not scientific gold.'}


def unresolved(bundle, reason='unsupported_layout'):
    return {'reason': reason, 'evidence': [selection(bundle, 'Table note')], 'note': 'Constructed unresolved source.'}


def test_multiple_samples_temperatures_and_range_restore_exact_fields_without_merging():
    bundle = multi_source()
    data = reply_data(bundle)
    data['measurements'].append(measurement(bundle, 'Sample N', '3–4', '40 °C', representation='range'))
    data['returned_measurement_count'] = 3
    resolved, pending = resolve_multi_reply(bundle, parse_multi_reply(json.dumps(data)))
    assert len(resolved.records) == 3 and not pending
    assert [r.sample_label.raw_text for r in resolved.records] == ['Sample L', 'Sample M', 'Sample N']
    assert [r.temperature.raw_text for r in resolved.records] == ['20 °C', '30 °C', '40 °C']
    assert resolved.records[2].value.raw_value.raw_text == '3–4'
    assert resolved.records[2].value.representation == 'range'
    assert all(r.method.status == 'not_found_in_context' for r in resolved.records)
    assert all(r.review_state == 'needs_review' and r.li_ion_confirmation == 'not_reviewed' for r in resolved.records)
    assert all(c.scientific_admission == 'not_evaluated' for c in check_bundle(resolved))


@pytest.mark.parametrize('variation', ['exact', 'notes', 'representation', 'observation_order', 'links'])
def test_duplicate_coordinates_cannot_inflate_count_with_cosmetic_variants(variation):
    bundle = multi_source()
    data = reply_data(bundle)
    duplicate = copy.deepcopy(data['measurements'][0])
    if variation == 'notes':
        duplicate['observations'][0]['note'] = 'Different model prose.'
    elif variation == 'representation':
        duplicate['representation'] = 'unparsed'
    elif variation == 'observation_order':
        duplicate['observations'].reverse()
    elif variation == 'links':
        duplicate['linkage']['sample_value'] = None
    data['measurements'][1] = duplicate
    with pytest.raises(ValueError, match='Duplicate multi-record'):
        resolve_multi_reply(bundle, parse_multi_reply(json.dumps(data)))


@pytest.mark.parametrize('mutation', ['count', 'boolean_count', 'empty_complete', 'partial_without_scope',
                                    'unsupported_with_records', 'empty_with_records', 'ceiling_complete', 'over_ceiling'])
def test_coverage_count_and_budget_contradictions_fail(mutation):
    bundle = multi_source()
    data = reply_data(bundle)
    if mutation == 'count':
        data['returned_measurement_count'] = 1
    elif mutation == 'boolean_count':
        data['returned_measurement_count'] = True
    elif mutation == 'empty_complete':
        data.update(returned_measurement_count=0, measurements=[])
    elif mutation == 'partial_without_scope':
        data['coverage'] = 'partial'
    elif mutation == 'unsupported_with_records':
        data.update(coverage='unsupported', unresolved=[unresolved(bundle)])
    elif mutation == 'empty_with_records':
        data['coverage'] = 'no_measurements_proposed'
    else:
        data['measurements'] *= 2 if mutation == 'ceiling_complete' else 3
        data['returned_measurement_count'] = len(data['measurements'])
    with pytest.raises(ValueError):
        parse_multi_reply(json.dumps(data))


def test_partial_and_unsupported_scope_keep_exact_source_spans_not_silent_omissions():
    bundle = multi_source()
    data = reply_data(bundle)
    data.update(coverage='partial', unresolved=[unresolved(bundle)])
    result, pending = resolve_multi_reply(bundle, parse_multi_reply(json.dumps(data)))
    assert len(result.records) == 2 and pending[0]['evidence'][0]['quote'] == 'Table note'
    data.update(coverage='unsupported', measurements=[], returned_measurement_count=0)
    assert resolve_multi_reply(bundle, parse_multi_reply(json.dumps(data)))[0].records == ()
    data.update(coverage='no_measurements_proposed', unresolved=[])
    assert resolve_multi_reply(bundle, parse_multi_reply(json.dumps(data)))[0].records == ()


@pytest.mark.parametrize('content', ['{"coverage":"partial","coverage":"unsupported"}',
                                   '{"nested":{"start_token":0,"start_token":1}}'])
def test_duplicate_json_keys_fail_at_every_reply_depth(content):
    with pytest.raises(ValueError, match='Duplicate JSON key'):
        parse_multi_reply(content)


@pytest.mark.parametrize('field', ['raw', 'unresolved'])
def test_foreign_or_outside_token_coordinates_fail(field):
    bundle = multi_source()
    data = reply_data(bundle)
    if field == 'raw':
        data['measurements'][0]['observations'][0]['raw_span']['end_token'] = 99999
    else:
        data.update(coverage='partial', unresolved=[unresolved(bundle)])
        data['unresolved'][0]['evidence'][0]['region'] = 'R99'
    with pytest.raises(ValueError, match='outside|Unknown token region'):
        resolve_multi_reply(bundle, parse_multi_reply(json.dumps(data)))


def test_footnote_and_prior_work_text_are_preserved_but_wrong_association_is_not_scientifically_accepted():
    bundle = multi_source()
    data = reply_data(bundle)
    # A deliberately incorrect source association remains literal, illustrating the
    # boundary of integrity checks rather than pretending semantic validation exists.
    obs = next(o for o in data['measurements'][1]['observations'] if o['field'] == 'temperature')
    obs['raw_span'] = selection(bundle, '20 °C')
    obs['evidence'] = [selection(bundle, 'Table note: Sample M at 30 °C, not 20 °C.')]
    # Use the occurrence inside the footnote, not an identical lexeme elsewhere.
    from app.records.spans import token_offsets

    text = bundle.regions[0].quote
    start = text.index('20 °C', text.index('Table note'))
    offsets = token_offsets(text)
    obs['raw_span'] = {'region': 'R1', 'start_token': next(i for i, x in enumerate(offsets) if x[0] == start),
                       'end_token': next(i for i, x in enumerate(offsets) if x[1] == start + len('20 °C'))}
    result, _ = resolve_multi_reply(bundle, parse_multi_reply(json.dumps(data)))
    assert result.records[1].temperature.raw_text == '20 °C'
    assert any(c.status == 'unknown' for c in check_bundle(result)[1].checks)
    assert check_bundle(result)[1].scientific_admission == 'not_evaluated'
    assert 'Prior work reports' in build_multi_messages(bundle, runner.TASK)[1]['content']


def test_new_format_is_separate_and_actual_request_contains_no_hidden_page_or_paths():
    bundle = multi_source()
    data = reply_data(bundle)
    with pytest.raises(ValueError):
        parse_fixed_reply(json.dumps(data))
    assert FixedSpanReply.model_json_schema()['properties']['measurements']['maxItems'] == 1
    request = runner.build_multi_request(bundle)
    assert request['text']['format']['schema']['properties']['measurements']['maxItems'] == MAX_RECORDS
    for definition in [request['text']['format']['schema'], *request['text']['format']['schema']['$defs'].values()]:
        if definition.get('type') == 'object':
            assert definition['additionalProperties'] is False
            assert set(definition['properties']) == set(definition['required'])
    assert 'Hidden unsent' not in json.dumps(request)
    assert '/synthetic/a.pdf' not in json.dumps(request)
    assert 'zero or ONE' not in request['input'][0]['content']


def fake_prepared(tmp_path, monkeypatch):
    bundle = multi_source()
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    rows = []
    for case, identifier in runner.CASES:
        directory = prepared / case
        directory.mkdir()
        (directory / 'input.json').write_text(bundle.model_dump_json(), encoding='utf-8')
        (directory / 'request.json').write_text(json.dumps(runner.build_multi_request(bundle), ensure_ascii=False), encoding='utf-8')
        rows.append({'case_id': case, 'context_id': identifier, 'input': f'{case}/input.json',
                     'request': f'{case}/request.json', 'page_number': 1, 'article_id': str(bundle.regions[0].article_id)})
    (prepared / 'manifest.json').write_text('{}', encoding='utf-8')
    bindings = {str(p.resolve()): file_hash(p) for p in prepared.rglob('*') if p.is_file()}
    from app.records.article_windows import source_page

    monkeypatch.setattr(runner, '_load_prepared', lambda _: ({'cases': rows}, [source_page(bundle.regions[0])], bindings))
    return prepared, bundle


def envelope(content, *, status='completed'):
    return json.dumps({'status': status, 'id': 'synthetic-response', 'model': 'synthetic-model',
                       'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
                                   'content': [{'type': 'output_text', 'text': content}]}],
                       'usage': {'input_tokens': 100, 'output_tokens': 100}}).encode()


def test_mocked_four_case_run_retains_multi_records_raw_response_and_coverage(tmp_path, monkeypatch):
    prepared, bundle = fake_prepared(tmp_path, monkeypatch)
    calls = []

    def send(payload, key, timeout):
        calls.append(payload)
        return envelope(json.dumps(reply_data(bundle))), 'synthetic-request'

    monkeypatch.setattr(runner, 'send_openai_request', send)
    report = runner.run_smoke(prepared, tmp_path / 'run', api_key='synthetic-key')
    assert len(calls) == 4 and report['summary']['proposed_records'] == 8
    assert report['summary']['integrity_valid'] == 4
    assert report['summary']['scientific_precision'] is None
    assert report['final_source_integrity']['status'] == 'verified'
    assert (tmp_path / 'run/review.html').read_text(encoding='utf-8').count('class="case"') == 4
    assert 'synthetic-key' not in (tmp_path / 'run/report.json').read_text(encoding='utf-8')


@pytest.mark.parametrize('failure', ['timeout', 'transport', 'incomplete', 'duplicate_key', 'wrong_span', 'refusal'])
def test_first_failure_stops_remaining_cases_and_is_not_a_successful_abstention(tmp_path, monkeypatch, failure):
    prepared, bundle = fake_prepared(tmp_path, monkeypatch)
    calls = []

    def send(*args):
        calls.append(1)
        if failure == 'timeout':
            raise TimeoutError('Constructed timeout')
        if failure == 'transport':
            raise URLError('Constructed network failure')
        if failure == 'incomplete':
            return envelope('{}', status='incomplete'), None
        if failure == 'refusal':
            value = json.loads(envelope('{}'))
            value['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'Constructed refusal'}]
            return json.dumps(value).encode(), None
        data = reply_data(bundle)
        if failure == 'wrong_span':
            data['measurements'][0]['observations'][0]['raw_span']['end_token'] = 99999
        content = json.dumps(data)
        if failure == 'duplicate_key':
            content = content.replace('"diagnostic":', '"diagnostic":"duplicate", "diagnostic":')
        return envelope(content), None

    monkeypatch.setattr(runner, 'send_openai_request', send)
    report = runner.run_smoke(prepared, tmp_path / 'run', api_key='synthetic-key')
    assert len(calls) == 1
    assert report['summary']['failed'] == 1 and report['summary']['unattempted'] == 3
    assert report['summary']['proposed_records'] == 0 and report['summary']['model_calls'] == 1
    assert not (tmp_path / 'run' / runner.CASES[0][0] / 'candidates.json').exists()


def test_request_scope_guard_and_changed_input_prevent_network_call(tmp_path, monkeypatch):
    prepared, bundle = fake_prepared(tmp_path, monkeypatch)
    path = prepared / runner.CASES[0][0] / 'input.json'
    path.write_bytes(path.read_bytes() + b' ')
    monkeypatch.setattr(runner, 'send_openai_request', lambda *args: pytest.fail('No network call allowed'))
    report = runner.run_smoke(prepared, tmp_path / 'run', api_key='synthetic-key')
    assert report['summary']['model_calls'] == 0
    assert report['final_source_integrity']['status'] == 'failed'
    from app.records.article_windows import source_page

    region = bundle.regions[0]
    # A different registered complete page exactly matching the submitted quote.
    page = source_page(region)
    from dataclasses import replace

    with pytest.raises(ValueError, match='Full-page scope guard'):
        runner.guard_request(runner.build_multi_request(bundle), bundle, [replace(page, text=region.quote)])
