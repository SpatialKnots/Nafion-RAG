"""Constructed dispatch and filesystem failures; no real API calls or credentials."""

import hashlib
import io
import json
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from pathlib import Path
from threading import Barrier
from urllib.error import HTTPError, URLError

import pytest

from app.evaluation import dsc_experiment_run as runner
from app.records import dsc_live as live
from tests.unit.test_dsc_experiment import admission as admission  # noqa: F401

KEY = 'constructed-test-credential-not-real'


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail('Real network/transport forbidden in DSC executor tests')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(live, 'send_openai_request', forbidden)
    monkeypatch.setattr(live, '_ledger_root', lambda: tmp_path / 'shared-ledger')


@pytest.fixture
def frozen(admission, tmp_path):
    runner.prepare(admission, tmp_path / 'prepared')
    runner.execute(tmp_path / 'prepared', tmp_path / 'frozen')
    return tmp_path / 'frozen'


def read(path):
    return json.loads(path.read_bytes())


def digest(source):
    return hashlib.sha256((source / 'request.json').read_bytes()).hexdigest()


def dispatch(source, output):
    return live.dispatch_frozen(source, output, api_key=KEY, api_calls_authorized=True)


@pytest.mark.parametrize('authorization', [False, None, 'yes', 1])
def test_no_permission_fails_before_validation_or_any_reservation(tmp_path, authorization):
    with pytest.raises(PermissionError, match='explicit current user API authorization'):
        live.dispatch_frozen(tmp_path / 'absent', tmp_path / 'out', api_key=KEY,
            api_calls_authorized=authorization)
    assert not live._ledger_root().exists()
    assert not (tmp_path / 'out').exists()


def test_blank_credential_cannot_consume_attempt(tmp_path):
    with pytest.raises(ValueError, match='nonempty API credential'):
        live.dispatch_frozen(tmp_path / 'absent', tmp_path / 'out', api_key=' ', api_calls_authorized=True)
    assert not live._ledger_root().exists()


def test_dispatch_reserves_and_syncs_before_exact_transport_then_blocks_copied_output(frozen, tmp_path, monkeypatch):
    raw = (frozen / 'request.json').read_bytes()
    response = b'\xffconstructed raw response, intentionally not JSON'
    syncs, calls = [], []
    original_sync = live.os.fsync

    def sync(fd):
        original_sync(fd)
        syncs.append(fd)

    monkeypatch.setattr(live.os, 'fsync', sync)

    def send(body, key, timeout):
        calls.append(body)
        assert body == raw and key == KEY and timeout == 180
        attempt = read(live._ledger_root() / digest(frozen) / 'attempt.json')
        assert attempt['request_sha256'] == digest(frozen)
        assert attempt['transport_attempts_reserved'] == 1
        assert (tmp_path / 'out/attempt.json').read_bytes() == live.payload(attempt)
        assert len(syncs) >= 3
        return response, 'constructed-request-id'

    monkeypatch.setattr(live, 'send_openai_request', send)
    result = dispatch(frozen, tmp_path / 'out')
    assert result['status'] == 'response_received_unvalidated'
    assert result['usage'] is None and result['returned_model'] is None
    assert result['scientific_acceptance'] == 'not_evaluated'
    assert result['request_id'] == 'constructed-request-id'
    assert (tmp_path / 'out/response_or_error.bin').read_bytes() == response
    assert read(live._ledger_root() / digest(frozen) / 'transport.json') == result
    assert KEY not in (tmp_path / 'out/attempt.json').read_text('utf-8')
    # Existing offline export reconstructs the same request in a different folder.
    runner.execute(frozen, tmp_path / 'copy', export=True)
    with pytest.raises(live.AttemptAlreadyReserved):
        dispatch(tmp_path / 'copy', tmp_path / 'copy-output')
    assert calls == [raw]


@pytest.mark.parametrize('failure', ['timeout', 'url', 'http'])
def test_transport_failures_keep_slot_without_retries_and_redact_error(frozen, tmp_path, monkeypatch, failure):
    calls = []

    def send(*args):
        calls.append(args)
        if failure == 'http':
            headers = Message()
            headers['x-request-id'] = 'constructed-error-request'
            raise HTTPError('https://api.openai.com/v1/responses', 400, 'fixture ' + KEY, headers,
                io.BytesIO(b'\xffHTTP fixture ' + KEY.encode()))
        if failure == 'url':
            raise URLError('fixture ' + KEY)
        raise TimeoutError('fixture ' + KEY)

    monkeypatch.setattr(live, 'send_openai_request', send)
    result = dispatch(frozen, tmp_path / 'out')
    assert result['status'] == 'transport_error'
    assert result['error']['type'] == {'http': 'HTTPError', 'url': 'URLError', 'timeout': 'TimeoutError'}[failure]
    assert result['delivery_status'] == 'unknown_or_rejected'
    assert result['usage'] is None
    assert KEY not in json.dumps(result)
    assert KEY.encode() not in (tmp_path / 'out/response_or_error.bin').read_bytes()
    if failure == 'http':
        assert (tmp_path / 'out/response_or_error.bin').read_bytes().startswith(b'\xffHTTP fixture ')
        assert result['request_id'] == 'constructed-error-request'
    with pytest.raises(live.AttemptAlreadyReserved):
        dispatch(frozen, tmp_path / 'another-out')
    assert len(calls) == 1


def test_thread_competition_dispatches_only_one_request(frozen, tmp_path, monkeypatch):
    barrier = Barrier(4)
    reserve = live._reserve
    calls = []

    def racing_reserve(*args):
        barrier.wait(timeout=20)
        return reserve(*args)

    def send(*args):
        calls.append(args)
        return b'constructed', None

    monkeypatch.setattr(live, '_reserve', racing_reserve)
    monkeypatch.setattr(live, 'send_openai_request', send)

    def worker(index):
        try:
            return dispatch(frozen, tmp_path / f'out-{index}')['status']
        except live.AttemptAlreadyReserved:
            return 'blocked'

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(worker, range(4)))
    assert sorted(outcomes) == ['blocked'] * 3 + ['response_received_unvalidated']
    assert len(calls) == 1


def test_process_competition_and_restart_cannot_reclaim_slot(tmp_path):
    # Independent interpreters share only the filesystem; no Python lock helps.
    script = (
        'import sys\nfrom pathlib import Path\n'
        'def guard(event,args):\n'
        '    if event in ("socket.connect","socket.getaddrinfo","socket.sendto"): raise RuntimeError("network forbidden")\n'
        'sys.addaudithook(guard)\n'
        'from app.records import dsc_live as live\n'
        'live._ledger_root = lambda: Path(sys.argv[1])\n'
        'try: live._reserve(sys.argv[2], {"constructed": True})\n'
        'except live.AttemptAlreadyReserved: sys.exit(23)\n'
    )
    args = [sys.executable, '-c', script, str(tmp_path / 'process-ledger'), 'a' * 64]
    workers = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
    results = []
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=40)
        results.append(worker.returncode)
        assert worker.returncode in (0, 23), (stdout, stderr)
    assert sorted(results) == [0, 23, 23, 23]
    restarted = subprocess.run(args, capture_output=True, timeout=40, check=False)
    assert restarted.returncode == 23, restarted.stderr


@pytest.mark.parametrize('failure_stage', ['reserve_write', 'before_transport', 'after_response'])
def test_crash_or_storage_error_after_reservation_never_refunds_slot(frozen, tmp_path, monkeypatch, failure_stage):
    write = live._durable_bytes
    calls = []

    def fail_write(path, raw):
        if (failure_stage == 'reserve_write' and path.parent.parent == live._ledger_root()
                or failure_stage == 'before_transport' and path == tmp_path / 'out/attempt.json'
                or failure_stage == 'after_response' and path == tmp_path / 'out/response_or_error.bin'):
            raise OSError('constructed disk failure')
        write(path, raw)

    def send(*args):
        calls.append(args)
        return b'constructed', None

    monkeypatch.setattr(live, '_durable_bytes', fail_write)
    monkeypatch.setattr(live, 'send_openai_request', send)
    with pytest.raises(OSError, match='constructed disk failure'):
        dispatch(frozen, tmp_path / 'out')
    assert (live._ledger_root() / digest(frozen)).is_dir()
    monkeypatch.setattr(live, '_durable_bytes', write)
    with pytest.raises(live.AttemptAlreadyReserved):
        dispatch(frozen, tmp_path / 'new-output')
    assert len(calls) == (1 if failure_stage == 'after_response' else 0)


def test_unexpected_interruption_propagates_but_consumes_slot(frozen, tmp_path, monkeypatch):
    def send(*args):
        raise KeyboardInterrupt('constructed interruption')

    monkeypatch.setattr(live, 'send_openai_request', send)
    with pytest.raises(KeyboardInterrupt):
        dispatch(frozen, tmp_path / 'out')
    assert not (tmp_path / 'out/transport.json').exists()
    with pytest.raises(live.AttemptAlreadyReserved):
        dispatch(frozen, tmp_path / 'new-output')


def test_validation_failure_cannot_consume_slot(frozen, tmp_path):
    (frozen / 'request.json').write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        dispatch(frozen, tmp_path / 'out')
    assert not live._ledger_root().exists()
    assert not (tmp_path / 'out').exists()


def test_output_protection_and_partial_reservation_fail_closed(frozen, tmp_path):
    with pytest.raises(ValueError, match='outside the frozen'):
        dispatch(frozen, frozen / 'nested')
    with pytest.raises(FileExistsError):
        dispatch(frozen, frozen)
    reservation = live._ledger_root() / digest(frozen)
    reservation.mkdir(parents=True)
    (reservation / 'attempt.json').write_bytes(b'{partial')
    with pytest.raises(live.AttemptAlreadyReserved):
        dispatch(frozen, tmp_path / 'out')


def test_ledger_location_is_anchored_to_code_not_cwd(tmp_path, monkeypatch):
    monkeypatch.undo()
    expected = Path(live.__file__).resolve().parents[2] / 'data/experiments/dsc_live_attempts'
    monkeypatch.chdir(tmp_path)
    assert live._ledger_root() == expected
