"""Frozen completeness/association development audit with explicit abstentions."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from app.evaluation.compact_context_run import CAPTURED as PARENT_PHASE
from app.evaluation.compact_context_run import CODE as PARENT_CODE
from app.evaluation.context_risks import canonical
from app.evaluation.source_context_packet_run import read, validate_native, validate_tac
from app.generation.compact_context_packet import VERSION as PARENT_VERSION
from app.generation.compact_context_packet import validate_compact_packet
from app.generation.context_completeness import VERSION, audit_completeness, validate_audit
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.sources import file_hash

CODE = (*PARENT_CODE, 'app/generation/context_completeness.py', 'app/evaluation/context_completeness_run.py',
    'scripts/context_completeness.py', 'tests/unit/test_context_completeness.py',
    'docs/records/context_completeness_protocol_v0.1.md')
PREPARED = 'prepared_before_completeness_audit'
CAPTURED = 'offline_context_completeness_review'


def assess_checks(identifier: str, packet: dict[str, Any], diagnostics: dict[str, Any],
                  checks: dict[str, Any], audit: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Validate exposed references before run; score only after audit exists."""
    if (checks['version'] != 'context_completeness_checks_v0.1'
            or checks['origin'] != 'assistant_source_development_before_new_audit_outcomes'
            or checks['independent_human_confirmation'] is not False):
        raise ValueError('Completeness development-check version/origin differs')
    cases = checks['cases']
    if not cases or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Completeness development-check identity empty or duplicated')
    nodes = {n['id']: n for n in diagnostics['wire']['nodes']}
    results = []
    for case in cases:
        if case['task_id'] != identifier:
            continue
        if case['kind'] == 'event_scope':
            node = nodes.get(case['node_ref'])
            if node is None or node['node_id'] != case['node_id']:
                raise ValueError('Completeness check foreign block identity')
            original = [e for e in node['events'] if e['event_id'] == case['event_id']]
            if len(original) != 1 or original[0]['context'] != case['context']:
                raise ValueError('Completeness check differs from exact original event')
            expected = case['expected']
            if not expected or set(expected) - {'chain_state', 'scope_role', 'condition_scope'}:
                raise ValueError('Completeness check has unsupported expected fields')
            if audit is not None:
                actual = next(e for e in audit['events'] if e['event_id'] == case['event_id'])
                results.append({'id': case['id'], 'passed': all(actual[k] == v for k, v in expected.items()),
                    'expected': expected, 'actual': {k: actual[k] for k in expected}})
        elif case['kind'] == 'protected_unit':
            required = case['node_ids']
            if not required or len(set(required)) != len(required) or not set(required) <= {n['node_id'] for n in nodes.values()}:
                raise ValueError('Completeness protected check has duplicate/foreign nodes')
            if audit is not None:
                units = [{nodes[n]['node_id'] for n in u['nodes']} for u in audit['units']]
                results.append({'id': case['id'], 'passed': any(set(required) <= u for u in units),
                    'scientific_table_semantics': 'not_established'})
        elif case['kind'] == 'unchanged_selection_and_refusal':
            if not packet['blocking_reasons']:
                raise ValueError('Completeness refusal check has no existing refusal')
            if audit is not None:
                results.append({'id': case['id'], 'passed': not audit['network_ready'] and not audit['selection_changed']
                    and audit['blocking_reasons'] == packet['blocking_reasons']
                    and audit['summary']['full_page_occurrences'] == len(packet['assembled_complete_pages'])})
        else:
            raise ValueError('Unsupported completeness development-check kind')
    return results


def validate_inputs(parent: Path, bindings: dict[str, str], checks: dict[str, Any]) -> list[dict[str, Any]]:
    report = read(parent / 'report.json')
    if checks['parent_report_sha256'] != file_hash(parent / 'report.json'):
        raise ValueError('Completeness checks bound to different parent report')
    rows = report['results']
    ids = {r['id'] for r in rows}
    if len(rows) != 4 or len(ids) != 4 or {c['task_id'] for c in checks['cases']} != ids:
        raise ValueError('Completeness requires all four tasks and complete check scope')
    tasks = []
    article_ids: set[str] = set()
    for row in rows:
        paths = {k: _safe(parent, row[k]) for k in ('packet_file', 'compact_packet_file', 'wire_file')}
        if any(bindings.get(str(p)) != file_hash(p) for p in paths.values()):
            raise ValueError('Completeness parent task references unfrozen files')
        diagnostic, packet = read(paths['packet_file']), read(paths['compact_packet_file'])
        validate_native(diagnostic['parent'])
        validate_compact_packet(packet, diagnostic)
        if paths['wire_file'].read_bytes() != canonical(packet['wire']).encode('utf-8'):
            raise ValueError('Completeness parent actual compact wire differs')
        assess_checks(row['id'], packet, diagnostic, checks)
        article_ids.update(e['article_id'] for e in diagnostic['parent']['preparation']['baseline']['evidence'])
        tasks.append({'id': row['id'], 'packet': str(paths['compact_packet_file']), 'diagnostics': str(paths['packet_file'])})
    validate_tac(read(parent / 'metadata.json'), article_ids)
    return tasks


def prepare(parent: Path, checks_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(parent, PARENT_VERSION, Path.cwd())
    if manifest['phase'] != PARENT_PHASE:
        raise ValueError('Completeness audit requires frozen stage38 capture')
    checks = read(checks_path)
    tasks = validate_inputs(parent, bindings, checks)
    bindings[str(checks_path.resolve())] = file_hash(checks_path)
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'tasks': tasks, 'parent': str(parent.resolve()),
        'checks': str(checks_path.resolve()), 'metadata': str((parent / 'metadata.json').resolve())})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings,
        'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(tasks), 'development_checks': len(checks['cases']), 'new_audit_outcomes': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != PREPARED or manifest['code'] != {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Completeness prepared phase/code inventory differs')
    plan = read(prepared / 'plan.json')
    paths = [p for t in plan['tasks'] for p in (t['packet'], t['diagnostics'])] + [plan['checks'], plan['metadata']]
    if plan['version'] != VERSION or any(str(Path(p).resolve()) not in bindings for p in paths):
        raise ValueError('Completeness plan references unfrozen inputs')
    return plan, bindings


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ('pages', 'full_page_occurrences', 'original_window_full_page_occurrences', 'core_full_page_occurrences',
        'single_complete_windows', 'open_page_boundaries', 'source_events', 'source_cooccurrence_proposals',
        'dependencies', 'units', 'selected_blocks', 'original_windows', 'added_dependency_blocks')
    return {'questions': len(rows), **{k: sum(r['summary'][k] for r in rows) for k in keys},
        'development_checks': sum(len(r['checks']) for r in rows),
        'development_checks_passed': sum(c['passed'] for r in rows for c in r['checks']),
        'network_ready': 0, 'database_access': False, 'retrieval_calls': 0, 'embedding_calls': 0, 'model_calls': 0,
        'scientific_accuracy': None}


def render(report: dict[str, Any], audits: dict[str, dict[str, Any]]) -> str:
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))

    def detail(title: str, value: Any) -> str:
        return '<details><summary>' + esc(title) + '</summary><pre>' + esc(value) + '</pre></details>'

    cards = []
    for row in report['results']:
        audit = audits[row['id']]
        pages = {p['page_ref']: p for p in audit['pages']}
        events = []
        for e in audit['events']:
            source = pages[e['page_ref']]['source']
            url = Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(source['page_number'])
            events.append('<tr data-event><td><a href="' + esc(url) + '">PDF p.' + str(source['page_number'])
                + '</a><br>' + esc(e['node_ref']) + ' · ' + esc(e['scope_role']) + '<br>' + esc(e['chain_state'])
                + '</td><td>' + detail('Полный исходный source event', e['context']['text'])
                + detail('Все literal fields, guards, границы и причины отказа', e) + '</td></tr>')
        cards.append('<article data-query><h2>' + esc(row['id']) + '</h2><p>' + esc(audit['question']) + '</p>'
            + '<a href="' + esc(row['audit_file']) + '">Полный аудит JSON</a> · '
            + '<a href="' + esc(row['parent_packet_file']) + '">Неизменённый compact packet</a> · '
            + '<a href="' + esc(row['diagnostics_file']) + '">Полная неизменённая диагностика</a>'
            + detail('Показатели и development checks', row)
            + detail('Все страницы: причины полного покрытия и открытые границы', audit['pages'])
            + detail('Все структурные зависимости: незавершённые связи не разрешены', audit['dependencies'])
            + detail('Все группы сохранения: без наследования полей между событиями', audit['units'])
            + '<table><thead><tr><th>Источник и статус</th><th>Точный контекст и диагностика</th></tr></thead><tbody>'
            + ''.join(events) + '</tbody></table></article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: полнота контекста</title>'
        '<style>body{font:15px system-ui;margin:22px;color:#18333f;background:#fafafa}table{border-collapse:collapse;'
        'width:100%;table-layout:fixed}td,th{border:1px solid #9aa;padding:9px;vertical-align:top;overflow-wrap:anywhere}'
        'td:first-child,th:first-child{width:27%}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        'article{border-top:2px solid #789;margin-top:24px}details{margin:8px 0}[hidden]{display:none!important}</style>'
        '<h1>Полнота контекста и применимость условий: source audit</h1><p>' + VERSION + '. '
        'Literal cooccurrence — предложение, не научное подтверждение. Подготовка и измерение разделены; '
        'поля между событиями не наследуются. Полные страницы, неизвестные связи и прежние отказы сохранены. '
        'Генерация отключена.</p><p><a href="metadata_review.html">TAC: все документы scope</a> · '
        '<a href="report.json">Отчёт</a> · <a href="manifest.json">Manifest</a></p>'
        + detail('Алгоритм, input snapshot и общий результат', {'version': VERSION, 'input_snapshot': report['input_snapshot'],
            'summary': report['summary']})
        + '<p><label>Поиск по вопросам, полному тексту и диагностике <input id="q" type="search"></label> '
        '<output id="count"></output></p>' + ''.join(cards)
        + '<script>const q=document.getElementById("q"),rows=[...document.querySelectorAll("[data-query]")];'
        'function filter(){let n=0;for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes('
        'q.value.toLocaleLowerCase());if(!r.hidden)n++}document.getElementById("count").textContent=n+" / "+rows.length}'
        'q.addEventListener("input",filter);filter();</script></html>\n')


def save(output: Path, report: dict[str, Any], audits: dict[str, dict[str, Any]],
         parents: dict[str, dict[str, bytes]], metadata: dict[str, Any], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for row in report['results']:
        _safe(output, row['id']).mkdir()
        write_json(_safe(output, row['audit_file']), audits[row['id']])
        for key in ('parent_packet_file', 'diagnostics_file'):
            with _safe(output, row[key]).open('xb') as stream:
                stream.write(parents[row['id']][key])
    write_json(output / 'report.json', report)
    write_json(output / 'metadata.json', metadata)
    (output / 'review.html').write_text(render(report, audits), encoding='utf-8', newline='\n')
    (output / 'metadata_review.html').write_text(render_metadata(metadata).replace('href="report.json"',
        'href="metadata.json"', 1), encoding='utf-8', newline='\n')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': CAPTURED, 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})


def run(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    checks = read(Path(plan['checks']))
    validate_inputs(Path(plan['parent']), bindings, checks)
    rows, audits, parents = [], {}, {}
    for task in plan['tasks']:
        identifier = task['id']
        packet, diagnostics = read(Path(task['packet'])), read(Path(task['diagnostics']))
        audit = audit_completeness(packet, diagnostics)
        audits[identifier] = audit
        parents[identifier] = {'parent_packet_file': Path(task['packet']).read_bytes(),
            'diagnostics_file': Path(task['diagnostics']).read_bytes()}
        rows.append({'id': identifier, 'summary': audit['summary'], 'blocking_reasons': audit['blocking_reasons'],
            'checks': assess_checks(identifier, packet, diagnostics, checks, audit),
            'audit_file': identifier + '/audit.json', 'parent_packet_file': identifier + '/parent_packet.json',
            'diagnostics_file': identifier + '/diagnostics.json'})
    report: dict[str, Any] = {'version': VERSION, 'summary': summarize(rows), 'results': rows,
        'input_snapshot': {'parent': plan['parent'], 'parent_report_sha256': checks['parent_report_sha256'],
            'checks_path': plan['checks'], 'checks_sha256': file_hash(Path(plan['checks']))}}
    save(output, report, audits, parents, read(Path(plan['metadata'])), bindings)
    return dict(report['summary'])


def export(captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(captured, VERSION, Path.cwd())
    report = read(captured / 'report.json')
    if manifest['phase'] != CAPTURED or report['version'] != VERSION or report['summary'] != summarize(report['results']):
        raise ValueError('Completeness captured version/phase/summary differs')
    audits, parents = {}, {}
    checks = read(Path(report['input_snapshot']['checks_path']))
    for row in report['results']:
        packet_path, diagnostic_path = [_safe(captured, row[k]) for k in ('parent_packet_file', 'diagnostics_file')]
        packet, diagnostics = read(packet_path), read(diagnostic_path)
        audit = read(_safe(captured, row['audit_file']))
        validate_audit(audit, packet, diagnostics)
        if audit['summary'] != row['summary'] or assess_checks(row['id'], packet, diagnostics, checks, audit) != row['checks']:
            raise ValueError('Completeness captured metrics/checks differ from exact audit')
        audits[row['id']] = audit
        parents[row['id']] = {'parent_packet_file': packet_path.read_bytes(), 'diagnostics_file': diagnostic_path.read_bytes()}
    verify_hashes(bindings)
    save(output, report, audits, parents, read(captured / 'metadata.json'), manifest['inputs'])
    return dict(report['summary'])
