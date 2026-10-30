"""Named source selection tests use constructed replies; no independent scientific gold."""

import copy
import io
import json
import socket
import ssl
from email.message import Message
from urllib.error import HTTPError

import pytest

from app.records import gigachat_dsc as transport
from app.records import gigachat_dsc_spans as named
from app.records.sources import file_hash
from tests.unit.test_dsc_experiment import inputs
from tests.unit.test_dsc_live import admission as admission  # noqa: F401
from tests.unit.test_dsc_live import frozen as frozen  # noqa: F401

KEY = 'constructed-second-giga-key-not-real'
TOKEN = 'constructed-second-giga-token-not-real'


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail('Real network forbidden in named DSC tests')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(transport, 'http', forbidden)
    monkeypatch.setattr(transport, 'ledger_root', lambda: tmp_path / 'shared-ledger')


@pytest.fixture
def prepared(frozen, tmp_path):
    baseline = tmp_path / 'baseline'
    baseline.mkdir()
    (baseline / 'result.json').write_bytes(named.payload({'status': 'response_invalid', 'fixture': True}))
    (baseline / 'response_or_error.bin').write_bytes(b'constructed baseline response, not a real API run')
    transport.manifest(baseline, 'recorded')
    output = tmp_path / 'named-prepared'
    named.prepare(frozen, baseline, output)
    return output


def selection(spans, present=6):
    fields = {}
    for i, topic in enumerate(named.TOPICS):
        ids = spans['protected_programme_span_ids'] if topic == 'temperature_programme' else [spans['spans'][0]['span_id']]
        fields[topic] = {'status': 'present' if i < present else 'unsupported',
            'span_ids': ids if i < present else [], 'diagnostic': 'Constructed fixture, not a scientific finding.'}
    return {'outcome': 'answer_proposal' if present == 6 else 'partial_proposal' if present else 'abstention',
        'fields': fields, 'diagnostic': 'Constructed source-reference test only.'}


def response(value, **extra):
    return named.payload({'model': 'constructed-returned-model', 'usage': {'prompt_tokens': 100, 'completion_tokens': 50},
        'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
            'content': json.dumps(value, ensure_ascii=False)}}], **extra})


def setup_transport(prepared, monkeypatch, *, fail=None, raw=None, available=True, positive=True):
    _, _, _, spans = named.read_prepared(prepared)
    calls = []

    def http(url, body, auth, context):
        calls.append(url)
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        if fail and url == fail[0]:
            raise fail[1]
        if url == transport.AUTH:
            assert auth == 'Basic ' + KEY
            return named.payload({'access_token': TOKEN}), None
        assert auth == 'Bearer ' + TOKEN
        if url.endswith('/models'):
            return named.payload({'data': [{'id': transport.MODEL}] if available else []}), None
        if url.endswith('/balance'):
            return named.payload({'balance': [{'usage': 'GigaChat-Max', 'value': 100000 if positive else 0}]}), None
        assert url.endswith('/chat/completions')
        assert body == (prepared / 'request.json').read_bytes()
        assert (transport.ledger_root() / transport.digest(body) / 'attempt.json').is_file()
        return response(selection(spans)) if raw is None else raw, 'constructed-request-id'

    monkeypatch.setattr(transport, 'http', http)
    return calls


def send(prepared, output):
    return named.dispatch(prepared, output, credentials=KEY, scope=transport.SCOPE, authorized=True)


def test_catalog_preserves_entire_body_heading_and_semicolon_programme():
    _, wire, sources = inputs()
    spans = named.catalog(wire, sources)
    source = next(s for s in sources if s.region_id == spans['source_region_id'])
    assert spans['heading'] + ''.join(s['text'] for s in spans['spans']) == source.quote
    program = next(s for s in spans['spans'] if s['span_id'] in spans['protected_programme_span_ids'])
    assert 'heating to 50' in program['text'] and 'cooling to -150' in program['text'] and 'heating to 300' in program['text']
    assert program['text'].count(';') == 2
    for span in spans['spans']:
        assert source.quote[span['start']:span['end']] == span['text']
        assert span['text_sha256'] == named.text_hash(span['text'])


def test_catalog_keeps_unicode_units_linebreaks_and_homogenisation():
    from app.evaluation.dsc_context_run import build
    from tests.unit.test_dsc_admission import BODY, source_plan

    text = BODY.replace('flow', 'ﬂow').replace('-150', '−150').replace('50 C;', '50 ◦C and hold for homogenisation;')
    wire, sources, _ = build(source_plan(text))
    spans = named.catalog(wire, sources)
    full = spans['heading'] + ''.join(s['text'] for s in spans['spans'])
    assert 'ﬂow' in full and '−150' in full and '◦C' in full and '\n' in full and 'homogenisation' in full
    decoded = named.inspect(response(selection(spans)), wire, sources, spans)
    program = decoded['decoded_reply']['fields'][-1]['evidence'][0]['quote']
    assert 'homogenisation' in program and program in full


def test_schema_requires_exactly_six_named_slots_and_enumerated_source_ids():
    _, wire, sources = inputs()
    spans = named.catalog(wire, sources)
    req = named.request(wire, spans)
    schema = req['response_format']['schema']
    fields = schema['$defs']['NamedFields']
    assert fields['additionalProperties'] is False and set(fields['required']) == set(named.TOPICS)
    assert schema['$defs']['Selection']['properties']['span_ids']['items']['enum'] == [s['span_id'] for s in spans['spans']]
    user = json.loads(req['messages'][1]['content'])
    assert user['source_packet'] == wire
    assert all(set(s) == {'span_id', 'text'} for s in user['source_spans'])
    assert 'protected_programme_span_ids' not in user


@pytest.mark.parametrize('present', [0, 2, 6])
def test_complete_partial_and_abstention_decode_only_exact_source(present):
    _, wire, sources = inputs()
    spans = named.catalog(wire, sources)
    result = named.inspect(response(selection(spans, present)), wire, sources, spans)
    assert len(result['resolved']) == 6 and result['evaluation']['scientific_acceptance'] == 'not_evaluated'
    assert sum(f['status'] == 'present' for f in result['resolved']) == present
    for field in result['resolved']:
        for evidence in field['evidence']:
            source = next(s for s in sources if s.region_id == evidence['region_id'])
            assert source.page_text[evidence['start']:evidence['end']] == evidence['quote']


@pytest.mark.parametrize('kind', ['missing_field', 'extra_field', 'unknown_id', 'bibliography', 'duplicate_id',
    'reversed_ids', 'short_programme', 'outcome', 'nonpresent_ids', 'present_no_ids', 'typed_quote'])
def test_invalid_named_selection_is_rejected_without_repair(kind):
    _, wire, sources = inputs()
    spans = named.catalog(wire, sources)
    value = selection(spans)
    field = value['fields']['instrument']
    if kind == 'missing_field':
        del value['fields']['measurement_environment']
    elif kind == 'extra_field':
        value['fields']['extra'] = field
    elif kind in ('unknown_id', 'bibliography'):
        field['span_ids'] = ['M1:S999' if kind == 'unknown_id' else 'B1:S001']
    elif kind == 'duplicate_id':
        field['span_ids'] *= 2
    elif kind == 'reversed_ids':
        field['span_ids'] = [s['span_id'] for s in reversed(spans['spans'])]
    elif kind == 'short_programme':
        value['fields']['temperature_programme']['span_ids'] = [spans['spans'][0]['span_id']]
    elif kind == 'outcome':
        value['outcome'] = 'abstention'
    elif kind == 'nonpresent_ids':
        field['status'] = 'unsupported'
    elif kind == 'present_no_ids':
        field['span_ids'] = []
    else:
        field['quote'] = 'Model must not type source text'
    with pytest.raises(ValueError):
        named.inspect(response(value), wire, sources, spans)


def test_duplicate_json_fields_are_rejected():
    _, wire, sources = inputs()
    spans = named.catalog(wire, sources)
    raw = response(selection(spans))
    envelope = transport.strict_json(raw)
    envelope['choices'][0]['message']['content'] = '{"outcome":"abstention","outcome":"answer_proposal"}'
    with pytest.raises(ValueError, match='Duplicate'):
        named.inspect(named.payload(envelope), wire, sources, spans)


def test_changed_catalog_and_source_text_are_rejected():
    _, wire, sources = inputs()
    spans = named.catalog(wire, sources)
    changed = copy.deepcopy(spans)
    changed['spans'][0]['text'] = 'edited source'
    with pytest.raises(ValueError, match='catalog differs'):
        named.inspect(response(selection(spans)), wire, sources, changed)
    modified = copy.deepcopy(wire)
    modified['contexts'][-1]['text'] = 'edited M1'
    with pytest.raises(ValueError, match='differs from registered'):
        named.catalog(modified, sources)


def test_non_method_source_cannot_supply_selection():
    _, wire, sources = inputs()
    wire['contexts'][-1]['role'] = 'bibliographic_identity'
    with pytest.raises(ValueError, match='not a methods source'):
        named.catalog(wire, sources)


@pytest.mark.parametrize('kind', ['missing', 'ambiguous'])
def test_missing_or_ambiguous_programme_boundary_fails_preparation(kind):
    from app.evaluation.dsc_context_run import build
    from tests.unit.test_dsc_admission import BODY, source_plan

    text = BODY.replace('temperature programme', 'procedure') if kind == 'missing' else BODY + ' Another temperature programme.'
    wire, sources, _ = build(source_plan(text))
    with pytest.raises(ValueError, match='unique complete source'):
        named.catalog(wire, sources)


@pytest.mark.parametrize('finish', ['length', 'content_filter', 'function_call'])
def test_incomplete_or_refused_response_fails(finish):
    _, wire, sources = inputs()
    spans = named.catalog(wire, sources)
    raw = transport.strict_json(response(selection(spans)))
    raw['choices'][0]['finish_reason'] = finish
    with pytest.raises(ValueError, match='incomplete or refused'):
        named.inspect(named.payload(raw), wire, sources, spans)


def test_preparation_copies_and_binds_baseline_without_touching_it(prepared):
    frozen, _, _, _ = named.read_prepared(prepared)
    baseline = prepared.parent / 'baseline'
    assert frozen['maximum_model_attempts'] == 1
    assert any(path.endswith('app\\records\\dsc_live.py') or path.endswith('app/records/dsc_live.py')
        for path in frozen['code'])
    for p in baseline.iterdir():
        assert p.read_bytes() == (prepared / 'baseline_snapshot' / p.name).read_bytes()
    assert not transport.ledger_root().exists()
    (baseline / 'response_or_error.bin').write_bytes(b'changed baseline')
    with pytest.raises(ValueError):
        named.read_prepared(prepared)


@pytest.mark.parametrize('kind', ['permission', 'key', 'scope'])
def test_no_permission_or_credentials_no_network_no_slot(tmp_path, kind):
    with pytest.raises((ValueError, PermissionError)):
        named.dispatch(tmp_path / 'absent', tmp_path / 'out', credentials='' if kind == 'key' else KEY,
            scope='GIGACHAT_API_CORP' if kind == 'scope' else transport.SCOPE, authorized=kind != 'permission')
    assert not (tmp_path / 'out').exists() and not transport.ledger_root().exists()


def test_real_dispatch_path_with_mock_records_raw_and_exact_sources_once(prepared, monkeypatch, tmp_path):
    calls = setup_transport(prepared, monkeypatch)
    output = tmp_path / 'out'
    result = send(prepared, output)
    assert result['status'] == 'integrity_valid' and result['model_attempts'] == 1
    assert result['evaluation']['programme_sequence_retained']
    assert result['evaluation']['exact_selected_references'] == 6
    assert result['scientific_acceptance'] == 'not_evaluated' and result['actual_cost'] is None
    assert result['usage'] == {'prompt_tokens': 100, 'completion_tokens': 50}
    assert result['returned_model'] == 'constructed-returned-model' and result['request_id'] == 'constructed-request-id'
    for name, checksum in transport.strict_json((output / 'manifest.json').read_bytes())['outputs'].items():
        assert file_hash(output / name) == checksum
    for path in output.iterdir():
        assert KEY.encode() not in path.read_bytes() and TOKEN.encode() not in path.read_bytes()
    with pytest.raises(FileExistsError, match='already reserved'):
        send(prepared, tmp_path / 'another')
    assert calls.count(transport.BASE + '/chat/completions') == 1


@pytest.mark.parametrize('kind', ['model', 'balance'])
def test_account_admission_cannot_be_bypassed(prepared, monkeypatch, tmp_path, kind):
    calls = setup_transport(prepared, monkeypatch, available=kind != 'model', positive=kind != 'balance')
    result = send(prepared, tmp_path / 'out')
    assert result['status'] == 'failed' and result['model_attempts'] == 0
    assert not transport.ledger_root().exists()
    assert transport.BASE + '/chat/completions' not in calls


@pytest.mark.parametrize('kind', ['timeout', 'http'])
def test_model_error_persists_reservation_and_never_retries(prepared, monkeypatch, tmp_path, kind):
    error = (TimeoutError('fixture delivery unknown') if kind == 'timeout' else
        HTTPError(transport.BASE + '/chat/completions', 429, KEY, Message(), io.BytesIO(TOKEN.encode())))
    calls = setup_transport(prepared, monkeypatch, fail=(transport.BASE + '/chat/completions', error))
    result = send(prepared, tmp_path / 'out')
    assert result['status'] == 'failed' and result['model_attempts'] == 1
    assert result['errors'][0]['stage'] == 'generation'
    assert KEY not in result['errors'][0]['message']
    with pytest.raises(FileExistsError):
        send(prepared, tmp_path / 'again')
    assert calls.count(transport.BASE + '/chat/completions') == 1


def test_post_transport_drift_blocks_acceptance(prepared, monkeypatch, tmp_path):
    setup_transport(prepared, monkeypatch)
    original = transport.http

    def http(*args):
        raw = original(*args)
        if args[0].endswith('/chat/completions'):
            (prepared / 'catalog.json').write_bytes(b'{}')
        return raw

    monkeypatch.setattr(transport, 'http', http)
    result = send(prepared, tmp_path / 'out')
    assert result['status'] == 'failed' and result['evaluation'] is None
    assert result['errors'][0]['stage'] == 'postflight'


def test_html_escapes_diagnostics_and_has_search_and_tac_link(tmp_path):
    html = named.render({'diagnostic': '<script>evil</script>'}, tmp_path)
    assert '<script>evil</script>' not in html and '&lt;script&gt;' in html
    assert 'type="search"' in html and 'metadata_review.html' in html
