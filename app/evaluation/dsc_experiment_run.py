"""Offline frozen experiment artifacts and explicitly offline response inspection."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.evaluation import dsc_admission_run as admission_run
from app.evaluation import dsc_context_run as context_run
from app.evaluation.evidence_gaps_run import runtime
from app.generation.dsc_admission import VERSION as ADMISSION_VERSION
from app.generation.dsc_admission import assess
from app.generation.dsc_experiment import (
    SYSTEM,
    VERSION,
    contract,
    guard_request,
    inspect_response,
    parse_unique_json,
    payload,
    request,
    result_template,
)
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import SourceRegion, text_hash
from app.records.sources import file_hash

PREPARED = 'prepared_before_offline_experiment_contract_checks'
CAPTURED = 'offline_frozen_dsc_experiment'
CODE = ('app/generation/dsc_experiment.py', 'app/evaluation/dsc_experiment_run.py', 'scripts/dsc_experiment.py',
    'tests/unit/test_dsc_experiment.py', 'docs/records/dsc_experiment_protocol_v0.1.md',
    'app/records/protocol_association_run.py', 'app/records/openai_backend.py', 'pyproject.toml')


def admitted(root: Path) -> tuple[dict[str, Any], dict[str, Any], list[SourceRegion], dict[str, str]]:
    manifest, bindings = read_frozen(root, ADMISSION_VERSION, Path.cwd())
    if manifest['phase'] != admission_run.CAPTURED:
        raise ValueError('DSC experiment requires frozen stage48 source admission')
    report, plan = context_run.read(root / 'report.json'), context_run.read(root / 'plan.json')
    source_plan, wire, sources, _ = admission_run.read_packet(Path(plan['parent']))
    current = assess(wire, sources, source_plan)
    for key, value in current.items():
        actual = report[key]
        if key == 'summary':
            actual = {k: actual[k] for k in value}
        if actual != value:
            raise ValueError('DSC source admission differs from exact reconstruction')
    if (not current['source_packet_eligible_for_frozen_experiment'] or current['current_source_blocking_reasons']
            or not all(report['development_checks'].values())):
        raise ValueError('DSC source packet lacks required source admission')
    return source_plan, wire, sources, bindings


def template(frozen: dict[str, Any]) -> dict[str, Any]:
    return result_template() | {'request_sha256': frozen['request_sha256'],
        'contract_sha256': text_hash(payload(frozen).decode('utf-8'))}


def prepare(parent: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    source_plan, wire, sources, bindings = admitted(parent)
    frozen = contract(wire, sources, source_plan)
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'parent': str(parent.resolve()), 'runtime': runtime(),
        'admission_report_sha256': file_hash(parent / 'report.json'), 'source_wire_sha256': frozen['source_wire_sha256']})
    write_json(output / 'contract.json', frozen)
    (output / 'request.json').write_bytes(payload(request(wire)))
    write_json(output / 'result_template.json', template(frozen))
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings, 'code': code,
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return {'questions': 1, 'future_maximum_calls': 1, 'model_calls': 0, 'network_ready': False}


def load(root: Path, phase: str) -> tuple[dict[str, Any], dict[str, Any], list[SourceRegion], dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(root, VERSION, Path.cwd())
    if manifest['phase'] != phase:
        raise ValueError('DSC experiment input phase differs')
    if phase == PREPARED and manifest['code'] != {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('DSC experiment prepared code inventory differs')
    plan = context_run.read(root / 'plan.json')
    parent = Path(plan['parent'])
    source_plan, wire, sources, _ = admitted(parent)
    frozen = contract(wire, sources, source_plan)
    if (plan['runtime'] != runtime() or plan['admission_report_sha256'] != file_hash(parent / 'report.json')
            or plan['source_wire_sha256'] != frozen['source_wire_sha256']
            or context_run.read(root / 'contract.json') != frozen
            or context_run.read(root / 'result_template.json') != template(frozen)):
        raise ValueError('DSC experiment frozen contract/source/runtime differs')
    guard_request((root / 'request.json').read_bytes(), wire, sources, source_plan)
    return plan, wire, sources, frozen, bindings


def render(frozen: dict[str, Any], report: dict[str, Any], result: dict[str, Any]) -> str:
    esc, detail = context_run.esc, context_run.detail
    sections = [('budget', 'Бюджет и модель', {'model_alias': frozen['model_alias'], 'budget': frozen['budget'],
        'compatibility': frozen['provider_compatibility']}), ('request', 'Полный запрос и prompt', report['request']),
        ('evaluation', 'Схема ответа и критерии', {'reply_schema': frozen['reply_schema'], 'evaluation': frozen['evaluation']}),
        ('result_template', 'Результаты и ошибки: только шаблон', {'template': result,
            'artifacts': frozen['required_execution_artifacts'], 'rules': frozen['execution_record_rules']})]
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>ARIADNE — frozen DSC experiment</title><style>body{font:16px system-ui;margin:24px;color:#18333f}'
        'section{border-top:2px solid #789;margin-top:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
        'max-height:65vh;overflow:auto}[hidden]{display:none!important}input{padding:8px;min-width:40%}</style>'
        '<h1>Контракт DSC-эксперимента</h1><p>' + VERSION + ' · ' + esc(frozen['question'])
        + '</p><p data-state>Контракт зафиксирован локально. API не вызывался; model_calls=0, network_ready=false.</p>'
        '<p>Доступность alias, поддержка нового reply schema и стоимость не проверены у провайдера. '
        'Научная корректность не установлена. Реальная отправка — отдельный пункт 4.</p>'
        '<p><a href="contract.json">Contract</a> · <a href="request.json">Точные bytes запроса</a> · '
        '<a href="result_template.json">Неисполненный result template</a> · <a href="reply_schema.json">Reply schema</a> · '
        '<a href="admission/review.html">Предыдущий source admission</a> · '
        '<a href="admission/packet/review.html">Source packet и PDF</a> · '
        '<a href="admission/packet/metadata_review.html">TAC</a> · <a href="manifest.json">Manifest</a></p>'
        + detail('Итоги, snapshot и hashes', {k: v for k, v in report.items() if k != 'request'})
        + '<label>Поиск <input id="q" type="search"></label>'
        + ''.join('<section data-section="' + key + '"><h2>' + title + '</h2>' + detail('Полное содержимое', value)
            + '</section>' for key, title, value in sections)
        + '<script>document.getElementById("q").addEventListener("input",e=>{for(const s of document.querySelectorAll("[data-section]"))'
        's.hidden=!s.textContent.toLocaleLowerCase().includes(e.target.value.toLocaleLowerCase())});</script></html>\n')


def execute(root: Path, output: Path, *, export: bool = False) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    phase = CAPTURED if export else PREPARED
    plan, wire, _, frozen, bindings = load(root, phase)
    manifest = context_run.read(root / 'manifest.json')
    report: dict[str, Any] = {'version': VERSION, 'input_snapshot': plan, 'request': request(wire),
        'summary': {'contract_ready_offline': True, 'request_bytes': frozen['request_bytes'],
            'future_maximum_calls': frozen['budget']['maximum_transport_attempts'],
            'max_output_tokens': frozen['budget']['max_output_tokens_per_attempt'], 'model_alias': frozen['model_alias'],
            'automatic_retries': 0, 'model_fallbacks': 0, 'model_calls': 0, 'network_ready': False,
            'provider_compatibility': 'not_live_verified', 'scientific_acceptance': 'not_evaluated'}}
    if export and context_run.read(root / 'report.json') != report:
        raise ValueError('DSC experiment report differs from exact reconstruction')
    output.mkdir(parents=True, exist_ok=False)
    for name in ('plan.json', 'contract.json', 'request.json', 'result_template.json'):
        (output / name).write_bytes((root / name).read_bytes())
    write_json(output / 'report.json', report)
    write_json(output / 'reply_schema.json', frozen['reply_schema'])
    (output / 'system_prompt.txt').write_text(SYSTEM, encoding='utf-8', newline='\n')
    (output / 'review.html').write_text(render(frozen, report, template(frozen)), encoding='utf-8', newline='\n')
    parent = Path(plan['parent'])
    for name in (*context_run.read(parent / 'manifest.json')['outputs'], 'manifest.json'):
        target = _safe(output / 'admission', name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_safe(parent, name).read_bytes())
    saved = manifest['inputs'] if export else bindings
    verify_hashes(saved)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': CAPTURED, 'inputs': saved, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})
    return dict(report['summary'])


def inspect_offline(root: Path, response: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError('Offline response inspection must not add files inside the frozen experiment')
    _, wire, sources, _, bindings = load(root, CAPTURED)
    raw = response.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if file_hash(response) != digest:
        raise ValueError('Offline response changed while reading')
    bindings[str(response.resolve())] = digest
    output.mkdir(parents=True, exist_ok=False)
    (output / 'request.json').write_bytes((root / 'request.json').read_bytes())
    (output / 'response.bin').write_bytes(raw)
    result: dict[str, Any] = {'origin': 'offline_supplied_response', 'model_calls_by_this_tool': 0,
        'original_transport_attempts': 'unknown_not_inferred_from_response', 'response_sha256': digest,
        'scientific_acceptance': 'not_evaluated'}
    metadata: dict[str, Any] = {}
    try:
        envelope = parse_unique_json(raw)
        if not isinstance(envelope, dict):
            raise ValueError('Offline Responses envelope must be an object')
        metadata = {k: envelope.get(k) for k in ('id', 'model', 'usage', 'service_tier', 'status')}
        inspected = inspect_response(raw, wire, sources)
        write_json(output / 'reply.json', inspected['reply'])
        write_json(output / 'resolved.json', inspected['resolved'])
        result.update(status='offline_integrity_valid', evaluation=inspected['evaluation'])
    except ValueError as exc:
        result.update(status='offline_response_invalid', error_type=type(exc).__name__, error=str(exc),
            stage='completion_schema_or_source_integrity')
    write_json(output / 'response_metadata.json', metadata)
    write_json(output / 'result.json', result)
    verify_hashes(bindings)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_supplied_response_inspection',
        'inputs': bindings, 'code': {}, 'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return result
