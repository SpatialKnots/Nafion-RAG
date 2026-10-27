"""Frozen identifier/reference audit with an explicitly separate source supplement."""

from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.evaluation.condition_applicability_run import CODE as PARENT_CODE
from app.evaluation.condition_applicability_run import FILES as PARENT_FILES
from app.evaluation.context_compaction import SourcePage
from app.evaluation.context_risks import canonical
from app.evaluation.context_windows import read_registered_blocks
from app.evaluation.source_context_packet_run import read, validate_tac
from app.evaluation.source_gaps import read_source_gaps
from app.evaluation.source_origin_run import values
from app.generation.condition_applicability import VERSION as PARENT_VERSION
from app.generation.condition_applicability import audit_applicability
from app.generation.sample_identifiers import VERSION, audit_identifiers, build_catalog
from app.generation.source_origin import audit_origin
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash

CODE = (*PARENT_CODE, 'app/generation/sample_identifiers.py', 'app/evaluation/sample_identifiers_run.py',
    'scripts/sample_identifiers.py', 'tests/unit/test_sample_identifiers.py',
    'docs/records/sample_identifiers_protocol_v0.1.md', 'app/records/table_cells.py', 'app/records/table_relations.py')
FILES = (*PARENT_FILES, 'applicability_file')
PREPARED = 'prepared_before_sample_identifier_outcomes'
CAPTURED = 'offline_sample_identifier_audit'


def source_supplement(history: Path, windows: Path) -> tuple[dict[str, Any], dict[str, str]]:
    # Historical runtime files can legitimately change after stage23. This is
    # a NEW source-only capture, not relaxed acceptance/replay of that old run.
    manifest_path = (history / 'manifest.json').resolve()
    manifest = read(manifest_path)
    if manifest['version'] != 'records_table_relations_v0.1':
        raise ValueError('Unsupported historical sample-table source version')
    expected = {str(Path(n).resolve()): digest for n, digest in (manifest['inputs'] | manifest['code']).items()}
    expected.update({str(_safe(history, n)): digest for n, digest in manifest['outputs'].items()})
    current = {n: file_hash(Path(n)) for n in expected if Path(n).is_file()}
    changed = [{'path': n, 'historical_sha256': digest, 'current_sha256': current.get(n)}
        for n, digest in expected.items() if current.get(n) != digest]
    bindings = {**current, str(manifest_path): file_hash(manifest_path)}
    path = (windows / 'report.json').resolve()
    report_path = (history / 'report.json').resolve()
    for required in (path, report_path):
        if expected.get(str(required)) != file_hash(required):
            raise ValueError('Sample source/geometry artifact differs from its historical hash')
    report = read(history / 'report.json')
    source = SourceRegion.model_validate(report['sources'][report['relation_map']['source_region_id']])
    pages = [p for p in read(path)['pages'] if p['article_id'] == str(source.article_id)
        and p['page_number'] == source.page_number and p['text_layer_id'] == str(source.text_layer_id)]
    if len(pages) != 1:
        raise ValueError('Sample supplement page missing/ambiguous')
    for pdf_path, digest in ((source.original_pdf_path, source.original_pdf_sha256), (source.layer_pdf_path, source.layer_pdf_sha256)):
        if file_hash(Path(pdf_path)) != digest or expected.get(str(Path(pdf_path).resolve())) != digest:
            raise ValueError('Sample supplement PDF differs from exact historical source')
    page = SourcePage(str(source.article_id), source.region_id, source.page_number, source.text_layer,
        str(source.text_layer_id), source.page_text, source.layer_pdf_path, source.layer_pdf_sha256)
    mapping = read_registered_blocks(page, Path(source.layer_pdf_path), source.layer_pdf_sha256)
    old_mapping = pages[0]['mapping']
    actual = asdict(mapping)
    if (mapping.diagnostic is not None or canonical(actual['blocks']) != canonical(old_mapping['blocks'])
            or any(actual[k] != old_mapping[k] for k in ('article_id', 'page', 'layer_id', 'text_sha256', 'selected_pdf_sha256'))):
        raise ValueError('Sample supplement current PDF text/block geometry differs from registered source')
    gaps = asdict(read_source_gaps(page, mapping))
    if not gaps['text_geometry_proven'] or canonical(gaps['lines']) != canonical(pages[0]['source_gaps']['lines']):
        raise ValueError('Sample supplement current PDF line geometry differs from registered source')
    # No native model candidate fields or values are copied or interpreted.
    return {'version': VERSION, 'source_only': True, 'tables': [{'source': source.model_dump(mode='json'), 'page': pages[0]}],
        'history_report_sha256': file_hash(history / 'report.json'), 'page_registry_sha256': file_hash(path),
        'historical_full_run_replayed': False, 'historical_binding_mismatches': changed,
        'current_pdf_text_blocks_and_lines_reverified': True}, bindings


def assess(checks: dict[str, Any], identifier: str, parent: dict[str, Any],
           audit: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if (checks['version'] != 'sample_identifier_checks_v0.1'
            or checks['origin'] != 'assistant_source_development_before_new_identifier_outcomes'
            or checks['independent_human_confirmation'] is not False):
        raise ValueError('Identifier reference version/origin differs')
    if not checks['cases'] or len({c['id'] for c in checks['cases']}) != len(checks['cases']):
        raise ValueError('Identifier reference identities empty/duplicated')
    nodes = {row['node_id']: row for row in parent['rows']}
    results = []
    for case in checks['cases']:
        if case['task_id'] != identifier:
            continue
        kind = case['kind']
        if kind == 'block_diagnostic':
            node = nodes.get(case['source']['node_id'])
            if node is None or any(node[k] != case['source'][k] for k in ('text', 'start', 'end', 'text_sha256')):
                raise ValueError('Identifier reference differs from exact source block')
            if not case['expected'] or set(case['expected']) - {'sample_ids', 'table_ids', 'binding_states', 'candidate_rows'}:
                raise ValueError('Unsupported/empty identifier expectations')
        elif kind != 'unchanged_source_and_refusals':
            raise ValueError('Unsupported identifier reference kind')
        if audit is None:
            continue
        if kind == 'unchanged_source_and_refusals':
            passed = (not audit['selection_changed'] and not audit['network_ready']
                and audit['wire_sha256_unchanged'] == parent['wire_sha256_unchanged']
                and audit['blocking_reasons'] == parent['blocking_reasons'])
        else:
            row = next(r for r in audit['rows'] if r['node_id'] == case['source']['node_id'])
            bindings = [b for e in row['events'] for b in e['bindings']]
            observed = {'sample_ids': sorted(h['identifier'] for e in row['events'] for h in e['inventory']['samples']),
                'table_ids': sorted({h['identifier'] for e in row['events'] for h in e['inventory']['tables']}),
                'binding_states': sorted(b['state'] for b in bindings),
                'candidate_rows': sorted(c['row']['identifier'] for b in bindings for c in b['candidates'])}
            passed = all(observed[k] == v for k, v in case['expected'].items())
        results.append({'id': case['id'], 'kind': kind, 'passed': passed})
    return results


def assess_catalog(checks: dict[str, Any], supplement: dict[str, Any], catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    references = checks.get('catalog_checks', [])
    if len({r['id'] for r in references}) != len(references):
        raise ValueError('Duplicate catalog development check')
    results = []
    for reference in references:
        sources = [t['source'] for t in supplement['tables'] if t['source']['region_id'] == reference['region_id']]
        if len(sources) != 1:
            raise ValueError('Catalog reference source missing/ambiguous')
        source = SourceRegion.model_validate(sources[0])
        for span in reference['expected'].values():
            if source.page_text[span['start']:span['end']] != span['text']:
                raise ValueError('Catalog reference differs from exact source span')
        if catalog is None:
            continue
        candidates = [r for t in catalog['tables'] if t['source']['region_id'] == reference['region_id']
            and t['table_identifier'] == reference['table_identifier'] for r in t['rows']
            if r['identifier'] == reference['sample_identifier']]
        passed = len(candidates) == 1 and all(candidates[0][key] is not None and
            all(candidates[0][key][k] == span[k] for k in ('start', 'end', 'text')) for key, span in reference['expected'].items())
        results.append({'id': reference['id'], 'passed': passed})
    return results


def prepare(parent: Path, history: Path, windows: Path, checks_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(parent, PARENT_VERSION, Path.cwd())
    if manifest['phase'] != 'offline_condition_applicability_audit':
        raise ValueError('Identifier audit requires frozen stage44 results')
    supplement, extra = source_supplement(history, windows)
    if any(n in bindings and bindings[n] != v for n, v in extra.items()):
        raise ValueError('Conflicting historical/parent source bindings')
    bindings.update(extra)
    rows, checks = read(parent / 'report.json')['results'], read(checks_path)
    if (len(rows) != 4 or len({r['id'] for r in rows}) != 4
            or {c['task_id'] for c in checks['cases']} != {r['id'] for r in rows}
            or checks['parent_report_sha256'] != file_hash(parent / 'report.json')
            or checks['history_report_sha256'] != file_hash(history / 'report.json')):
        raise ValueError('Identifier source identities/four-question scope differs')
    ids: set[str] = set()
    for row in rows:
        for key in FILES:
            path = _safe(parent, row[key])
            if bindings.get(str(path)) != file_hash(path):
                raise ValueError('Identifier input is not frozen')
        assess(checks, row['id'], read(_safe(parent, row['applicability_file'])))
        diagnostic = read(_safe(parent, row['diagnostics_file']))
        ids.update(e['article_id'] for e in diagnostic['parent']['preparation']['baseline']['evidence'])
    if any(t['source']['article_id'] not in ids for t in supplement['tables']):
        raise ValueError('Identifier supplement adds an undeclared article')
    validate_tac(read(parent / 'metadata.json'), ids)
    assess_catalog(checks, supplement)
    bindings[str(checks_path.resolve())] = file_hash(checks_path)
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'supplement.json', supplement)
    write_json(output / 'plan.json', {'version': VERSION, 'parent': str(parent.resolve()),
        'checks': str(checks_path.resolve()), 'rows': rows})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings, 'code': code,
        'outputs': {n: file_hash(output / n) for n in ('plan.json', 'supplement.json')}})
    return {'questions': len(rows), 'supplemental_pages': len(supplement['tables']),
        'development_cases': len(checks['cases']), 'new_identifier_bindings': 0}


def summary(rows: list[dict[str, Any]], catalog: dict[str, Any]) -> dict[str, Any]:
    states = sorted({k for row in rows for k in row['selected_binding_states']})
    return {'questions': len(rows), 'checks': sum(len(row['checks']) for row in rows),
        'checks_passed': sum(c['passed'] for row in rows for c in row['checks']),
        **{k: sum(row['metrics'][k] for row in rows) for k in rows[0]['metrics']},
        'selected_binding_states': {s: sum(row['selected_binding_states'].get(s, 0) for row in rows) for s in states},
        'supplemental_tables': len(catalog['tables']), 'catalog_rows': sum(len(t['rows']) for t in catalog['tables']),
        'model_calls': 0, 'retrieval_calls': 0, 'embedding_calls': 0, 'database_access': False,
        'network_ready': 0, 'selection_changed': False, 'scientific_loss_status': 'not_evaluated'}


def render(report: dict[str, Any], audits: dict[str, Any], parents: dict[str, dict[str, bytes]], catalog: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))

    def detail(title: str, value: Any) -> str:
        return '<details><summary>' + esc(title) + '</summary><pre>' + esc(value) + '</pre></details>'

    tables = []
    for table in catalog['tables']:
        source = table['source']
        uri = Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(source['page_number'])
        tables.append('<section data-supplement><h2>Отдельный source supplement: Table ' + esc(table['table_identifier'])
            + '</h2><a href="' + esc(uri) + '">Original PDF p.' + str(source['page_number']) + '</a>'
            + detail('Полный зарегистрированный source context', source['quote'])
            + detail('Заголовок, sample column, все строки и printed plasticiser evidence', table) + '</section>')
    cards = []
    for entry in report['results']:
        audit = audits[entry['id']]
        diag = json.loads(parents[entry['id']]['diagnostics_file'])
        sources = {p['source']['region_id']: p['source'] for p in diag['parent']['audit']['pages']}
        blocks = []
        for row in audit['rows']:
            source = sources[row['source']['parent_region_id']]
            uri = Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(row['source']['page'])
            blocks.append('<tr data-block data-selected="' + str(row['selected']).lower() + '"><td>' + esc(row['node_ref'])
                + ' · ' + ('selected' if row['selected'] else 'local_only') + '<br><a href="' + esc(uri) + '">PDF p.'
                + str(row['source']['page']) + '</a></td><td>' + detail('Полный исходный блок', row['text'])
                + detail('Идентификаторы, table/figure refs, кандидаты строк и отказы', row['events'])
                + detail('Source identity', {k: row[k] for k in ('source', 'node_id', 'start', 'end', 'text_sha256')}) + '</td></tr>')
        links = ' · '.join('<a href="' + esc(entry[k]) + '">' + esc(k) + '</a>' for k in (*FILES, 'identifiers_file'))
        cards.append('<article data-query><h2>' + esc(entry['id']) + '</h2><p>' + esc(audit['question']) + '</p><p>' + links
            + '</p>' + detail('Результат и development checks', entry) + detail('Явные numbering anchors', audit['numbering_anchors'])
            + detail('Все прежние отказы', audit['blocking_reasons'])
            + '<p data-empty hidden>Нет соответствующих блоков; прежние источники и отказы сохранены.</p>'
            + '<table><thead><tr><th>Блок</th><th>Точный источник и связи</th></tr></thead><tbody>' + ''.join(blocks)
            + '</tbody></table></article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE sample/table identifiers</title>'
        '<style>body{font:15px system-ui;margin:22px;color:#18333f}table{border-collapse:collapse;width:100%;table-layout:fixed}'
        'td,th{border:1px solid #9aa;padding:8px;vertical-align:top;overflow-wrap:anywhere}th:first-child{width:23%}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        '[hidden]{display:none!important}article,section[data-supplement]{border-top:2px solid #789;margin-top:24px}</style>'
        '<h1>Образцы и таблицы: локальные ссылки на источники</h1><p>' + VERSION
        + '. Дополнительная таблица хранится отдельно от прежнего wire. Printed plasticiser column не является '
        'составом мембраны или средой измерения. Sample identity/applicability не подтверждены; допуск не менялся.</p>'
        '<p><a href="metadata_review.html">TAC: все документы</a> · <a href="catalog.json">Source catalog</a> · '
        '<a href="report.json">Report</a> · <a href="manifest.json">Manifest</a></p>'
        + detail('Версия, snapshot и итоги', {k: report[k] for k in ('version', 'input_snapshot', 'summary')})
        + ''.join(tables) + '<label>Поиск <input id="q" type="search"></label> '
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
         catalog: dict[str, Any], supplement: dict[str, Any], metadata: dict[str, Any], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for row in report['results']:
        _safe(output, row['id']).mkdir()
        write_json(_safe(output, row['identifiers_file']), audits[row['id']])
        for key in FILES:
            _safe(output, row[key]).write_bytes(parents[row['id']][key])
    for name, content in (('report.json', report), ('catalog.json', catalog), ('supplement.json', supplement), ('metadata.json', metadata)):
        write_json(output / name, content)
    (output / 'review.html').write_text(render(report, audits, parents, catalog), encoding='utf-8', newline='\n')
    (output / 'metadata_review.html').write_text(render_metadata(metadata).replace('href="report.json"',
        'href="metadata.json"', 1), encoding='utf-8', newline='\n')
    verify_hashes(bindings)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': CAPTURED, 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})


def execute(root: Path, output: Path, *, export: bool = False) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(root, VERSION, Path.cwd())
    if manifest['phase'] != (CAPTURED if export else PREPARED):
        raise ValueError('Identifier input phase differs')
    if not export and manifest['code'] != {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Identifier prepared code inventory differs')
    supplement = read(root / 'supplement.json')
    catalog = build_catalog(supplement)
    plan = read(root / ('report.json' if export else 'plan.json'))
    parent = root if export else Path(plan['parent'])
    snapshot = plan['input_snapshot'] if export else {'parent': plan['parent'], 'checks': plan['checks'],
        'parent_report_sha256': file_hash(parent / 'report.json'), 'checks_sha256': file_hash(Path(plan['checks']))}
    checks = read(Path(snapshot['checks']))
    catalog_checks = assess_catalog(checks, supplement, catalog)
    rows, audits, parents = [], {}, {}
    for row in plan['results'] if export else plan['rows']:
        origin = read(_safe(parent, row['origin_file']))
        applicability = read(_safe(parent, row['applicability_file']))
        if origin != audit_origin(*values(parent, row)) or applicability != audit_applicability(origin):
            raise ValueError('Identifier parent differs from exact source reconstruction')
        audit = audit_identifiers(applicability, origin, catalog)
        identifier = row['id']
        current = {'id': identifier, **{k: identifier + '/' + k + '.json' for k in FILES},
            'identifiers_file': identifier + '/identifiers.json', 'checks': assess(checks, identifier, applicability, audit),
            'metrics': audit['metrics'], 'selected_binding_states': audit['selected_binding_states']}
        if export and (read(_safe(parent, row['identifiers_file'])) != audit or current != row):
            raise ValueError('Identifier capture differs from exact reconstruction')
        rows.append(current)
        audits[identifier] = audit
        parents[identifier] = {k: _safe(parent, row[k]).read_bytes() for k in FILES}
    report: dict[str, Any] = {'version': VERSION, 'input_snapshot': snapshot, 'results': rows,
        'catalog_checks': catalog_checks, 'summary': summary(rows, catalog)}
    report['summary'].update(catalog_checks=len(catalog_checks), catalog_checks_passed=sum(c['passed'] for c in catalog_checks))
    if export and (plan != report or read(root / 'catalog.json') != catalog):
        raise ValueError('Identifier captured summary/catalog differs')
    save(output, report, audits, parents, catalog, supplement, read(parent / 'metadata.json'),
        manifest['inputs'] if export else bindings)
    return dict(report['summary'])
