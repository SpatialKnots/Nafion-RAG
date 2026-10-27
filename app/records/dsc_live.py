"""Explicit one-attempt DSC dispatch; importing this module never sends a request.

The checkout-wide reservation is append-only and deliberately survives failure.
Saved responses are checked with the unchanged frozen DSC response inspector.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from http.client import HTTPException, IncompleteRead
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from app.evaluation.dsc_experiment_run import CAPTURED, load
from app.generation.dsc_experiment import inspect_response, parse_reply, parse_unique_json, payload
from app.records.multi_run import verify_hashes
from app.records.openai_backend import responses_content, send_openai_request
from app.records.schema import SourceRegion
from app.records.sources import file_hash

VERSION = 'dsc_live_dispatch_v0.2'
RESULT_VERSION = 'dsc_live_result_v0.1'


class AttemptAlreadyReserved(RuntimeError):
    """The request's only slot is consumed, including incomplete reservations."""


def _ledger_root() -> Path:
    # Never derive the ledger from cwd, the output directory, or a caller option.
    return Path(__file__).resolve().parents[2] / 'data/experiments/dsc_live_attempts'


def _durable_bytes(path: Path, raw: bytes) -> None:
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _reserve(request_sha256: str, attempt: dict[str, Any]) -> Path:
    if len(request_sha256) != 64 or any(c not in '0123456789abcdef' for c in request_sha256):
        raise ValueError('DSC reservation requires a lowercase SHA256 request identity')
    root = _ledger_root()
    root.mkdir(parents=True, exist_ok=True)
    reservation = root / request_sha256
    try:
        reservation.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise AttemptAlreadyReserved(
            f'DSC request attempt already reserved; no retry or refund: {reservation}'
        ) from exc
    # Atomic mkdir selects one process. Even an empty/partial directory blocks
    # subsequent attempts. Never clean up a failed reservation.
    _durable_bytes(reservation / 'attempt.json', payload(attempt))
    return reservation


def _redact(raw: bytes, api_key: str) -> bytes:
    for secret in (api_key, api_key.strip()):
        if secret:
            raw = raw.replace(secret.encode('utf-8'), b'[REDACTED]')
    return raw


def _record_result(
    output: Path, reservation: Path, *, wire: dict[str, Any], sources: list[SourceRegion],
    attempt: dict[str, Any], receipt: dict[str, Any], api_key: str,
) -> dict[str, Any]:
    """Record a dispatch's saved bytes locally; no sender or budget reset here."""
    started = time.perf_counter()
    raw = (output / 'response_or_error.bin').read_bytes()
    errors: list[dict[str, Any]] = []
    if receipt['error'] is not None:
        errors.append(dict(receipt['error']))

    def failure(stage: str, exc: Exception) -> None:
        errors.append({'stage': stage, 'type': type(exc).__name__,
            'message': _redact(str(exc).encode('utf-8'), api_key).decode('utf-8')})

    metadata: dict[str, Any] = {'request_id': receipt['request_id'], 'response_id': None,
        'returned_model': None, 'usage': None, 'service_tier': None, 'response_status': None,
        'provider_error': None, 'incomplete_details': None, 'metadata_json_valid': False,
        'provenance': 'observed_envelope_fields_not_model_identity_or_billing_verification'}
    reply: dict[str, Any] | None = None
    inspected: dict[str, Any] | None = None
    schema_valid = False
    source_valid: bool | None = None
    status = 'transport_error' if receipt['error'] is not None else 'response_invalid'
    stage = 'metadata_json'
    try:
        envelope = parse_unique_json(raw)
        if not isinstance(envelope, dict):
            raise ValueError('DSC response envelope must be a JSON object')
        # Keep the frozen parser unchanged while rejecting non-JSON numeric
        # constants in newly recorded provider metadata (NaN/Infinity).
        json.dumps(envelope, allow_nan=False)
        metadata.update({target: envelope.get(name) for target, name in (
            ('response_id', 'id'), ('returned_model', 'model'), ('usage', 'usage'),
            ('service_tier', 'service_tier'), ('response_status', 'status'),
            ('provider_error', 'error'), ('incomplete_details', 'incomplete_details'))})
        metadata['metadata_json_valid'] = True
        # A JSON HTTP error body can contribute observed metadata, never success.
        if receipt['error'] is None:
            stage = 'completion_contract'
            content = responses_content(raw)
            stage = 'reply_schema'
            reply = parse_reply(content).model_dump(mode='json')
            schema_valid = True
            stage = 'source_integrity'
            source_valid = False
            inspected = inspect_response(raw, wire, sources)
            source_valid = True
            status = 'integrity_valid'
    except ValueError as exc:
        failure(stage, exc)
    # Missing usage/model remains unknown even for otherwise valid replies.
    metadata['missing_observed_fields'] = [name for name in
        ('request_id', 'response_id', 'returned_model', 'usage', 'service_tier') if metadata[name] is None]
    artifact_integrity_valid = True
    try:
        if (hashlib.sha256(raw).hexdigest() != receipt['response_or_error_sha256']
                or file_hash(output / 'response_or_error.bin') != receipt['response_or_error_sha256']):
            raise ValueError('Saved DSC response/error bytes differ from transport receipt')
        for name, expected in (('request.json', attempt['request_sha256']),
                ('contract.json', attempt['contract_sha256'])):
            if file_hash(output / name) != expected:
                raise ValueError('Saved DSC request/contract differs from reserved attempt: ' + name)
        for path, expected in ((output / 'attempt.json', attempt), (reservation / 'attempt.json', attempt),
                (output / 'transport.json', receipt), (reservation / 'transport.json', receipt)):
            if path.read_bytes() != payload(expected):
                raise ValueError('Saved DSC attempt/transport receipt changed: ' + str(path))
        verify_hashes(attempt['inputs'] | attempt['executor_code'])
    except (ValueError, OSError) as exc:
        artifact_integrity_valid = False
        status = 'artifact_integrity_error'
        failure('artifact_integrity', exc)
    if receipt['credential_redaction_applied']:
        # Redacted provider bytes can be inspected, but cannot be accepted as
        # exact source-valid model evidence after a storage transformation.
        if artifact_integrity_valid:
            status = 'transport_error' if receipt['error'] is not None else 'response_invalid'
        failure('credential_redaction', ValueError('Credential redaction changed stored provider bytes'))
    _durable_bytes(output / 'response_metadata.json', payload(metadata))
    if reply is not None:
        _durable_bytes(output / 'reply.json', payload(reply))
    if inspected is not None and artifact_integrity_valid and not receipt['credential_redaction_applied']:
        _durable_bytes(output / 'resolved.json', payload({'fields': inspected['resolved']}))
    result: dict[str, Any] = {
        'version': RESULT_VERSION, 'origin': 'single_attempt_dispatch', 'status': status,
        'request_sha256': attempt['request_sha256'], 'contract_sha256': attempt['contract_sha256'],
        'transport_attempts': 1, 'automatic_retries': 0, 'model_fallbacks': 0,
        'delivery_status': receipt['delivery_status'], 'request_id': metadata['request_id'],
        'response_id': metadata['response_id'], 'returned_model': metadata['returned_model'],
        'usage': metadata['usage'], 'service_tier': metadata['service_tier'],
        'response_status': metadata['response_status'], 'elapsed_seconds': receipt['elapsed_seconds'],
        'elapsed_seconds_scope': 'transport_only', 'recording_elapsed_seconds': time.perf_counter() - started,
        'completed_at_utc': datetime.now(UTC).isoformat(),
        'response_or_error_sha256': hashlib.sha256(raw).hexdigest(),
        'response_sha256': hashlib.sha256(raw).hexdigest() if receipt['error'] is None else None,
        'observed_response_sha256': receipt['observed_response_sha256'],
        'credential_redaction_applied': receipt['credential_redaction_applied'],
        'checks': {'metadata_json_valid': metadata['metadata_json_valid'], 'reply_schema_valid': schema_valid,
            'source_integrity_valid': source_valid, 'artifact_integrity_valid': artifact_integrity_valid},
        'evaluation': inspected['evaluation'] if status == 'integrity_valid' and inspected is not None else None,
        'outcome': inspected['evaluation']['outcome'] if status == 'integrity_valid' and inspected is not None else None,
        'error': errors[0] if errors else None, 'errors': errors,
        'actual_cost_usd': None, 'scientific_acceptance': 'not_evaluated',
    }
    _durable_bytes(output / 'result.json', payload(result))
    manifest = {'version': RESULT_VERSION, 'phase': 'recorded_single_dispatch_result',
        'status': status, 'inputs': attempt['inputs'], 'code': attempt['executor_code'],
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}}
    # No manifest yet means an incomplete recording. Mirror the result and its
    # hashes before writing the final output completeness marker.
    _durable_bytes(reservation / 'result.json', payload(result))
    _durable_bytes(reservation / 'result_manifest.json', payload(manifest))
    _durable_bytes(output / 'manifest.json', payload(manifest))
    return result


def dispatch_frozen(
    source: Path, output: Path, *, api_key: str, api_calls_authorized: bool = False,
) -> dict[str, Any]:
    """Dispatch once only after a caller explicitly attests current API permission.

    This flag is not permission inferred from source eligibility or stage49's
    historical execution flags. The current user prohibition is still in force
    until explicitly lifted. No CLI or production route invokes this function.
    Return the immutable transport receipt; full interpretation is in result.json.
    """
    if api_calls_authorized is not True:
        raise PermissionError('DSC dispatch requires explicit current user API authorization')
    if not api_key.strip():
        raise ValueError('DSC dispatch requires a nonempty API credential')
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError(output)
    if output.is_relative_to(source):
        raise ValueError('DSC dispatch output must be outside the frozen experiment')
    _, wire, sources, frozen, bindings = load(source, CAPTURED)
    raw = (source / 'request.json').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != frozen['request_sha256']:
        raise ValueError('DSC request bytes changed after frozen validation')
    if (frozen['budget']['maximum_transport_attempts'] != 1
            or frozen['budget']['automatic_retries'] != 0 or frozen['budget']['model_fallbacks'] != 0):
        raise ValueError('DSC live dispatch requires the frozen one-attempt budget')
    code = {str(Path(__file__).resolve()): file_hash(Path(__file__))}
    verify_hashes(bindings | code)
    attempt = {
        'version': VERSION, 'request_sha256': digest,
        'contract_sha256': hashlib.sha256((source / 'contract.json').read_bytes()).hexdigest(),
        'reserved_at_utc': datetime.now(UTC).isoformat(), 'output': str(output),
        'source': str(source), 'endpoint': frozen['endpoint'], 'model_alias': frozen['model_alias'],
        'budget': frozen['budget'], 'transport_attempts_reserved': 1,
        'delivery_status': 'unknown_until_transport_receipt',
        'authorization': 'caller_attested_explicit_current_user_permission',
        'inputs': bindings, 'executor_code': code,
    }
    # Local preparation errors before reservation do not consume a slot. After
    # mkdir succeeds all failures, including process interruption, consume it.
    output.mkdir(parents=True, exist_ok=False)
    _durable_bytes(output / 'request.json', raw)
    _durable_bytes(output / 'contract.json', (source / 'contract.json').read_bytes())
    reservation = _reserve(digest, attempt)
    _durable_bytes(output / 'attempt.json', payload(attempt))
    started = time.perf_counter()
    request_id: str | None = None
    error: dict[str, Any] | None = None
    status = 'response_received_unvalidated'
    try:
        response, request_id = send_openai_request(raw, api_key, frozen['budget']['timeout_seconds'])
    except HTTPError as exc:
        status = 'transport_error'
        error = {'type': type(exc).__name__, 'stage': 'http', 'http_status': exc.code,
            'message': _redact(str(exc).encode('utf-8'), api_key).decode('utf-8')}
        request_id = exc.headers.get('x-request-id') if exc.headers else None
        try:
            response = exc.read()
        except (OSError, HTTPException) as read_error:
            error['body_read_error_type'] = type(read_error).__name__
            response = read_error.partial if isinstance(read_error, IncompleteRead) else str(read_error).encode('utf-8')
    except (URLError, OSError, HTTPException) as exc:
        status = 'transport_error'
        response = exc.partial if isinstance(exc, IncompleteRead) else str(exc).encode('utf-8')
        error = {'type': type(exc).__name__, 'stage': 'transport',
            'message': _redact(str(exc).encode('utf-8'), api_key).decode('utf-8')}
    elapsed = time.perf_counter() - started
    observed_digest = hashlib.sha256(response).hexdigest()
    stored_response = _redact(response, api_key)
    redacted = stored_response != response
    # Save bytes before any parsing. Storage failures propagate and cannot refund
    # the slot. Unexpected exceptions/interruption also leave it reserved.
    _durable_bytes(output / 'response_or_error.bin', stored_response)
    receipt = {
        'version': VERSION, 'status': status, 'request_sha256': digest,
        'transport_attempts': 1, 'automatic_retries': 0, 'model_fallbacks': 0,
        'request_id': request_id, 'elapsed_seconds': elapsed,
        'delivery_status': 'response_received' if error is None else 'unknown_or_rejected',
        'error': error, 'response_or_error_sha256': hashlib.sha256(stored_response).hexdigest(),
        'observed_response_sha256': observed_digest, 'credential_redaction_applied': redacted,
        'stored_bytes_policy': 'exact_unless_literal_credential_redaction',
        'returned_model': None, 'usage': None, 'actual_cost_usd': None,
        'response_interpretation': 'not_performed', 'scientific_acceptance': 'not_evaluated',
    }
    _durable_bytes(output / 'transport.json', payload(receipt))
    _durable_bytes(reservation / 'transport.json', payload(receipt))
    _record_result(output, reservation, wire=wire, sources=sources, attempt=attempt, receipt=receipt, api_key=api_key)
    return receipt
