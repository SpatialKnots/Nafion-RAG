"""Freeze and exercise the new preparation API in-process, with real read-only retrieval."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from app.evaluation.query_qualifiers_run import load as load_qualifiers
from app.generation.preparation import VERSION
from app.generation.preparation_routes import render_preparation
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash, verify_live_region

CODE = ('app/main.py', 'app/ui.py', 'app/generation/preparation.py', 'app/generation/preparation_routes.py',
        'app/evaluation/preparation_run.py', 'scripts/answer_preparation.py', 'tests/unit/test_answer_preparation.py',
        'docs/records/answer_preparation_protocol_v0.1.md')


def prepare(parent: Path, cache_manifest: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load_qualifiers(parent)
    cache = json.loads(cache_manifest.read_bytes())
    cache_bindings = cache['query_embedding_files']
    if any(n in bindings and bindings[n] != h for n, h in cache_bindings.items()):
        raise ValueError('Preparation smoke cached weights conflict with inherited bindings')
    bindings.update(cache_bindings)
    bindings[str(cache_manifest.resolve())] = file_hash(cache_manifest)
    verify_hashes(bindings)
    questions = [{'id': row['id'], 'request': {'question': row['question'], 'collection': 'literature', 'top_k': 5,
        'method': 'hybrid_cross_lingual', 'answer_style': 'claims', 'answer_language': 'auto'},
        'previous_evidence': row['trace']['evidence'], 'previous_sources': row['sources']} for row in plan['observed_queries']]
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'questions': questions,
        'cache_directory': cache['cache_directory'], 'new_model_calls': 0,
        'exposure': 'Four exposed development questions; actual integration smoke, no independent scientific gold.'})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_read_only_api_smoke',
        'inputs': bindings, 'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(questions), 'cached_files': len(cache_bindings), 'new_model_calls': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_read_only_api_smoke' or manifest['code'] != {
            str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Preparation smoke phase or code inventory differs')
    plan = json.loads((prepared / 'plan.json').read_bytes())
    if plan['version'] != VERSION:
        raise ValueError('Preparation smoke plan version differs')
    return plan, bindings


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

    # Verify old registered pages before new requests; no old text is silently repaired.
    pages = {r['region_id']: SourceRegion.model_validate(r) for q in plan['questions']
             for r in q['previous_sources']['pages'].values()}
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        for region in pages.values():
            verify_live_region(session, get_settings(), region)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    with TestClient(app) as client:
        for q in plan['questions']:
            directory = output / q['id']
            directory.mkdir()
            write_json(directory / 'request.json', q['request'])
            response = client.post('/answer/prepare', json=q['request'])
            (directory / 'response.json').write_bytes(response.content)
            if response.status_code != 200:
                raise ValueError(f'Preparation API smoke failed for {q["id"]}: HTTP {response.status_code}')
            payload = response.json()
            if payload['version'] != VERSION or payload['generation_performed'] or payload['external_request_constructed']:
                raise ValueError('Preparation API violated the explicit no-generation contract')
            (directory / 'ui_fragment.html').write_text(render_preparation(payload), encoding='utf-8')
            rows.append({'id': q['id'], 'response': payload,
                         'evidence_identical_to_stage29': payload['evidence'] == q['previous_evidence']})
    verify_hashes(bindings)
    summary = summarize(rows)
    write_json(output / 'report.json', {'version': VERSION, 'summary': summary, 'results': rows})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'read_only_api_smoke', 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})
    return summary


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {'questions': len(rows), 'evidence_items': sum(len(r['response']['evidence']) for r in rows),
        'checks_passed': sum(r['response']['status'] == 'checks_passed' for r in rows),
        'baseline_allowed': sum(r['response']['baseline_allowed'] for r in rows),
        'qualifier_allowed': sum(r['response']['query_qualifiers']['candidate_allowed'] for r in rows),
        'network_ready': sum(r['response']['network_ready'] for r in rows),
        'identical_stage29_contexts': sum(r['evidence_identical_to_stage29'] for r in rows),
        'new_generative_api_calls': 0, 'scientific_precision': None, 'scientific_recall': None}


def export(prepared: Path, captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    manifest, additions = read_frozen(captured, VERSION, Path.cwd())
    if manifest['phase'] != 'read_only_api_smoke' or any(n in bindings and bindings[n] != h for n, h in additions.items()):
        raise ValueError('Preparation smoke capture phase or bindings conflict')
    bindings.update(additions)
    report: dict[str, Any] = json.loads((captured / 'report.json').read_bytes())
    if ([r['id'] for r in report['results']] != [q['id'] for q in plan['questions']]
            or report['summary'] != summarize(report['results'])):
        raise ValueError('Preparation smoke result inventory or summary differs')
    cards = []
    for row in report['results']:
        payload = row['response']
        links = ' '.join('<a href="' + html.escape(Path(r['original_pdf_path']).resolve().as_uri()
            + '#page=' + str(r['page_number']), quote=True) + '">PDF p.' + str(r['page_number']) + '</a>'
            for r in payload['sources']['pages'].values())
        cards.append('<article class="query"><h2>' + html.escape(row['id']) + '</h2><p>' + html.escape(payload['question'])
            + '</p>' + links + '<details><summary>Полный ответ режима подготовки и диагностика</summary><pre>'
            + html.escape(json.dumps(row, ensure_ascii=False, indent=2)) + '</pre></details></article>')
    page = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — подготовка ответа</title>'
        '<style>body{font:16px system-ui;margin:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        'article{border-top:1px solid #789;padding:12px}[hidden]{display:none!important}</style><h1>Подготовка ответа</h1><p>'
        + VERSION + '. Четыре запроса к локальному API; генерация отключена.</p><pre>'
        + html.escape(json.dumps(report['summary'], ensure_ascii=False, indent=2)) + '</pre>'
        '<a href="report.json">JSON</a> · <a href="manifest.json">Manifest</a><p><label>Поиск <input type="search" id="q"></label></p>'
        + ''.join(cards) + '<script>const rows=[...document.querySelectorAll("article.query")];document.getElementById("q")'
        '.addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();for(const r of rows)'
        'r.hidden=!r.textContent.toLocaleLowerCase().includes(q)});</script></html>\n')
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'report.json', report)
    (output / 'review.html').write_text(page, encoding='utf-8')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_preparation_review', 'inputs': bindings, 'code': {},
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return dict(report['summary'])
