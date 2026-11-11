"""Verify source reference directions, assumption, dose and chosen relative zero."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import kondo_potential_method_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression, fresh = base / 'comparison_v01', base / 'regression_v01', base / 'fresh_api_v01/Kondo_02'
    for folder in (comparison, regression, fresh, base / 'capture_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result, history, prepared = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (19, 20, ['Kondo_02']):
        raise ValueError('Unexpected availability')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Kondo_02'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical regression differs')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    ablation = run.read(comparison / 'Kondo_02/ablation.json')
    if ablation != {'ranking_only_ready': False, 'contract_only_ready': False, 'both_ready': True}:
        raise ValueError('Ablation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 702
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    trace = run.read(comparison / 'Kondo_02/after.json')['trace']
    parent = Evidence(**trace['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    raw = json.loads(parent.text)['raw_source']
    facts, anchors = record['facts'], 0
    if len(facts) != 5 or record['arithmetic'] is not None:
        raise ValueError('Method record count or no-calculation policy differs')
    observation, dose, definition, equation, zero = facts
    if ('Fc/Fc+ with reference to Li reference electrode' not in observation['value']['text']
            or definition['value']['text'] != 'Li electrode potential with reference to the Fc/Fc+ redox potential'
            or definition['conditions']['assumption']['text'] != 'supposing that the redox potential of Fc/Fc+ was constant'
            or dose['unit']['text'] != 'mmol dm−3' or zero['operation'] != 'chosen_relative_zero_convention'
            or zero['conditions']['basis']['text'] != 'LiFSI/DME' or zero['conditions']['ratio']['text'] != '1/10'
            or equation['value']['text'] != 'μLi+ = FELi + constant'):
        raise ValueError('Source reference/dose/formula/zero owner differs')
    for fact in facts:
        for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], fact['unit'], fact['method'],
                                                             *fact['conditions'].values()) if v]]:
            if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
                raise ValueError('Raw method/reference binding drift')
            anchors += 1
    pools = {c['id']: c['rows'] for c in run.read(base / 'capture_v01/cases.json')}
    if len(trace['retrieval']['results']) != 5 or any(r not in pools['Kondo_02'] for r in trace['retrieval']['results']):
        raise ValueError('Ranking altered raw objects or top5')
    pdf = f.ROOT / 'data/pdf/615828f87ad5a0d9_Kond_2025.pdf'
    expected_pdf_sha = run.read(base / 'capture_v01/bindings.json')[str(pdf)]
    if f.sha(pdf.read_bytes()) != expected_pdf_sha:
        raise ValueError('Original PDF changed')
    with fitz.open(pdf) as document:
        text = document[4].get_text()
        if (text != (base / 'capture_v01/page5.txt').read_text(encoding='utf-8') or text.strip() not in raw
                or any(fact['support']['text'] not in text for fact in facts)):
            raise ValueError('Fresh page5/support differs from selected raw')
    synthetic = run.read(comparison / 'Kondo_02/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'Предполагая постоянство' not in render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})
            or '25' in claim):
        raise ValueError('Assumption/temperature scope lost by rendering')
    out = base / 'review_v01'
    out.mkdir(exist_ok=False)

    def link(path, label):
        if not path.is_file():
            raise FileNotFoundError(path)
        return '<a href="' + html.escape(os.path.relpath(path, out).replace('\\', '/'), quote=True) + '">' + label + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
        str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td></tr>' for r in result['cases'])
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Kondo02 — метод и относительный ноль</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Kondo02: CV, опорная пара и относительный ноль</h1>'
        '<p>11 ноября 2026. Готовность входов19 → 20 из30; остальные29 full results и19 ready native exact. '
        'Реальных ответов модели нет, scientific accuracy не измерена.</p><h2>Серверный текст после synthetic F1</h2><p>' +
        html.escape(claim) + '</p><p>Сохранены разные направления: редокс-потенциал пары относительно Li reference '
        'при измерении и определение ELi относительно редокс-пары. Постоянство потенциала пары — предположение '
        'источника; ноль — выбранный относительный стандарт. Численный μ не рассчитывается, температура cycling '
        'не переносится на CV. Доза берётся из явной mmol dm−3 записи; shorthand не исправляется автоматически.</p>'
        '<p>Нужный Methods-фрагмент был вне top5. Узкая роль сохраняет неизменённый объект существующего полного '
        'пула разрешённой статьи, без дополнительных lookup/изменения top5/filters/scores. Ranking-only и '
        'contract-only сохраняют отказ.702 теста,51 новый; mypy app216.81 исторический service case/пять native exact. '
        'Четыре synthetic API исхода:200 F1/200 abstention/502 prose/502 wrong citation; guard not_evaluated. '
        'Свежая actual API подготовка read-only/rollback, trace/native exact/registry0, реальные model/OAuth/slots0.</p><p>' +
        ' · '.join([link(pdf, 'Исходный PDF'), link(base / 'capture_v01/page5.png', 'Полный PDF5'),
        link(comparison / 'Kondo_02/ablation.json', 'Аblation'), link(comparison / 'Kondo_02/source_audit.json', 'Raw-привязки'),
        link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Точный raw-контекст приготовления</h2><pre>' + html.escape(dose['support']['text']) + '</pre>'
        '<h2>Точный raw-контекст метода</h2><pre>' + html.escape(observation['support']['text']) + '</pre>'
        '<h2>Все30 случаев</h2><table><thead><tr><th>ID</th><th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' +
        rows + '</tbody></table><p>Первые127passed/2failed: пропущен Previously reported перед preparation; '
        'API-test выбирал E1 вместо фактического E2. Снимки сохранены, guard/fixture исправлены; wrong citation '
        'теперь отдельный502 контроль. Отдельный constructed probe допускал M вместо mmol-dose shorthand; '
        'источник/проба сохранены, неизвестные или противоречивые сокращения теперь отклоняются.</p>'
        '<p>Ограничения: конечная exposed source-method grammar, не независимая научная проверка потенциалов '
        'или универсальности redox reference. Другие методики/формы записи/реальные ответы модели/transfer/'
        'browser layout/полный suite/wheel/deployment не проверены. Остаются10 отказов, live scopes закрыты.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 19, 'after_ready': 20, 'newly_ready': ['Kondo_02'], 'other_results_exact': 29,
        'old_ready_native_exact': 19, 'fresh_pool_old_ranks_exact': 30, 'top_k': 5, 'additional_lookups': 0,
        'facts': 5, 'raw_anchor_observations': anchors, 'tests_passed': 702, 'new_tests': 51,
        'historical_service_cases_exact': 81, 'historical_native_exact': 5, 'ablation': ablation,
        'fresh_API': prepared, 'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh / 'manifest.json', base / 'affected_v01.xml', pdf, base / 'capture_v01/manifest.json']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
