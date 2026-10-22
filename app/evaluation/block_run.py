"""Frozen read-only block preparation comparison with explicit historical-code binding."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from app.generation.block_context import VERSION
from app.generation.block_routes import render_blocks
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash, verify_live_region
from scripts.freeze_baseline import ROOT_FILES, TREE_RULES, verify

CODE = ('app/generation/block_context.py', 'app/generation/block_routes.py', 'app/evaluation/block_run.py',
        'app/main.py', 'app/generation/preparation_routes.py', 'scripts/block_preparation.py',
        'scripts/freeze_baseline.py', 'tests/unit/test_block_preparation.py', 'docs/records/block_context_protocol_v0.1.md')
SUPPORT = ('app/evaluation/context_windows.py', 'app/evaluation/layout_groups.py', 'app/evaluation/ruled_tables.py',
           'app/evaluation/source_gaps.py', 'app/records/article_windows.py', 'app/records/condition_multilingual.py',
           'app/generation/query_qualifiers.py', 'app/generation/preparation.py')


def read_archived(directory: Path, snapshot: Path, *, source_root: Path) -> tuple[dict[str, Any], dict[str, str], list[dict[str, str]]]:
    """Only hash-identified historical source may move to its verified snapshot path.

    Private artifacts/PDFs/indexes/cache cannot use this fallback. Original paths
    and expected hashes remain explicit in the mapping, not silently rewritten.
    """
    verify(snapshot)
    archive = json.loads((snapshot / 'manifest.json').read_bytes())
    source_hashes = {r['path']: r['sha256'] for r in archive['files']}
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    if any(not (directory / n).resolve().is_relative_to(directory.resolve()) for n in manifest['outputs']):
        raise ValueError('Historical output path escapes its frozen directory')
    declared = [*manifest['inputs'].items(), *manifest['code'].items(),
                *((str((directory / n).resolve()), h) for n, h in manifest['outputs'].items())]
    bindings = {str(manifest_path.resolve()): file_hash(manifest_path),
                str((snapshot / 'manifest.json').resolve()): file_hash(snapshot / 'manifest.json')}
    bindings.update({str((snapshot / n).resolve()): h for n, h in archive['artifacts'].items()})
    mappings = []
    expected: dict[str, str] = {}
    for name, checksum in declared:
        original = Path(name).resolve()
        if str(original) in expected and expected[str(original)] != checksum:
            raise ValueError('Conflicting historical source/input hashes')
        expected[str(original)] = checksum
        if original.is_file() and file_hash(original) == checksum:
            bindings[str(original)] = checksum
            continue
        if not original.is_relative_to(source_root.resolve()):
            raise ValueError('Changed historical input outside source snapshot')
        relative = original.relative_to(source_root.resolve()).as_posix()
        parts = Path(relative).parts
        selected_source = relative in ROOT_FILES or (parts[0] in TREE_RULES and Path(relative).suffix in TREE_RULES[parts[0]])
        if not selected_source or source_hashes.get(relative) != checksum:
            raise ValueError(f'Changed historical non-source input cannot use archive: {relative}')
        archived = (snapshot / 'source' / relative).resolve()
        bindings[str(archived)] = checksum
        mappings.append({'historical_path': str(original), 'archived_source_path': str(archived), 'sha256': checksum})
    verify_hashes(bindings)
    return manifest, bindings, mappings


def prepare(parent: Path, snapshot: Path, cache_manifest: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings, mappings = read_archived(parent, snapshot, source_root=Path.cwd())
    if manifest['version'] != 'answer_preparation_v0.1' or manifest['phase'] != 'read_only_api_smoke':
        raise ValueError('Block preparation requires preserved stage31 API results')
    report = json.loads((parent / 'report.json').read_bytes())
    cache = json.loads(cache_manifest.read_bytes())
    additions = {**cache['query_embedding_files'], str(cache_manifest.resolve()): file_hash(cache_manifest)}
    if any(n in bindings and bindings[n] != h for n, h in additions.items()):
        raise ValueError('Block preparation query cache conflicts with historical identity')
    bindings.update(additions)
    verify_hashes(bindings)
    questions = []
    for row in report['results']:
        request = parent / row['id'] / 'request.json'
        if str(request.resolve()) not in bindings:
            raise ValueError('Historical API request is not bound by its manifest')
        questions.append({'id': row['id'], 'request': json.loads(request.read_bytes()), 'previous_baseline': row['response']})
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in (*CODE, *SUPPORT)}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'questions': questions, 'historical_code_mapping': mappings,
        'cache_directory': cache['cache_directory'], 'new_generative_api_calls': 0,
        'exposure': 'Exposed integration questions; no independent scientific reference labels.'})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_block_api_smoke', 'inputs': bindings,
        'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(questions), 'archived_source_bindings': len(mappings), 'new_generative_api_calls': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    declared = json.loads((prepared / 'manifest.json').read_bytes())
    seen: dict[str, str] = {}
    for name, checksum in [*declared['inputs'].items(), *declared['code'].items(),
                           *((str((prepared / n).resolve()), h) for n, h in declared['outputs'].items())]:
        path = str(Path(name).resolve())
        if path in seen and seen[path] != checksum:
            raise ValueError('Conflicting block preparation input/code/output hashes')
        seen[path] = checksum
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_block_api_smoke' or manifest['code'] != {
            str(Path(n).resolve()): file_hash(Path(n)) for n in (*CODE, *SUPPORT)}:
        raise ValueError('Block preparation frozen phase or code inventory differs')
    plan = json.loads((prepared / 'plan.json').read_bytes())
    if plan['version'] != VERSION:
        raise ValueError('Block preparation plan version differs')
    return plan, bindings


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {'questions': len(rows), 'baseline_evidence_items': sum(len(r['response']['baseline']['evidence']) for r in rows),
        'page_occurrences': sum(len(r['response']['pages']) for r in rows),
        'registered_blocks': sum(len(p['blocks']) for r in rows for p in r['response']['pages']),
        'deferred_page_occurrences': sum(bool(p['diagnostics']) for r in rows for p in r['response']['pages']),
        'proposed_contexts': sum(len(r['response']['proposals']) for r in rows),
        'technical_checks_passed': sum(r['response']['technical_checks_passed'] for r in rows),
        'network_ready': sum(r['response']['network_ready'] for r in rows),
        'identical_stage31_evidence': sum(r['evidence_identical_to_stage31'] for r in rows),
        'new_generative_api_calls': 0, 'scientific_precision': None, 'scientific_recall': None}


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

    regions = {r['region_id']: SourceRegion.model_validate(r) for q in plan['questions']
               for r in q['previous_baseline']['sources']['pages'].values()}
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        for r in regions.values():
            verify_live_region(session, get_settings(), r)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    with TestClient(app) as client:
        for q in plan['questions']:
            folder = output / q['id']
            folder.mkdir()
            write_json(folder / 'request.json', q['request'])
            response = client.post('/answer/prepare/blocks', json=q['request'])
            (folder / 'response.json').write_bytes(response.content)
            if response.status_code != 200:
                raise ValueError(f'Block preparation failed: {q["id"]}, HTTP {response.status_code}')
            payload = response.json()
            if (payload['version'] != VERSION or payload['generation_performed'] or payload['external_request_constructed']
                    or payload['network_ready']):
                raise ValueError('Block preparation violated no-generation boundary')
            (folder / 'ui_fragment.html').write_text(render_blocks(payload), encoding='utf-8')
            rows.append({'id': q['id'], 'response': payload,
                'evidence_identical_to_stage31': payload['baseline']['evidence'] == q['previous_baseline']['evidence']})
    verify_hashes(bindings)
    result = summary(rows)
    write_json(output / 'report.json', {'version': VERSION, 'summary': result, 'results': rows})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'read_only_block_api_smoke', 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})
    return result


def export(prepared: Path, captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    manifest, additions = read_frozen(captured, VERSION, Path.cwd())
    if manifest['phase'] != 'read_only_block_api_smoke' or any(n in bindings and bindings[n] != h for n, h in additions.items()):
        raise ValueError('Frozen block run phase or bindings differ')
    bindings.update(additions)
    report = json.loads((captured / 'report.json').read_bytes())
    if (report['summary'] != summary(report['results'])
            or [r['id'] for r in report['results']] != [q['id'] for q in plan['questions']]):
        raise ValueError('Block result summary or question inventory differs')
    cards = []
    for row in report['results']:
        payload = row['response']
        links = ' '.join('<a href="' + html.escape(Path(r['original_pdf_path']).resolve().as_uri()
            + '#page=' + str(r['page_number']), quote=True) + '">PDF p.' + str(r['page_number']) + '</a>'
            for r in payload['baseline']['sources']['pages'].values())
        cards.append('<article class="query"><h2>' + html.escape(row['id']) + '</h2><p>'
            + html.escape(payload['baseline']['question']) + '</p>' + links
            + '<details><summary>Все блоки, контексты, исходный baseline и диагностика</summary><pre>'
            + html.escape(json.dumps(row, ensure_ascii=False, indent=2)) + '</pre></details></article>')
    page = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — PDF-блоки</title>'
        '<style>body{font:16px system-ui;margin:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        'article{border-top:1px solid #789;padding:12px}[hidden]{display:none!important}</style><h1>Контексты PDF-блоков</h1><p>'
        + VERSION + '. Исходный baseline сохранён; генерация отключена.</p><pre>'
        + html.escape(json.dumps(report['summary'], ensure_ascii=False, indent=2)) + '</pre>'
        '<a href="report.json">JSON</a> · <a href="manifest.json">Manifest</a><p><label>Поиск <input type="search" id="q"></label></p>'
        + ''.join(cards) + '<script>const rows=[...document.querySelectorAll("article.query")];document.getElementById("q")'
        '.addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();for(const r of rows)'
        'r.hidden=!r.textContent.toLocaleLowerCase().includes(q)});</script></html>\n')
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'report.json', report)
    (output / 'review.html').write_text(page, encoding='utf-8')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_block_review', 'inputs': bindings, 'code': {},
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return dict(report['summary'])
