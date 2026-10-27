"""Observed result recording from constructed mock transports; never live API."""

import hashlib
import io
import json
from email.message import Message
from http.client import IncompleteRead
from urllib.error import HTTPError

import pytest

from app.generation.dsc_experiment import result_template
from app.records import dsc_live as live
from tests.unit.test_dsc_experiment import envelope, reply
from tests.unit.test_dsc_live import KEY, digest, dispatch, read
from tests.unit.test_dsc_live import admission as admission  # noqa: F401
from tests.unit.test_dsc_live import frozen as frozen  # noqa: F401
from tests.unit.test_dsc_live import offline as offline  # noqa: F401


def wire(source):
    return json.loads(read(source / 'request.json')['input'][1]['content'])


def mock_response(monkeypatch, raw, request_id='constructed-header-request'):
    def send(*args):
        return raw, request_id

    monkeypatch.setattr(live, 'send_openai_request', send)


@pytest.mark.parametrize('present', [0, 2, 6])
def test_valid_complete_partial_abstention_keep_actual_metadata_and_all_artifact_hashes(frozen, tmp_path, monkeypatch, present):
    raw = envelope(reply(wire(frozen), present), model='constructed-returned-model-differs-from-alias',
        usage={'input_tokens': 101, 'output_tokens': 23, 'total_tokens': 124,
            'input_tokens_details': {'cached_tokens': 0}, 'extra_observed_counter': 7}, service_tier='constructed-tier')
    mock_response(monkeypatch, raw)
    receipt = dispatch(frozen, tmp_path / 'out')
    result = read(tmp_path / 'out/result.json')
    metadata = read(tmp_path / 'out/response_metadata.json')
    assert receipt['status'] == 'response_received_unvalidated'  # immutable transport snapshot
    assert result['status'] == 'integrity_valid'
    assert result['outcome'] == ('answer_proposal' if present == 6 else 'partial_proposal' if present else 'abstention')
    assert result['returned_model'] == 'constructed-returned-model-differs-from-alias'
    assert result['usage'] == json.loads(raw)['usage'] == metadata['usage']
    assert result['request_id'] == 'constructed-header-request'
    assert result['response_id'] == 'constructed-response'
    assert result['service_tier'] == 'constructed-tier'
    assert result['actual_cost_usd'] is None and result['scientific_acceptance'] == 'not_evaluated'
    assert result['errors'] == [] and all(result['checks'].values())
    assert result_template().keys() <= result.keys()
    assert result['error'] is None
    assert result['response_sha256'] == hashlib.sha256(raw).hexdigest()
    assert result['elapsed_seconds'] == receipt['elapsed_seconds'] >= 0
    assert result['recording_elapsed_seconds'] >= 0
    assert (tmp_path / 'out/response_or_error.bin').read_bytes() == raw
    assert len(read(tmp_path / 'out/resolved.json')['fields']) == 6
    reservation = live._ledger_root() / digest(frozen)
    assert (reservation / 'result.json').read_bytes() == (tmp_path / 'out/result.json').read_bytes()
    manifest = read(tmp_path / 'out/manifest.json')
    assert manifest == read(reservation / 'result_manifest.json')
    assert set(manifest['outputs']) == {p.name for p in (tmp_path / 'out').iterdir() if p.name != 'manifest.json'}
    for name, expected in manifest['outputs'].items():
        assert hashlib.sha256((tmp_path / 'out' / name).read_bytes()).hexdigest() == expected
    assert manifest['code'] and manifest['inputs']


@pytest.mark.parametrize('usage', [None, {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}])
def test_missing_provider_metadata_stays_unknown_and_zero_usage_is_not_missing(frozen, tmp_path, monkeypatch, usage):
    value = json.loads(envelope(reply(wire(frozen))))
    for key in ('model', 'id', 'usage'):
        value.pop(key)
    if usage is not None:
        value['usage'] = usage
    mock_response(monkeypatch, json.dumps(value).encode(), request_id=None)
    dispatch(frozen, tmp_path / 'missing')
    result = read(tmp_path / 'missing/result.json')
    assert result['status'] == 'integrity_valid'
    assert result['usage'] == usage
    assert result['returned_model'] is result['request_id'] is result['response_id'] is None
    missing = {'request_id', 'response_id', 'returned_model', 'service_tier'}
    if usage is None:
        missing.add('usage')
    assert set(read(tmp_path / 'missing/response_metadata.json')['missing_observed_fields']) == missing


@pytest.mark.parametrize('kind,stage', [
    ('non_utf8', 'metadata_json'), ('malformed', 'metadata_json'), ('array', 'metadata_json'),
    ('duplicate_json', 'metadata_json'), ('nonfinite', 'metadata_json'),
    ('incomplete', 'completion_contract'), ('refusal', 'completion_contract'),
    ('schema', 'reply_schema'), ('foreign_citation', 'source_integrity'), ('invented_quote', 'source_integrity'),
])
def test_invalid_response_is_explicit_error_never_successful_abstention(frozen, tmp_path, monkeypatch, kind, stage):
    value = reply(wire(frozen))
    if kind == 'schema':
        value['fields'].pop()
    if kind == 'foreign_citation':
        value['fields'][0]['evidence'][0]['citation_id'] = 'B1'
    if kind == 'invented_quote':
        value['fields'][0]['evidence'][0]['quote'] = 'constructed quote absent from source'
    raw = envelope(value)
    if kind == 'incomplete':
        raw = envelope(value, status='incomplete', incomplete_details={'reason': 'constructed_output_limit'})
    elif kind == 'refusal':
        message = json.loads(raw)
        message['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'Constructed refusal.'}]
        raw = json.dumps(message).encode()
    elif kind in ('non_utf8', 'malformed', 'array', 'duplicate_json', 'nonfinite'):
        raw = {'non_utf8': b'\xfffixture', 'malformed': b'{incomplete', 'array': b'[]',
            'duplicate_json': b'{"status":"completed","status":"incomplete"}',
            'nonfinite': b'{"status":"completed","usage":{"input_tokens":NaN}}'}[kind]
    mock_response(monkeypatch, raw)
    dispatch(frozen, tmp_path / 'out')
    result = read(tmp_path / 'out/result.json')
    assert result['status'] == 'response_invalid'
    assert result['error'] is not None
    assert result['outcome'] is result['evaluation'] is None
    assert any(error['stage'] == stage for error in result['errors'])
    assert (tmp_path / 'out/response_or_error.bin').read_bytes() == raw
    assert not (tmp_path / 'out/resolved.json').exists()
    assert (tmp_path / 'out/reply.json').exists() == (stage == 'source_integrity')
    if stage != 'metadata_json':
        assert result['usage'] == {'fixture_tokens': 7}
        assert result['returned_model'] == 'constructed-model-not-provider'
    if kind == 'incomplete':
        assert read(tmp_path / 'out/response_metadata.json')['incomplete_details'] == {'reason': 'constructed_output_limit'}
    assert (tmp_path / 'out/manifest.json').exists()
    with pytest.raises(live.AttemptAlreadyReserved):
        dispatch(frozen, tmp_path / 'no-refund')


def test_http_json_error_preserves_observed_usage_but_never_accepts_valid_looking_reply(frozen, tmp_path, monkeypatch):
    raw = envelope(reply(wire(frozen)), error={'type': 'constructed-error', 'message': 'not a successful response'})

    def send(*args):
        headers = Message()
        headers['x-request-id'] = 'constructed-error-header'
        raise HTTPError('https://api.openai.com/v1/responses', 429, 'Constructed HTTP failure', headers, io.BytesIO(raw))

    monkeypatch.setattr(live, 'send_openai_request', send)
    dispatch(frozen, tmp_path / 'out')
    result = read(tmp_path / 'out/result.json')
    assert result['status'] == 'transport_error'
    assert result['errors'][0]['type'] == 'HTTPError'
    assert result['request_id'] == 'constructed-error-header'
    assert result['usage'] == {'fixture_tokens': 7}
    assert read(tmp_path / 'out/response_metadata.json')['provider_error']['type'] == 'constructed-error'
    assert result['outcome'] is None
    assert not (tmp_path / 'out/reply.json').exists()


def test_error_credentials_are_redacted_and_transformation_recorded(frozen, tmp_path, monkeypatch):
    raw = envelope(reply(wire(frozen)), error={'message': 'Constructed echoed credential: ' + KEY})
    mock_response(monkeypatch, raw)
    dispatch(frozen, tmp_path / 'out')
    result = read(tmp_path / 'out/result.json')
    assert result['status'] == 'response_invalid'
    assert result['credential_redaction_applied']
    assert result['observed_response_sha256'] == hashlib.sha256(raw).hexdigest()
    assert result['response_or_error_sha256'] != result['observed_response_sha256']
    assert any(error['stage'] == 'credential_redaction' for error in result['errors'])
    for path in (tmp_path / 'out').iterdir():
        assert KEY.encode() not in path.read_bytes()


def test_incomplete_http_read_retains_available_partial_bytes(frozen, tmp_path, monkeypatch):
    raw = b'\xffconstructed partial HTTP bytes'

    def send(*args):
        raise IncompleteRead(raw, 100)

    monkeypatch.setattr(live, 'send_openai_request', send)
    dispatch(frozen, tmp_path / 'out')
    result = read(tmp_path / 'out/result.json')
    assert result['status'] == 'transport_error'
    assert result['error']['type'] == 'IncompleteRead'
    assert result['response_sha256'] is None
    assert result['response_or_error_sha256'] == hashlib.sha256(raw).hexdigest()
    assert (tmp_path / 'out/response_or_error.bin').read_bytes() == raw


def test_raw_bytes_are_saved_and_synced_before_response_inspection(frozen, tmp_path, monkeypatch):
    raw = envelope(reply(wire(frozen)))
    mock_response(monkeypatch, raw)
    inspect = live.inspect_response
    syncs = []
    sync = live.os.fsync

    def synced(fd):
        sync(fd)
        syncs.append(fd)

    def inspect_saved(*args):
        assert (tmp_path / 'out/response_or_error.bin').read_bytes() == raw
        assert (tmp_path / 'out/transport.json').exists()
        assert len(syncs) >= 7  # request/contract/reservation/copy/raw/two receipts
        return inspect(*args)

    monkeypatch.setattr(live.os, 'fsync', synced)
    monkeypatch.setattr(live, 'inspect_response', inspect_saved)
    dispatch(frozen, tmp_path / 'out')
    assert read(tmp_path / 'out/result.json')['status'] == 'integrity_valid'


@pytest.mark.parametrize('changed', ['source', 'saved_response', 'saved_request'])
def test_post_transport_drift_is_recorded_without_acceptance_or_refund(frozen, tmp_path, monkeypatch, changed):
    raw = envelope(reply(wire(frozen)))
    inspect = live.inspect_response

    def inspect_then_change(*args):
        result = inspect(*args)
        path = {'source': frozen / 'request.json', 'saved_response': tmp_path / 'out/response_or_error.bin',
            'saved_request': tmp_path / 'out/request.json'}[changed]
        path.write_bytes(b'constructed drift')
        return result

    mock_response(monkeypatch, raw)
    monkeypatch.setattr(live, 'inspect_response', inspect_then_change)
    dispatch(frozen, tmp_path / 'out')
    result = read(tmp_path / 'out/result.json')
    assert result['status'] == 'artifact_integrity_error'
    assert result['outcome'] is result['evaluation'] is None
    assert not result['checks']['artifact_integrity_valid']
    assert any(error['stage'] == 'artifact_integrity' for error in result['errors'])
    assert not (tmp_path / 'out/resolved.json').exists()
    assert (live._ledger_root() / result['request_sha256']).is_dir()


@pytest.mark.parametrize('failed_file', ['response_metadata.json', 'result.json', 'manifest.json'])
def test_recording_storage_failure_propagates_without_completeness_marker_or_refund(frozen, tmp_path, monkeypatch, failed_file):
    mock_response(monkeypatch, envelope(reply(wire(frozen))))
    write = live._durable_bytes

    def fail_write(path, raw):
        if path == tmp_path / 'out' / failed_file:
            raise OSError('constructed result storage failure')
        write(path, raw)

    monkeypatch.setattr(live, '_durable_bytes', fail_write)
    with pytest.raises(OSError, match='constructed result storage failure'):
        dispatch(frozen, tmp_path / 'out')
    assert (tmp_path / 'out/response_or_error.bin').exists()
    assert not (tmp_path / 'out/manifest.json').exists()
    monkeypatch.setattr(live, '_durable_bytes', write)
    with pytest.raises(live.AttemptAlreadyReserved):
        dispatch(frozen, tmp_path / 'no-refund')
