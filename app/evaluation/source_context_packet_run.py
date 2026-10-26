"""Frozen source-packet development comparison with no database or model access."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]

from app.evaluation.block_run import read_archived
from app.evaluation.context_risks import canonical
from app.generation.block_context import page_plan
from app.generation.source_context_packet import (
    PARENT_VERSION,
    VERSION,
    build_source_packet,
    expand_context,
    node_identity,
    validate_packet,
)
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import SourceRegion, text_hash
from app.records.sources import file_hash

CODE = ('app/generation/source_context_packet.py', 'app/evaluation/source_context_packet_run.py',
    'scripts/source_context_packet.py', 'tests/unit/test_source_context_packet.py',
    'docs/records/source_context_packet_protocol_v0.1.md', 'app/generation/block_context.py',
    'app/evaluation/context_risks.py', 'app/evaluation/context_windows.py', 'app/evaluation/layout_groups.py',
    'app/evaluation/ruled_tables.py', 'app/evaluation/source_gaps.py', 'app/evaluation/context_compaction.py',
    'app/evaluation/query_packet.py', 'app/generation/query_qualifiers.py', 'app/records/article_windows.py',
    'app/records/condition_multilingual.py', 'app/records/material_roles.py', 'app/records/protocol_association.py',
    'app/generation/providers.py', 'app/records/schema.py', 'app/records/sources.py',
    'app/metadata/bridge_run.py', 'app/metadata/bibliography.py', 'pyproject.toml')


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def merge(left: dict[str, str], right: dict[str, str]) -> None:
    if any(n in left and left[n] != h for n, h in right.items()):
        raise ValueError('Source packet conflicting frozen bindings')
    left.update(right)


def validate_native(parent: dict[str, Any]) -> None:
    sources = {r['region_id']: SourceRegion.model_validate(r)
        for r in parent['preparation']['baseline']['sources']['pages'].values()}
    for page in parent['preparation']['pages']:
        if canonical(page_plan(sources[page['parent_region_id']])) != canonical(page['plan']):
            raise ValueError('Source packet current selected-PDF registration drift')


def validate_tac(metadata: dict[str, Any], ids: set[str]) -> None:
    rows = metadata['articles']
    if len(rows) != len(ids) or {r['article_id'] for r in rows} != ids:
        raise ValueError('Source packet TAC scope differs from all selected documents')
    for row in rows:
        regions = list(row['proposal']['sources']['regions'])
        for section in row['historical_tac']['sections']:
            if not section['current_source_valid']:
                raise ValueError('Source packet historical TAC section was not source-validated')
            region = section['registered_source']
            if (region['page_text'][section['start']:section['end']] != section['quote']
                    or region['page_text_sha256'] != section['page_text_sha256']
                    or region['text_layer_id'] != section['layer_id']):
                raise ValueError('Source packet historical TAC source span differs')
            regions.append(region)
        for raw in regions:
            source = SourceRegion.model_validate(raw)
            if file_hash(Path(source.original_pdf_path)) != source.original_pdf_sha256:
                raise ValueError('Source packet TAC original PDF drift')
            if file_hash(Path(source.layer_pdf_path)) != source.layer_pdf_sha256:
                raise ValueError('Source packet TAC selected PDF drift')
            with fitz.open(source.layer_pdf_path) as document:
                if document[source.page_number - 1].get_text('text') != source.page_text:
                    raise ValueError('Source packet TAC current PDF text differs from exact frozen text')


def validate_challenges(tasks: list[dict[str, Any]], challenges: dict[str, Any]) -> None:
    by_id = {t['id']: read(Path(t['response_path'])) for t in tasks}
    cases = challenges['cases']
    if not cases or len({c['id'] for c in cases}) != len(cases) or {c['task_id'] for c in cases} != set(by_id):
        raise ValueError('Source packet challenge/task scope incomplete or duplicate')
    if (challenges['version'] != 'source_context_retention_challenges_v0.1'
            or challenges['origin'] != 'assistant_source_development_before_new_packet_outcomes'
            or challenges['independent_human_confirmation'] is not False):
        raise ValueError('Source packet challenge origin/version differs')
    for case in cases:
        parent = by_id[case['task_id']]
        if case['kind'] == 'no_refusal_upgrade':
            if not parent['preparation']['blocking_reasons']:
                raise ValueError('Refusal challenge lacks an existing parent blocker')
            continue
        if case['kind'] != 'one_co_preservation_unit':
            raise ValueError('Unsupported source retention challenge')
        regions = parent['preparation']['baseline']['sources']['pages'].values()
        sources = [r for r in regions if r['region_id'] == case['parent_region_id']]
        if len(sources) != 1 or any(sources[0][k] != v for k, v in case['source'].items()):
            raise ValueError('Retention challenge source identity differs')
        source = sources[0]
        plan = next(p for p in parent['preparation']['pages'] if p['parent_region_id'] == case['parent_region_id'])
        blocks = {b['block_number']: b for b in plan['blocks']}
        required = case['required_blocks']
        if not required or len({b['block_number'] for b in required}) != len(required):
            raise ValueError('Retention challenge block scope empty or duplicate')
        for target in required:
            block = blocks.get(target['block_number'])
            if block is None or (block['start'], block['end']) != (target['start'], target['end']):
                raise ValueError('Retention challenge block range differs from source')
            quote = source['page_text'][target['start']:target['end']]
            if quote != target['quote'] or text_hash(quote) != target['text_sha256']:
                raise ValueError('Retention challenge quote/hash differs from source')


def prepare(parent: Path, archive: Path, metadata: Path, challenges: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings, mappings = read_archived(parent, archive, source_root=Path.cwd())
    if manifest['version'] != PARENT_VERSION or manifest['phase'] != 'read_only_risk_api_smoke':
        raise ValueError('Source packet requires frozen native stage34 results')
    meta_manifest, additions = read_frozen(metadata, 'registered_tac_metadata_v0.1', Path.cwd())
    if meta_manifest['phase'] != 'applied_metadata_proposals':
        raise ValueError('Source packet requires frozen stage35 metadata proposals')
    merge(bindings, additions)
    report, references = read(parent / 'report.json'), read(challenges)
    if references['parent_report_sha256'] != file_hash(parent / 'report.json'):
        raise ValueError('Source packet challenge parent report differs')
    tasks: list[dict[str, Any]] = []
    ids: set[str] = set()
    for row in report['results']:
        native = _safe(parent, row['id'] + '/response.json')
        if bindings.get(str(native)) != file_hash(native) or canonical(read(native)) != canonical(row['response']):
            raise ValueError('Source packet native/aggregate parent mismatch')
        validate_native(row['response'])
        ids.update(e['article_id'] for e in row['response']['preparation']['baseline']['evidence'])
        tasks.append({'id': row['id'], 'response_path': str(native)})
    if len(tasks) != 4 or len({t['id'] for t in tasks}) != 4:
        raise ValueError('Source packet requires all four frozen questions')
    validate_challenges(tasks, references)
    validate_tac(read(metadata / 'report.json'), ids)
    bindings[str(challenges.resolve())] = file_hash(challenges)
    visual = references['visual_evidence']
    merge(bindings, {visual['path']: visual['sha256']})
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'tasks': tasks, 'challenges': str(challenges.resolve()),
        'metadata_report': str((metadata / 'report.json').resolve()), 'historical_source_mappings': mappings})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_source_packet_run',
        'inputs': bindings, 'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(tasks), 'documents': len(ids), 'challenges': len(references['cases']),
        'historical_source_mappings': len(mappings), 'new_packet_outcomes': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_source_packet_run' or manifest['code'] != {
            str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Source packet prepared phase/code inventory differs')
    plan = read(prepared / 'plan.json')
    if plan['version'] != VERSION:
        raise ValueError('Source packet plan version differs')
    declared = [Path(t['response_path']).resolve() for t in plan['tasks']]
    declared.extend(Path(plan[k]).resolve() for k in ('challenges', 'metadata_report'))
    if any(str(path) not in bindings for path in declared):
        raise ValueError('Source packet plan references an input outside frozen bindings')
    return plan, bindings


def assess_challenges(task_id: str, packet: dict[str, Any], references: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = {n['id']: n['node_id'] for n in packet['wire']['nodes']}
    units = [set(nodes[n] for n in unit) for unit in packet['wire']['co_preservation_units']]
    results = []
    for case in references['cases']:
        if case['task_id'] != task_id:
            continue
        if case['kind'] == 'no_refusal_upgrade':
            passed = (not packet['network_ready'] and set(packet['parent']['preparation']['blocking_reasons'])
                <= set(packet['blocking_reasons']))
            results.append({'id': case['id'], 'kind': case['kind'], 'passed': passed,
                'basis': 'Old blockers preserved; no new source fetched or admitted.'})
            continue
        source = SourceRegion.model_validate(next(r for r in
            packet['parent']['preparation']['baseline']['sources']['pages'].values()
            if r['region_id'] == case['parent_region_id']))
        required = {node_identity(source, b['start'], b['end']) for b in case['required_blocks']}
        numbers = {b['block_number'] for b in case['required_blocks']}
        old = any(numbers <= set(w['block_numbers']) for p in packet['parent']['audit']['pages']
            if p['source']['region_id'] == source.region_id for w in p['windows'])
        results.append({'id': case['id'], 'kind': case['kind'], 'passed': any(required <= unit for unit in units),
            'retained_as_exact_nodes': required <= set(nodes.values()), 'old_single_window_contains_all': old,
            'required_node_ids': sorted(required), 'scientific_applicability': 'not_evaluated'})
    return results


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ('original_windows', 'unique_window_blocks', 'unique_packet_blocks', 'added_dependency_blocks',
        'original_window_text_bytes', 'unique_window_text_bytes', 'packet_text_bytes_after_closure', 'wire_bytes',
        'baseline_evidence_items_preserved')
    return {'questions': len(rows), **{key: sum(r['metrics'][key] for r in rows) for key in keys},
        'retention_challenges': sum(len(r['challenges']) for r in rows),
        'retention_challenges_passed': sum(c['passed'] for r in rows for c in r['challenges']),
        'assembled_complete_page_occurrences': sum(r['metrics']['assembled_complete_pages'] for r in rows),
        'network_ready': 0, 'retrieval_calls': 0, 'embedding_calls': 0, 'model_calls': 0,
        'database_access': False, 'scientific_accuracy': None}


def render(report: dict[str, Any], packets: dict[str, dict[str, Any]]) -> str:
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))

    def detail(label: str, value: Any) -> str:
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(value) + '</pre></details>'

    cards = []
    for row in report['results']:
        packet = packets[row['id']]
        wire = packet['wire']
        nodes = {n['id']: n for n in wire['nodes']}
        sources = {r['region_id']: r for r in packet['parent']['preparation']['baseline']['sources']['pages'].values()}
        page_rows = []
        for page in wire['pages']:
            source = sources[page['parent_region_id']]
            url = Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(page['page'])
            selected = [n for n in wire['nodes'] if n['page_ref'] == page['page_ref']]
            page_rows.append('<section data-packet-page><h3><a href="' + esc(url) + '">PDF p.' + str(page['page'])
                + '</a> · ' + esc(page['article_id']) + '</h3>'
                + detail('Все блоки, графика, границы и неизвестные связи', page)
                + ''.join(detail('Блок ' + str(n['block_number']) + ' · ' + n['id'], n['text'])
                    + detail('Точные source events и guards · ' + n['id'], n) for n in selected) + '</section>')
        contexts = ''.join('<tr data-context><td>' + esc(c['context_id']) + '<br>' + esc(c['nodes']) + '</td><td>'
            + detail('Полный восстановленный исходный контекст', expand_context(packet, c['context_id']))
            + detail('Исходные риски и идентичность', c) + '</td></tr>' for c in wire['contexts'])
        groups = ''.join('<tr><td>' + str(i) + '<br>' + esc(unit) + '</td><td>'
            + detail('Полная группа сохранения: без восстановления предложения', '\n'.join(nodes[n]['text'] for n in unit))
            + '</td></tr>' for i, unit in enumerate(wire['co_preservation_units'], 1))
        cards.append('<article data-query><h2>' + esc(row['id']) + '</h2><p>' + esc(wire['question']) + '</p>'
            + '<a href="' + esc(row['packet_file']) + '">Полный пакет и неизменённый baseline</a> · '
            + '<a href="' + esc(row['expanded_file']) + '">Все восстановленные окна JSON</a>'
            + detail('Результаты, пределы объёма и все запреты', row)
            + '<h3>Группы совместного сохранения</h3><table><tbody>' + groups + '</tbody></table>'
            + '<h3>Исходные окна: точное восстановление</h3><table><tbody>' + contexts + '</tbody></table>'
            + '<details><summary>Все страницы, блоки и диагностика</summary>' + ''.join(page_rows) + '</details></article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: пакет исходного контекста</title>'
        '<style>body{font:15px system-ui;margin:22px;color:#18333f;background:#fafafa}table{border-collapse:collapse;width:100%;'
        'table-layout:fixed}td{border:1px solid #9aa;padding:9px;vertical-align:top;overflow-wrap:anywhere}'
        'td:first-child{width:30%}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}'
        'details{margin:8px 0}article{border-top:2px solid #789;margin-top:24px}[hidden]{display:none!important}</style>'
        '<h1>Пакет исходного контекста</h1><p>' + VERSION + '. Точные блоки и структурные зависимости. '
        'Научная связь свойство/метод/условия не подтверждена. Генерация отключена, прежние отказы сохранены.</p>'
        '<p><a href="metadata_review.html">TAC-таблица всех документов scope: Title, Authors, Journal, Year, '
        'Abstract, Conclusions, Terms, Original file</a></p><a href="report.json">Отчёт JSON</a> · '
        '<a href="manifest.json">Manifest</a>' + detail('Общий результат и явные знаменатели', report['summary'])
        + '<p><label>Поиск по вопросам, полному тексту и диагностике <input id="q" type="search"></label> '
        '<output id="count"></output></p>' + ''.join(cards)
        + '<script>const q=document.getElementById("q"),rows=[...document.querySelectorAll("[data-query]")];'
        'function filter(){let n=0;for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes('
        'q.value.toLocaleLowerCase());if(!r.hidden)n++}document.getElementById("count").textContent=n+" / "+rows.length}'
        'q.addEventListener("input",filter);filter();</script></html>\n')


def save_review(output: Path, report: dict[str, Any], packets: dict[str, dict[str, Any]],
                metadata: dict[str, Any], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for row in report['results']:
        folder = _safe(output, row['id'])
        folder.mkdir()
        packet = packets[row['id']]
        write_json(output / row['packet_file'], packet)
        write_json(output / row['expanded_file'], {c['context_id']: expand_context(packet, c['context_id'])
            for c in packet['wire']['contexts']})
    write_json(output / 'report.json', report)
    write_json(output / 'metadata.json', metadata)
    (output / 'review.html').write_text(render(report, packets), encoding='utf-8', newline='\n')
    metadata_html = render_metadata(metadata).replace('href="report.json"', 'href="metadata.json"', 1)
    (output / 'metadata_review.html').write_text(metadata_html, encoding='utf-8', newline='\n')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_source_packet_review', 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})


def run(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    references = read(Path(plan['challenges']))
    validate_challenges(plan['tasks'], references)
    metadata = read(Path(plan['metadata_report']))
    packets: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    for task in plan['tasks']:
        parent = read(Path(task['response_path']))
        validate_native(parent)
        packet = build_source_packet(parent)
        packets[task['id']] = packet
        for page in parent['audit']['pages']:
            for window in page['windows']:
                if expand_context(packet, window['context_id']) != window['quote']:
                    raise ValueError('Source packet did not preserve an exact original window')
        metrics = {k: packet[k] for k in ('original_windows', 'unique_window_blocks', 'unique_packet_blocks',
            'added_dependency_blocks', 'original_window_text_bytes', 'unique_window_text_bytes',
            'packet_text_bytes_after_closure', 'wire_bytes', 'baseline_evidence_items_preserved')}
        metrics.update(assembled_complete_pages=len(packet['assembled_complete_pages']), byte_ceiling=packet['byte_ceiling'])
        ids.update(e['article_id'] for e in parent['preparation']['baseline']['evidence'])
        rows.append({'id': task['id'], 'metrics': metrics, 'blocking_reasons': packet['blocking_reasons'],
            'challenges': assess_challenges(task['id'], packet, references),
            'packet_file': task['id'] + '/packet.json', 'expanded_file': task['id'] + '/expanded_contexts.json'})
    validate_tac(metadata, ids)
    report = {'version': VERSION, 'summary': summarize(rows), 'results': rows,
        'historical_source_mappings': plan['historical_source_mappings'],
        'metadata_source': {'path': plan['metadata_report'], 'sha256': file_hash(Path(plan['metadata_report'])),
            'version': 'registered_tac_metadata_v0.1', 'scientific_confirmation': False}}
    save_review(output, report, packets, metadata, bindings)
    return dict(report['summary'])


def export(captured: Path, output: Path) -> dict[str, Any]:
    manifest, bindings = read_frozen(captured, VERSION, Path.cwd())
    if manifest['phase'] != 'offline_source_packet_review':
        raise ValueError('Source packet export phase differs')
    report = read(captured / 'report.json')
    if report['summary'] != summarize(report['results']):
        raise ValueError('Source packet captured summary differs')
    packets = {}
    for row in report['results']:
        packet = read(_safe(captured, row['packet_file']))
        validate_packet(packet)
        original = read(_safe(captured, row['expanded_file']))
        if original != {c['context_id']: expand_context(packet, c['context_id']) for c in packet['wire']['contexts']}:
            raise ValueError('Source packet expanded context file differs')
        packets[row['id']] = packet
    verify_hashes(bindings)
    # Keep original input bindings so independent exports have identical manifests.
    save_review(output, report, packets, read(captured / 'metadata.json'), manifest['inputs'])
    return dict(report['summary'])
