"""Reproducible source-only full-PDF search and per-question gap review."""

from __future__ import annotations

import ast
import html
import importlib.metadata
import json
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from packaging.requirements import Requirement

from app.evaluation.context_compaction import SourcePage
from app.evaluation.context_windows import read_registered_blocks
from app.generation.evidence_gaps import PATTERNS, REQUIREMENTS, VERSION, document_checklist, search_pages
from app.ingestion.pdf_extract import extract_pages
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import text_hash
from app.records.sources import file_hash

CODE = ('app/generation/evidence_gaps.py', 'app/evaluation/evidence_gaps_run.py', 'scripts/evidence_gaps.py',
    'tests/unit/test_evidence_gaps.py', 'docs/records/evidence_gaps_protocol_v0.1.md',
    'docs/records/evidence_gaps_protocol_v0.2.md',
    'app/ingestion/pdf_extract.py', 'app/evaluation/context_windows.py', 'app/metadata/bridge_run.py',
    'app/evaluation/query_packet_run.py', 'pyproject.toml')
PREPARED = 'prepared_before_evidence_gap_outcomes'
CAPTURED = 'offline_evidence_gap_audit'


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def runtime() -> dict[str, Any]:
    project = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']
    versions = {}
    for raw in project['dependencies']:
        requirement = Requirement(raw)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        version = importlib.metadata.version(requirement.name)
        if not requirement.specifier.contains(version):
            raise ValueError('Installed requirement mismatch: ' + raw)
        versions[requirement.name] = version
    return {'python': sys.version, 'direct_dependency_versions': versions,
        'scope': 'installed direct dependencies, not a portable lockfile or complete transitive environment'}


def frozen_questions() -> dict[str, str]:
    tree = ast.parse(Path('app/evaluation/query_packet_run.py').read_text(encoding='utf-8'))
    values = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'QUESTIONS' for t in n.targets)]
    if len(values) != 1 or len(values[0]) != 4 or {i for i, _ in values[0]} != set(REQUIREMENTS):
        raise ValueError('Frozen four-question definition differs')
    return dict(values[0])


def load_parent(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(root, 'sample_identifier_audit_v0.1', Path.cwd())
    if manifest['phase'] != 'offline_sample_identifier_audit':
        raise ValueError('Evidence gaps require frozen stage45 results')
    report, metadata = read(root / 'report.json'), read(root / 'metadata.json')
    if [r['id'] for r in report['results']] != list(frozen_questions()):
        raise ValueError('Evidence-gap parent question order/scope differs')
    return report, metadata, bindings


def registration_check(registration: dict[str, Any], first_page: str) -> dict[str, Any]:
    if registration['version'] != 'source_identity_registration_v0.1':
        raise ValueError('Unsupported source registration version')
    anchors = registration['anchors']
    if set(anchors) != {'title', 'authors', 'publication', 'doi'} or any(not v for v in anchors.values()):
        raise ValueError('Source registration requires four nonempty header anchors')
    spans = {}
    for key, quote in anchors.items():
        # A repeated header or reference match cannot silently establish identity.
        starts = [i for i in range(len(first_page)) if first_page.startswith(quote, i)]
        if len(starts) != 1:
            return {'verified': False, 'diagnostic': 'missing_or_ambiguous_first_page_' + key, 'spans': {}}
        start = starts[0]
        spans[key] = {'start': start, 'end': start + len(quote), 'text': quote}
    if ('Istomina' not in anchors['authors'] or '2021' not in anchors['publication']
            or not first_page.startswith('polymers\nArticle\n' + anchors['title'] + '\n' + anchors['authors'])):
        return {'verified': False, 'diagnostic': 'requested_identity_header_not_established', 'spans': {}}
    return {'verified': True, 'diagnostic': 'exact_pinned_header_anchors_not_independent_scientific_confirmation', 'spans': spans}


def source_inventory(parent: Path, report: dict[str, Any], metadata: dict[str, Any],
                     registration: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    documents = {}
    for article in metadata['articles']:
        source = article['proposal']['sources']
        documents[article['article_id']] = {k: source[k] for k in ('article_id', 'original_pdf_path', 'original_pdf_sha256')}
        documents[article['article_id']].update(title=article['title'], scope='historical_parent', requested_identity_verified=False)
    scopes: dict[str, list[str]] = {}
    registered: dict[str, Any] = {}
    for row in report['results']:
        audit = read(_safe(parent, row['audit_file']))
        if audit['question'] != frozen_questions()[row['id']]:
            raise ValueError('Frozen question text differs')
        ids = []
        for page in audit['pages']:
            source = page['source']
            if source['text_layer'] != 'original':
                raise ValueError('This source-capture contract supports original layers only; no implicit layer switch')
            article = source['article_id']
            if article not in documents or source['original_pdf_sha256'] != documents[article]['original_pdf_sha256']:
                raise ValueError('Foreign parent source/PDF')
            key = article + ':' + str(source['page_number'])
            if key in registered and registered[key] != source:
                raise ValueError('Historical page registrations disagree')
            registered[key] = source
            if article not in ids:
                ids.append(article)
        scopes[row['id']] = ids
    if set(documents) != {i for ids in scopes.values() for i in ids}:
        raise ValueError('TAC and source document scopes differ')
    path = Path(registration['original_pdf_path']).resolve()
    if file_hash(path) != registration['original_pdf_sha256']:
        raise ValueError('Registered candidate PDF hash differs')
    if any(d['original_pdf_sha256'] == registration['original_pdf_sha256'] for d in documents.values()):
        raise ValueError('Candidate source duplicates historical document')
    identifier = str(uuid5(NAMESPACE_URL, VERSION + ':' + registration['original_pdf_sha256']))
    documents[identifier] = {'article_id': identifier, 'article_id_scope': 'local_source_capture_not_database_id',
        'original_pdf_path': str(path), 'original_pdf_sha256': registration['original_pdf_sha256'],
        'title': registration['anchors']['title'], 'scope': 'separate_candidate_supplement',
        'requested_identity_verified': False}
    scopes['dsc_protocol'].append(identifier)
    return list(documents.values()), scopes, registered


def capture(documents: list[dict[str, Any]], registered: dict[str, Any]) -> list[dict[str, Any]]:
    pages = []
    for document in documents:
        path = Path(document['original_pdf_path'])
        if file_hash(path) != document['original_pdf_sha256']:
            raise ValueError('PDF changed before source capture')
        extracted = extract_pages(path)  # Unchanged ingestion extractor; exceptions remain visible.
        if not extracted:
            raise ValueError('Source PDF contains no pages')
        for page in extracted:
            old = registered.get(document['article_id'] + ':' + str(page.page_number))
            if old and text_hash(page.text) != old['page_text_sha256']:
                raise ValueError('Historical page text differs from current extraction')
            layer_id = old['text_layer_id'] if old else str(uuid5(NAMESPACE_URL,
                VERSION + ':original:' + document['original_pdf_sha256'] + ':' + str(page.page_number)))
            ref = document['article_id'] + ':p' + str(page.page_number)
            source = SourcePage(document['article_id'], ref, page.page_number, 'original', layer_id,
                page.text, str(path), document['original_pdf_sha256'])
            mapping = read_registered_blocks(source, path, document['original_pdf_sha256'])
            blocks = [asdict(b) | {'bbox': list(b.bbox)} for b in mapping.blocks] if mapping.diagnostic is None else [
                {'page_start': 0, 'page_end': len(page.text), 'bbox': None, 'block_number': None}]
            pages.append({'page_ref': ref, **{k: document[k] for k in ('article_id', 'original_pdf_path', 'original_pdf_sha256')},
                'page_number': page.page_number, 'text_layer': 'original', 'text_layer_id': layer_id,
                'layer_id_scope': 'historically_registered' if old else 'new_local_capture_not_database_layer',
                'layer_pdf_path': str(path), 'layer_pdf_sha256': document['original_pdf_sha256'],
                'source_type': 'full_original_pdf_text_capture', 'text': page.text, 'text_sha256': text_hash(page.text),
                'blocks': blocks, 'mapping_diagnostic': mapping.diagnostic,
                'diagnostics': ['visual_and_graphical_content_not_interpreted'] + ([] if page.text.strip() else ['empty_text_no_new_ocr'])})
        if file_hash(path) != document['original_pdf_sha256']:
            raise ValueError('PDF changed during source capture')
    return pages


def check_references(checks: dict[str, Any], parent: Path, report: dict[str, Any]) -> None:
    if (checks['version'] != 'evidence_gap_checks_v0.1'
            or checks['origin'] != 'exposed_source_development_not_independent_gold'
            or checks['parent_report_sha256'] != file_hash(parent / 'report.json')
            or checks['questions'] != frozen_questions()):
        raise ValueError('Evidence-gap checks differ from frozen exposed scope')
    if len(checks['cases']) != 4 or {c['id'] for c in checks['cases']} != set(frozen_questions()):
        raise ValueError('Evidence-gap checks require all four questions exactly once')
    for row in report['results']:
        expected = next(c for c in checks['cases'] if c['id'] == row['id'])
        audit = read(_safe(parent, row['identifiers_file']))
        if expected['blocking_reasons'] != audit['blocking_reasons'] or audit['network_ready']:
            raise ValueError('Frozen refusal/reference differs')


def prepare(parent: Path, registration_path: Path, checks_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    report, metadata, bindings = load_parent(parent)
    registration, checks = read(registration_path), read(checks_path)
    check_references(checks, parent, report)
    documents, scopes, registered = source_inventory(parent, report, metadata, registration)
    bindings.update({str(p.resolve()): file_hash(p) for p in (registration_path, checks_path)})
    bindings.update({d['original_pdf_path']: d['original_pdf_sha256'] for d in documents})
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'parent': str(parent.resolve()),
        'registration': registration, 'checks': checks, 'documents': documents, 'scopes': scopes,
        'registered_pages': registered, 'patterns': PATTERNS, 'runtime': runtime()})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings, 'code': code,
        'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': 4, 'documents': len(documents), 'bindings': len(bindings), 'new_gap_outcomes': 0}


def build_report(plan: dict[str, Any], pages: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parent = Path(plan['parent'])
    historical = read(parent / 'report.json')
    documents = json.loads(json.dumps(plan['documents']))
    candidate = next(d for d in documents if d['scope'] == 'separate_candidate_supplement')
    first = next(p for p in pages if p['article_id'] == candidate['article_id'] and p['page_number'] == 1)
    identity = registration_check(plan['registration'], first['text'])
    candidate['requested_identity_verified'] = identity['verified']
    candidate['identity'] = identity
    hits = search_pages(pages)
    results = []
    for row in historical['results']:
        audit = read(_safe(parent, row['identifiers_file']))
        scoped = [d for d in documents if d['article_id'] in plan['scopes'][row['id']]]
        result = {'id': row['id'], 'question': audit['question'],
            'purpose': 'negative_control_not_reported_measurement' if row['id'] == 'absent_material' else 'substantive',
            'documents': [document_checklist(row['id'], d, pages, hits, audit['rows']) for d in scoped],
            'historical_metrics': audit['metrics'], 'historical_binding_states': audit['selected_binding_states'],
            'historical_source_files': {k: 'baseline/' + row[k] for k in (
                'identifiers_file', 'origin_file', 'applicability_file', 'audit_file') if k in row},
            'blocking_reasons': audit['blocking_reasons'], 'network_ready': False, 'selection_changed': False,
            'checks': [{'kind': 'unchanged_question_refusals_and_no_relation_promotion',
                'passed': audit['question'] == plan['checks']['questions'][row['id']] and not audit['network_ready']}]}
        results.append(result)
    states = [req['status'] for r in results for d in r['documents'] for req in d['requirements']]
    report = {'version': VERSION, 'input_snapshot': {'parent': plan['parent'],
        'parent_report_sha256': plan['checks']['parent_report_sha256'], 'runtime': plan['runtime'],
        'search_patterns': plan['patterns'], 'reference_origin': plan['checks']['origin']},
        'documents': documents, 'results': results,
        'summary': {'questions': len(results), 'documents': len(documents), 'text_pages_searched': len(pages),
            'matching_block_occurrences': len(hits), 'checklist_statuses': {s: states.count(s) for s in sorted(set(states))},
            'unresolved_document_relations': sum(len(r['documents']) for r in results),
            'identity_verified': identity['verified'], 'checks_passed': sum(c['passed'] for r in results for c in r['checks']),
            'model_calls': 0, 'retrieval_calls': 0, 'embedding_calls': 0, 'database_access': False,
            'network_ready': 0, 'scientific_relations_established': 0, 'scientific_accuracy': 'not_evaluated',
            'visual_coverage': 'not_inspected_by_algorithm'}}
    return report, hits


def esc(value: Any) -> str:
    return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))


def detail(label: str, value: Any) -> str:
    return '<details><summary>' + esc(label) + '</summary><pre>' + esc(value) + '</pre></details>'


def pdf_link(source: dict[str, Any]) -> str:
    uri = Path(source['original_pdf_path']).resolve().as_uri()
    if 'page_number' in source:
        uri += '#page=' + str(source['page_number'])
    return '<a data-pdf href="' + esc(uri) + '">Original PDF' + (
        ' p.' + str(source['page_number']) if 'page_number' in source else '') + '</a>'


def render(report: dict[str, Any], pages: list[dict[str, Any]], hits: list[dict[str, Any]]) -> str:
    by_page = {p['page_ref']: p for p in pages}
    docs = {d['article_id']: d for d in report['documents']}
    cards = []
    for result in report['results']:
        tables = []
        ids = {d['article_id'] for d in result['documents']}
        for entry in result['documents']:
            doc = docs[entry['article_id']]
            rows = ['<tr data-gap><td>' + esc(req['required_evidence']) + '</td><td>' + esc(req['status'])
                + '<br>Кандидаты: ' + str(len(req['hit_indices'])) + '; в прежнем пакете: '
                + str(len(req['selected_hit_indices'])) + '</td><td>' + esc(req['gap'])
                + detail('Что проверить дальше', req['next_check']) + '</td></tr>' for req in entry['requirements']]
            rows.append('<tr data-gap><td>Связь и применимость · blocking</td><td>relation_unresolved</td><td>'
                + esc(entry['relation']['required_evidence']) + detail('Следующий шаг', entry['relation']['next_check']) + '</td></tr>')
            tables.append('<section><h3>' + esc(doc['title']) + '</h3>' + pdf_link(doc)
                + detail('Source identity, scope и проверка нового источника', doc)
                + detail('Фактически проверено; визуальные/OCR пробелы', entry['coverage'])
                + detail('Прежние sample/table кандидаты, exact endpoints и причины отказа', entry['historical_sample_bindings'])
                + '<table><thead><tr><th>Нужное доказательство</th><th>Состояние</th><th>Пробел / следующий шаг</th>'
                + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></section>')
        source_rows = []
        for index, hit in enumerate(hits):
            page = by_page[hit['page_ref']]
            if page['article_id'] in ids:
                source_rows.append('<tr data-hit><td>#' + str(index) + ' ' + esc(docs[page['article_id']]['title'])
                    + '<br>' + pdf_link(page) + '</td><td>' + esc(', '.join(hit['matches']))
                    + detail('Точный полный исходный блок', hit['text'])
                    + detail('Все literal matches, offsets, bbox и ограничения', hit)
                    + detail('Source/page/layer identity', {k: v for k, v in page.items() if k not in ('text', 'blocks')}) + '</td></tr>')
        cards.append('<article data-query><h2>' + esc(result['id']) + '</h2><p>' + esc(result['question'])
            + '</p><p>' + esc(result['purpose']) + '</p><p>'
            + ' · '.join('<a href="' + esc(v) + '">' + esc(k) + '</a>' for k, v in result['historical_source_files'].items())
            + '</p>' + detail('Прежние отказы и результаты', result)
            + ''.join(tables) + '<details><summary>Все найденные исходные блоки (' + str(len(source_rows))
            + ')</summary><table><thead><tr><th>Источник</th><th>Цитата и диагностика</th></tr></thead><tbody>'
            + ''.join(source_rows) + '</tbody></table></details></article>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>ARIADNE — пробелы доказательств</title><style>body{font:15px system-ui;margin:24px;color:#18333f}'
        'table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #9aa;padding:8px;'
        'vertical-align:top;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}'
        '[hidden]{display:none!important}article{border-top:3px solid #789;margin-top:24px}section{margin:18px 0}'
        'input{padding:8px;min-width:40%}</style><h1>Каких доказательств не хватает</h1><p>' + VERSION
        + '. Literal candidate ≠ научная поддержка. supported_in_packet означает только точное присутствие текста. '
        'Новые находки не добавлены в прежние пакеты. Научные связи не установлены; допуск не менялся. '
        'not_found_in_inspected_scope относится только к проверенному текстовому слою, не ко всему PDF/корпусу.</p>'
        '<p><a href="metadata_review.html">TAC: все документы стадии</a> · <a href="report.json">Report</a> · '
        '<a href="source_pages.json">Полный текст всех страниц</a> · <a href="manifest.json">Manifest</a> · '
        '<a href="baseline/review.html">Неизменённый stage45</a></p>'
        + detail('Версия, input snapshot, правила поиска и итоги', report['input_snapshot'] | report['summary'])
        + '<label>Поиск <input id="q" type="search"></label> <output id="count"></output>' + ''.join(cards)
        + '<script>const q=document.getElementById("q"),cards=[...document.querySelectorAll("[data-query]")];'
        'function filter(){const term=q.value.toLocaleLowerCase();let n=0;for(const c of cards){'
        'c.hidden=!c.textContent.toLocaleLowerCase().includes(term);if(!c.hidden)n++;'
        'for(const r of c.querySelectorAll("[data-hit]"))r.hidden=!r.textContent.toLocaleLowerCase().includes(term)}'
        'document.getElementById("count").textContent=n+" / 4 questions"}q.addEventListener("input",filter);filter();'
        '</script></html>\n')


def metadata_review(metadata: dict[str, Any], report: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    doc = next(d for d in report['documents'] if d['scope'] == 'separate_candidate_supplement')
    page = next(p for p in pages if p['article_id'] == doc['article_id'] and p['page_number'] == 1)
    spans = doc['identity']['spans']
    row = '<tr data-article data-new-source><td>' + esc(spans.get('title', {}).get('text', 'Не подтверждено')) + '</td>'
    row += '<td>' + esc(spans.get('authors', {}).get('text', 'Не подтверждено')) + '</td>'
    # Publication quote is left raw rather than silently inventing normalized metadata.
    row += '<td>' + esc(spans.get('publication', {}).get('text', 'Не подтверждено')) + '</td>'
    row += '<td>2021 — только source-header proposal</td>' if doc['identity']['verified'] else '<td>Не подтверждено</td>'
    row += ('<td>Abstract: извлечение не реализовано для нового supplement.</td>'
        '<td>Conclusions: извлечение не реализовано для нового supplement.</td>'
        '<td>Terms: не реализовано; не требуется ручная классификация.</td><td>' + pdf_link(doc)
        + detail('Полный текст первой страницы; исходная цитата, не TAC-разметка', page['text'])
        + detail('Source registration, exact anchors и ограничения', doc) + '</td></tr>')
    original = render_metadata(metadata).replace('href="report.json"', 'href="metadata.json"', 1)
    return original.replace('</tbody>', row + '</tbody>', 1).replace('<h1>',
        '<p>' + VERSION + ' · Stage46: historical TAC unchanged; one separate source-only supplement. '
        'Missing new TAC fields explicitly unimplemented. <a href="report.json">Stage46 snapshot</a></p><h1>', 1)


def save(output: Path, plan: dict[str, Any], report: dict[str, Any], pages: list[dict[str, Any]],
         hits: list[dict[str, Any]], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    parent = Path(plan['parent'])
    metadata = read(parent / 'metadata.json')
    for name in read(parent / 'manifest.json')['outputs']:
        target = _safe(output / 'baseline', name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_safe(parent, name).read_bytes())
    (output / 'baseline' / 'manifest.json').write_bytes((parent / 'manifest.json').read_bytes())
    (output / 'metadata.json').write_bytes((parent / 'metadata.json').read_bytes())
    for name, value in (('plan.json', plan), ('report.json', report), ('source_pages.json', pages), ('hits.json', hits)):
        write_json(output / name, value)
    (output / 'review.html').write_text(render(report, pages, hits), encoding='utf-8', newline='\n')
    (output / 'metadata_review.html').write_text(metadata_review(metadata, report, pages), encoding='utf-8', newline='\n')
    verify_hashes(bindings)
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': CAPTURED, 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})


def execute(root: Path, output: Path, *, export: bool = False) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(root, VERSION, Path.cwd())
    if manifest['phase'] != (CAPTURED if export else PREPARED):
        raise ValueError('Evidence-gap input phase differs')
    if not export and manifest['code'] != {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Prepared evidence-gap code inventory differs')
    plan = read(root / 'plan.json')
    if plan['patterns'] != PATTERNS or plan['runtime'] != runtime():
        raise ValueError('Search rules or installed runtime changed')
    parent_report, metadata, _ = load_parent(Path(plan['parent']))
    check_references(plan['checks'], Path(plan['parent']), parent_report)
    docs, scopes, registered = source_inventory(Path(plan['parent']), parent_report, metadata, plan['registration'])
    if (docs, scopes, registered) != (plan['documents'], plan['scopes'], plan['registered_pages']):
        raise ValueError('Source inventory differs from frozen preparation')
    pages = capture(plan['documents'], plan['registered_pages'])
    report, hits = build_report(plan, pages)
    if export and any(read(root / name) != value for name, value in
            (('source_pages.json', pages), ('hits.json', hits), ('report.json', report))):
        raise ValueError('Captured evidence gaps differ from exact source reconstruction')
    save(output, plan, report, pages, hits, manifest['inputs'] if export else bindings)
    return dict(report['summary'])
