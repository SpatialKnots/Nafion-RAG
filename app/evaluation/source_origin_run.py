"""Freeze and replay source-origin diagnostics without any inference or selection."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from app.evaluation.sample_scope_run import CODE as PARENT_CODE
from app.evaluation.sample_scope_run import PARENTS, parent_values
from app.evaluation.source_context_packet_run import read, validate_tac
from app.generation.sample_scope import SELECTION_VERSION
from app.generation.source_origin import VERSION, audit_origin
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.sources import file_hash

CODE = (*PARENT_CODE, 'app/generation/source_origin.py', 'app/evaluation/source_origin_run.py',
    'scripts/source_origin.py', 'tests/unit/test_source_origin.py', 'docs/records/source_origin_protocol_v0.1.md')
FILES = (*PARENTS, 'scope_audit_file', 'scope_selection_file', 'wire_file')
PREPARED = 'prepared_before_source_origin_outcomes'
CAPTURED = 'offline_source_origin_audit'


def values(root: Path, row: dict[str, Any]) -> tuple[Any, ...]:
    old, packet, diagnostic, completeness = parent_values(root, row)
    return (read(_safe(root, row['scope_selection_file'])), read(_safe(root, row['scope_audit_file'])),
        old, packet, diagnostic, completeness)


def checks_for(checks: dict[str, Any], identifier: str, inputs: tuple[Any, ...],
               audit: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if (checks['version'] != 'source_origin_checks_v0.1' or checks['independent_human_confirmation'] is not False
            or checks['origin'] != 'assistant_source_development_before_new_origin_outcomes'):
        raise ValueError('Source origin reference version/origin differs')
    if not checks['cases'] or len({c['id'] for c in checks['cases']}) != len(checks['cases']):
        raise ValueError('Source origin reference cases empty or duplicated')
    selection, _, _, _, diagnostic, _ = inputs
    nodes = {n['node_id']: n for n in diagnostic['wire']['nodes']}
    results = []
    for case in checks['cases']:
        if case['task_id'] != identifier:
            continue
        kind = case['kind']
        if kind not in ('block_diagnostic', 'unchanged_selection_and_refusals'):
            raise ValueError('Unsupported source origin development check')
        if kind == 'block_diagnostic':
            source = case['source']
            node = nodes.get(source['node_id'])
            if node is None or any(node[k] != source[k] for k in ('text', 'start', 'end', 'text_sha256')):
                raise ValueError('Source origin reference differs from exact source block')
            allowed = {'section_kind', 'event_origin_state', 'procedure_role', 'retained', 'all_applicability_unknown'}
            if not case['expected'] or set(case['expected']) - allowed:
                raise ValueError('Source origin reference has unsupported/empty expectations')
        if audit is None:
            continue
        if kind == 'unchanged_selection_and_refusals':
            passed = (not audit['selection_changed'] and not audit['network_ready']
                and audit['wire_sha256_unchanged'] == selection['wire_sha256']
                and audit['blocking_reasons'] == selection['blocking_reasons'])
        else:
            row = next(r for r in audit['rows'] if r['node_id'] == case['source']['node_id'])
            observed = {'section_kind': row['section_hint']['kind'],
                'event_origin_state': sorted({e['origin_state'] for e in row['events']}),
                'procedure_role': sorted({e['procedure_role'] for e in row['events']}),
                'retained': row['selected'], 'all_applicability_unknown': all(
                    e['own_work_origin'] == e['sample_identity'] == e['per_result_applicability'] == 'not_established'
                    and not e['cross_event_field_inheritance'] for e in row['events'])}
            passed = all(observed[k] == v for k, v in case['expected'].items())
        results.append({'id': case['id'], 'kind': kind, 'passed': passed})
    return results


def prepare(parent: Path, checks_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(parent, SELECTION_VERSION, Path.cwd())
    if manifest['phase'] != 'offline_sample_scope_selection':
        raise ValueError('Source origin requires complete frozen stage42 results')
    report, checks = read(parent / 'report.json'), read(checks_path)
    rows = report['results']
    if (checks['parent_report_sha256'] != file_hash(parent / 'report.json') or len(rows) != 4
            or len({r['id'] for r in rows}) != 4 or {c['task_id'] for c in checks['cases']} != {r['id'] for r in rows}):
        raise ValueError('Source origin parent identity/four-question scope differs')
    ids: set[str] = set()
    for row in rows:
        for key in FILES:
            path = _safe(parent, row[key])
            if bindings.get(str(path)) != file_hash(path):
                raise ValueError('Source origin references an unfrozen parent')
        inputs = values(parent, row)
        checks_for(checks, row['id'], inputs)
        ids.update(e['article_id'] for e in inputs[4]['parent']['preparation']['baseline']['evidence'])
    validate_tac(read(parent / 'metadata.json'), ids)
    bindings[str(checks_path.resolve())] = file_hash(checks_path)
    code = {str(Path(p).resolve()): file_hash(Path(p)) for p in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'parent': str(parent.resolve()),
        'checks': str(checks_path.resolve()), 'rows': rows})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings, 'code': code,
        'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(rows), 'development_cases': len(checks['cases']), 'new_origin_outcomes': 0}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {'questions': len(rows), 'checks': sum(len(r['checks']) for r in rows),
        'checks_passed': sum(c['passed'] for r in rows for c in r['checks']),
        'selection_changed': False, 'scientific_loss_status': 'not_evaluated', 'network_ready': 0,
        'model_calls': 0, 'embedding_calls': 0, 'retrieval_calls': 0, 'database_access': False}
    result.update({k: sum(r['metrics'][k] for r in rows) for k in ('blocks', 'selected_blocks', 'events', 'selected_events')})
    for key in ('selected_section_hints', 'selected_origin_states', 'selected_procedure_roles'):
        keys = sorted({k for r in rows for k in r[key]})
        result[key] = {k: sum(r[key].get(k, 0) for r in rows) for k in keys}
    return result


def render(report: dict[str, Any], audits: dict[str, Any], parents: dict[str, dict[str, bytes]]) -> str:
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))

    def detail(title: str, value: Any) -> str:
        return '<details><summary>' + esc(title) + '</summary><pre>' + esc(value) + '</pre></details>'

    cards = []
    for result in report['results']:
        identifier = result['id']
        audit = audits[identifier]
        diagnostic = json.loads(parents[identifier]['diagnostics_file'])
        sources = {p['source']['region_id']: p['source'] for p in diagnostic['parent']['audit']['pages']}
        blocks = []
        for row in audit['rows']:
            source = sources[row['source']['parent_region_id']]
            uri = Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(row['source']['page'])
            blocks.append('<tr data-block data-selected="' + str(row['selected']).lower() + '"><td>'
                + esc(row['node_ref']) + ' · ' + ('selected' if row['selected'] else 'local_only') + '<br>'
                + esc(row['section_hint']['kind']) + '<br><a href="' + esc(uri) + '">PDF p.'
                + str(row['source']['page']) + '</a></td><td>' + detail('Полный исходный блок', row['text'])
                + detail('Заголовок: только геометрическое предложение', row['section_hint'])
                + detail('Все события, origin cues и неизменённые guards', row['events'])
                + detail('Точная source identity', {k: row[k] for k in ('node_id', 'source', 'start', 'end', 'text_sha256')})
                + '</td></tr>')
        links = ' · '.join('<a href="' + esc(result[k]) + '">' + esc(k) + '</a>' for k in (*FILES, 'origin_file'))
        cards.append('<article data-query><h2>' + esc(identifier) + '</h2><p>' + esc(audit['question']) + '</p><p>'
            + links + '</p>' + detail('Результат, counters и development checks', result)
            + detail('Все прежние отказы сохранены', audit['blocking_reasons'])
            + '<p data-empty hidden>Нет соответствующих блоков; прежние отказы и полные источники сохранены.</p>'
            + '<table><thead><tr><th>Блок / proposal</th><th>Источник и диагностика</th></tr></thead><tbody>'
            + ''.join(blocks) + '</tbody></table></article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE source origin audit</title>'
        '<style>body{font:15px system-ui;margin:22px;color:#18333f}table{border-collapse:collapse;width:100%;table-layout:fixed}'
        'td,th{border:1px solid #9aa;padding:8px;vertical-align:top;overflow-wrap:anywhere}'
        'th:first-child{width:23%}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        'article{border-top:2px solid #789;margin-top:24px}[hidden]{display:none!important}</style>'
        '<h1>Происхождение и применимость: локальный аудит</h1><p>' + VERSION + '. '
        'Заголовок и цитата не подтверждают own-work origin. Sample identity и applicability не установлены. '
        'Подготовка не наследуется измерением; отбор и допуск не менялись.</p><p>'
        '<a href="metadata_review.html">TAC: все документы</a> · <a href="report.json">Report</a> · '
        '<a href="manifest.json">Manifest</a></p>' + detail('Версия, snapshot и итоги',
            {k: report[k] for k in ('version', 'input_snapshot', 'summary')})
        + '<label>Поиск <input id="q" type="search"></label> '
        '<label><input id="selected" type="checkbox"> Только ранее выбранные блоки</label> <output id="count"></output>'
        + ''.join(cards) + '<script>const q=document.getElementById("q"),s=document.getElementById("selected"),'
        'cards=[...document.querySelectorAll("[data-query]")];function filter(){let n=0,b=0;'
        'for(const card of cards){let visible=0;const header=(card.querySelector("h2").textContent+'
        'card.querySelector("p").textContent).toLocaleLowerCase().includes(q.value.toLocaleLowerCase());'
        'for(const row of card.querySelectorAll("[data-block]")){'
        'row.hidden=(s.checked&&row.dataset.selected!=="true")||(!header&&!row.textContent.toLocaleLowerCase()'
        '.includes(q.value.toLocaleLowerCase()));'
        'if(!row.hidden){visible++;b++}}card.hidden=!visible&&!header;'
        'card.querySelector("[data-empty]").hidden=visible>0;if(!card.hidden)n++}'
        'document.getElementById("count").textContent=n+" questions / "+b+" blocks"}'
        'q.addEventListener("input",filter);s.addEventListener("change",filter);filter();</script></html>\n')


def save(output: Path, report: dict[str, Any], audits: dict[str, Any], parents: dict[str, dict[str, bytes]],
         metadata: dict[str, Any], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for row in report['results']:
        _safe(output, row['id']).mkdir()
        write_json(_safe(output, row['origin_file']), audits[row['id']])
        for key in FILES:
            _safe(output, row[key]).write_bytes(parents[row['id']][key])
    write_json(output / 'report.json', report)
    write_json(output / 'metadata.json', metadata)
    (output / 'review.html').write_text(render(report, audits, parents), encoding='utf-8', newline='\n')
    (output / 'metadata_review.html').write_text(render_metadata(metadata).replace('href="report.json"',
        'href="metadata.json"', 1), encoding='utf-8', newline='\n')
    verify_hashes(bindings)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': CAPTURED, 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})


def run(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != PREPARED or manifest['code'] != {str(Path(p).resolve()): file_hash(Path(p)) for p in CODE}:
        raise ValueError('Source origin prepared code/phase differs')
    plan = read(prepared / 'plan.json')
    parent = Path(plan['parent'])
    checks = read(Path(plan['checks']))
    rows, audits, parents = [], {}, {}
    for row in plan['rows']:
        identifier = row['id']
        inputs = values(parent, row)
        audit = audit_origin(*inputs)
        audits[identifier] = audit
        parents[identifier] = {k: _safe(parent, row[k]).read_bytes() for k in FILES}
        rows.append({'id': identifier, **{k: identifier + '/' + k + '.json' for k in FILES},
            'origin_file': identifier + '/origin.json', 'checks': checks_for(checks, identifier, inputs, audit),
            **{k: audit[k] for k in ('metrics', 'selected_section_hints', 'selected_origin_states', 'selected_procedure_roles')}})
    report: dict[str, Any] = {'version': VERSION, 'summary': summarize(rows), 'results': rows,
        'input_snapshot': {'parent': str(parent), 'parent_report_sha256': checks['parent_report_sha256'],
            'checks': plan['checks'], 'checks_sha256': file_hash(Path(plan['checks']))}}
    save(output, report, audits, parents, read(parent / 'metadata.json'), bindings)
    return dict(report['summary'])


def export(captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, _ = read_frozen(captured, VERSION, Path.cwd())
    report = read(captured / 'report.json')
    if (manifest['phase'] != CAPTURED or report['version'] != VERSION
            or report['summary'] != summarize(report['results'])):
        raise ValueError('Source origin capture phase/version/summary differs')
    audits, parents = {}, {}
    checks = read(Path(report['input_snapshot']['checks']))
    for row in report['results']:
        identifier = row['id']
        inputs = values(captured, row)
        audit = audit_origin(*inputs)
        if (audit != read(_safe(captured, row['origin_file']))
                or checks_for(checks, identifier, inputs, audit) != row['checks']
                or any(audit[k] != row[k] for k in
                    ('metrics', 'selected_section_hints', 'selected_origin_states', 'selected_procedure_roles'))):
            raise ValueError('Source origin capture differs from exact frozen reconstruction')
        audits[identifier] = audit
        parents[identifier] = {k: _safe(captured, row[k]).read_bytes() for k in FILES}
    save(output, report, audits, parents, read(captured / 'metadata.json'), manifest['inputs'])
    return dict(report['summary'])
