"""Frozen query selection experiment with explicit parent coverage losses."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from app.evaluation.context_completeness_run import CAPTURED as PARENT_PHASE
from app.evaluation.context_completeness_run import CODE as PARENT_CODE
from app.evaluation.context_risks import canonical
from app.evaluation.source_context_packet_run import read, validate_native, validate_tac
from app.generation.context_completeness import VERSION as PARENT_VERSION
from app.generation.context_completeness import validate_audit
from app.generation.query_context_selection import VERSION, expand_selected_unit, select_context, validate_selection
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.sources import file_hash

CODE = (*PARENT_CODE, 'app/generation/query_context_selection.py', 'app/evaluation/query_context_selection_run.py',
    'scripts/query_context_selection.py', 'tests/unit/test_query_context_selection.py',
    'docs/records/query_context_selection_protocol_v0.1.md')
PREPARED = 'prepared_before_query_context_selection'
CAPTURED = 'offline_query_context_selection_review'
PARENT_FILES = ('audit_file', 'parent_packet_file', 'diagnostics_file')


def assess_checks(identifier: str, diagnostics: dict[str, Any], checks: dict[str, Any],
                  result: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if (checks['version'] != 'query_context_selection_checks_v0.1'
            or checks['origin'] != 'assistant_source_development_before_new_selection_outcomes'
            or checks['independent_human_confirmation'] is not False):
        raise ValueError('Query selection development-check origin/version differs')
    if not checks['cases'] or len({c['id'] for c in checks['cases']}) != len(checks['cases']):
        raise ValueError('Query selection check identities empty or duplicate')
    nodes = diagnostics['wire']['nodes']
    source_ids = {n['node_id'] for n in nodes}
    selected = set() if result is None else {b[0] for b in result['wire']['blocks']}
    retained_ids = {n['node_id'] for i, n in enumerate(nodes, 1) if i in selected}
    rows = []
    for case in checks['cases']:
        if case['task_id'] != identifier:
            continue
        kind = case['kind']
        if kind in ('required_exact_nodes', 'protected_all_or_none'):
            required = case['nodes']
            if not required or len({n['node_id'] for n in required}) != len(required):
                raise ValueError('Query selection retention check nodes empty or duplicate')
            for target in required:
                original = next((n for n in nodes if n['node_id'] == target['node_id']), None)
                if original is None or any(original[k] != target[k] for k in ('text', 'start', 'end', 'text_sha256')):
                    raise ValueError('Query selection retention check differs from exact source block')
            required_ids = {n['node_id'] for n in required}
            if not required_ids <= source_ids:
                raise ValueError('Query selection development check has foreign source nodes')
            if result is not None:
                retained = required_ids & retained_ids
                rows.append({'id': case['id'], 'kind': kind,
                    'passed': required_ids <= retained_ids if kind == 'required_exact_nodes' else not retained or retained == required_ids,
                    'required_nodes': len(required_ids), 'retained_nodes': len(retained)})
        elif kind in ('no_admission_upgrade', 'no_substitute_selected'):
            if result is not None:
                rows.append({'id': case['id'], 'kind': kind, 'passed': not result['network_ready']
                    and set(diagnostics['blocking_reasons']) <= set(result['blocking_reasons'])
                    and (kind != 'no_substitute_selected' or not selected)})
        else:
            raise ValueError('Unsupported query selection development check')
    return rows


def validate_parent(parent: Path, bindings: dict[str, str], checks: dict[str, Any]) -> list[dict[str, Any]]:
    if checks['parent_report_sha256'] != file_hash(parent / 'report.json'):
        raise ValueError('Query selection check parent report differs')
    report = read(parent / 'report.json')
    rows = report['results']
    if len(rows) != 4 or len({r['id'] for r in rows}) != 4 or {c['task_id'] for c in checks['cases']} != {r['id'] for r in rows}:
        raise ValueError('Query selection requires all four tasks and complete development-check scope')
    tasks = []
    ids: set[str] = set()
    for row in rows:
        paths = {k: _safe(parent, row[k]) for k in PARENT_FILES}
        if any(bindings.get(str(p)) != file_hash(p) for p in paths.values()):
            raise ValueError('Query selection parent references unfrozen files')
        audit, packet, diagnostics = [read(paths[k]) for k in PARENT_FILES]
        validate_native(diagnostics['parent'])
        validate_audit(audit, packet, diagnostics)
        assess_checks(row['id'], diagnostics, checks)
        ids.update(e['article_id'] for e in diagnostics['parent']['preparation']['baseline']['evidence'])
        tasks.append({'id': row['id'], **{k: str(p) for k, p in paths.items()}})
    validate_tac(read(parent / 'metadata.json'), ids)
    return tasks


def prepare(parent: Path, checks_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(parent, PARENT_VERSION, Path.cwd())
    if manifest['phase'] != PARENT_PHASE:
        raise ValueError('Query selection requires complete frozen stage39 results')
    checks = read(checks_path)
    tasks = validate_parent(parent, bindings, checks)
    bindings[str(checks_path.resolve())] = file_hash(checks_path)
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'tasks': tasks, 'checks': str(checks_path.resolve()),
        'parent': str(parent.resolve()), 'metadata': str((parent / 'metadata.json').resolve())})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings, 'code': code,
        'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(tasks), 'development_checks': len(checks['cases']), 'new_selection_outcomes': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != PREPARED or manifest['code'] != {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Query selection prepared phase/code inventory differs')
    plan = read(prepared / 'plan.json')
    paths = [t[k] for t in plan['tasks'] for k in PARENT_FILES] + [plan['checks'], plan['metadata']]
    if plan['version'] != VERSION or any(str(Path(p).resolve()) not in bindings for p in paths):
        raise ValueError('Query selection plan references an unfrozen input')
    return plan, bindings


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ('parent_blocks', 'selected_blocks', 'seed_blocks', 'deferred_blocks', 'parent_units', 'selected_units',
        'selected_dependencies', 'parent_source_text_bytes', 'selected_source_text_bytes', 'parent_wire_bytes', 'wire_bytes',
        'parent_windows', 'whole_windows_retained', 'partial_windows_local_only', 'deferred_windows_local_only',
        'parent_event_occurrences', 'selected_event_occurrences', 'parent_full_page_occurrences', 'selected_full_page_occurrences')
    return {'questions': len(rows), **{k: sum(r['metrics'][k] for r in rows) for k in keys},
        'current_byte_checks_passed': sum(r['current_byte_check_passed'] for r in rows),
        'development_checks': sum(len(r['checks']) for r in rows),
        'development_checks_passed': sum(c['passed'] for r in rows for c in r['checks']),
        'scientific_loss_status': 'not_evaluated', 'network_ready': 0, 'database_access': False,
        'retrieval_calls': 0, 'embedding_calls': 0, 'model_calls': 0}


def render(report: dict[str, Any], results: dict[str, dict[str, Any]], parents: dict[str, dict[str, bytes]]) -> str:
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))

    def detail(title: str, value: Any) -> str:
        return '<details><summary>' + esc(title) + '</summary><pre>' + esc(value) + '</pre></details>'

    cards = []
    for row in report['results']:
        result = results[row['id']]
        wire = result['wire']
        diagnostic = json.loads(parents[row['id']]['diagnostics_file'])
        pages = {p['page_ref']: p for p in diagnostic['wire']['pages']}
        sources = {p['source']['region_id']: p['source'] for p in diagnostic['parent']['audit']['pages']}
        blocks = {b[0]: b for b in wire['blocks']}
        units = []
        for ref, unit in zip(wire['unit_refs'], wire['co_preservation_units'], strict=True):
            excerpts = []
            for n in unit:
                block = blocks[n]
                source = sources[pages[block[1]]['parent_region_id']]
                url = Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(source['page_number'])
                excerpts.append('<section><a href="' + esc(url) + '">PDF p.' + str(source['page_number'])
                    + '</a> · N' + str(n) + ' · block ' + str(block[2]) + '<pre>' + esc(block[5]) + '</pre></section>')
            units.append('<tr data-unit><td>Unit ' + str(ref) + '<br>' + esc(unit) + '</td><td><details>'
                '<summary>Полная выбранная группа: отдельные точные блоки</summary>' + ''.join(excerpts) + '</details></td></tr>')
        cards.append('<article data-query><h2>' + esc(row['id']) + '</h2><p>' + esc(wire['question']) + '</p><p>'
            + ' · '.join('<a href="' + esc(row[k]) + '">' + title + '</a>' for k, title in (
                ('wire_file', 'Выбранный wire JSON'), ('selection_file', 'Отбор и все ledgers'),
                ('audit_file', 'Прежний полный audit'), ('parent_packet_file', 'Прежний packet'),
                ('diagnostics_file', 'Полная исходная диагностика'))) + '</p>'
            + detail('Результаты, потери исходных окон и development checks', row)
            + detail('Уточнения вопроса и article restrictions', result['article_restrictions'])
            + detail('Каждый исходный блок: выбран или отложен с неизвестной релевантностью', result['block_ledger'])
            + detail('Каждое исходное окно: полное, частичное или отложенное', result['original_window_ledger'])
            + '<table><thead><tr><th>Группа</th><th>Точный выбранный источник</th></tr></thead><tbody>'
            + ''.join(units) + '</tbody></table></article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: отбор контекста по вопросу</title>'
        '<style>body{font:15px system-ui;margin:22px;color:#18333f;background:#fafafa}table{border-collapse:collapse;'
        'width:100%;table-layout:fixed}td,th{border:1px solid #9aa;padding:9px;vertical-align:top;overflow-wrap:anywhere}'
        'td:first-child,th:first-child{width:24%}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        'article{border-top:2px solid #789;margin-top:24px}details{margin:8px 0}[hidden]{display:none!important}</style>'
        '<h1>Отбор контекста по вопросу: отдельный эксперимент</h1><p>' + VERSION + '. '
        'Selection изменена; научная сохранность не подтверждена. Полный parent сохранён локально. '
        'Подготовка не наследуется измерением; прежние отказы и full-page guard сохранены. Генерация отключена.</p>'
        '<p><a href="metadata_review.html">TAC: все документы scope</a> · <a href="report.json">Отчёт</a> · '
        '<a href="manifest.json">Manifest</a></p>' + detail('Алгоритм, input snapshot и общий результат',
            {'version': VERSION, 'input_snapshot': report['input_snapshot'], 'summary': report['summary']})
        + '<p><label>Поиск по вопросам, выбранному тексту и ledgers <input id="q" type="search"></label> '
        '<output id="count"></output></p>' + ''.join(cards)
        + '<script>const q=document.getElementById("q"),rows=[...document.querySelectorAll("[data-query]")];'
        'function filter(){let n=0;for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes('
        'q.value.toLocaleLowerCase());if(!r.hidden)n++}document.getElementById("count").textContent=n+" / "+rows.length}'
        'q.addEventListener("input",filter);filter();</script></html>\n')


def save(output: Path, report: dict[str, Any], results: dict[str, dict[str, Any]],
         parents: dict[str, dict[str, bytes]], metadata: dict[str, Any], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for row in report['results']:
        _safe(output, row['id']).mkdir()
        write_json(_safe(output, row['selection_file']), results[row['id']])
        with _safe(output, row['wire_file']).open('xb') as stream:
            stream.write(canonical(results[row['id']]['wire']).encode('utf-8'))
        for key in PARENT_FILES:
            with _safe(output, row[key]).open('xb') as stream:
                stream.write(parents[row['id']][key])
    write_json(output / 'report.json', report)
    write_json(output / 'metadata.json', metadata)
    (output / 'review.html').write_text(render(report, results, parents), encoding='utf-8', newline='\n')
    (output / 'metadata_review.html').write_text(render_metadata(metadata).replace('href="report.json"',
        'href="metadata.json"', 1), encoding='utf-8', newline='\n')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': CAPTURED, 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})


def run(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    checks = read(Path(plan['checks']))
    validate_parent(Path(plan['parent']), bindings, checks)
    rows, results, parents = [], {}, {}
    for task in plan['tasks']:
        audit, packet, diagnostic = [read(Path(task[k])) for k in PARENT_FILES]
        result = select_context(packet, diagnostic, audit)
        identifier = task['id']
        results[identifier] = result
        parents[identifier] = {k: Path(task[k]).read_bytes() for k in PARENT_FILES}
        rows.append({'id': identifier, 'metrics': result['metrics'],
            'current_byte_check_passed': result['current_byte_check_passed'], 'blocking_reasons': result['blocking_reasons'],
            'checks': assess_checks(identifier, diagnostic, checks, result),
            'selection_file': identifier + '/selection.json', 'wire_file': identifier + '/wire.json',
            'audit_file': identifier + '/parent_audit.json', 'parent_packet_file': identifier + '/parent_packet.json',
            'diagnostics_file': identifier + '/diagnostics.json'})
    report: dict[str, Any] = {'version': VERSION, 'summary': summarize(rows), 'results': rows,
        'input_snapshot': {'parent': plan['parent'], 'parent_report_sha256': checks['parent_report_sha256'],
            'checks_path': plan['checks'], 'checks_sha256': file_hash(Path(plan['checks']))}}
    save(output, report, results, parents, read(Path(plan['metadata'])), bindings)
    return dict(report['summary'])


def export(captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(captured, VERSION, Path.cwd())
    report = read(captured / 'report.json')
    if manifest['phase'] != CAPTURED or report['version'] != VERSION or report['summary'] != summarize(report['results']):
        raise ValueError('Query selection captured version/phase/summary differs')
    results, parents = {}, {}
    checks = read(Path(report['input_snapshot']['checks_path']))
    for row in report['results']:
        audit, packet, diagnostic = [read(_safe(captured, row[k])) for k in PARENT_FILES]
        result = read(_safe(captured, row['selection_file']))
        validate_selection(result, packet, diagnostic, audit)
        if _safe(captured, row['wire_file']).read_bytes() != canonical(result['wire']).encode('utf-8'):
            raise ValueError('Query selected wire differs from exact measured serialization')
        if result['metrics'] != row['metrics'] or assess_checks(row['id'], diagnostic, checks, result) != row['checks']:
            raise ValueError('Query selection captured metrics/checks differ')
        for ref in result['wire']['unit_refs']:
            expand_selected_unit(result['wire'], ref)
        results[row['id']] = result
        parents[row['id']] = {k: _safe(captured, row[k]).read_bytes() for k in PARENT_FILES}
    verify_hashes(bindings)
    save(output, report, results, parents, read(captured / 'metadata.json'), manifest['inputs'])
    return dict(report['summary'])
