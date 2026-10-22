"""Freeze an additive RU/EN comparison against the complete stage26 packet."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.records.condition_multilingual import VERSION, source_events
from app.records.condition_transfer import VERSION as BASELINE_VERSION
from app.records.condition_transfer import block_source, execute_packet, packet_inventory
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash

CODE = ('app/records/condition_multilingual.py', 'app/records/condition_multilingual_export.py',
        'scripts/records_condition_multilingual.py', 'tests/unit/test_record_condition_multilingual.py',
        'docs/records/condition_multilingual_protocol_v0.1.md')


def prepare_comparison(baseline: Path, output: Path, *, source_root: Path) -> dict[str, Any]:
    """No policy execution or outcome inspection in this preparation phase."""
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(baseline, BASELINE_VERSION, source_root)
    if manifest['phase'] != 'executed_frozen_rules':
        raise ValueError('Multilingual comparison requires an executed frozen transfer baseline')
    for name in ('prepared_packet.json', 'report.json'):
        if name not in manifest['outputs']:
            raise ValueError('Multilingual comparison baseline is missing required frozen outputs')
    parent = json.loads((baseline / 'prepared_packet.json').read_bytes())
    if parent['version'] != BASELINE_VERSION or packet_inventory(parent) != parent['inventory']:
        raise ValueError('Multilingual baseline source inventory differs')
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in CODE}
    if set(code) & set(bindings):
        raise ValueError('New multilingual code must remain separate from frozen baseline code')
    packet = {'version': VERSION, 'baseline_packet': parent,
              'baseline_report': json.loads((baseline / 'report.json').read_bytes()),
              'inventory': parent['inventory'],
              'exposure': 'Development-exposed, including stage26 post-hoc English examples; not independent holdout.',
              'comparison_unit': 'Same complete registered block; clause/event boundaries may differ between policies.',
              'policy': {'version': VERSION, 'code': code},
              'scientific_admission': 'not_evaluated', 'new_model_calls': 0}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'packet.json', packet)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_policy_execution',
        'inputs': bindings, 'code': code, 'outputs': {'packet.json': file_hash(output / 'packet.json')}})
    return dict(packet['inventory'])


def classify(events: list[dict[str, Any]]) -> str:
    if any(e['state'] == 'scope_proposal' for e in events):
        return 'scope_proposal_observed'
    return 'cue_observed_but_withheld' if any(e['cues'] for e in events) else 'no_literal_cue'


def evaluate_source(source: SourceRegion) -> list[dict[str, Any]]:
    events = [event.model_dump(mode='json') for event in source_events(source)]
    for event in events:
        spans = [event['context'], *[c['span'] for c in event['cues']], *[g['span'] for g in event['block_guards']]]
        for span in spans:
            if (span['region_id'] != source.region_id or not source.start <= span['start'] < span['end'] <= source.end
                    or source.page_text[span['start']:span['end']] != span['text']):
                raise ValueError('Multilingual context/cue/guard differs from exact block source')
    return events


def execute_comparison(packet: dict[str, Any]) -> dict[str, Any]:
    if packet['version'] != VERSION or packet_inventory(packet['baseline_packet']) != packet['inventory']:
        raise ValueError('Multilingual version/source inventory changed')
    baseline = execute_packet(packet['baseline_packet'])
    expected = packet['baseline_report']
    if any(baseline[key] != expected[key] for key in baseline):
        raise ValueError('Stage26 baseline raw replay differs; comparison stopped')
    old = {r['unit_id']: r for r in baseline['results']}
    results, all_events = [], []
    transitions: Counter[str] = Counter()
    for page in packet['baseline_packet']['pages']:
        if page['source'] is None:
            continue
        parent = SourceRegion.model_validate(page['source'])
        for unit in page['units']:
            source = block_source(parent, unit)
            events = evaluate_source(source)
            outcome = classify(events)
            previous = old[unit['unit_id']]
            transitions[previous['outcome'] + ' -> ' + outcome] += 1
            results.append({'unit_id': unit['unit_id'], 'article_id': page['article_id'], 'page_number': page['page_number'],
                'block_region_id': source.region_id, 'baseline': previous, 'outcome': outcome, 'events': events,
                'paragraph_adequacy': 'not_established', 'per_result_applicability': 'not_established'})
            all_events.extend(events)
    if len(results) != packet['inventory']['probe_units'] or {r['unit_id'] for r in results} != set(old):
        raise ValueError('Comparison did not account for every baseline source block')
    control = evaluate_source(SourceRegion.model_validate(packet['baseline_packet']['control_source']))
    summary = {**packet['inventory'], 'executed_units': len(results), 'baseline_replay_exact': True,
        'baseline_summary': baseline['summary'], 'unit_outcomes': dict(Counter(r['outcome'] for r in results)),
        'unit_transitions': dict(transitions), 'source_events': len(all_events),
        'event_states': dict(Counter(e['state'] for e in all_events)),
        'proposed_kinds': dict(Counter(e['proposed_kind'] for e in all_events if e['proposed_kind'])),
        'cue_rules': dict(Counter(c['rule_id'] for e in all_events for c in e['cues'])),
        'guarded_units': sum(any(e['block_guards'] for e in r['events']) for r in results),
        'guard_reasons_by_unit': dict(Counter(reason for r in results for reason in
            sorted({g['reason'] for e in r['events'] for g in e['block_guards']}))),
        'separate_control_events': len(control), 'separate_control_outcome': classify(control),
        'new_measurement_records': 0, 'new_model_calls': 0, 'scientific_precision': None, 'scientific_recall': None,
        'scientific_admission': 'not_evaluated'}
    return {'version': VERSION, 'summary': summary, 'results': results, 'separate_control_events': control,
            'baseline_control_events': baseline['separate_control_events']}


def render_comparison(packet: dict[str, Any], report: dict[str, Any]) -> str:
    def detail(label: str, value: Any) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    results = {r['unit_id']: r for r in report['results']}
    documents = {d['article_id']: d for d in packet['baseline_packet']['documents']}
    rows = []
    for page in packet['baseline_packet']['pages']:
        document = documents[page['article_id']]
        uri = Path(document['original_pdf_path']).resolve().as_uri() + '#page=' + str(page['page_number'])
        cards = []
        for unit in page['units']:
            result = results[unit['unit_id']]
            cards.append('<article class="unit"><h3>Блок ' + str(unit['block_number']) + ' · '
                + html.escape(result['baseline']['outcome'] + ' → ' + result['outcome']) + '</h3>'
                + detail('Точный полный текст блока', unit['source']['text'])
                + detail('Геометрия и абсолютные координаты', unit)
                + detail('Прежние события без изменений', result['baseline'])
                + detail('Новые события, cues, guards и диагностика', result['events']) + '</article>')
        rows.append('<tr class="page"><td>' + html.escape(document['title']) + '<p>' + html.escape(document['role'])
            + '</p><a href="' + html.escape(uri, quote=True) + '">Исходный PDF, стр. ' + str(page['page_number'])
            + '</a></td><td>' + str(page['page_number'])
            + detail('Полная страница, source identities и прежняя диагностика', {k: v for k, v in page.items() if k != 'units'})
            + '</td><td>' + ''.join(cards) + ('Нет доказанных единиц; страница сохранена.' if not cards else '') + '</td></tr>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>ARIADNE — RU/EN условия, сравнение политик</title><style>body{font:15px system-ui;margin:24px;color:#18342d}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #bccbc4;padding:10px;vertical-align:top}'
        'td{max-width:70ch}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:50vh;overflow:auto}'
        'article{border-bottom:2px solid #8eaaa0}input{padding:8px;width:65%}[hidden]{display:none!important}</style>'
        '<h1>RU/EN условия: отдельное замороженное сравнение</h1><p>' + html.escape(VERSION)
        + '. Development-источники, включая ранее просмотренные English examples. Независимого эталона нет. '
        'Буквальные scope proposals не подтверждают научную связь или origin. '
        'Guards действуют на весь блок, намеренно сохраняя лишние отказы. Нет новых измерений и model calls.</p>'
        + '<pre id="summary">' + html.escape(json.dumps(report['summary'], ensure_ascii=False, indent=2)) + '</pre>'
        + detail('Версия, политика и input snapshot', {k: v for k, v in packet.items() if k not in {'baseline_packet', 'baseline_report'}})
        + '<p><a href="report.json">JSON</a> · <a href="prepared_packet.json">Замороженный пакет</a> · '
        '<a href="manifest.json">Manifest</a></p>'
        + detail('Отдельный контроль, вне transfer counts', {k: report[k] for k in ('baseline_control_events', 'separate_control_events')})
        + '<label>Поиск <input id="q" type="search"></label><p id="count"></p><table><thead><tr>'
        '<th>Документ и PDF</th><th>Страница и диагностика</th><th>Каждый блок: обе версии</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table><script>const rows=[...document.querySelectorAll("tr.page")];'
        'function filter(){const q=document.getElementById("q").value.toLocaleLowerCase();let n=0;'
        'for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++;}'
        'document.getElementById("count").textContent=n+" / "+rows.length;}'
        'document.getElementById("q").addEventListener("input",filter);filter();</script></html>\n')


def run_comparison(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_policy_execution' or 'packet.json' not in manifest['outputs']:
        raise ValueError('Multilingual comparison requires a separately frozen packet')
    raw = (prepared / 'packet.json').read_bytes()
    packet = json.loads(raw)
    code = {str(Path(name).resolve()): file_hash(Path(name)) for name in CODE}
    if packet['policy'] != {'version': VERSION, 'code': code} or manifest['code'] != code:
        raise ValueError('Frozen multilingual policy/code identity differs')
    report = execute_comparison(packet)
    report['prepared_packet_sha256'] = file_hash(prepared / 'packet.json')
    report['preparation_manifest_sha256'] = file_hash(prepared / 'manifest.json')
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'prepared_packet.json').write_bytes(raw)
    write_json(output / 'report.json', report)
    (output / 'review.html').write_text(render_comparison(packet, report), encoding='utf-8')
    verify_hashes(bindings)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'executed_frozen_comparison', 'inputs': bindings,
        'code': code, 'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return dict(report['summary'])
