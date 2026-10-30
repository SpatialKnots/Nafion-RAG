"""Constructed GigaChat transport fixtures only; network and real credentials forbidden."""

import copy
import io
import json
import socket
import ssl
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

from app.records import gigachat_dsc as giga
from app.records.sources import file_hash
from tests.unit.test_dsc_experiment import inputs, reply
from tests.unit.test_dsc_live import admission as admission  # noqa: F401
from tests.unit.test_dsc_live import frozen as frozen  # noqa: F401

KEY = 'constructed-giga-key-not-a-real-credential'
TOKEN = 'constructed-oauth-token-not-a-real-token'


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail('Real networking forbidden in GigaChat tests')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(giga, 'http', forbidden)
    monkeypatch.setattr(giga, 'ledger_root', lambda: tmp_path / 'ledger')


@pytest.fixture
def prepared(frozen, tmp_path):
    output = tmp_path / 'giga-prepared'
    giga.prepare(frozen, output)
    return output


def observed(wire, present=6, **extra):
    return giga.payload({'model': 'constructed-returned-giga:version', 'usage': {'total_tokens': 73},
        'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
            'content': json.dumps(reply(wire, present), ensure_ascii=False)}}], **extra})


def setup_transport(monkeypatch, prepared, *, response=None, balance=None, available=None, fail=None):
    _, wire, _ = giga.read_prepared(prepared)
    calls = []

    def http(url, body, authorization, context):
        calls.append(url)
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        if fail and url == fail[0]:
            raise fail[1]
        if url == giga.AUTH:
            assert authorization == 'Basic ' + KEY
            return giga.payload({'access_token': TOKEN, 'expires_at': 12345}), None
        assert authorization == 'Bearer ' + TOKEN
        if url.endswith('/models'):
            return giga.payload({'data': [{'id': v} for v in (available if available is not None else [giga.MODEL])]}), None
        if url.endswith('/balance'):
            return giga.payload({'balance': balance if balance is not None else [{'usage': giga.MODEL, 'value': 25000}]}), None
        assert url == giga.BASE + '/chat/completions'
        assert body == (prepared / 'request.json').read_bytes()
        slot = giga.ledger_root() / giga.digest(body)
        assert (slot / 'attempt.json').is_file()
        return response if response is not None else observed(wire), 'constructed-header-id'

    monkeypatch.setattr(giga, 'http', http)
    return calls


def send(prepared, output):
    return giga.dispatch(prepared, output, credentials=KEY, scope=giga.SCOPE, authorized=True)


def test_prepared_request_preserves_question_prompt_schema_and_sources(prepared, frozen):
    contract, wire, sources = giga.read_prepared(prepared)
    request = giga.strict_json((prepared / 'request.json').read_bytes())
    old = giga.strict_json((frozen / 'request.json').read_bytes())
    assert request['messages'] == old['input']
    assert request['response_format']['schema'] == old['text']['format']['schema']
    assert request['response_format']['strict'] is True
    assert len(sources) == 5 and len(wire['contexts']) == 5
    assert request['model'] == giga.MODEL and request['max_tokens'] == 4096
    assert not {'reasoning', 'store', 'truncation', 'service_tier'} & request.keys()
    assert contract['automatic_retries'] == contract['fallbacks'] == 0
    assert not giga.ledger_root().exists()
    assert (prepared / 'parent_snapshot/request.json').read_bytes() == (frozen / 'request.json').read_bytes()


@pytest.mark.parametrize('present', [0, 2, 6])
def test_exact_quotes_partial_and_abstention_preserve_offsets(present):
    _, wire, sources = inputs()
    checked = giga.inspect(observed(wire, present), wire, sources)
    assert len(checked['resolved']) == 6
    assert checked['evaluation']['scientific_acceptance'] == 'not_evaluated'
    assert sum(f['status'] == 'present' for f in checked['resolved']) == present
    for field in checked['resolved']:
        for evidence in field['evidence']:
            source = next(s for s in sources if s.region_id == evidence['region_id'])
            assert source.page_text[evidence['start']:evidence['end']] == evidence['quote']


@pytest.mark.parametrize('kind', ['length', 'refusal', 'function_call', 'foreign', 'invented', 'duplicate_topic', 'many_choices'])
def test_incomplete_and_unsupported_responses_rejected(kind):
    _, wire, sources = inputs()
    envelope = giga.strict_json(observed(wire))
    choice = envelope['choices'][0]
    if kind in ('length', 'refusal'):
        choice['finish_reason'] = kind
    elif kind == 'function_call':
        choice['message']['function_call'] = {'name': 'unexpected'}
    elif kind == 'many_choices':
        envelope['choices'].append(copy.deepcopy(choice))
    else:
        value = json.loads(choice['message']['content'])
        if kind == 'foreign':
            value['fields'][0]['evidence'][0]['citation_id'] = 'B1'
        elif kind == 'invented':
            value['fields'][0]['evidence'][0]['quote'] = 'Invented scientific claim'
        else:
            value['fields'][1]['topic'] = value['fields'][0]['topic']
        choice['message']['content'] = json.dumps(value)
    with pytest.raises(ValueError):
        giga.inspect(giga.payload(envelope), wire, sources)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"usage":NaN}', b'[]', b'\xff'])
def test_malformed_duplicate_nonfinite_json_rejected(raw):
    with pytest.raises(ValueError):
        giga.strict_json(raw)


@pytest.mark.parametrize('kind', ['permission', 'missing_key', 'wrong_scope'])
def test_permission_credentials_scope_fail_without_outputs_or_network(tmp_path, kind):
    with pytest.raises((ValueError, PermissionError)):
        giga.dispatch(tmp_path / 'absent', tmp_path / 'out', credentials='' if kind == 'missing_key' else KEY,
            scope='GIGACHAT_API_CORP' if kind == 'wrong_scope' else giga.SCOPE, authorized=kind != 'permission')
    assert not (tmp_path / 'out').exists() and not giga.ledger_root().exists()


def test_dispatch_saves_raw_usage_hashes_and_blocks_repeat_across_outputs(prepared, tmp_path, monkeypatch):
    calls = setup_transport(monkeypatch, prepared)
    output = tmp_path / 'live'
    result = send(prepared, output)
    assert result['status'] == 'integrity_valid' and result['model_attempts'] == 1
    assert result['oauth_attempts'] == 1 and result['account_read_attempts'] == 2
    assert result['usage'] == {'total_tokens': 73} and result['actual_cost'] is None
    assert result['returned_model'] == 'constructed-returned-giga:version'
    assert result['scientific_acceptance'] == 'not_evaluated'
    assert len(calls) == 4 and calls.count(giga.BASE + '/chat/completions') == 1
    assert b'choices' in (output / 'response_or_error.bin').read_bytes()
    stored = giga.strict_json((output / 'manifest.json').read_bytes())
    for name, checksum in stored['outputs'].items():
        assert file_hash(output / name) == checksum
    for path in output.iterdir():
        assert KEY.encode() not in path.read_bytes() and TOKEN.encode() not in path.read_bytes()
    with pytest.raises(FileExistsError, match='already reserved'):
        send(prepared, tmp_path / 'another-output')
    assert len(calls) == 4


@pytest.mark.parametrize('kind', ['no_model', 'empty_balance', 'negative_balance', 'unknown_balance'])
def test_account_preflight_blocks_generation_without_guess_or_fallback(prepared, tmp_path, monkeypatch, kind):
    calls = setup_transport(monkeypatch, prepared, available=[] if kind == 'no_model' else None,
        balance=[] if kind == 'empty_balance' else [{'usage': 'unknown' if kind == 'unknown_balance' else giga.MODEL,
            'value': -1 if kind == 'negative_balance' else 12}])
    result = send(prepared, tmp_path / 'out')
    assert result['status'] == 'failed' and result['model_attempts'] == 0
    assert not giga.ledger_root().exists()
    assert giga.BASE + '/chat/completions' not in calls


@pytest.mark.parametrize('stage', ['oauth', 'models', 'balance', 'generation'])
def test_http_error_is_typed_redacted_and_does_not_retry(prepared, tmp_path, monkeypatch, stage):
    url = giga.AUTH if stage == 'oauth' else giga.BASE + '/' + ('chat/completions' if stage == 'generation' else stage)
    error = HTTPError(url, 403, 'constructed ' + KEY, Message(), io.BytesIO(('body ' + KEY + ' ' + TOKEN).encode()))
    calls = setup_transport(monkeypatch, prepared, fail=(url, error))
    output = tmp_path / 'failed'
    result = send(prepared, output)
    assert result['status'] == 'failed' and result['errors'][0]['http_status'] == 403
    assert result['errors'][0]['stage'] == stage and calls.count(url) == 1
    assert result['model_attempts'] == (1 if stage == 'generation' else 0)
    for path in output.iterdir():
        assert KEY.encode() not in path.read_bytes()
        if stage != 'oauth':
            assert TOKEN.encode() not in path.read_bytes()
    if stage == 'oauth':
        assert (output / 'response_or_error.bin').read_bytes() == b''


def test_tls_failure_retained_before_any_model_attempt(prepared, tmp_path, monkeypatch):
    setup_transport(monkeypatch, prepared, fail=(giga.AUTH, URLError(ssl.SSLCertVerificationError('fixture TLS failure'))))
    result = send(prepared, tmp_path / 'tls-failure')
    assert result['status'] == 'failed' and result['model_attempts'] == 0
    assert result['errors'][0]['stage'] == 'oauth' and 'TLS failure' in result['errors'][0]['message']


def test_timeout_consumes_model_attempt_without_retry_or_refund(prepared, tmp_path, monkeypatch):
    calls = setup_transport(monkeypatch, prepared,
        fail=(giga.BASE + '/chat/completions', TimeoutError('constructed timeout; delivery unknown')))
    result = send(prepared, tmp_path / 'timeout')
    assert result['status'] == 'failed' and result['model_attempts'] == 1
    assert result['errors'][0]['type'] == 'TimeoutError'
    with pytest.raises(FileExistsError, match='already reserved'):
        send(prepared, tmp_path / 'another-output')
    assert calls.count(giga.BASE + '/chat/completions') == 1


def test_missing_usage_stays_unknown_and_echoed_secrets_cannot_be_accepted(prepared, tmp_path, monkeypatch):
    _, wire, _ = giga.read_prepared(prepared)
    raw = observed(wire, usage=None, extra_field=TOKEN)
    setup_transport(monkeypatch, prepared, response=raw)
    result = send(prepared, tmp_path / 'echo')
    assert result['status'] == 'response_invalid' and result['usage'] is None
    assert result['credential_redaction_applied']
    assert result['evaluation'] is None
    assert TOKEN.encode() not in (tmp_path / 'echo/response_or_error.bin').read_bytes()


def test_stale_prepared_request_fails_before_transport(prepared, tmp_path):
    (prepared / 'request.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='artifact changed'):
        send(prepared, tmp_path / 'out')
    assert not (tmp_path / 'out').exists() and not giga.ledger_root().exists()


def test_post_transport_drift_blocks_acceptance(prepared, tmp_path, monkeypatch):
    setup_transport(monkeypatch, prepared)
    original = giga.http

    def http(*args):
        result = original(*args)
        if args[0].endswith('/chat/completions'):
            (prepared / 'request.json').write_bytes(b'{}')
        return result

    monkeypatch.setattr(giga, 'http', http)
    result = send(prepared, tmp_path / 'out')
    assert result['status'] == 'failed' and result['evaluation'] is None
    assert result['errors'][0]['stage'] == 'postflight'


def test_html_escapes_model_text_and_has_historical_tac_link(tmp_path):
    html = giga.render({'reply': '<script>unsafe</script>'}, tmp_path)
    assert '<script>unsafe</script>' not in html and '&lt;script&gt;unsafe' in html
    assert 'metadata_review.html' in html and 'type="search"' in html
