"""Frozen live risk-preparation integration and deterministic offline UI exports."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from app.evaluation.block_run import read_archived
from app.evaluation.context_risks import VERSION as AUDIT_VERSION
from app.evaluation.context_risks import canonical
from app.evaluation.context_risks_run import CODE as AUDIT_CODE
from app.generation.block_context import VERSION as BLOCK_VERSION
from app.generation.risk_routes import VERSION, render_risks
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash, verify_live_region

CODE = (*AUDIT_CODE, 'app/generation/risk_routes.py', 'app/evaluation/risk_preparation_run.py',
        'scripts/risk_preparation.py', 'tests/unit/test_risk_preparation.py', 'docs/records/risk_preparation_protocol_v0.1.md')


def prepare(blocks: Path, audit: Path, snapshot: Path, cache_manifest: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    bindings: dict[str, str] = {}
    mappings = []
    for directory, version, phase in [(blocks, BLOCK_VERSION, 'read_only_block_api_smoke'),
                                     (audit, AUDIT_VERSION, 'offline_context_risk_review')]:
        manifest, additions, historical = read_archived(directory, snapshot, source_root=Path.cwd())
        if manifest['version'] != version or manifest['phase'] != phase:
            raise ValueError('Risk preparation parent version/phase differs')
        if any(n in bindings and bindings[n] != h for n, h in additions.items()):
            raise ValueError('Risk preparation conflicting historical inputs')
        bindings.update(additions)
        mappings.extend(historical)
    cache = json.loads(cache_manifest.read_bytes())
    if bindings.get(str(cache_manifest.resolve())) != file_hash(cache_manifest):
        raise ValueError('Risk preparation cache identity is not bound by historical inputs')
    block_report = json.loads((blocks / 'report.json').read_bytes())
    audit_report = json.loads((audit / 'report.json').read_bytes())
    if [r['id'] for r in block_report['results']] != [r['id'] for r in audit_report['results']]:
        raise ValueError('Risk preparation parent question scopes differ')
    tasks = []
    for old, previous in zip(block_report['results'], audit_report['results'], strict=True):
        request, response = _safe(blocks, old['id'] + '/request.json'), _safe(blocks, old['id'] + '/response.json')
        if any(str(p) not in bindings for p in (request, response)):
            raise ValueError('Risk preparation request/native result is not frozen')
        if canonical(json.loads(response.read_bytes())) != canonical(old['response']):
            raise ValueError('Risk preparation native and aggregate parent differ')
        tasks.append({'id': old['id'], 'request': json.loads(request.read_bytes()),
                      'previous_preparation': old['response'], 'previous_audit': previous['audit']})
    if not tasks or len({t['id'] for t in tasks}) != len(tasks):
        raise ValueError('Risk preparation requires unique nonempty tasks')
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    if any(n in bindings and bindings[n] != h for n, h in code.items()):
        raise ValueError('Risk preparation current source conflicts with historical bindings')
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'tasks': tasks, 'cache_directory': cache['cache_directory'],
        'historical_source_mappings': sorted({canonical(m): m for m in mappings}.values(), key=canonical)})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_risk_api_smoke',
        'inputs': bindings, 'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(tasks), 'bindings': len(bindings)}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_risk_api_smoke' or manifest['code'] != {
            str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Risk preparation prospective phase/code inventory differs')
    declared = [*manifest['inputs'].items(), *manifest['code'].items()]
    expected: dict[str, str] = {}
    for name, checksum in declared:
        name = str(Path(name).resolve())
        if name in expected and expected[name] != checksum:
            raise ValueError('Risk preparation conflicting frozen hashes')
        expected[name] = checksum
    plan = json.loads((prepared / 'plan.json').read_bytes())
    if plan['version'] != VERSION:
        raise ValueError('Risk preparation plan version differs')
    return plan, bindings


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {'questions': len(rows), 'preparation_identical_to_stage32': sum(r['preparation_identical'] for r in rows),
        'audit_identical_to_stage33': sum(r['audit_identical'] for r in rows),
        'diagnostic_windows': sum(len(p['windows']) for r in rows for p in r['response']['audit']['pages']),
        'page_occurrences': sum(len(r['response']['audit']['pages']) for r in rows),
        'network_ready': sum(r['response']['network_ready'] for r in rows), 'new_generative_api_calls': 0,
        'scientific_accuracy': None, 'local_query_embedding_calls': 'not_instrumented'}


def run(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    os.environ['FASTEMBED_CACHE_PATH'] = plan['cache_directory']
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.main import app

    regions = {r['region_id']: SourceRegion.model_validate(r) for q in plan['tasks']
               for r in q['previous_preparation']['baseline']['sources']['pages'].values()}
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        for region in regions.values():
            verify_live_region(session, get_settings(), region)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    with TestClient(app) as client:
        for task in plan['tasks']:
            folder = _safe(output, task['id'])
            folder.mkdir()
            write_json(folder / 'request.json', task['request'])
            response = client.post('/answer/prepare/blocks/risks', json=task['request'])
            (folder / 'response.json').write_bytes(response.content)
            if response.status_code != 200:
                raise ValueError(f'Risk preparation failed: {task["id"]}, HTTP {response.status_code}')
            payload = response.json()
            if payload['version'] != VERSION or any(payload[k] for k in (
                    'generation_performed', 'external_request_constructed', 'network_ready')):
                raise ValueError('Risk preparation violated no-generation envelope')
            (folder / 'ui_fragment.html').write_text(render_risks(payload), encoding='utf-8')
            rows.append({'id': task['id'], 'response': payload,
                'preparation_identical': canonical(payload['preparation']) == canonical(task['previous_preparation']),
                'audit_identical': canonical(payload['audit']) == canonical(task['previous_audit'])})
    verify_hashes(bindings)
    summary = summarize(rows)
    write_json(output / 'report.json', {'version': VERSION, 'summary': summary, 'results': rows})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'read_only_risk_api_smoke', 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})
    return summary


def export(prepared: Path, captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    manifest, additions = read_frozen(captured, VERSION, Path.cwd())
    if manifest['phase'] != 'read_only_risk_api_smoke' or any(n in bindings and bindings[n] != h for n, h in additions.items()):
        raise ValueError('Risk preparation captured phase/bindings differ')
    bindings.update(additions)
    report = json.loads((captured / 'report.json').read_bytes())
    if report['summary'] != summarize(report['results']) or [r['id'] for r in report['results']] != [t['id'] for t in plan['tasks']]:
        raise ValueError('Risk preparation captured summary/scope differs')
    cards = []
    for row, task in zip(report['results'], plan['tasks'], strict=True):
        native = _safe(captured, row['id'] + '/response.json')
        if bindings.get(str(native)) != file_hash(native) or canonical(json.loads(native.read_bytes())) != canonical(row['response']):
            raise ValueError('Risk preparation aggregate/native binding differs')
        if (row['preparation_identical'] != (canonical(row['response']['preparation']) == canonical(task['previous_preparation']))
                or row['audit_identical'] != (canonical(row['response']['audit']) == canonical(task['previous_audit']))):
            raise ValueError('Risk preparation parent comparison differs')
        fragment = render_risks(row['response'], local_pdf_links=True)
        # The nested unchanged parent renderer uses production PDF routes. In
        # standalone review every such PDF link must also point at its original.
        for p in row['response']['preparation']['baseline']['sources']['pages'].values():
            from app.documents.service import build_pdf_url
            fragment = fragment.replace(html.escape(build_pdf_url(p['article_id'], 'original', p['page_number']), quote=True),
                html.escape(Path(p['original_pdf_path']).resolve().as_uri() + '#page=' + str(p['page_number']), quote=True))
        cards.append('<article class="query"><h2>' + html.escape(row['id']) + '</h2><p>'
            + html.escape(row['response']['preparation']['baseline']['question']) + '</p>' + fragment + '</article>')
    page = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — подготовка с аудитом</title>'
        '<style>body{font:16px system-ui;margin:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #789;padding:8px;vertical-align:top;text-align:left}'
        '[hidden]{display:none!important}</style><h1>Подготовка ответа: аудит окружения</h1><p>' + VERSION
        + '. Генерация отключена.</p><a href="report.json">Полный JSON</a> · <a href="manifest.json">Manifest</a><pre>'
        + html.escape(json.dumps(report['summary'], ensure_ascii=False, indent=2)) + '</pre>' + ''.join(cards) + '</html>\n')
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'report.json', report)
    (output / 'review.html').write_text(page, encoding='utf-8')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_risk_preparation_review',
        'inputs': bindings, 'code': {}, 'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return dict(report['summary'])
