"""Frozen local condition-link experiment with exact parent preservation."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from app.evaluation.source_context_packet_run import read, validate_tac
from app.evaluation.source_origin_run import CODE as PARENT_CODE
from app.evaluation.source_origin_run import FILES as PARENT_FILES
from app.evaluation.source_origin_run import values
from app.generation.condition_applicability import VERSION, audit_applicability
from app.generation.source_origin import VERSION as PARENT_VERSION
from app.generation.source_origin import audit_origin
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.sources import file_hash

CODE = (*PARENT_CODE, 'app/generation/condition_applicability.py', 'app/evaluation/condition_applicability_run.py',
    'scripts/condition_applicability.py', 'tests/unit/test_condition_applicability.py',
    'docs/records/condition_applicability_protocol_v0.1.md')
FILES = (*PARENT_FILES, 'origin_file')
PREPARED = 'prepared_before_condition_applicability_outcomes'
CAPTURED = 'offline_condition_applicability_audit'


def assess(checks: dict[str, Any], identifier: str, origin: dict[str, Any],
           audit: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if (checks['version'] != 'condition_applicability_checks_v0.1'
            or checks['origin'] != 'assistant_source_development_before_new_applicability_outcomes'
            or checks['independent_human_confirmation'] is not False):
        raise ValueError('Applicability reference version/origin differs')
    if not checks['cases'] or len({c['id'] for c in checks['cases']}) != len(checks['cases']):
        raise ValueError('Applicability reference identities empty/duplicated')
    events = {e['event_id']: e for row in origin['rows'] for e in row['events']}
    rows = []
    for case in checks['cases']:
        if case['task_id'] != identifier:
            continue
        kind = case['kind']
        if kind == 'event_diagnostic':
            event = events.get(case['event_id'])
            if event is None or event['context'] != case['context']:
                raise ValueError('Applicability reference differs from exact original event')
            if not case['expected'] or set(case['expected']) - {'condition_roles', 'link_states', 'sample_identity_state'}:
                raise ValueError('Unsupported/empty applicability expectations')
        elif kind != 'unchanged_source_and_refusals':
            raise ValueError('Unsupported applicability reference kind')
        if audit is None:
            continue
        if kind == 'unchanged_source_and_refusals':
            passed = (not audit['selection_changed'] and not audit['network_ready']
                and audit['wire_sha256_unchanged'] == origin['wire_sha256_unchanged']
                and audit['blocking_reasons'] == origin['blocking_reasons'])
        else:
            event = next(e for row in audit['rows'] for e in row['events'] if e['event_id'] == case['event_id'])
            observed = {'condition_roles': sorted(h['kind'] for h in event['inventory']['conditions']),
                'link_states': sorted(link['state'] for link in event['links']),
                'sample_identity_state': event['inventory']['sample_identity_state']}
            passed = all(observed[k] == v for k, v in case['expected'].items())
        rows.append({'id': case['id'], 'kind': kind, 'passed': passed})
    return rows


def prepare(parent: Path, checks_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(parent, PARENT_VERSION, Path.cwd())
    if manifest['phase'] != 'offline_source_origin_audit':
        raise ValueError('Applicability requires complete frozen stage43 results')
    report, checks = read(parent / 'report.json'), read(checks_path)
    rows = report['results']
    if (checks['parent_report_sha256'] != file_hash(parent / 'report.json') or len(rows) != 4
            or len({r['id'] for r in rows}) != 4 or {c['task_id'] for c in checks['cases']} != {r['id'] for r in rows}):
        raise ValueError('Applicability parent identity/four-question scope differs')
    ids: set[str] = set()
    for row in rows:
        for key in FILES:
            path = _safe(parent, row[key])
            if bindings.get(str(path)) != file_hash(path):
                raise ValueError('Applicability input is not frozen')
        assess(checks, row['id'], read(_safe(parent, row['origin_file'])))
        diagnostic = read(_safe(parent, row['diagnostics_file']))
        ids.update(e['article_id'] for e in diagnostic['parent']['preparation']['baseline']['evidence'])
    validate_tac(read(parent / 'metadata.json'), ids)
    bindings[str(checks_path.resolve())] = file_hash(checks_path)
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'parent': str(parent.resolve()),
        'checks': str(checks_path.resolve()), 'rows': rows})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings, 'code': code,
        'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(rows), 'development_cases': len(checks['cases']), 'new_applicability_outcomes': 0}


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {'questions': len(rows), 'checks': sum(len(r['checks']) for r in rows),
        'checks_passed': sum(c['passed'] for r in rows for c in r['checks']),
        'network_ready': 0, 'model_calls': 0, 'retrieval_calls': 0, 'embedding_calls': 0,
        'database_access': False, 'selection_changed': False, 'scientific_loss_status': 'not_evaluated'}
    result.update({k: sum(r['metrics'][k] for r in rows) for k in rows[0]['metrics']})
    for field in ('selected_condition_roles', 'selected_link_states'):
        keys = sorted({k for r in rows for k in r[field]})
        result[field] = {k: sum(r[field].get(k, 0) for r in rows) for k in keys}
    return result


def render(report: dict[str, Any], audits: dict[str, Any], parents: dict[str, dict[str, bytes]]) -> str:
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))

    def detail(title: str, value: Any) -> str:
        return '<details><summary>' + esc(title) + '</summary><pre>' + esc(value) + '</pre></details>'

    cards = []
    for entry in report['results']:
        audit = audits[entry['id']]
        diagnostic = json.loads(parents[entry['id']]['diagnostics_file'])
        sources = {p['source']['region_id']: p['source'] for p in diagnostic['parent']['audit']['pages']}
        blocks = []
        for row in audit['rows']:
            source = sources[row['source']['parent_region_id']]
            uri = Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(row['source']['page'])
            blocks.append('<tr data-block data-selected="' + str(row['selected']).lower() + '"><td>' + esc(row['node_ref'])
                + ' · ' + ('selected' if row['selected'] else 'local_only') + '<br><a href="' + esc(uri) + '">PDF p.'
                + str(row['source']['page']) + '</a></td><td>' + detail('Полный исходный блок', row['text'])
                + detail('Условия, образцы, предложения связей и отказы', row['events'])
                + detail('Source identity', {k: row[k] for k in ('node_id', 'source', 'start', 'end', 'text_sha256')}) + '</td></tr>')
        links = ' · '.join('<a href="' + esc(entry[k]) + '">' + esc(k) + '</a>' for k in (*FILES, 'applicability_file'))
        cards.append('<article data-query><h2>' + esc(entry['id']) + '</h2><p>' + esc(audit['question']) + '</p><p>' + links
            + '</p>' + detail('Метрики и development checks', entry) + detail('Все прежние отказы', audit['blocking_reasons'])
            + '<p data-empty hidden>Нет соответствующих блоков; источники и отказы сохранены.</p>'
            + '<table><thead><tr><th>Блок</th><th>Точный источник и связь</th></tr></thead><tbody>' + ''.join(blocks)
            + '</tbody></table></article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE condition applicability</title>'
        '<style>body{font:15px system-ui;margin:22px;color:#18333f}table{border-collapse:collapse;width:100%;table-layout:fixed}'
        'td,th{border:1px solid #9aa;padding:8px;vertical-align:top;overflow-wrap:anywhere}th:first-child{width:23%}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        '[hidden]{display:none!important}article{border-top:2px solid #789;margin-top:24px}</style>'
        '<h1>Условия → измерение → образец: локальные предложения связей</h1><p>' + VERSION
        + '. Диапазон, шаг и точность сохраняют разные роли. Аргон подготовки не наследуется измерением. '
        'Generic sample — только класс; scientific applicability не установлена. Отбор и допуск не менялись.</p>'
        '<p><a href="metadata_review.html">TAC: все документы</a> · <a href="report.json">Report</a> · '
        '<a href="manifest.json">Manifest</a></p>' + detail('Версия, snapshot и итоги',
            {k: report[k] for k in ('version', 'input_snapshot', 'summary')})
        + '<label>Поиск <input id="q" type="search"></label> '
        '<label><input id="selected" type="checkbox"> Только ранее выбранные блоки</label> <output id="count"></output>'
        + ''.join(cards) + '<script>const q=document.getElementById("q"),s=document.getElementById("selected"),'
        'cards=[...document.querySelectorAll("[data-query]")];function filter(){let n=0,b=0;for(const card of cards){'
        'const header=(card.querySelector("h2").textContent+card.querySelector("p").textContent).toLocaleLowerCase()'
        '.includes(q.value.toLocaleLowerCase());let visible=0;for(const row of card.querySelectorAll("[data-block]")){'
        'row.hidden=(s.checked&&row.dataset.selected!=="true")||(!header&&!row.textContent.toLocaleLowerCase()'
        '.includes(q.value.toLocaleLowerCase()));if(!row.hidden){visible++;b++}}card.hidden=!visible&&!header;'
        'card.querySelector("[data-empty]").hidden=visible>0;if(!card.hidden)n++}'
        'document.getElementById("count").textContent=n+" questions / "+b+" blocks"}'
        'q.addEventListener("input",filter);s.addEventListener("change",filter);filter();</script></html>\n')


def save(output: Path, report: dict[str, Any], audits: dict[str, Any], parents: dict[str, dict[str, bytes]],
         metadata: dict[str, Any], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for row in report['results']:
        _safe(output, row['id']).mkdir()
        write_json(_safe(output, row['applicability_file']), audits[row['id']])
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
        raise ValueError('Applicability prepared code/phase differs')
    plan = read(prepared / 'plan.json')
    parent = Path(plan['parent'])
    checks = read(Path(plan['checks']))
    rows, audits, parents = [], {}, {}
    for row in plan['rows']:
        origin = read(_safe(parent, row['origin_file']))
        if origin != audit_origin(*values(parent, row)):
            raise ValueError('Applicability origin parent differs from exact reconstruction')
        audit = audit_applicability(origin)
        identifier = row['id']
        audits[identifier] = audit
        parents[identifier] = {k: _safe(parent, row[k]).read_bytes() for k in FILES}
        rows.append({'id': identifier, **{k: identifier + '/' + k + '.json' for k in FILES},
            'applicability_file': identifier + '/applicability.json', 'checks': assess(checks, identifier, origin, audit),
            **{k: audit[k] for k in ('metrics', 'selected_condition_roles', 'selected_link_states')}})
    report: dict[str, Any] = {'version': VERSION, 'results': rows, 'summary': summary(rows), 'input_snapshot': {'parent': str(parent),
        'checks': plan['checks'], 'checks_sha256': file_hash(Path(plan['checks'])),
        'parent_report_sha256': checks['parent_report_sha256']}}
    save(output, report, audits, parents, read(parent / 'metadata.json'), bindings)
    return dict(report['summary'])


def export(captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, _ = read_frozen(captured, VERSION, Path.cwd())
    report = read(captured / 'report.json')
    if (manifest['phase'] != CAPTURED or report['version'] != VERSION or report['summary'] != summary(report['results'])):
        raise ValueError('Applicability capture phase/version/summary differs')
    checks = read(Path(report['input_snapshot']['checks']))
    audits, parents = {}, {}
    for row in report['results']:
        origin = read(_safe(captured, row['origin_file']))
        if origin != audit_origin(*values(captured, row)):
            raise ValueError('Applicability captured parent differs from exact reconstruction')
        audit = audit_applicability(origin)
        if (read(_safe(captured, row['applicability_file'])) != audit or assess(checks, row['id'], origin, audit) != row['checks']
                or any(row[k] != audit[k] for k in ('metrics', 'selected_condition_roles', 'selected_link_states'))):
            raise ValueError('Applicability capture differs from exact reconstruction')
        audits[row['id']] = audit
        parents[row['id']] = {k: _safe(captured, row[k]).read_bytes() for k in FILES}
    save(output, report, audits, parents, read(captured / 'metadata.json'), manifest['inputs'])
    return dict(report['summary'])
