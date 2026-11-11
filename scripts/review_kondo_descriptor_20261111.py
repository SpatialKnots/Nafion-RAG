"""Recheck source definitions, direction anchors and unchanged old preparations."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import kondo_descriptor_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression, fresh = base / 'comparison_v02', base / 'regression_v01', base / 'fresh_api_v01/Kondo_01'
    for folder in (comparison, regression, fresh, base / 'pdf_probe_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result, history, prepared = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (17, 18, ['Kondo_01']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Kondo_01'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 607
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    trace = run.read(comparison / 'Kondo_01/after.json')['trace']
    parent = Evidence(**trace['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    raw = json.loads(parent.text)['raw_source']
    facts, anchors = record['facts'], 0
    if len(facts) != 3 or any(fact['value']['numeric_value'] is not None or fact['unit'] is not None
                             or fact['epistemic_status'] != 'source_reported_definition' for fact in facts):
        raise ValueError('Definition mislabeled as numeric measurement')
    if (facts[2]['conditions']['higher_state']['text'], facts[2]['conditions']['lower_state']['text']) != ('unstable', 'stable'):
        raise ValueError('Stability direction changed')
    for fact in facts:
        for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], *fact['conditions'].values()) if v]]:
            if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
                raise ValueError('Raw definition/ion/direction binding drift')
            anchors += 1
    pdf_info = run.read(base / 'pdf_probe_v01/source.json')
    pdf = Path(pdf_info['pdf'])
    if f.sha(pdf.read_bytes()) != pdf_info['pdf_sha256']:
        raise ValueError('Original PDF changed')
    with fitz.open(pdf) as doc:
        page = doc[0].get_text()
        if (page != (base / 'pdf_probe_v01/page1.txt').read_text(encoding='utf-8') or page.strip() not in raw
                or any(fact['support']['text'] not in page for fact in facts)):
            raise ValueError('Fresh page1 differs from source/support')
    synthetic = run.read(comparison / 'Kondo_01/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'сильная корреляция' not in render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
        raise ValueError('Definition/correlation lost by UI adapters')
    out = base / 'review_v01'
    out.mkdir(exist_ok=False)

    def link(path, label):
        if not path.is_file():
            raise FileNotFoundError(path)
        return '<a href="' + html.escape(os.path.relpath(path, out).replace('\\', '/'), quote=True) + '">' + label + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
        str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td></tr>' for r in result['cases'])
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Kondo01 — определение дескриптора</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Kondo01: определение и термодинамический смысл</h1>'
        '<p>11 ноября 2026. Готовность входов17 → 18 из30; новый Kondo01. Остальные29 полных результатов '
        'и17 ready native точны. Реальных ответов модели нет, scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p><p>Три факта: дескриптор, '
        'термодинамическое определение и направление интерпретации. Они помечены source definitions, '
        'не численными измерениями. Сохраняется reported correlation; пороги, механизм и SEI не добавляются.</p>'
        '<p>607 тестов,37 новых; mypy app214.81 прежний service case/пять native exact. Три synthetic API исхода '
        '200/200/502; guard not_evaluated. Свежая actual API подготовка read-only/rollback, trace/native exact, '
        'registry0. Реальные model/OAuth/slots0.</p><p>' + ' · '.join([
        link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page1.png', 'Полный PDF1'),
        link(comparison / 'Kondo_01/source_audit.json', 'Raw-привязки'), link(fresh / 'result.json', 'Свежая API подготовка'),
        link(base / 'affected_v01.xml', 'Тесты')]) + '</p><h2>Точный raw-фрагмент</h2><pre>' +
        html.escape(facts[0]['support']['text']) + '</pre><h2>Все30 случаев</h2><table><thead><tr><th>ID</th>'
        '<th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Ограничения: конечная грамматика по открытым development источникам; источник и направление '
        'проверены агентом, независимая scientific ownership/accuracy не установлена. Новые статьи/другие '
        'формулировки/реальные ответы модели/browser layout/полный suite/deployment не проверены. '
        'Retrieval, вопросы, thresholds, prompt, DB/PDF/index и UI прежние. Остаются12 отказов. '
        'Старые live scopes закрыты.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 17, 'after_ready': 18, 'newly_ready': ['Kondo_01'], 'other_results_exact': 29,
        'old_ready_native_exact': 17, 'facts': 3, 'raw_anchor_observations': anchors, 'fresh_full_PDF_pages_reviewed': 1,
        'tests_passed': 607, 'new_tests': 37, 'historical_service_cases_exact': 81, 'historical_native_exact': 5,
        'fresh_API': prepared, 'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh / 'manifest.json', base / 'affected_v01.xml', pdf, base / 'pdf_probe_v01/manifest.json']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
