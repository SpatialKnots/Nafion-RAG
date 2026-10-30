"""Explicit bounded GigaChat experiment; imports and preparation never use the network."""

from __future__ import annotations

import hashlib
import json
import shutil
import ssl
import time
from datetime import UTC, datetime
from email.message import Message
from html import escape
from http.client import HTTPException, IncompleteRead
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

from app.evaluation.dsc_experiment_run import CAPTURED, admitted, load
from app.generation.dsc_experiment import Reply, guard_request, inspect_response, parse_unique_json, payload
from app.records.dsc_live import _durable_bytes
from app.records.multi_run import verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash

VERSION = 'gigachat_dsc_smoke_v0.1'
AUTH = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
BASE = 'https://api.giga.chat/v1'
MODEL = 'GigaChat-2-Max'
SCOPE = 'GIGACHAT_API_PERS'
CODE = ('app/records/gigachat_dsc.py', 'scripts/gigachat_dsc.py',
    'docs/records/gigachat_dsc_protocol_v0.1.md', 'tests/unit/test_gigachat_dsc.py')


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw: bytes) -> dict[str, Any]:
    value = parse_unique_json(raw)
    if not isinstance(value, dict):
        raise ValueError('GigaChat JSON envelope must be an object')
    json.dumps(value, allow_nan=False)
    return value


def redact(raw: bytes, secrets: list[str]) -> bytes:
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            raw = raw.replace(secret.encode('utf-8'), b'[REDACTED]')
    return raw


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        raise HTTPError(req.full_url, code, 'GigaChat redirects are forbidden', Message(), None)


def http(url: str, body: bytes | None, authorization: str, context: ssl.SSLContext) -> tuple[bytes, str | None]:
    if url not in (AUTH, BASE + '/models', BASE + '/balance', BASE + '/chat/completions'):
        raise ValueError('Unregistered GigaChat endpoint')
    headers = {'Authorization': authorization, 'Accept': 'application/json', 'User-Agent': 'ARIADNE-DSC-smoke/0.1'}
    if body is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if url == AUTH else 'application/json'
    if url == AUTH:
        headers['RqUID'] = str(uuid4())
    request = Request(url, data=body, headers=headers, method='GET' if body is None else 'POST')
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=context))
    with opener.open(request, timeout=180 if url.endswith('/chat/completions') else 30) as response:
        return bytes(response.read()), response.headers.get('x-request-id')


def request_from_parent(source: Path) -> tuple[dict[str, Any], dict[str, Any], list[SourceRegion], dict[str, str]]:
    _, wire, sources, _, bindings = load(source, CAPTURED)
    source_plan, _, _, _ = admitted(Path(strict_json((source / 'plan.json').read_bytes())['parent']))
    original = strict_json((source / 'request.json').read_bytes())
    # Run the historical source/byte/full-page guards on an envelope containing
    # the GigaChat schema as well. No scientific source text or reply rule changes.
    request = {'model': MODEL, 'messages': original['input'], 'max_tokens': 4096, 'stream': False,
        'response_format': {'type': 'json_schema', 'schema': Reply.model_json_schema(), 'strict': True}}
    raw = payload(request)
    guard_request(payload(original), wire, sources, source_plan)
    from app.evaluation.context_compaction import SourcePage, require_no_complete_pages
    from app.evaluation.query_packet import MAX_BYTES

    if len(raw) > MAX_BYTES:
        raise ValueError('GigaChat envelope exceeds the existing byte ceiling; no clipping')
    pages = [SourcePage(p['article_id'], p['page_ref'], p['page_number'], p['text_layer'], p['text_layer_id'],
        p['text'], p['layer_pdf_path'], p['layer_pdf_sha256']) for p in source_plan['pages']]
    require_no_complete_pages(raw.decode('utf-8'), pages)
    return request, wire, sources, bindings


def prepare(source: Path, output: Path) -> dict[str, Any]:
    source, output = source.resolve(), output.resolve()
    if output.is_relative_to(source):
        raise ValueError('GigaChat output must be outside historical artifacts')
    request, _, _, bindings = request_from_parent(source)
    code = {str(Path(p).resolve()): file_hash(Path(p)) for p in CODE}
    contract = {'version': VERSION, 'parent': str(source), 'provider': 'gigachat', 'endpoint': BASE + '/chat/completions',
        'model_alias': MODEL, 'scope': SCOPE, 'request_sha256': digest(payload(request)), 'request_bytes': len(payload(request)),
        'maximum_model_attempts': 1, 'automatic_retries': 0, 'fallbacks': 0, 'timeout_seconds': 180,
        'max_output_tokens': 4096, 'sampling': 'provider_default_not_equated_to_OpenAI_reasoning',
        'response_schema': 'unchanged_DSC_Reply', 'scientific_acceptance': 'not_evaluated',
        'authorization': 'user_requested_GigaChat_test_in_current_chat; OpenAI_permission_unchanged',
        'pricing': 'personal_token_package_required; balance_is_not_independent_price_verification',
        'inputs': bindings, 'code': code}
    output.mkdir(parents=True, exist_ok=False)
    _durable_bytes(output / 'request.json', payload(request))
    _durable_bytes(output / 'contract.json', payload(contract))
    shutil.copytree(source, output / 'parent_snapshot')
    manifest(output, 'prepared')
    return {'status': 'prepared', 'model_calls': 0, 'request_bytes': contract['request_bytes'], 'model': MODEL}


def manifest(output: Path, phase: str) -> None:
    _durable_bytes(output / 'manifest.json', payload({'version': VERSION, 'phase': phase,
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*'))
            if p.is_file() and p != output / 'manifest.json'}}))


def read_prepared(source: Path) -> tuple[dict[str, Any], dict[str, Any], list[SourceRegion]]:
    stored = strict_json((source / 'manifest.json').read_bytes())
    if stored['version'] != VERSION or stored['phase'] != 'prepared':
        raise ValueError('Expected a prepared GigaChat experiment')
    actual = {p.relative_to(source).as_posix(): file_hash(p) for p in source.rglob('*')
        if p.is_file() and p != source / 'manifest.json'}
    if actual != stored['outputs']:
        raise ValueError('Prepared GigaChat artifact changed')
    frozen = strict_json((source / 'contract.json').read_bytes())
    verify_hashes(frozen['inputs'] | frozen['code'])
    request, wire, sources, _ = request_from_parent(Path(frozen['parent']))
    raw = (source / 'request.json').read_bytes()
    if raw != payload(request) or digest(raw) != frozen['request_sha256']:
        raise ValueError('GigaChat request differs from reconstructed frozen input')
    return frozen, wire, sources


def inspect(raw: bytes, wire: dict[str, Any], sources: list[SourceRegion]) -> dict[str, Any]:
    observed = strict_json(raw)
    choices = observed.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError('GigaChat requires exactly one response choice')
    choice = choices[0]
    message = choice.get('message')
    if (choice.get('finish_reason') != 'stop' or not isinstance(message, dict)
            or message.get('role') != 'assistant' or not isinstance(message.get('content'), str)
            or message.get('function_call') is not None or observed.get('error') is not None):
        raise ValueError('GigaChat response is incomplete, refused or not plain assistant content')
    # This is an explicitly derived local adapter envelope, never the provider's
    # raw response. It reuses the frozen exact-quote validator without editing it.
    bridge = {'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
        'content': [{'type': 'output_text', 'text': message['content']}]}]}
    checked = inspect_response(payload(bridge), wire, sources)
    return {'reply': checked['reply'], 'resolved': checked['resolved'], 'evaluation': checked['evaluation'],
        'adapter_provenance': 'GigaChat_stop_choice_to_local_DSC_validator; raw_response_unchanged'}


def ledger_root() -> Path:
    return Path(__file__).resolve().parents[2] / 'data/experiments/gigachat_dsc_attempts'


def render(result: dict[str, Any], prepared: Path) -> str:
    def detail(value: Any) -> str:
        return '<pre>' + escape(json.dumps(value, ensure_ascii=False, indent=2)) + '</pre>'

    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — GigaChat DSC</title>'
        '<style>body{font:16px system-ui;margin:24px;max-width:1100px}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'input{padding:8px;width:50%}[hidden]{display:none!important}</style><h1>GigaChat: DSC experiment</h1>'
        '<p>Предложения модели; научная корректность независимо не оценена.</p><p><a href="'
        + escape((prepared / 'parent_snapshot/admission/packet/metadata_review.html').as_uri(), quote=True)
        + '">Полная историческая TAC-таблица и PDF</a> · <a href="response_or_error.bin">Raw response/error</a>'
        ' · <a href="request.json">Request</a> · <a href="result.json">Result</a></p>'
        '<label>Поиск <input id="q" type="search"></label><section>' + detail(result) + '</section>'
        '<script>document.getElementById("q").addEventListener("input",e=>{document.querySelector("section").hidden='
        '!document.querySelector("section").textContent.toLocaleLowerCase().includes(e.target.value.toLocaleLowerCase())})'
        '</script></html>\n')


def dispatch(prepared: Path, output: Path, *, credentials: str, scope: str, authorized: bool = False,
        ca_bundle: Path | None = None) -> dict[str, Any]:
    if authorized is not True:
        raise PermissionError('Explicit user authorization required for GigaChat test')
    credentials = credentials.strip().removeprefix('Basic ').strip()
    if not credentials or '\n' in credentials or '\r' in credentials or scope != SCOPE:
        raise ValueError('GigaChat authorization key and personal Scope required')
    prepared, output = prepared.resolve(), output.resolve()
    frozen, wire, sources = read_prepared(prepared)
    if output.is_relative_to(prepared) or output.is_relative_to(Path(frozen['parent'])):
        raise ValueError('Live output must be outside frozen experiments')
    context = ssl.create_default_context()
    if ca_bundle:
        context.load_verify_locations(cafile=str(ca_bundle))
    raw_request = (prepared / 'request.json').read_bytes()
    slot = ledger_root() / frozen['request_sha256']
    if slot.exists():
        raise FileExistsError('GigaChat model attempt already reserved; no retry or refund')
    output.mkdir(parents=True, exist_ok=False)
    for name in ('request.json', 'contract.json'):
        _durable_bytes(output / name, (prepared / name).read_bytes())
    secrets = [credentials]
    result: dict[str, Any] = {'version': VERSION, 'status': 'not_executed', 'model_attempts': 0,
        'oauth_attempts': 0, 'account_read_attempts': 0, 'automatic_retries': 0, 'fallbacks': 0,
        'request_sha256': frozen['request_sha256'], 'returned_model': None, 'usage': None, 'request_id': None,
        'response_id': None, 'actual_cost': None, 'scientific_acceptance': 'not_evaluated', 'evaluation': None,
        'prepared': str(prepared), 'errors': [], 'tls_verification': True, 'scope': scope}
    started, stage, reservation = time.perf_counter(), 'oauth', None
    raw = b''
    try:
        result['oauth_attempts'] = 1
        auth, _ = http(AUTH, ('scope=' + scope).encode('ascii'), 'Basic ' + credentials, context)
        auth_value = strict_json(auth)
        token = auth_value.get('access_token')
        if not isinstance(token, str) or not token.strip() or '\n' in token or '\r' in token:
            raise ValueError('GigaChat OAuth response lacks a valid access token')
        secrets.append(token)
        result['oauth_expires_at'] = auth_value.get('expires_at')
        for name in ('models', 'balance'):
            stage = name
            result['account_read_attempts'] += 1
            body, _ = http(BASE + '/' + name, None, 'Bearer ' + token, context)
            _durable_bytes(output / (name + '.json'), redact(body, secrets))
        models = strict_json((output / 'models.json').read_bytes())
        balance = strict_json((output / 'balance.json').read_bytes())
        available = [v.get('id') for v in models.get('data', []) if isinstance(v, dict)]
        if MODEL not in available:
            raise ValueError('Frozen GigaChat-2-Max model is unavailable; no fallback')
        entries = balance.get('balance', [])
        matching = [v for v in entries if isinstance(v, dict) and v.get('usage') in ('GigaChat-Max', MODEL)]
        if not any(type(v.get('value')) is int and v['value'] > 0 for v in matching):
            raise ValueError('Positive Max token-package balance not established; generation blocked')
        result['balance_before'] = matching
        result['billing_status'] = 'personal_package_balance_observed_not_independent_price_verification'
        stage = 'reservation'
        read_prepared(prepared)
        attempt = {'version': VERSION, 'request_sha256': frozen['request_sha256'],
            'contract_sha256': digest((prepared / 'contract.json').read_bytes()),
            'reserved_at_utc': datetime.now(UTC).isoformat(), 'output': str(output), 'model_alias': MODEL,
            'authorization': 'explicit_user_GigaChat_test', 'maximum_model_attempts': 1,
            'automatic_retries': 0, 'fallbacks': 0}
        slot.parent.mkdir(parents=True, exist_ok=True)
        slot.mkdir(exist_ok=False)
        reservation = slot
        _durable_bytes(slot / 'attempt.json', payload(attempt))
        _durable_bytes(output / 'attempt.json', payload(attempt))
        stage = 'generation'
        result['model_attempts'] = 1
        model_started = time.perf_counter()
        raw, result['request_id'] = http(BASE + '/chat/completions', raw_request, 'Bearer ' + token, context)
        result['model_elapsed_seconds'] = time.perf_counter() - model_started
        result['observed_response_sha256'] = digest(raw)
        stored = redact(raw, secrets)
        _durable_bytes(output / 'response_or_error.bin', stored)
        stage = 'response_metadata'
        observed = strict_json(stored)
        result.update(returned_model=observed.get('model'), usage=observed.get('usage'), response_id=observed.get('id'))
        if stored != raw:
            raise ValueError('Credential redaction changed response; integrity acceptance blocked')
        stage = 'reply_source_integrity'
        checked = inspect(stored, wire, sources)
        stage = 'postflight'
        read_prepared(prepared)
        if (output / 'request.json').read_bytes() != raw_request or (output / 'response_or_error.bin').read_bytes() != stored:
            raise ValueError('Saved request/response changed during dispatch')
        result.update(checked)
        result['status'] = 'integrity_valid'
    except (HTTPError, URLError, OSError, HTTPException, ValueError) as exc:
        # Expected failures remain typed, staged and visible. Storage errors in
        # recording below propagate; no rollback/refund of an existing slot.
        result['status'] = 'response_invalid' if stage in ('response_metadata', 'reply_source_integrity') else 'failed'
        error: dict[str, Any] = {'stage': stage, 'type': type(exc).__name__,
            'message': redact(str(exc).encode('utf-8'), secrets).decode('utf-8')}
        if isinstance(exc, HTTPError):
            error['http_status'] = exc.code
            result['request_id'] = exc.headers.get('x-request-id') if exc.headers else None
            if stage != 'oauth':
                try:
                    raw = exc.read()
                except (OSError, HTTPException) as read_error:
                    error['body_read_error_type'] = type(read_error).__name__
                    raw = read_error.partial if isinstance(read_error, IncompleteRead) else b''
        elif isinstance(exc, IncompleteRead):
            raw = exc.partial
        result['errors'].append(error)
        if not (output / 'response_or_error.bin').exists():
            _durable_bytes(output / 'response_or_error.bin', redact(raw if stage != 'oauth' else b'', secrets))
    result['elapsed_seconds'] = time.perf_counter() - started
    result['credential_redaction_applied'] = stage != 'oauth' and redact(raw, secrets) != raw
    result['observed_response_sha256'] = digest(raw) if stage != 'oauth' and raw else None
    result['stored_response_sha256'] = file_hash(output / 'response_or_error.bin')
    result['completed_at_utc'] = datetime.now(UTC).isoformat()
    _durable_bytes(output / 'result.json', payload(result))
    _durable_bytes(output / 'review.html', render(result, prepared).encode('utf-8'))
    if reservation:
        _durable_bytes(reservation / 'result.json', payload(result))
    manifest(output, 'recorded')
    return result
