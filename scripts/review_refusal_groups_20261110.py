"""Review every remaining refusal, the proven source loss and bounded next actions."""

from __future__ import annotations

import ast
import json
import os
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from scripts import assess_refusal_groups_20261110 as assess
from scripts import gigachat_answer_smoke as f
from scripts import refusal_groups_20261110 as capture

GROUP_WORK = {
    'quantitative': {'requirements': ['объект/ячейка', 'показатель', 'значение и исходная единица',
                                    'условия/цикл/период', 'сопоставляемый режим'],
                     'next_check': 'Source-bound numeric/comparison tuples; missing units remain unknown.'},
    'context': {'requirements': ['химическая идентичность', 'метод и операция', 'опорное состояние',
                                'электрод/ячейка', 'явно указанные условия'],
                'next_check': 'Identity/method/scope bindings, not loose keyword translation.'},
    'explanation': {'requirements': ['наблюдаемый эффект', 'авторское объяснение', 'направление связи',
                                    'can/may/suggest и ограничения', 'неподтверждённая интерпретация'],
                    'next_check': 'Preserve epistemic status and causal role; lexical mentions cannot authorize this.'},
    'limits': {'requirements': ['точный проверяемый тезис', 'область применимости', 'контрпример',
                               'отрицание достаточности', 'оговорки и незнание'],
               'next_check': 'Bounded counterexample/caveat validation; no universal claim from absence of a cue.'},
}


def main():
    base = capture.BASE
    for name in ('capture_v01', 'assessment_v01', 'comparison_v01', 'render_v01', 'regression_v01'):
        f.verify_manifest(base / name)
    capture_bindings = capture.read(base / 'capture_v01/bindings.json')
    original_script, archived = str(f.ROOT / 'scripts/refusal_groups_20261110.py'), base / 'capture_script_v01.py'
    if ast.dump(ast.parse(archived.read_text(encoding='utf-8'))) != ast.dump(ast.parse(Path(original_script).read_text(encoding='utf-8'))):
        raise ValueError('Capture script change is not whitespace-only')
    f.verify({str(archived) if p == original_script else p: h for p, h in capture_bindings.items()})
    f.verify(capture.read(base / 'comparison_v01/bindings.json'))
    current = capture.read(base / 'comparison_v01/result.json')
    f.verify_manifest(base / 'diagnostic_packets_v01')
    f.verify(capture.read(base / 'diagnostic_packets_v01/bindings.json'))
    packets = capture.read(base / 'diagnostic_packets_v01/summary.json')
    if packets['case_count'] != 21 or packets['explicit_offline_actions'] != 5:
        raise ValueError('Incomplete diagnostic source packets')
    previous = capture.read(base / 'assessment_v01/result.json')
    cases = {r['case']['id']: r for r in capture.read(base / 'comparison_v01/cases_after.json')}
    chunks = capture.read(base / 'capture_v01/chunks.json')
    articles = capture.read(base / 'capture_v01/articles.json')
    pdfs = capture.read(base / 'capture_v01/original_pdf_text.json')
    annotation = capture.read(assess.ANNOTATIONS)
    proposals, summary, panels, table = [], defaultdict(Counter), [], []
    before_cases = {r['id']: r for r in previous['cases']}
    for row in current['analysis_after']:
        cid, group = row['id'], row['group']
        summary[group]['count'] += 1
        summary[group]['complete_before'] += before_cases[cid]['all_annotated_witnesses_selected']
        summary[group]['complete_after'] += row['all_annotated_witnesses_selected']
        case = cases[cid]
        selected_pages = {p for e in case['preparation']['trace']['evidence'] for p in range(e['page_start'], e['page_end'] + 1)}
        missing = [o for o in row['observations'] if not o['selected_chunk_ids']]
        proposal = None
        if missing:
            candidates = [c for c in chunks.values() if c['article_id'] == case['case']['article_id']
                          and c['text_layer'] == 'original' and all(o['quote'] in c['text'] for o in missing)]
            if not candidates:
                raise ValueError('No one-chunk registered action candidate: ' + cid)
            chosen = min(candidates, key=lambda c: (len(set(range(c['page_start'], c['page_end'] + 1)) - selected_pages),
                                                    len(c['text']), c['chunk_index'], c['chunk_id']))
            proposal = {'id': cid, 'candidate': chosen, 'raw_text_sha256': f.sha(chosen['text'].encode()),
                        'covers_required_pages': sorted({o['page'] for o in missing}),
                        'existing_scope': {'collection': 'literature', 'article_id': chosen['article_id'],
                                           'text_layer': chosen['text_layer'], 'source_type': chosen['source_type']},
                        'extra_chunk_budget_proposed': 1, 'executed_in_runtime': False, 'executed_offline': True,
                        'automatic_continuation': False,
                        'scientific_support': 'not_evaluated'}
            proposals.append(proposal)
        panel = '<section id="' + cid + '"><h2>' + escape(cid) + '</h2><p>' + escape(row['question']) + '</p>'
        panel += '<p><b>Действие:</b> ' + escape(row['action']) + '</p>'
        for o in row['observations']:
            page = pdfs[o['article_id']][o['page'] - 1]
            if page['text'][o['start']:o['end']] != o['quote'] or f.sha(page['text'].encode()) != o['page_text_sha256']:
                raise ValueError('Original page witness differs')
            href = os.path.relpath(articles[o['article_id']]['pdf_path'], base / 'review_v01').replace('\\', '/')
            png = next(r['png'] for r in capture.read(base / 'render_v01/render.json')
                       if r['article_id'] == o['article_id'] and r['page'] == o['page'])
            png_href = os.path.relpath(png, base / 'review_v01').replace('\\', '/')
            panel += '<details><summary>' + escape(o['label'] + ': ' + o['status']) + '</summary><p>'
            panel += '<a href="' + escape(href, quote=True) + '#page=' + str(o['page']) + '">PDF ' + str(o['page']) + '</a> · '
            panel += '<a href="' + escape(png_href, quote=True) + '">Просмотренная страница</a></p><pre>'
            panel += escape(o['quote']) + '</pre></details>'
        if proposal:
            panel += '<p>Зарегистрированный кандидат для отдельного добора: ' + escape(proposal['candidate']['chunk_id'])
            panel += '. Добавлен в отдельный offline-пакет; normal API не изменён этим добором.</p>'
        panel += '<p><a href="../diagnostic_packets_v01/' + cid + '/packet.json">Диагностический пакет источников</a></p>'
        panels.append(panel + '</section>')
        status = ('Все отмеченные сведения выбраны' if row['all_annotated_witnesses_selected']
                  else 'Дополнен offline-пакет; runtime неполный')
        table.append('<tr><td><a href="#' + cid + '">' + cid + '</a></td><td>' + escape(annotation['groups'][group])
                     + '</td><td>' + escape(row['question']) + '</td><td>' + status + '</td><td>'
                     + escape(row['action']) + '</td></tr>')
    if len(proposals) != 5 or current['ready_before'] != current['ready_after']:
        raise ValueError('Unexpected action/admission scope')
    regression = capture.read(base / 'regression_v01/summary.json')
    if regression['actual_service_executions'] != 81 or any(not r['full_service_identical'] or not r['native_identical']
                                                        for r in regression['current_comparisons']):
        raise ValueError('Old service regression changed')
    fresh = []
    for cid in ('Kondo_08', 'Nambu_09'):
        folder = base / 'fresh_api_v01' / cid
        f.verify_manifest(folder)
        f.verify(capture.read(folder / 'bindings.json'))
        result = capture.read(folder / 'result.json')
        if result['status'] != 'insufficient_evidence' or result['model_calls'] or result['oauth_calls'] or result['network_denials']:
            raise ValueError('Fresh check changed admission or sent transport')
        fresh.append(result)
    junit = f.ROOT / 'output/refusal_groups_tests_v02_20261110.xml'
    suites = ET.fromstring(junit.read_bytes()).findall('testsuite')
    if any(int(s.attrib.get(k, '0')) for s in suites for k in ('failures', 'errors', 'skipped')):
        raise ValueError('Affected tests not passed')
    tests = sum(int(s.attrib['tests']) for s in suites)
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    report = {'groups': summary, 'group_work': GROUP_WORK, 'original_refusals': 21, 'fully_selected_before': 13,
        'fully_selected_after': 16, 'ready_before': 9, 'ready_after': 9, 'remaining_refusals': 21,
        'annotated_source_observations': sum(len(r['observations']) for r in current['analysis_after']),
        'context_action_proposals': proposals, 'source_capture': capture.read(base / 'capture_v01/summary.json'),
        'annotation_guided_offline_packets': packets,
        'old_service_cases_exact': 81, 'old_native_inputs_exact': 5, 'current_ready_native_inputs_exact': 9,
        'tests_passed': tests, 'new_controls': 17, 'fresh_readonly_API_checks': fresh,
        'rendered_and_visually_reviewed_pages': 14, 'scientific_accuracy': None, 'model_calls': 0, 'oauth_calls': 0,
        'browser_layout_verified': False, 'app_freeze_id': f.sha(f.encode(app)),
        'historical_capture_code_mapping': {original_script: str(archived)},
        'limitations': ['Assistant post-hoc requirements are not independent gold or a completeness proof.',
                        'Source recovery does not recompute admission or establish semantic/scientific support.',
                        'All21 refusals remain; general bilingual/causal/status admission is not implemented.',
                        'Five one-chunk additions executed in offline diagnostic packets only; no runtime continuation.',
                        'All21 packet coverage is annotation-guided and not independent retrieval performance.']}
    folder = base / 'review_v03'
    folder.mkdir(exist_ok=False)
    f.write(folder / 'report.json', report)
    f.write(folder / 'context_action_proposals.json', proposals)
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: группы отказов</title>'
            '<style>body{font:16px system-ui;color:#183540;margin:24px}table{border-collapse:collapse}'
            'td,th{border:1px solid #abc;padding:10px}section{border:1px solid #abc;padding:16px;margin:20px 0}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>21 отказ: причины и работа по группам</h1>'
            '<p>Опорные сведения полностью выбраны для13→16 из21 разобранных вопросов. '
            'Исправлена потеря уже найденного текста при approximate deduplication в отказавших подготовках. '
            'Готовых запросов по-прежнему9/30: восстановление контекста не снимает отказ автоматически.</p>'
            '<p>Четыре группы:8 количественных,6 методов/идентичности,5 объяснений,2 границ вывода. '
            'Для пяти неполных контекстов выполнено по одному добавлению в отдельные offline-пакеты. '
            'Во всех21 диагностических пакетах есть отмеченные источники; это результат source-aware '
            'аннотации, не новая retrieval accuracy и не научная полнота ответов.</p>'
            '<p>' + str(tests) + ' tests passed;81 старый сценарий/5native и9 текущих ready inputs сохранены. '
            'Две реальные read-only API проверки возвращают прежний отказ с полнее сохранённым контекстом. '
            'Model/OAuth0. Наличие текста и source review не научная accuracy.</p>'
            '<p><a href="report.json">Полный отчёт</a> · <a href="context_action_proposals.json">Пять конкретных действий</a></p>'
            '<table><thead><tr><th>ID</th><th>Группа</th><th>Вопрос</th><th>Источник после исправления</th><th>Действие/ограничение</th>'
            '</tr></thead><tbody>' + ''.join(table) + '</tbody></table>' + ''.join(panels) + '</html>')
    f.save(folder / 'review.html', body.encode())
    bindings = [Path(__file__), assess.ANNOTATIONS, archived, junit, base / 'capture_v01/manifest.json',
                base / 'assessment_v01/manifest.json', base / 'comparison_v01/manifest.json',
                base / 'regression_v01/manifest.json', base / 'render_v01/manifest.json',
                base / 'diagnostic_packets_v01/manifest.json',
                *[base / 'fresh_api_v01' / r['id'] / 'manifest.json' for r in fresh]]
    f.write(folder / 'bindings.json', {**app, **f.bindings(bindings)})
    f.manifest(folder)
    print(json.dumps({k: report[k] for k in ('groups', 'fully_selected_after', 'ready_after', 'tests_passed')}))


if __name__ == '__main__':
    main()
