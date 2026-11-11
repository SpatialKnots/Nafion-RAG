"""Verify source-declared names, degree correspondence and frozen regressions."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import nambu_identity_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression, fresh = base / 'comparison_v01', base / 'regression_v01', base / 'fresh_api_v01/Nambu_01'
    for folder in (comparison, regression, fresh, base / 'pdf_probe_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result, history, prepared = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (18, 19, ['Nambu_01']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Nambu_01'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 651
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    parent = Evidence(**run.read(comparison / 'Nambu_01/after.json')['trace']['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    raw = json.loads(parent.text)['raw_source']
    facts, anchors = record['facts'], 0
    if (len(facts) != 3 or any(fact['value']['numeric_value'] is not None or fact['unit'] is not None
                             or fact['epistemic_status'] != 'source_declared_chemical_identity' for fact in facts)):
        raise ValueError('Identity mislabeled as numeric measurement')
    expected = [('FETFEE', 'tetrafluorinated'), ('ETFEE', 'trifluorinated'), ('EFEE', 'monofluorinated')]
    if [(fact['sample']['text'], fact['conditions']['degree']['text']) for fact in facts] != expected:
        raise ValueError('Source alias/degree correspondence differs')
    for fact in facts:
        if fact['value']['normalization'] != 'nfkc_dehyphenation_whitespace_then_chemical_name_whitespace_compaction':
            raise ValueError('Chemical-name normalization not explicit')
        for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], *fact['conditions'].values()) if v]]:
            if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
                raise ValueError('Raw chemical name/base/degree binding drift')
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
    synthetic = run.read(comparison / 'Nambu_01/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'тетрафторированный' not in render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
        raise ValueError('Identity/source language lost by UI adapters')
    out = base / 'review_v01'
    out.mkdir(exist_ok=False)

    def link(path, label):
        if not path.is_file():
            raise FileNotFoundError(path)
        return '<a href="' + html.escape(os.path.relpath(path, out).replace('\\', '/'), quote=True) + '">' + label + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
        str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td></tr>' for r in result['cases'])
    identities = ''.join('<tr><td>' + html.escape(fact['sample']['text']) + '</td><td>' + html.escape(fact['value']['text']) +
        '</td><td>' + html.escape(fact['conditions']['degree']['text']) + '</td></tr>' for fact in facts)
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Nambu01 — химические идентичности</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Nambu01: три эфира и степени фторирования</h1>'
        '<p>11 ноября 2026. Готовность входов18 → 19 из30; новый Nambu01. Остальные29 полных результатов '
        'и18 ready native точны. Реальных ответов модели нет, scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<table><thead><tr><th>Обозначение</th><th>Полное название в источнике</th><th>Класс</th></tr></thead><tbody>' +
        identities + '</tbody></table><p>Соответствие сопоставлено по обозначениям: порядок имён и порядок классификации '
        'в статье различаются. Конечная проверка ethoxy-локантов/fluoro-приставок и двух эквивалентных концов '
        'этого симметричного основания защищает от простых противоречий/дубликатов. Это не общий structure toolkit.</p>'
        '<p>651 тест,44 новых; mypy app215.81 прежний service case/пять native exact. Три synthetic API исхода '
        '200/200/502; guard not_evaluated. Свежая actual API подготовка read-only/rollback, trace/native exact, '
        'registry0. Реальные model/OAuth/slots0.</p><p>' + ' · '.join([
        link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page1.png', 'Полный PDF1'),
        link(comparison / 'Nambu_01/source_audit.json', 'Raw-привязки'), link(fresh / 'result.json', 'Свежая API подготовка'),
        link(base / 'affected_v01.xml', 'Тесты')]) + '</p><h2>Точный raw-фрагмент</h2><pre>' +
        html.escape(facts[0]['support']['text']) + '</pre><h2>Все30 случаев</h2><table><thead><tr><th>ID</th>'
        '<th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Первый focused:112passed/1failed, inline References не был исключён; отдельный constructed probe '
        'также допускал симметричный дубликат. Снимки/ошибка/probe сохранены; финальный focused114passed.</p>'
        '<p>Ограничения: конечная source-declared identity grammar по открытым development источникам, '
        'не независимая проверка molecular graph/стереохимии/научной accuracy. Только явные названия, '
        'локанты и классы источника; новые статьи/реальные ответы модели/browser layout/полный suite/'
        'deployment не проверены. Retrieval/вопросы/thresholds/prompt/DB/PDF/index/UI прежние. '
        'Остаются11 отказов. Старые live scopes закрыты.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 18, 'after_ready': 19, 'newly_ready': ['Nambu_01'], 'other_results_exact': 29,
        'old_ready_native_exact': 18, 'facts': 3, 'raw_anchor_observations': anchors, 'fresh_full_PDF_pages_reviewed': 1,
        'tests_passed': 651, 'new_tests': 44, 'historical_service_cases_exact': 81, 'historical_native_exact': 5,
        'fresh_API': prepared, 'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh / 'manifest.json', base / 'affected_v01.xml', pdf, base / 'pdf_probe_v01/manifest.json']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
