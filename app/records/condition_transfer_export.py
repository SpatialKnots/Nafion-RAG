"""Freeze transfer scope before execution; preserve all raw frozen-rule outcomes."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from app.records.condition_scope import VERSION as RULE_VERSION
from app.records.condition_transfer import VERSION, build_packet, execute_packet
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import CandidateBundle, SourceRegion
from app.records.sources import file_hash

CODE = ('app/records/condition_transfer.py', 'app/records/condition_transfer_export.py', 'scripts/records_condition_transfer.py',
        'tests/unit/test_record_condition_transfer.py', 'docs/records/condition_transfer_protocol_v0.1.md')


def read_frozen(directory: Path, expected: str, source_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    path = (directory / 'manifest.json').resolve()
    manifest = json.loads(path.read_bytes())
    if manifest['version'] != expected:
        raise ValueError('Unsupported frozen transfer input version')
    bindings = {str(Path(name).resolve()): value for name, value in manifest['inputs'].items()}
    bindings[str(path)] = file_hash(path)
    for name, value in manifest['code'].items():
        code_path = Path(name) if Path(name).is_absolute() else source_root / name
        bindings[str(code_path.resolve())] = value
    for name, value in manifest['outputs'].items():
        bindings[str(_safe(directory, name))] = value
    verify_hashes(bindings)
    return manifest, bindings


def prepare_transfer(scope_dir: Path, windows_dir: Path, stage25: Path, output: Path, *, source_root: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    bindings: dict[str, str] = {}
    for directory, expected in ((scope_dir, 'records_article_scope_v0.1'), (windows_dir, 'records_article_windows_v0.1'),
                                (stage25, RULE_VERSION)):
        _, additions = read_frozen(directory, expected, source_root)
        if any(name in bindings and bindings[name] != value for name, value in additions.items()):
            raise ValueError('Conflicting frozen source/code bindings')
        bindings.update(additions)
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in CODE}
    rule_path = str((source_root / 'app/records/condition_scope.py').resolve())
    if rule_path not in bindings or file_hash(Path(rule_path)) != bindings[rule_path]:
        raise ValueError('Transfer requires the exact frozen stage25 rule implementation')
    scope = json.loads((scope_dir / 'report.json').read_bytes())
    windows = json.loads((windows_dir / 'report.json').read_bytes())
    catalog = json.loads((stage25 / 'source_events.json').read_bytes())
    history = json.loads((stage25 / 'parent_report.json').read_bytes())
    source_ids = {e['context']['region_id'] for e in catalog['events']}
    if len(source_ids) != 1:
        raise ValueError('Transfer control must identify exactly one stage25 method source')
    control = SourceRegion.model_validate(history['sources'][next(iter(source_ids))])
    pages: dict[tuple[str, int], SourceRegion] = {}
    for task in scope['tasks']:
        for declaration in task['documents']:
            path = _safe(scope_dir, declaration['bundle'])
            if file_hash(path) != declaration['sha256'] or bindings.get(str(path)) != declaration['sha256']:
                raise ValueError('Transfer source bundle differs from frozen task binding')
            bundle = CandidateBundle.model_validate_json(path.read_bytes())
            if bundle.records:
                raise ValueError('Transfer requires unchanged source-only bundles')
            for source in bundle.regions:
                key = (str(source.article_id), source.page_number)
                if key in pages or str(source.article_id) != declaration['article_id']:
                    raise ValueError('Transfer source bundle contains duplicate/foreign pages')
                if source.original_pdf_path != declaration['original_pdf_path']:
                    raise ValueError('Transfer original PDF path differs from task declaration')
                for name, expected in ((source.original_pdf_path, source.original_pdf_sha256),
                                       (source.layer_pdf_path, source.layer_pdf_sha256)):
                    if bindings.get(str(Path(name).resolve())) != expected:
                        raise ValueError('Transfer PDF is not hash-bound by its frozen parents')
                pages[key] = source
    packet = build_packet(scope, windows, pages, control, catalog['events'])
    packet['frozen_rule'] = {'version': RULE_VERSION, 'path': rule_path, 'sha256': bindings[rule_path]}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'packet.json', packet)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_rule_execution',
        'inputs': bindings, 'code': code, 'outputs': {'packet.json': file_hash(output / 'packet.json')}})
    return dict(packet['inventory'])


def render_transfer(packet: dict[str, Any], report: dict[str, Any]) -> str:
    def detail(label: str, value: Any) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    by_id = {r['unit_id']: r for r in report['results']}
    documents = {d['article_id']: d for d in packet['documents']}
    rows = []
    for page in packet['pages']:
        document = documents[page['article_id']]
        source = page['source']
        units = []
        for unit in page['units']:
            result = by_id[unit['unit_id']]
            units.append('<article class="unit"><h3>Блок ' + str(unit['block_number']) + ' · '
                + html.escape(result['outcome']) + '</h3>' + detail('Точный полный текст блока', unit['source']['text'])
                + detail('Исходная геометрия и координаты', unit) + detail('Все события без исправлений', result) + '</article>')
        uri = Path(document['original_pdf_path']).resolve().as_uri() + '#page=' + str(page['page_number'])
        diagnostics = {k: page[k] for k in ('planning_state', 'diagnostics', 'layout_diagnostics', 'table_diagnostics',
                                           'probe_diagnostics', 'paragraph_adequacy', 'per_result_applicability')}
        rows.append('<tr class="page"><td>' + html.escape(document['title']) + '<p>' + html.escape(document['role'])
            + '</p><a href="' + html.escape(uri, quote=True) + '">Исходный PDF, стр. ' + str(page['page_number'])
            + '</a></td><td>' + str(page['page_number']) + detail('Прежние и новые диагностики', diagnostics)
            + detail('Полный исходный текст страницы', source['quote'] if source else 'missing_or_empty_source_page')
            + detail('Полная страница и source/layer/PDF identities', {k: v for k, v in page.items() if k != 'units'})
            + '</td><td>' + ''.join(units) + ('Нет доказанных единиц; страница сохранена.' if not units else '') + '</td></tr>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>ARIADNE — перенос замороженных правил</title><style>body{font:15px system-ui;margin:24px;color:#18342d}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #bccbc4;padding:10px;vertical-align:top}'
        'td{max-width:70ch}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:50vh;overflow:auto}'
        'article{border-bottom:2px solid #8eaaa0}input{padding:8px;width:65%}[hidden]{display:none!important}</style>'
        '<h1>Перенос замороженных правил условий</h1><p>Development-проверка на других документах. '
        'no_literal_cue означает отказ буквального правила; наличие или отсутствие условий этим не установлено. '
        'Независимого эталона и научных метрик нет; новых измерений и model calls нет.</p>'
        + detail('Версия, замороженные правила и итоги', {'version': VERSION, 'rule': packet['frozen_rule'], 'summary': report['summary']})
        + '<p><a href="report.json">Результаты JSON</a> · <a href="prepared_packet.json">Замороженный пакет</a> · '
        '<a href="manifest.json">Manifest</a></p>' + detail('Объявленные документы и группы', packet['documents'])
        + detail('Отдельный replay-контроль; исключён из transfer counts', report['separate_control_events'])
        + '<label>Поиск <input id="q" type="search"></label><p id="count"></p><table><thead><tr>'
        '<th>Документ и PDF</th><th>Страница и диагностика</th><th>Все зарегистрированные блоки</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table><script>const rows=[...document.querySelectorAll("tr.page")];'
        'function filter(){const q=document.getElementById("q").value.toLocaleLowerCase();let n=0;'
        'for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++;}'
        'document.getElementById("count").textContent=n+" / "+rows.length;}'
        'document.getElementById("q").addEventListener("input",filter);filter();</script></html>\n')


def run_transfer(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_rule_execution':
        raise ValueError('Transfer execution requires a separate prepared packet')
    packet_raw = (prepared / 'packet.json').read_bytes()
    packet = json.loads(packet_raw)
    rule = packet['frozen_rule']
    if rule['version'] != RULE_VERSION or bindings.get(rule['path']) != rule['sha256']:
        raise ValueError('Prepared transfer rule identity changed')
    report = execute_packet(packet)
    report['preparation_manifest_sha256'] = file_hash(prepared / 'manifest.json')
    report['prepared_packet_sha256'] = file_hash(prepared / 'packet.json')
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'prepared_packet.json').write_bytes(packet_raw)
    write_json(output / 'report.json', report)
    (output / 'review.html').write_text(render_transfer(packet, report), encoding='utf-8')
    verify_hashes(bindings)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'executed_frozen_rules', 'inputs': bindings,
        'code': manifest['code'], 'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return dict(report['summary'])
