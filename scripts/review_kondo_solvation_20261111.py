"""Recheck source definitions, direction anchors and unchanged old preparations."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import kondo_solvation_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression, fresh = base / 'comparison_v01', base / 'regression_v01', base / 'fresh_api_v01/Kondo_03'
    for folder in (comparison, regression, fresh, base / 'pdf_probe_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result, history, prepared = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (23, 24, ['Kondo_03']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Kondo_03'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 948
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    trace = run.read(comparison / 'Kondo_03/after.json')['trace']
    parent = Evidence(**trace['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    raw = json.loads(parent.text)['raw_source']
    facts, anchors = record['facts'], 0
    if (len(facts) != 4 or any(fact['value']['numeric_value'] is not None or fact['unit'] is not None
                              or fact['scientific_ownership_verified'] for fact in facts)
            or facts[0]['value']['text'] != 'increases' or facts[1]['value']['text'] != 'increases'
            or facts[0]['conditions']['solvation']['text'] != 'weaker solvation ability of solvents'
            or facts[1]['conditions']['concentration']['text'] != 'higher salt concentration'
            or facts[0]['conditions']['stability']['text'] != 'destabilized'
            or facts[2]['value']['text'] != 'linear correlation' or facts[2]['conditions']['status']['text'] != 'suggesting'
            or record['source_grammar']['basicity_direction'] != 'not_asserted' or record['arithmetic'] is not None):
        raise ValueError('Directions, correlation status or basicity interpretation differ')
    for fact in facts:
        for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], *fact['conditions'].values()) if v]]:
            if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
                raise ValueError('Raw definition/ion/direction binding drift')
            anchors += 1
    pdf = f.ROOT / 'data/pdf/615828f87ad5a0d9_Kond_2025.pdf'
    with fitz.open(pdf) as doc:
        for number in (2, 3):
            page = doc[number - 1].get_text()
            if page != (base / f'pdf_probe_v01/page{number}.txt').read_text(encoding='utf-8'):
                raise ValueError('Fresh extraction differs from frozen page')
        page = doc[1].get_text()
        if page.strip() not in raw or any(fact['support']['text'] not in page for fact in facts):
            raise ValueError('Raw source or fact support differs from PDF2')
    synthetic = run.read(comparison / 'Kondo_03/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'предложенная авторами интерпретация' not in render(
                {'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
        raise ValueError('Definition/correlation lost by UI adapters')
    out = base / 'review_v01'
    out.mkdir(exist_ok=False)

    def link(path, label):
        if not path.is_file():
            raise FileNotFoundError(path)
        return '<a href="' + html.escape(os.path.relpath(path, out).replace('\\', '/'), quote=True) + '">' + label + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
        str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td></tr>' for r in result['cases'])
    details = ''.join('<details><summary>' + html.escape(fact['property']) + '</summary><pre>' +
        html.escape(json.dumps(fact, ensure_ascii=False, indent=2)) + '</pre></details>' for fact in facts)
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Kondo03 — сольватация и μ</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Kondo03: направления μ и Raman-корреляция</h1>'
        '<p>11 ноября 2026. Подготовленные входы23 → 24 из30; новый Kondo03. Остальные29 полных результатов '
        'и23 прежних native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Четыре записи разделяют два направления, наблюдаемую корреляцию и итоговое объяснение авторов. '
        'Weaker solvation и higher concentration (including localized) дают increases/destabilized в bound source. '
        'Raman-связь сохраняет suggesting/commonly related, не становится независимым causal proof. '
        'Lewis basicity сохраняется как важный фактор без придуманного направления эффекта. '
        'Числа μ, коэффициенты, SEI и graphite thresholds не добавляются. Источник уже присутствовал в top5.</p>'
        '<p>Согласуются все6μ/3cation/2anion/salt/figure и порядок preparation→trend→correlation. '
        'Соответствие имени соли ограничено литеральными monovalent cation+anion codes, не общей '
        'проверкой химической формулы. Нет межфрагментной или межсекционной сборки; нераспознанные '
        'условия/why/proof/negative/универсальные запросы не допускаются.</p>'
        '<p>948 тестов,60 новых; полный mypy app220.81 historical service case/пять native exact. '
        'Четыре synthetic API исхода200/200/502/502 и три synthetic service исхода; guard not_evaluated. '
        'Свежая actual API preparation read-only/rollback, trace/native exact, registry0,9608bytes. '
        'Реальные model/OAuth/newslots0.</p><p>' + ' · '.join([
            link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page2.png', 'Полный PDF2'),
            link(base / 'pdf_probe_v01/page3.png', 'Полный PDF3 / Fig2'),
            link(comparison / 'Kondo_03/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Четыре записи с raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr><th>ID</th>'
        '<th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Первый source probe отказал из-за отсутствия пробела в PDF text FSI−vibration; snapshot/diagnosis '
        'сохранены. Конечный pattern разрешает ноль или более whitespace после заряда перед vibration, '
        'точные raw offsets прежние. Focused60passed с первой попытки; новых glyph aliases не потребовалось.</p>'
        '<p>Ограничения: конечная grammar по открытым development источникам. Не общий semantic/causal validator '
        'или независимое подтверждение Raman-интерпретации. Свежо просмотрены полные Poppler PDF2/3; '
        'пики/fit/точки графика не переизмерялись. Новые статьи/реальные F-ID ответы/browser layout/полный '
        'repository suite/wheel/deployment не проверены. Retrieval/ranking/вопросы/thresholds/prompt/DB/PDF/'
        'index/UI/resources/config прежние. Шесть отказов остаются:4объяснение/2ограничения. '
        'Live scopes закрыты; независимая оценка открыта, план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 23, 'after_ready': 24, 'newly_ready': ['Kondo_03'], 'other_results_exact': 29,
        'old_ready_native_exact': 23, 'facts': 4, 'raw_anchor_observations': anchors, 'fresh_full_PDF_pages_reviewed': 2,
        'tests_passed': 948, 'new_tests': 60, 'historical_service_cases_exact': 81, 'historical_native_exact': 5,
        'fresh_API': prepared, 'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh / 'manifest.json', base / 'affected_v01.xml', pdf, base / 'pdf_probe_v01/manifest.json']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
