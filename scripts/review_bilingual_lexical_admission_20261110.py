"""Export verified lexical-admission comparisons without generation or database access."""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

from app.generation.bilingual_lexical import VERSION, assess
from app.generation.providers import Evidence
from scripts import bilingual_lexical_admission_20261110 as run
from scripts import gigachat_answer_smoke as f


def status(ready):
    return 'Готов к отправке, не отправлен' if ready else 'Лексический отказ'


def main():
    base = run.BASE
    comparison, regression = base / 'comparison_v03', base / 'regression_v03'
    for folder in (base / 'pre_edit_v01', comparison, regression):
        f.verify_manifest(folder)
    f.verify(run.read(comparison / 'bindings.json'))
    summary = run.read(comparison / 'summary.json')
    old = run.read(regression / 'summary.json')
    if old['actual_service_executions'] != 81 or old['old_cases'] != 76:
        raise ValueError('Incomplete old service regression')
    if any(not r['full_service_identical'] or not r['native_identical'] for r in old['current_comparisons']):
        raise ValueError('Old service/native regression')
    if run.read(regression / 'network.json')['external_denials']:
        raise ValueError('Regression attempted external network')
    junit = f.ROOT / 'output/bilingual_lexical_tests_v04_20261110.xml'
    suites = ET.fromstring(junit.read_bytes()).findall('testsuite')
    if any(int(s.attrib.get(k, '0')) for s in suites for k in ('failures', 'errors', 'skipped')):
        raise ValueError('Affected tests are incomplete or failed')
    tests = sum(int(s.attrib['tests']) for s in suites)
    controls = sum(c.attrib['classname'].endswith('test_bilingual_lexical') for s in suites for c in s.findall('testcase'))
    adverse = run.read(base / 'adverse_v01.json')['constructed_controls']
    for case in adverse:
        current = assess(case['question'], [Evidence(**case['evidence'])], case['metadata'])
        if not case['observed']['eligible'] or current is not None and current['eligible']:
            raise ValueError('Adverse probe was not closed')
    fresh = []
    for cid in ('Nambu_02', 'Nambu_04'):
        folder = base / 'fresh_api_v01' / cid
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
        result = run.read(folder / 'result.json')
        if (not result['trace_exact_frozen_comparison'] or not result['native_exact_frozen_comparison']
                or result['transaction_read_only'] != 'on' or result['network_denials']
                or result['model_POSTs'] or result['OAuth_exchanges'] or result['new_slots']):
            raise ValueError('Invalid fresh read-only preparation')
        fresh.append(result)
    rows, panels, pages, pdfs, witnesses = [], [], {}, {}, []
    bindings = [Path(__file__), junit, comparison / 'manifest.json', regression / 'manifest.json',
                base / 'adverse_v01.json', base / 'pre_edit_v01/manifest.json',
                f.ROOT / 'docs/records/bilingual_lexical_admission_2026-11-10_v0.2.md']
    bindings.extend(base / 'fresh_api_v01' / row['id'] / 'manifest.json' for row in fresh)
    for row in summary['cases']:
        cid = row['id']
        folder = comparison / cid
        f.verify_manifest(folder)
        sources = run.read(run.PARENT / cid / 'sources.json')
        for page in sources['pages'].values():
            if f.sha(page['page_text'].encode()) != page['page_text_sha256']:
                raise ValueError('Stored registered page text drift')
            pages[(page['article_id'], page['page_number'], page['text_layer'])] = page['page_text_sha256']
            for prefix in ('original', 'layer'):
                path, digest = page[prefix + '_pdf_path'], page[prefix + '_pdf_sha256']
                if path not in pdfs:
                    if f.sha(Path(path).read_bytes()) != digest:
                        raise ValueError('Source PDF drift')
                    pdfs[path] = digest
        before = run.read(folder / 'before.json')
        after = run.read(folder / 'after.json')
        if before['trace']['evidence'] != after['trace']['evidence'] or before['trace']['retrieval'] != after['trace']['retrieval']:
            raise ValueError('Changed frozen raw selection')
        rows.append('<tr><td>' + escape(cid) + '</td><td>' + escape(row['question']) + '</td><td>'
                    + status(row['before_reached']) + '</td><td>' + status(row['after_reached'])
                    + '</td><td><a href="../comparison_v03/' + cid + '/result.json">Диагностика</a></td></tr>')
        if row['after_reached'] and not row['before_reached']:
            items = {e['citation_id']: e for e in after['trace']['evidence']}
            panel = '<section><h2>' + escape(cid) + '</h2><p>' + escape(row['question']) + '</p>'
            for witness in row['bridge']['witnesses']:
                item = items[witness['citation_id']]
                matches = [page for page in sources['pages'].values() if page['article_id'] == item['article_id']
                           and page['page_text'].count(item['text']) == 1]
                if len(matches) != 1:
                    raise ValueError('New witness does not have a unique stored page address')
                page = matches[0]
                offset = page['page_text'].index(item['text'])
                href = os.path.relpath(page['original_pdf_path'], base / 'review_v01').replace('\\', '/')
                panel += '<p>' + escape(item['citation_id'] + ', source_type=' + item['source_type'])
                panel += ' · <a href="' + escape(href, quote=True) + '#page=' + str(page['page_number'])
                panel += '">PDF, страница ' + str(page['page_number']) + '</a></p>'
                for field, hit in {**witness['concept_matches'], **witness['identifier_matches']}.items():
                    if page['page_text'][offset + hit['start']:offset + hit['end']] != hit['text']:
                        raise ValueError('Page-level exact field anchor drift')
                    witnesses.append({'id': cid, 'field': field, 'page': page['page_number'],
                        'start': offset + hit['start'], 'end': offset + hit['end'], 'quote': hit['text']})
                    panel += '<details><summary>' + escape(field + ': ' + hit['text']) + '</summary><pre>'
                    panel += escape(hit['context_text']) + '</pre></details>'
                count = witness['item_count_match']
                if count:
                    if page['page_text'][offset + count['start']:offset + count['end']] != count['text']:
                        raise ValueError('Page-level item count anchor drift')
                    witnesses.append({'id': cid, 'field': 'item_count', 'page': page['page_number'],
                        'start': offset + count['start'], 'end': offset + count['end'], 'quote': count['text']})
                    panel += '<pre>' + escape(count['text']) + '</pre>'
            panels.append(panel + '</section>')
        bindings.append(folder / 'manifest.json')
    if summary['before_ready'] != 7 or summary['after_ready'] != 9 or len(rows) != 30:
        raise ValueError('Unexpected comparison scope/result')
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    report = {'policy': VERSION, 'before_ready': 7, 'after_ready': 9, 'case_count': 30,
        'newly_ready': summary['newly_ready'], 'remaining_lexical_refusals': 21, 'previously_ready_native_inputs_exact': 7,
        'old_service_cases_exact': 81, 'old_native_inputs_exact': 5, 'tests_passed': tests,
        'new_constructed_controls': controls, 'closed_adverse_probes': len(adverse),
        'source_PDF_hashes': pdfs, 'stored_page_hashes_checked': len(pages), 'raw_page_anchors': witnesses,
        'model_POSTs': 0, 'OAuth_exchanges': 0, 'frozen_replay_DB_queries': 0, 'new_slots': 0,
        'fresh_readonly_API_preparations': fresh,
        'scientific_accuracy': None, 'fresh_retrieval_executed': True, 'fresh_PDF_extraction': False,
        'browser_layout_verified': False, 'app_freeze_id': f.sha(f.encode(app)), 'app_bindings': app,
        'scope': 'Exposed questions/frozen sources; admission availability only, not new model quality.',
        'limitations': ['Finite direct-field vocabulary; other21 refusals not scientifically adjudicated.',
                        'Field mentions and local identity/count cues do not prove ownership, entailment or scientific validity.',
                        'Existing baseline admissions are preserved; no new broad false-answer guarantee.',
                        'No automatic rewrite, retry, deployment/reload or permission for new model calls.']}
    folder = base / 'review_v02'
    folder.mkdir(exist_ok=False)
    f.write(folder / 'report.json', report)
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: лексические отказы</title>'
            '<style>body{font:16px system-ui;margin:28px;color:#193440}table{border-collapse:collapse}'
            'td,th{border:1px solid #abc;padding:9px}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            'section{border:1px solid #abc;padding:16px;margin:20px 0}</style><h1>Лексические отказы: проверка исправления</h1>'
            '<p>На тех же30 вопросах и фрагментах подготовлено9 запросов вместо7. '
            'Исправлены два разобранных случая: Nambu_02 иNambu_04. '
            'Остальные21 отказ не объявляются научно обоснованными.</p>'
            '<p>Сравнение на сохранённых источниках выполнено без БД. '
            'Дополнительно две свежие API-подготовки с текущей БД/read-only/rollback точно совпали с прогнозом. '
            'Новых ответов модели, OAuth и слотов0. '
            'Это доступность подготовки, не измерение научной точности.</p><p>'
            + str(tests) + ' tests passed; ' + str(controls) + ' constructed controls. '
            'Все81 прежних service cases/5native inputs и7 готовых текущих inputs сохранены.</p>'
            '<p><a href="report.json">Полный отчёт</a> · '
            '<a href="../adverse_v01.json">Две ошибки первоначального варианта и сохранённые контроли</a> · '
            '<a href="../fresh_api_v01/Nambu_02/result.json">Свежая подготовка Nambu_02</a> · '
            '<a href="../fresh_api_v01/Nambu_04/result.json">Свежая подготовка Nambu_04</a></p>'
            '<table><thead><tr><th>ID</th><th>Вопрос</th><th>До</th><th>После</th><th>Артефакты</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
            '<h2>Точные исходные фразы в двух новых допусках</h2>' + ''.join(panels) + '</html>')
    f.save(folder / 'review.html', body.encode())
    f.write(folder / 'bindings.json', {**app, **f.bindings([*bindings, *map(Path, pdfs)])})
    f.manifest(folder)
    print(json.dumps({k: report[k] for k in ('before_ready', 'after_ready', 'tests_passed', 'new_constructed_controls',
                                          'stored_page_hashes_checked', 'old_service_cases_exact')}))


if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main()
