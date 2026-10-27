"""Frozen offline admission of the new DSC packet, preserving all old decisions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.evaluation import dsc_context_run as parent_run
from app.evaluation.evidence_gaps_run import runtime
from app.generation.dsc_admission import VERSION, assess
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash

PREPARED = 'prepared_before_dsc_source_admission'
CAPTURED = 'offline_dsc_source_admission'
CODE = ('app/generation/dsc_admission.py', 'app/evaluation/dsc_admission_run.py', 'scripts/dsc_admission.py',
    'tests/unit/test_dsc_admission.py', 'docs/records/dsc_admission_protocol_v0.1.md',
    'app/evaluation/dsc_context_run.py', 'app/generation/query_qualifiers.py', 'pyproject.toml')


def read_packet(root: Path) -> tuple[dict[str, Any], dict[str, Any], list[SourceRegion], dict[str, str]]:
    manifest, bindings = read_frozen(root, parent_run.VERSION, Path.cwd())
    if manifest['phase'] != parent_run.CAPTURED:
        raise ValueError('DSC source admission requires a captured stage47 packet')
    plan = parent_run.read(root / 'plan.json')
    current, _ = parent_run.load_source(Path(plan['parent']))
    if current != {k: v for k, v in plan.items() if k != 'runtime'} or plan['runtime'] != runtime():
        raise ValueError('DSC source admission parent plan/runtime differs')
    wire, sources, report = parent_run.build(plan)
    if any(parent_run.read(root / name) != value for name, value in (
            ('wire.json', wire), ('sources.json', [s.model_dump(mode='json') for s in sources]), ('report.json', report))):
        raise ValueError('DSC source admission packet differs from exact reconstruction')
    return plan, wire, sources, bindings


def prepare(parent: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    _, _, _, bindings = read_packet(parent)
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'parent': str(parent.resolve()), 'runtime': runtime(),
        'parent_wire_sha256': file_hash(parent / 'wire.json'),
        'development_expectations': {'origin': 'exposed_source_development_not_independent_gold',
            'source_packet_eligible_for_frozen_experiment': True, 'network_ready': False,
            'historical_blockers_preserved': True}})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings, 'code': code,
        'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': 1, 'new_admission_outcomes': 0, 'network_ready': False}


def render(report: dict[str, Any]) -> str:
    esc, detail = parent_run.esc, parent_run.detail
    rows = ['<tr data-check><td>' + esc(c['id']) + '</td><td>' + ('passed' if c['passed'] else 'blocked')
        + '</td><td>' + detail('Проверенные source spans и границы утверждения', c['evidence']) + '</td></tr>'
        for c in report['checks']]
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>ARIADNE — допуск DSC-пакета</title><style>body{font:16px system-ui;margin:24px;color:#18333f}'
        'table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #9aa;padding:10px;'
        'vertical-align:top;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}'
        '[hidden]{display:none!important}input{padding:8px;min-width:40%}</style><h1>Допуск нового DSC-пакета</h1><p>'
        + VERSION + ' · ' + esc(report['question']) + '</p><p data-source-status>Пригодность исходного пакета для '
        'подготовки frozen-эксперимента: ' + esc(report['source_packet_status']) + '</p>'
        '<p data-network-status>Сетевая отправка запрещена: network_ready=false. Это не научная приёмка и не разрешение API.</p>'
        '<p><a href="packet/review.html">Неизменённый пакет и PDF-ссылки</a> · '
        '<a href="packet/metadata_review.html">TAC: документ стадии</a> · <a href="packet/wire.json">Точный wire</a> · '
        '<a href="report.json">Report</a> · <a href="manifest.json">Manifest</a></p>'
        + detail('Версия и input snapshot', report['input_snapshot']) + detail('Итоги и development expectations', report['summary'])
        + detail('Текущие source blockers', report['current_source_blocking_reasons'])
        + detail('Прежние отказы: история, не перезаписана', report['historical_blocking_reasons'])
        + detail('Отдельные запреты исполнения', report['execution']) + detail('Научные ограничения', report['limitations'])
        + '<label>Поиск <input id="q" type="search"></label><table><thead><tr><th>Проверка</th><th>Результат</th>'
        '<th>Evidence / диагностика</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
        '<script>document.getElementById("q").addEventListener("input",e=>{for(const r of document.querySelectorAll("[data-check]"))'
        'r.hidden=!r.textContent.toLocaleLowerCase().includes(e.target.value.toLocaleLowerCase())});</script></html>\n')


def execute(root: Path, output: Path, *, export: bool = False) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(root, VERSION, Path.cwd())
    if manifest['phase'] != (CAPTURED if export else PREPARED):
        raise ValueError('DSC source admission input phase differs')
    if not export and manifest['code'] != {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Prepared DSC source admission code inventory differs')
    plan = parent_run.read(root / 'plan.json')
    parent = Path(plan['parent'])
    source_plan, wire, sources, _ = read_packet(parent)
    if plan['runtime'] != runtime() or plan['parent_wire_sha256'] != file_hash(parent / 'wire.json'):
        raise ValueError('DSC source admission frozen runtime/wire drift')
    report = assess(wire, sources, source_plan)
    expected = plan['development_expectations']
    checks = {'source_eligibility': report['source_packet_eligible_for_frozen_experiment'] ==
        expected['source_packet_eligible_for_frozen_experiment'],
        'network_prohibition': report['execution']['network_ready'] == expected['network_ready'],
        'historical_blockers_preserved': report['historical_blocking_reasons'] == source_plan['historical_blocking_reasons']}
    report.update(input_snapshot={'parent': str(parent), 'parent_wire_sha256': plan['parent_wire_sha256'],
        'runtime': plan['runtime'], 'expectation_origin': expected['origin']}, development_checks=checks)
    report['summary'].update(development_checks=len(checks), development_checks_passed=sum(checks.values()))
    if export and parent_run.read(root / 'report.json') != report:
        raise ValueError('DSC source admission result differs from exact reconstruction')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', plan)
    write_json(output / 'report.json', report)
    (output / 'review.html').write_text(render(report), encoding='utf-8', newline='\n')
    for name in (*parent_run.read(parent / 'manifest.json')['outputs'], 'manifest.json'):
        target = _safe(output / 'packet', name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_safe(parent, name).read_bytes())
    saved_bindings = manifest['inputs'] if export else bindings
    verify_hashes(saved_bindings)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': CAPTURED, 'inputs': saved_bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})
    return dict(report['summary'])
