"""Freeze and audit preserved block results without retrieval or inference."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.evaluation.block_run import CODE as PARENT_CODE
from app.evaluation.block_run import SUPPORT, read_archived
from app.evaluation.context_risks import VERSION, audit_context_risks, canonical
from app.generation.block_context import VERSION as PARENT_VERSION
from app.generation.block_context import page_plan
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash

CODE = (*PARENT_CODE, *SUPPORT, 'app/evaluation/context_risks.py', 'app/evaluation/context_risks_run.py',
        'scripts/context_risks.py', 'tests/unit/test_context_risks.py', 'docs/records/context_risks_protocol_v0.1.md')


def prepare(parent: Path, snapshot: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings, mappings = read_archived(parent, snapshot, source_root=Path.cwd())
    if manifest['version'] != PARENT_VERSION or manifest['phase'] != 'read_only_block_api_smoke':
        raise ValueError('Context risks require preserved stage32 native block results')
    report = json.loads((parent / 'report.json').read_bytes())
    tasks = []
    for row in report['results']:
        path = (parent / row['id'] / 'response.json').resolve()
        if str(path) not in bindings:
            raise ValueError('Context risk native result is not frozen')
        if canonical(json.loads(path.read_bytes())) != canonical(row['response']):
            raise ValueError('Context risk native and aggregate parent results differ')
        tasks.append({'id': row['id'], 'response_path': str(path)})
    if not tasks or len({t['id'] for t in tasks}) != len(tasks):
        raise ValueError('Context risk scope requires distinct nonempty query IDs')
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    if any(n in bindings and bindings[n] != h for n, h in code.items()):
        raise ValueError('Context risk current code conflicts with historical bindings')
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'tasks': tasks, 'historical_source_mappings': mappings})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_risk_audit',
        'inputs': bindings, 'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'queries': len(tasks), 'bindings': len(bindings), 'historical_source_mappings': len(mappings)}


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    pages = [p for r in results for p in r['audit']['pages']]
    windows = [w for p in pages for w in p['windows']]
    relations = Counter(a['relation'] for w in windows for a in w['asset_relations'])
    triggers = Counter(t['relation'] for w in windows for t in w['trigger_relations'])
    return {'queries': len(results), 'page_occurrences': len(pages), 'diagnostic_windows': len(windows),
        'mapping_unproven_page_occurrences': sum(p['mapping_unproven'] for p in pages),
        'visual_asset_occurrences': sum(len(p['visual_registry'].get('assets', [])) for p in pages),
        'text_trigger_block_occurrences': sum(len(p['text_triggers']) for p in pages),
        'asset_window_relations': dict(sorted(relations.items())), 'trigger_window_relations': dict(sorted(triggers.items())),
        'page_occurrences_with_unlocalized_diagnostics': sum(bool(p['unlocalized_page_diagnostics']) for p in pages),
        'diagnostic_window_unions_covering_page': sum(p['diagnostic_windows_assemble_complete_page'] for p in pages),
        'parent_assembled_page_occurrences': sum(len(r['audit']['parent_assembled_complete_pages']) for r in results),
        'selection_changed': False, 'admission_changed': False, 'generative_api_calls': 0,
        'retrieval_calls': 0, 'scientific_exclusion_proven': False, 'network_ready': False}


def render(report: dict[str, Any]) -> str:
    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(raw) + '</pre></details>'

    cards = []
    for row in report['results']:
        audit = row['audit']
        pages = []
        for page in audit['pages']:
            source = page['source']
            link = Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(source['page_number'])
            rows = []
            for w in page['windows']:
                rows.append('<tr><td>' + html.escape(str(w['block_numbers'])) + '</td><td>'
                    + str(w['start']) + ':' + str(w['end']) + '</td><td>' + detail('Полный текст контекста', w['quote'])
                    + detail('Геометрия, риски и unknown', w) + '</td></tr>')
            pages.append('<section><h3><a href="' + html.escape(link, quote=True) + '">Оригинал PDF, стр. '
                + str(source['page_number']) + '</a></h3>' + detail('Диагностика и реестр страницы',
                    {k: v for k, v in page.items() if k != 'windows'})
                + '<table><thead><tr><th>Блоки</th><th>Offsets</th><th>Диагностическое окружение</th></tr></thead><tbody>'
                + ''.join(rows) + '</tbody></table></section>')
        cards.append('<article class="query"><h2>' + html.escape(row['id']) + '</h2><p>' + html.escape(audit['question'])
            + '</p><a href="' + html.escape(Path(row['parent_response_path']).resolve().as_uri(), quote=True)
            + '">Неизменённый stage32 JSON</a>' + detail('Прежние запреты сохранены', audit['parent_blocking_reasons'])
            + ''.join(pages) + '</article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — локализация рисков</title>'
        '<style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #789;'
        'padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}'
        'article{border-top:2px solid #789;margin-top:24px}[hidden]{display:none!important}</style>'
        '<h1>Локализация рисков контекста</h1><p>' + VERSION + '. Только диагностика. Выбор и допуск не изменены. '
        'Удалённая геометрия не доказывает научную нерелевантность. Генерация отключена.</p>'
        + detail('Scope и результаты', report['summary'])
        + '<a href="report.json">Полный JSON</a> · <a href="manifest.json">Manifest</a>'
        '<p><label>Поиск <input type="search" id="q"></label></p>' + ''.join(cards)
        + '<script>const rows=[...document.querySelectorAll("article.query")];document.getElementById("q")'
        '.addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();for(const r of rows)'
        'r.hidden=!r.textContent.toLocaleLowerCase().includes(q)});</script></html>\n')


def run(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_risk_audit':
        raise ValueError('Context risk audit requires a prospective prepared plan')
    plan = json.loads((prepared / 'plan.json').read_bytes())
    if plan['version'] != VERSION:
        raise ValueError('Context risk plan version differs')
    results = []
    for task in plan['tasks']:
        path = Path(task['response_path']).resolve()
        if str(path) not in bindings:
            raise ValueError('Context risk task is outside frozen native inputs')
        parent = json.loads(path.read_bytes())
        regions = {r['region_id']: SourceRegion.model_validate(r) for r in parent['baseline']['sources']['pages'].values()}
        for p in parent['pages']:
            # No database or new text layer: compare current PDF registration to
            # the exact preserved page text, blocks, protected groups and assets.
            if canonical(page_plan(regions[p['parent_region_id']])) != canonical(p['plan']):
                raise ValueError('Context risk selected-PDF registration drift')
        results.append({'id': task['id'], 'parent_response_path': str(path), 'audit': audit_context_risks(parent)})
    report = {'version': VERSION, 'summary': summarize(results), 'results': results,
              'historical_source_mappings': plan['historical_source_mappings']}
    page = render(report)
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'report.json', report)
    (output / 'review.html').write_text(page, encoding='utf-8')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_context_risk_review',
        'inputs': bindings, 'code': {}, 'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return dict(report['summary'])
