"""Exclusive frozen audit, selection and replay of sample-class proposals."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from app.evaluation.context_risks import canonical
from app.evaluation.query_context_selection_run import CODE as PARENT_CODE
from app.evaluation.source_context_packet_run import read, validate_tac
from app.generation.query_context_selection import VERSION as PARENT_VERSION
from app.generation.sample_scope import AUDIT_VERSION, SELECTION_VERSION, audit_scope, select_scope
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.sources import file_hash

CODE = (*PARENT_CODE, 'app/generation/sample_scope.py', 'app/evaluation/sample_scope_run.py',
    'scripts/sample_scope.py', 'tests/unit/test_sample_scope.py',
    'docs/records/sample_scope_protocol_v0.1.md', 'docs/records/sample_scope_selection_protocol_v0.1.md')
PARENTS = ('selection_file', 'parent_packet_file', 'audit_file', 'diagnostics_file')
PREPARED = 'prepared_before_sample_scope_outcomes'
AUDITED = 'offline_sample_scope_audit'
SELECTED = 'offline_sample_scope_selection'


def parent_values(root: Path, row: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    selection, packet, completeness, diagnostic = (read(_safe(root, row[k])) for k in PARENTS)
    return selection, packet, diagnostic, completeness


def assess(checks: dict[str, Any], identifier: str, values: tuple[Any, Any, Any, Any],
           audit: dict[str, Any], result: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if checks['version'] != 'sample_scope_checks_v0.1' or checks['independent_human_confirmation'] is not False:
        raise ValueError('Sample scope development reference version/origin differs')
    if checks['origin'] != 'assistant_source_development_before_new_scope_outcomes':
        raise ValueError('Sample scope reference origin differs')
    if not checks['cases'] or len({c['id'] for c in checks['cases']}) != len(checks['cases']):
        raise ValueError('Sample scope reference identities empty or duplicated')
    selection, _, diagnostic, _ = values
    nodes = diagnostic['wire']['nodes']
    by_id = {n['node_id']: (i, n) for i, n in enumerate(nodes, 1)}
    selected = {b[0] for b in (selection if result is None else result)['wire']['blocks']}
    rows = []
    for case in checks['cases']:
        if case['task_id'] != identifier:
            continue
        numbers = set()
        for target in case.get('nodes', []):
            if target['node_id'] not in by_id:
                raise ValueError('Sample scope check references a foreign source node')
            number, node = by_id[target['node_id']]
            if any(node[k] != target[k] for k in ('text', 'start', 'end', 'text_sha256')):
                raise ValueError('Sample scope check differs from exact source block')
            numbers.add(number)
        kind = case['kind']
        if kind == 'unit_state':
            unit = next((u for u in audit['units'] if numbers <= set(u['members'])), None)
            if not numbers or unit is None:
                raise ValueError('Sample scope check nodes do not identify a complete source unit')
            passed = unit['state'] == case['expected_state']
        elif kind in ('retain_nodes', 'defer_nodes'):
            if not numbers:
                raise ValueError('Sample scope retention check has no source nodes')
            if result is None:
                continue
            passed = numbers <= selected if kind == 'retain_nodes' else not numbers & selected
        elif kind == 'no_admission_upgrade':
            candidate = selection if result is None else result
            passed = not candidate['network_ready'] and set(selection['blocking_reasons']) <= set(candidate['blocking_reasons'])
        else:
            raise ValueError('Unsupported sample scope development check')
        rows.append({'id': case['id'], 'kind': kind, 'passed': passed, 'source_nodes': len(numbers)})
    return rows


def prepare(parent: Path, checks_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(parent, PARENT_VERSION, Path.cwd())
    if manifest['phase'] != 'offline_query_context_selection_review':
        raise ValueError('Sample scope requires the complete frozen stage40 capture')
    report, checks = read(parent / 'report.json'), read(checks_path)
    rows = report['results']
    if (checks['parent_report_sha256'] != file_hash(parent / 'report.json') or len(rows) != 4
            or len({r['id'] for r in rows}) != 4 or {c['task_id'] for c in checks['cases']} != {r['id'] for r in rows}):
        raise ValueError('Sample scope parent identity or four-question scope differs')
    ids: set[str] = set()
    for row in rows:
        for k in PARENTS:
            p = _safe(parent, row[k])
            if bindings.get(str(p)) != file_hash(p):
                raise ValueError('Sample scope references an unfrozen parent')
        selection, packet, diagnostic, _ = parent_values(parent, row)
        if _safe(parent, row['wire_file']).read_bytes() != canonical(selection['wire']).encode('utf-8'):
            raise ValueError('Parent wire differs from exact captured selection')
        ids.update(e['article_id'] for e in diagnostic['parent']['preparation']['baseline']['evidence'])
        # Validate source references before new audit/selection outcomes. A dummy
        # unknown state does not measure the proposed policy during preparation.
        dummy = {'units': [{'members': u, 'state': 'not_run'}
            for u in packet['wire']['co_preservation_units']]}
        assess(checks, row['id'], parent_values(parent, row), dummy)
    validate_tac(read(parent / 'metadata.json'), ids)
    bindings[str(checks_path.resolve())] = file_hash(checks_path)
    code = {str(Path(p).resolve()): file_hash(Path(p)) for p in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': AUDIT_VERSION, 'parent': str(parent.resolve()),
        'checks': str(checks_path.resolve()), 'rows': rows})
    write_json(output / 'manifest.json', {'version': AUDIT_VERSION, 'phase': PREPARED, 'inputs': bindings,
        'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(rows), 'new_scope_outcomes': 0, 'development_cases': len(checks['cases'])}


def render(report: dict[str, Any], audits: dict[str, Any], parents: dict[str, dict[str, bytes]],
           selections: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))

    def detail(title: str, value: Any) -> str:
        return '<details><summary>' + esc(title) + '</summary><pre>' + esc(value) + '</pre></details>'

    cards = []
    for row in report['results']:
        identifier = row['id']
        selection = json.loads(parents[identifier]['selection_file'])
        diagnostic = json.loads(parents[identifier]['diagnostics_file'])
        packet = json.loads(parents[identifier]['parent_packet_file'])
        nodes = diagnostic['wire']['nodes']
        pages = {p['page_ref']: p for p in diagnostic['wire']['pages']}
        sources = {p['source']['region_id']: p['source'] for p in diagnostic['parent']['audit']['pages']}
        current = selections.get(identifier, selection)
        retained = set(current['wire']['unit_refs'])
        units = []
        for unit in audits[identifier]['units']:
            state = 'selected' if unit['unit_ref'] in retained else 'local_only_relevance_unknown'
            blocks = []
            for number in unit['members']:
                node = nodes[number - 1]
                p = pages[node['page_ref']]
                s = sources[p['parent_region_id']]
                uri = Path(s['original_pdf_path']).resolve().as_uri() + '#page=' + str(p['page'])
                blocks.append('<section><a href="' + esc(uri) + '">PDF p.' + str(p['page']) + '</a> · '
                    + esc(node['id']) + '<pre>' + esc(node['text']) + '</pre></section>')
            units.append('<tr data-unit><td>' + str(unit['unit_ref']) + ' · ' + esc(unit['state']) + '<br>' + state
                + '</td><td>' + detail('Точные spans и неизвестные связи', unit)
                + '<details><summary>Все отдельные исходные блоки группы</summary>' + ''.join(blocks) + '</details></td></tr>')
        cards.append('<article data-query><h2>' + esc(identifier) + '</h2><p>' + esc(selection['wire']['question'])
            + '</p>' + detail('Метрики и development checks', row)
            + detail('Уточнения класса вопроса', {k: audits[identifier][k] for k in ('query_hits', 'target_class', 'counts')})
            + detail('Полный учёт блоков и окон', {k: current[k] for k in ('block_ledger', 'original_window_ledger')})
            + '<p>' + ' · '.join('<a href="' + esc(row[k]) + '">' + esc(k) + '</a>'
                for k in (*PARENTS, 'scope_audit_file'))
            + (' · <a href="' + esc(row['wire_file']) + '">wire</a>' if 'wire_file' in row else '') + '</p>'
            + detail('Полный исходный registry и flags', {k: packet['wire'][k] for k in ('documents', 'pages', 'flags')})
            + '<table><thead><tr><th>Группа / scope</th><th>Точный источник</th></tr></thead><tbody>'
            + ''.join(units) + '</tbody></table></article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE sample scope</title>'
        '<style>body{font:15px system-ui;margin:22px;color:#18333f}table{border-collapse:collapse;width:100%;table-layout:fixed}'
        'td,th{border:1px solid #9aa;padding:8px;vertical-align:top;overflow-wrap:anywhere}td:first-child{width:25%}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}[hidden]{display:none!important}'
        'article{border-top:2px solid #789;margin-top:24px}</style><h1>Класс образца: аудит и эксперимент отбора</h1><p>'
        + esc(report['version']) + '. Literal class ≠ sample identity. Unknown и смешанные случаи сохраняются. '
        'Научная ненужность отложенных источников не доказана. Допуск к API закрыт.</p>'
        '<p><a href="metadata_review.html">TAC: все документы</a> · <a href="report.json">Report</a> · '
        '<a href="manifest.json">Manifest</a></p>' + detail('Версия, snapshot и итоги',
            {k: report[k] for k in ('version', 'input_snapshot', 'summary')})
        + '<label>Поиск <input id="q" type="search"></label> <output id="count"></output>' + ''.join(cards)
        + '<script>const q=document.getElementById("q"),rows=[...document.querySelectorAll("[data-query]")];'
        'function filter(){let n=0;for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes('
        'q.value.toLocaleLowerCase());if(!r.hidden)n++}document.getElementById("count").textContent=n+" / "+rows.length}'
        'q.addEventListener("input",filter);filter();</script></html>\n')


def summary(rows: list[dict[str, Any]], selected: bool) -> dict[str, Any]:
    checks = [c for r in rows for c in r['checks']]
    metrics = {k: sum(r['metrics'][k] for r in rows) for k in rows[0]['metrics']} if selected else {}
    states = sorted({state for r in rows for state in r['counts']})
    return {'questions': len(rows), **metrics, 'checks': len(checks), 'checks_passed': sum(c['passed'] for c in checks),
        'audited_units': sum(sum(r['counts'].values()) for r in rows),
        'unit_states': {s: sum(r['counts'].get(s, 0) for r in rows) for s in states},
        'parent_selected_unit_states': {s: sum(r['parent_selected_counts'].get(s, 0) for r in rows) for s in states},
        'development_wrong_retention': sum(not c['passed'] for c in checks if c['kind'] == 'defer_nodes'),
        'development_wrong_deferral': sum(not c['passed'] for c in checks if c['kind'] == 'retain_nodes'),
        'scientific_loss_status': 'not_evaluated', 'network_ready': 0, 'model_calls': 0, 'retrieval_calls': 0,
        'database_access': False}


def save(output: Path, report: dict[str, Any], audits: dict[str, Any], parents: dict[str, dict[str, bytes]],
         selections: dict[str, Any], metadata: dict[str, Any], bindings: dict[str, str], phase: str) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for row in report['results']:
        _safe(output, row['id']).mkdir()
        for k in PARENTS:
            _safe(output, row[k]).write_bytes(parents[row['id']][k])
        write_json(_safe(output, row['scope_audit_file']), audits[row['id']])
        if selections:
            result = selections[row['id']]
            write_json(_safe(output, row['scope_selection_file']), result)
            _safe(output, row['wire_file']).write_bytes(canonical(result['wire']).encode('utf-8'))
    write_json(output / 'report.json', report)
    write_json(output / 'metadata.json', metadata)
    (output / 'review.html').write_text(render(report, audits, parents, selections), encoding='utf-8', newline='\n')
    (output / 'metadata_review.html').write_text(render_metadata(metadata).replace('href="report.json"',
        'href="metadata.json"', 1), encoding='utf-8', newline='\n')
    verify_hashes(bindings)
    write_json(output / 'manifest.json', {'version': report['version'], 'phase': phase, 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})


def execute(source: Path, output: Path, *, select: bool = False) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(source, AUDIT_VERSION, Path.cwd())
    if manifest['phase'] != (AUDITED if select else PREPARED):
        raise ValueError('Sample scope input phase differs')
    if not select and manifest['code'] != {str(Path(p).resolve()): file_hash(Path(p)) for p in CODE}:
        raise ValueError('Sample scope prepared code inventory differs')
    plan = read(source / ('report.json' if select else 'plan.json'))
    snapshot = plan['input_snapshot'] if select else {'parent': plan['parent'], 'checks': plan['checks'],
        'parent_report_sha256': file_hash(Path(plan['parent']) / 'report.json'), 'checks_sha256': file_hash(Path(plan['checks']))}
    checks = read(Path(snapshot['checks']))
    root = source if select else Path(plan['parent'])
    rows, audits, selections, parents = [], {}, {}, {}
    for row in plan['results'] if select else plan['rows']:
        identifier = row['id']
        values = parent_values(root, row)
        audit = audit_scope(*values)
        if select and read(_safe(root, row['scope_audit_file'])) != audit:
            raise ValueError('Captured sample scope audit differs from exact source reconstruction')
        audits[identifier] = audit
        result = select_scope(audit, *values) if select else None
        if result is not None:
            selections[identifier] = result
        parents[identifier] = {k: _safe(root, row[k]).read_bytes() for k in PARENTS}
        new = {'id': identifier, 'checks': assess(checks, identifier, values, audit, result),
            'counts': audit['counts'], 'parent_selected_counts': audit['parent_selected_counts'],
            **{k: identifier + '/' + k + '.json' for k in PARENTS},
            'scope_audit_file': identifier + '/scope_audit.json'}
        if result is not None:
            new.update(metrics=result['metrics'], scope_selection_file=identifier + '/scope_selection.json',
                wire_file=identifier + '/wire.json')
        rows.append(new)
    report: dict[str, Any] = {'version': SELECTION_VERSION if select else AUDIT_VERSION, 'input_snapshot': snapshot,
        'summary': summary(rows, select), 'results': rows}
    save(output, report, audits, parents, selections, read(root / 'metadata.json'), bindings, SELECTED if select else AUDITED)
    return dict(report['summary'])


def export(captured: Path, output: Path, *, select: bool = False) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, _ = read_frozen(captured, SELECTION_VERSION if select else AUDIT_VERSION, Path.cwd())
    if manifest['phase'] != (SELECTED if select else AUDITED):
        raise ValueError('Sample scope export phase differs')
    report = read(captured / 'report.json')
    audits, parents, selections = {}, {}, {}
    checks = read(Path(report['input_snapshot']['checks']))
    for row in report['results']:
        identifier = row['id']
        values = parent_values(captured, row)
        audit = audit_scope(*values)
        if read(_safe(captured, row['scope_audit_file'])) != audit:
            raise ValueError('Sample scope export audit differs')
        audits[identifier] = audit
        result = select_scope(audit, *values) if select else None
        if result is not None:
            if (read(_safe(captured, row['scope_selection_file'])) != result
                    or _safe(captured, row['wire_file']).read_bytes() != canonical(result['wire']).encode('utf-8')
                    or row['metrics'] != result['metrics']):
                raise ValueError('Sample scope export selection/metrics/wire differs')
            selections[identifier] = result
        if (assess(checks, identifier, values, audit, result) != row['checks']
                or row['counts'] != audit['counts'] or row['parent_selected_counts'] != audit['parent_selected_counts']):
            raise ValueError('Sample scope captured checks/counts differ')
        parents[identifier] = {k: _safe(captured, row[k]).read_bytes() for k in PARENTS}
    if report['summary'] != summary(report['results'], select):
        raise ValueError('Sample scope captured summary differs')
    save(output, report, audits, parents, selections, read(captured / 'metadata.json'), manifest['inputs'], manifest['phase'])
    return dict(report['summary'])
