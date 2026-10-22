"""Frozen preview/application and source-preserving TAC review for a bounded backfill."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.models import Article
from app.db.session import SessionLocal
from app.documents.service import DocumentAccessError
from app.evaluation.block_run import read_archived
from app.metadata.bibliography import VERSION, article_values, canonical, preview, recorded, refresh, tac_experiment
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import verify_hashes
from app.records.schema import text_hash
from app.records.sources import file_hash, source_region_from_page

CODE = ('app/metadata/bibliography.py', 'app/metadata/bridge_run.py', 'app/metadata/routes.py', 'app/db/models.py',
    'app/ingestion/service.py', 'app/main.py', 'app/generation/preparation_routes.py', 'app/generation/block_routes.py',
    'app/generation/risk_routes.py',
    'scripts/tac_metadata.py', 'scripts/tac_experiment.py', 'scripts/metadata_bridge.py', 'pyproject.toml',
    'alembic/versions/0006_article_metadata_extractions.py', 'tests/unit/test_bibliography_bridge.py',
    'tests/unit/test_bibliography_api.py', 'docs/records/bibliography_bridge_protocol_v0.1.md')


def prepare(parent: Path, archive: Path, corpus: Path, profiles: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings, mappings = read_archived(parent, archive, source_root=Path.cwd())
    if manifest['version'] != 'answer_preparation_risks_v0.1' or manifest['phase'] != 'read_only_risk_api_smoke':
        raise ValueError('Metadata bridge requires preserved stage34 native results')
    report = json.loads((parent / 'report.json').read_bytes())
    ids = sorted({e['article_id'] for r in report['results'] for e in r['response']['preparation']['baseline']['evidence']})
    if not ids:
        raise ValueError('Metadata bridge requires explicit nonempty article scope')
    for path in (corpus, profiles):
        bindings[str(path.resolve())] = file_hash(path)
    snapshot, tac = json.loads(corpus.read_bytes()), json.loads(profiles.read_bytes())
    tac_experiment.validate_profiles(snapshot, tac, file_hash(corpus))
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    if any(n in bindings and bindings[n] != h for n, h in code.items()):
        raise ValueError('Metadata bridge conflicting current/historical code bindings')
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'article_ids': ids, 'corpus': str(corpus.resolve()),
        'profiles': str(profiles.resolve()), 'historical_source_mappings': mappings})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_metadata_preview',
        'inputs': bindings, 'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'articles': len(ids), 'bindings': len(bindings)}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_metadata_preview' or manifest['code'] != {
            str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Metadata bridge prepared phase/code inventory differs')
    plan = json.loads((prepared / 'plan.json').read_bytes())
    if plan['version'] != VERSION:
        raise ValueError('Metadata bridge plan version differs')
    return plan, bindings


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {'articles': len(rows), 'field_states': dict(sorted(Counter(f + ':' + r['proposal']['extracted']['fields'][f]['status']
        for r in rows for f in ('authors', 'journal', 'year')).items())),
        'changed_field_values': sum(r['proposal']['projection']['previous_values'][f] != r['proposal']['projection']['after_values'][f]
            for r in rows for f in ('authors', 'journal', 'year')), 'new_generative_api_calls': 0,
        'new_retrieval_or_embedding_calls': 0, 'scientific_confirmation': False}


def render(report: dict[str, Any]) -> str:
    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(raw) + '</pre></details>'

    rows = []
    for row in report['articles']:
        proposal = row['proposal']
        previous = row['historical_tac']
        sections = previous.get('sections', [])
        cells = {}
        for kind in ('T', 'A', 'C'):
            selected = [s for s in sections if s['kind'] == kind and s.get('current_source_valid')]
            cells[kind] = detail('Полный текст: историческое предложение ' + kind,
                '\n\n'.join(s['quote'] for s in selected)) if selected else 'Не обнаружено / текущая привязка не подтверждена'
        values = proposal['projection']['after_values']
        sources = proposal['sources']
        url = Path(sources['original_pdf_path']).resolve().as_uri()
        metadata_cells = ''.join('<td>' + html.escape(json.dumps(values[f], ensure_ascii=False))
            + detail('Предложение, альтернативы и точные цитаты', proposal['extracted']['fields'][f])
            + '</td>' for f in ('authors', 'journal', 'year'))
        rows.append('<tr data-article><td>' + html.escape(row['title'] or 'Название в БД неизвестно') + cells['T'] + '</td>'
            + metadata_cells + '<td>' + cells['A'] + '</td><td>' + cells['C'] + '</td>'
            '<td>Terms не пересчитывались и не подключались на этом этапе.</td><td><a href="'
            + html.escape(url, quote=True) + '">Оригинальный PDF</a>' + detail('Полный источник и диагностика', row) + '</td></tr>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — метаданные TAC</title>'
        '<style>body{font:15px system-ui;margin:20px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #789;'
        'padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}'
        '[hidden]{display:none!important}</style><h1>Подключение метаданных TAC</h1><p>' + VERSION + ' · '
        + html.escape(str(report['phase'])) + '. Значения — предложения алгоритма; независимого подтверждения нет. '
        'T/A/C показаны из отдельного исторического snapshot при точной текущей привязке. Terms не пересчитывались.</p>'
        + detail('Scope, алгоритм и входы', report['summary']) + '<a href="report.json">Полный JSON</a> · '
        '<a href="manifest.json">Manifest</a><p><label>Поиск <input id="q" type="search"></label></p>'
        '<table><thead><tr>' + ''.join('<th>' + h + '</th>' for h in
            ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms', 'Original file'))
        + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
        '<script>document.getElementById("q").addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();'
        'for(const r of document.querySelectorAll("[data-article]"))'
        'r.hidden=!r.textContent.toLocaleLowerCase().includes(q)});</script></html>\n')


def write_review(output: Path, report: dict[str, Any], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'report.json', report)
    (output / 'review.html').write_text(render(report), encoding='utf-8')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': report['phase'], 'inputs': bindings, 'code': {},
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})


def run_preview(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    tac = json.loads(Path(plan['profiles']).read_bytes())
    profiles = {p['article_id']: p for p in tac['profiles']}
    rows = []
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        for name in plan['article_ids']:
            article = session.get(Article, UUID(name))
            if article is None:
                raise ValueError('Metadata bridge scoped article missing')
            proposal = preview(session, get_settings(), article)
            for region in proposal['sources']['regions']:
                for path, checksum in ((region['original_pdf_path'], region['original_pdf_sha256']),
                                       (region['layer_pdf_path'], region['layer_pdf_sha256'])):
                    if path in bindings and bindings[path] != checksum:
                        raise ValueError('Metadata bridge source hash conflict')
                    bindings[path] = checksum
            old = profiles.get(name)
            historical = {'schema': tac['schema'], 'snapshot_sha256': tac['snapshot_sha256'], 'sections': [], 'state': 'not_in_snapshot'}
            if old:
                historical['state'] = 'historical_proposals_not_confirmed'
                for span in old['sections']:
                    check = {**span, 'current_source_valid': False}
                    try:
                        current = source_region_from_page(session, get_settings(), article.id, span['page'],
                            layer=span['layer'], start=span['start'], end=span['end'], selection_basis='fixed_page',
                            selection_note='Historical TAC source verification only; no section repair.')
                        check['current_source_valid'] = (current.quote == span['quote'] and
                            str(current.text_layer_id) == span['layer_id'] and current.page_text_sha256 == span['page_text_sha256'])
                        check['registered_source'] = current.model_dump(mode='json')
                        for path, checksum in ((current.original_pdf_path, current.original_pdf_sha256),
                                               (current.layer_pdf_path, current.layer_pdf_sha256)):
                            if path in bindings and bindings[path] != checksum:
                                raise ValueError('Historical TAC PDF conflicts with frozen source hash')
                            bindings[path] = checksum
                    except (DocumentAccessError, ValueError) as exc:
                        check['diagnostic'] = str(exc)
                    historical['sections'].append(check)
            rows.append({'article_id': name, 'title': article.title, 'proposal': proposal, 'historical_tac': historical})
    report: dict[str, Any] = {'version': VERSION, 'phase': 'read_only_metadata_preview', 'articles': rows, 'summary': summary(rows)}
    write_review(output, report, bindings)
    return dict(report['summary'])


def apply(prepared: Path, preview_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    manifest, additions = read_frozen(preview_dir, VERSION, Path.cwd())
    if manifest['phase'] != 'read_only_metadata_preview' or any(n in bindings and bindings[n] != h for n, h in additions.items()):
        raise ValueError('Metadata bridge preview phase/input conflict')
    bindings.update(additions)
    report = json.loads((preview_dir / 'report.json').read_bytes())
    if [r['article_id'] for r in report['articles']] != plan['article_ids']:
        raise ValueError('Metadata bridge preview article inventory differs')
    applied = []
    with SessionLocal.begin() as session:
        articles = {}
        for row in report['articles']:
            article = session.scalar(select(Article).where(Article.id == UUID(row['article_id'])).with_for_update())
            if article is None or article_values(article) != row['proposal']['projection']['previous_values']:
                raise ValueError('Metadata bridge current article fields differ from preview')
            if canonical(preview(session, get_settings(), article)) != canonical(row['proposal']):
                raise ValueError('Metadata bridge live proposal differs from frozen preview')
            articles[row['article_id']] = article
        for row in report['articles']:
            extraction = refresh(session, get_settings(), articles[row['article_id']])
            expected = row['proposal']
            if (extraction.input_sha256 != expected['input_sha256']
                    or extraction.code_sha256 != text_hash(canonical(expected['implementation']))
                    or canonical(extraction.payload['extracted']) != canonical(expected['extracted'])
                    or extraction.payload['projection']['managed_values'] != expected['projection']['managed_values']
                    or article_values(articles[row['article_id']]) != expected['projection']['after_values']):
                raise ValueError('Metadata bridge stored projection differs from preview')
            applied.append({**row, 'extraction_id': str(extraction.id)})
        verify_hashes(bindings)
    with SessionLocal() as session:
        for row in applied:
            article = session.get(Article, UUID(row['article_id']))
            if article is None:
                raise ValueError('Metadata bridge committed article missing')
            row['recorded'] = recorded(session, get_settings(), article)
    result: dict[str, Any] = {'version': VERSION, 'phase': 'applied_metadata_proposals', 'articles': applied, 'summary': summary(applied)}
    write_review(output, result, bindings)
    return dict(result['summary'])


def export(captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(captured, VERSION, Path.cwd())
    if manifest['phase'] not in {'read_only_metadata_preview', 'applied_metadata_proposals'}:
        raise ValueError('Unsupported metadata bridge review phase')
    report = json.loads((captured / 'report.json').read_bytes())
    # Bindings stay identical across repeated exports of the same capture.
    write_review(output, report, bindings)
    return dict(report['summary'])
