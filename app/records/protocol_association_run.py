"""Frozen bounded API comparison with exact source-sentence restoration and offline replay."""

from __future__ import annotations

import html
import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from app.evaluation.context_compaction import SourcePage, require_no_complete_pages
from app.records.condition_multilingual import VERSION as PARENT_VERSION
from app.records.condition_multilingual_export import execute_comparison
from app.records.condition_transfer import block_source
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import verify_hashes
from app.records.openai_backend import ENDPOINT, responses_content, send_openai_request
from app.records.protocol_association import VERSION, AssociationReply, local_baseline, messages, parse_reply, resolve_reply, validate_case
from app.records.schema import SourceRegion
from app.records.sources import file_hash

MODEL = 'gpt-6-astra'
MAX_CALLS = 5
MAX_OUTPUT = 4096
TIMEOUT = 180
MAX_BYTES = 100000
CODE = ('app/records/protocol_association.py', 'app/records/protocol_association_run.py',
        'scripts/records_protocol_association.py', 'tests/unit/test_record_protocol_association.py',
        'docs/records/protocol_association_protocol_v0.1.md')
SUPPORT = ('app/records/openai_backend.py', 'app/evaluation/context_compaction.py', 'app/generation/providers.py')


def request(case: dict[str, Any]) -> dict[str, Any]:
    return {'model': MODEL, 'input': messages(case), 'reasoning': {'effort': 'medium'},
            'max_output_tokens': MAX_OUTPUT, 'store': False, 'stream': False, 'truncation': 'disabled', 'service_tier': 'default',
            'text': {'format': {'type': 'json_schema', 'name': 'protocol_association', 'strict': True,
                                'schema': AssociationReply.model_json_schema()}}}


def page_record(source: SourceRegion) -> SourcePage:
    return SourcePage(str(source.article_id), source.region_id, source.page_number, source.text_layer,
                      str(source.text_layer_id), source.page_text, source.layer_pdf_path, source.layer_pdf_sha256)


def build_cases(packet: dict[str, Any], report: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    old = packet['baseline_packet']
    expected = {r['unit_id']: r for r in report['results']}
    if len(expected) != old['inventory']['probe_units']:
        raise ValueError('Association parent lost complete transfer accounting')
    cases, pages = [], []

    def add(identifier: str, source: SourceRegion, events: list[dict[str, Any]], role: str) -> None:
        sentences = [{'id': 'S' + str(i), 'span': e['context'], 'stage27_event': e} for i, e in enumerate(events, 1)]
        case = {'case_id': identifier, 'role': role, 'source': source.model_dump(mode='json'), 'sentences': sentences,
                'target_ids': [s['id'] for s in sentences if s['stage27_event']['cues']]}
        validate_case(case)
        cases.append(case)

    for page in old['pages']:
        if page['source'] is None:
            continue
        source = SourceRegion.model_validate(page['source'])
        pages.append(asdict(page_record(source)))
        for unit in page['units']:
            result = expected[unit['unit_id']]
            if any(e['cues'] for e in result['events']):
                add(unit['unit_id'], block_source(source, unit), result['events'], 'transfer_development')
                cases[-1]['parent_page_diagnostics'] = {k: v for k, v in page.items() if k not in {'source', 'units'}}
    control = SourceRegion.model_validate(old['control_source'])
    pages.append(asdict(page_record(control)))
    add('separate_control', control, report['separate_control_events'], 'separate_control')
    if not 1 <= len(cases) <= MAX_CALLS or len({c['case_id'] for c in cases}) != len(cases):
        raise ValueError('All cue-bearing contexts plus control exceed the declared call budget or have duplicate IDs')
    return cases, pages


def guard(payload: bytes, case: dict[str, Any], pages: list[SourcePage]) -> None:
    if payload != json.dumps(request(case), ensure_ascii=False).encode('utf-8') or len(payload) > MAX_BYTES:
        raise ValueError('Association request differs from frozen source/settings or exceeds byte budget')
    require_no_complete_pages(validate_case(case).quote, pages)
    require_no_complete_pages('\n'.join(m['content'] for m in request(case)['input']), pages)


def prepare(parent: Path, output: Path, *, source_root: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(parent, PARENT_VERSION, source_root)
    if manifest['phase'] != 'executed_frozen_comparison':
        raise ValueError('Association requires executed stage27 parent')
    if not {'prepared_packet.json', 'report.json'} <= set(manifest['outputs']):
        raise ValueError('Association parent lacks required frozen artifacts')
    packet = json.loads((parent / 'prepared_packet.json').read_bytes())
    report = json.loads((parent / 'report.json').read_bytes())
    replay = execute_comparison(packet)
    if any(report[key] != replay[key] for key in replay):
        raise ValueError('Stage27 replay differs before association preparation')
    cases, raw_pages = build_cases(packet, report)
    pages = [SourcePage(**p) for p in raw_pages]
    for case in cases:
        case['local_baseline'] = local_baseline(case)
        case['request'] = request(case)
        guard(json.dumps(case['request'], ensure_ascii=False).encode('utf-8'), case, pages)
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in (*CODE, *SUPPORT)}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    plan = {'version': VERSION, 'endpoint': ENDPOINT, 'model': MODEL, 'maximum_calls': MAX_CALLS,
            'max_output_tokens_per_call': MAX_OUTPUT, 'timeout_seconds': TIMEOUT, 'cases': cases, 'pages': raw_pages,
            'selection': 'Every stage27 cue-bearing transfer block plus separate control; development-exposed, no gold.',
            'parent_inventory': packet['inventory'], 'scientific_precision': None, 'scientific_recall': None}
    write_json(output / 'plan.json', plan)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_api_calls', 'inputs': bindings,
        'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'cases': len(cases), 'targets': sum(len(c['target_ids']) for c in cases), 'maximum_calls': MAX_CALLS,
            'maximum_output_tokens': MAX_CALLS * MAX_OUTPUT, 'new_model_calls': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_api_calls' or 'plan.json' not in manifest['outputs']:
        raise ValueError('Association requires a frozen preparation')
    code = {str(Path(name).resolve()): file_hash(Path(name)) for name in (*CODE, *SUPPORT)}
    if manifest['code'] != code:
        raise ValueError('Association frozen code inventory differs')
    plan = json.loads((prepared / 'plan.json').read_bytes())
    if (plan['version'], plan['endpoint'], plan['model'], plan['maximum_calls'], plan['max_output_tokens_per_call'],
            plan['timeout_seconds']) != (VERSION, ENDPOINT, MODEL, MAX_CALLS, MAX_OUTPUT, TIMEOUT):
        raise ValueError('Association execution budget/settings changed')
    if not 1 <= len(plan['cases']) <= MAX_CALLS or len({c['case_id'] for c in plan['cases']}) != len(plan['cases']):
        raise ValueError('Association case inventory differs from call budget')
    pages = [SourcePage(**p) for p in plan['pages']]
    for case in plan['cases']:
        if local_baseline(case) != case['local_baseline']:
            raise ValueError('Association local baseline differs')
        guard(json.dumps(case['request'], ensure_ascii=False).encode('utf-8'), case, pages)
    return plan, bindings


def run(prepared: Path, output: Path, *, api_key: str) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    if not api_key.strip():
        raise ValueError('Association credential unavailable; no model call')
    plan, bindings = load(prepared)
    output.mkdir(parents=True, exist_ok=False)
    rows, stopped = [], False
    for case in plan['cases']:
        row: dict[str, Any] = {'case_id': case['case_id'], 'role': case['role'], 'status': 'unattempted', 'model_calls': 0}
        rows.append(row)
        if stopped:
            continue
        directory = output / case['case_id']
        directory.mkdir()
        payload = json.dumps(case['request'], ensure_ascii=False).encode('utf-8')
        (directory / 'request.json').write_bytes(payload)
        stage, started = 'frozen_binding', time.perf_counter()
        try:
            verify_hashes(bindings)
            stage = 'transport'
            row['model_calls'] = 1
            raw, request_id = send_openai_request(payload, api_key, TIMEOUT)
            (directory / 'response.json').write_bytes(raw)
            stage = 'completion_and_source_contract'
            envelope = json.loads(raw)
            if not isinstance(envelope, dict):
                raise ValueError('Association API response root must be an object')
            row.update(request_id=request_id, returned_model=envelope.get('model'), usage=envelope.get('usage'),
                       response_status=envelope.get('status'), response_id=envelope.get('id'))
            reply = parse_reply(responses_content(raw))
            write_json(directory / 'reply.json', reply.model_dump(mode='json'))
            resolved = resolve_reply(case, reply)
            verify_hashes(bindings)
            write_json(directory / 'resolved.json', resolved)
            row.update(status='integrity_valid', resolved=resolved)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            if isinstance(exc, HTTPError):
                (directory / 'http_error_redacted.bin').write_bytes(exc.read().replace(api_key.encode(), b'<redacted>'))
            row.update(status='failed', stage=stage, error_type=type(exc).__name__, error=str(exc).replace(api_key, '<redacted>'))
            stopped = True
        row['elapsed_seconds'] = round(time.perf_counter() - started, 3)
        write_json(directory / 'result.json', row)
    verify_hashes(bindings)
    summary = {'cases': len(rows), 'model_calls': sum(r['model_calls'] for r in rows),
               'statuses': dict(Counter(r['status'] for r in rows)), 'scientific_admission': 'not_evaluated'}
    report = {'version': VERSION, 'summary': summary, 'results': rows}
    write_json(output / 'report.json', report)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'executed_bounded_api', 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})
    return summary


def export(prepared: Path, run_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    manifest, run_bindings = read_frozen(run_dir, VERSION, Path.cwd())
    if manifest['phase'] != 'executed_bounded_api':
        raise ValueError('Association export requires a bounded executed run')
    if any(name in bindings and bindings[name] != value for name, value in run_bindings.items()):
        raise ValueError('Association run/preparation bindings conflict')
    bindings.update(run_bindings)
    report = json.loads((run_dir / 'report.json').read_bytes())
    if [r['case_id'] for r in report['results']] != [c['case_id'] for c in plan['cases']]:
        raise ValueError('Association export case inventory differs')
    comparisons, cards = [], []
    for case, result in zip(plan['cases'], report['results'], strict=True):
        if result['status'] == 'integrity_valid':
            raw = (run_dir / case['case_id'] / 'response.json').read_bytes()
            actual = resolve_reply(case, parse_reply(responses_content(raw)))
            if actual != result['resolved']:
                raise ValueError('Association raw response replay differs')
            for local, proposal in zip(case['local_baseline'], actual, strict=True):
                comparisons.append({'case_id': case['case_id'], 'role': case['role'], 'target_id': local['target_id'],
                    'baseline_property': local['property_kind'], 'api_property': proposal['proposal']['property_kind'],
                    'category_agreement': local['property_kind'] == proposal['proposal']['property_kind'],
                    'scientific_correctness': 'not_evaluated'})
        source = validate_case(case)
        uri = Path(source.original_pdf_path).resolve().as_uri() + '#page=' + str(source.page_number)
        detail = {'case': case, 'result': result}
        cards.append('<article class="case"><h2>' + html.escape(case['case_id']) + ' · ' + html.escape(case['role'])
            + '</h2><a href="' + html.escape(uri, quote=True) + '">Исходный PDF, стр. ' + str(source.page_number)
            + '</a><details><summary>Полный точный блок</summary><pre>' + html.escape(source.quote)
            + '</pre></details><details><summary>Обе версии и все source references</summary><pre>'
            + html.escape(json.dumps(detail, ensure_ascii=False, indent=2)) + '</pre></details></article>')
    summary = {**report['summary'], 'raw_replayed_cases': sum(r['status'] == 'integrity_valid' for r in report['results']),
               'compared_targets': len(comparisons), 'category_agreements': sum(c['category_agreement'] for c in comparisons),
               'transfer_targets': sum(c['role'] == 'transfer_development' for c in comparisons),
               'transfer_category_agreements': sum(c['role'] == 'transfer_development' and c['category_agreement'] for c in comparisons),
               'control_targets': sum(c['role'] == 'separate_control' for c in comparisons),
               'control_category_agreements': sum(c['role'] == 'separate_control' and c['category_agreement'] for c in comparisons),
               'scientific_precision': None, 'scientific_recall': None, 'new_model_calls': 0}
    page = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — protocol association</title>'
        '<style>body{font:16px system-ui;margin:24px;max-width:1200px}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
        'max-height:65vh;overflow:auto}article{border-top:1px solid #789;padding:12px}input{padding:10px;width:65%}'
        '[hidden]{display:none!important}</style><h1>Свойство, метод и условия: development comparison</h1><p>'
        + html.escape(VERSION) + '. Source-bound proposals; не научно принятые записи. Agreement не означает accuracy. '
        'Контроль показан отдельно, исходные guards и неоднозначности сохранены.</p><pre>'
        + html.escape(json.dumps(summary, ensure_ascii=False, indent=2))
        + '</pre><a href="report.json">Отчёт JSON</a> · <a href="manifest.json">Manifest</a>'
        '<p><label>Поиск <input id="q" type="search"></label></p>' + ''.join(cards)
        + '<script>const rows=[...document.querySelectorAll("article.case")];document.getElementById("q")'
        '.addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();for(const r of rows)'
        'r.hidden=!r.textContent.toLocaleLowerCase().includes(q)});</script></html>\n')
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'report.json', {'version': VERSION, 'summary': summary, 'comparisons': comparisons, 'results': report['results']})
    (output / 'review.html').write_text(page, encoding='utf-8')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_replayed', 'inputs': bindings, 'code': {},
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return summary
