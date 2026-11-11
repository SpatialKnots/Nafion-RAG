"""Recheck table coordinates, raw anchors and frozen regressions; export local HTML."""

from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import peng_table_binding_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    comparison, regression = run.BASE / 'comparison_v01', run.BASE / 'regression_v01'
    fresh_path = run.BASE / 'fresh_api_v03/Peng_06'
    for folder in (comparison, regression, fresh_path, run.BASE / 'pdf_probe_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    data = run.read(comparison / 'result.json')
    old, fresh = run.read(regression / 'summary.json'), run.read(fresh_path / 'result.json')
    if (data['before_ready'], data['after_ready'], data['newly_ready']) != (14, 15, ['Peng_06']):
        raise ValueError('Unexpected availability result')
    if (old['actual_service_executions'] != 81 or old['old_cases'] != 76
            or not all(r['full_service_identical'] and r['native_identical'] for r in old['current_comparisons'])
            or not all(r['full_service_identical'] for r in old['regressions'])):
        raise ValueError('Historical service regression differs')
    if (not fresh['trace_exact'] or not fresh['native_exact'] or fresh['registry_diagnostics']
            or fresh['network_denials'] or fresh['real_model_calls'] or fresh['real_oauth_calls']):
        raise ValueError('Fresh API preparation not verified')
    suites = list(ET.parse(run.BASE / 'affected_v01.xml').getroot().iter('testsuite'))
    tests = sum(int(s.get('tests', '0')) for s in suites)
    if tests != 477 or any(int(s.get(k, '0')) for s in suites for k in ('failures', 'errors')):
        raise ValueError('Affected tests not all successful')
    trace = run.read(comparison / 'Peng_06/after.json')['trace']
    evidence = [Evidence(**e) for e in trace['evidence']]
    record = answer_facts.selection_records(evidence)['F1']
    raw = json.loads(evidence[0].text)['raw_source']
    facts = record['facts']
    if len(facts) != 12 or any(x['unit'] is not None or 'unit' not in x['unknown_fields'] for x in facts):
        raise ValueError('Unit absence not explicit')
    anchors = 0
    for fact in facts:
        for anchor in [fact['support'], *[v['source'] for v in (
                fact['sample'], fact['value'], *fact['conditions'].values()) if v]]:
            if (raw[anchor['start']:anchor['end']] != anchor['text']
                    or anchor['raw_chunk_sha256'] != f.sha(raw.encode())):
                raise ValueError('Raw field/header anchor drift')
            anchors += 1
    pdf = f.ROOT / 'data/pdf/6ab4542d9156e377_Peng_2021.pdf'
    proof = record['source_grammar']['glyph_decoding']
    if f.sha(pdf.read_bytes()) != proof['original_pdf_sha256']:
        raise ValueError('Original PDF changed')
    positioned = run.read(run.BASE / 'pdf_table_words_v01.json')
    geometry = []
    with fitz.open(pdf) as document:
        page = document[3]
        words = [list(w) for w in page.get_text('words') if w[0] < 300 and w[1] < 150]
        if words != positioned['words'] or page.get_text().strip() not in raw:
            raise ValueError('Fresh full-page extraction or table positions differ')
        for operation in proof['operations']:
            if (document[operation['pdf_page'] - 1].get_text()[operation['pdf_text_offset']] != operation['raw_character']
                    or f.sha(document.extract_font(operation['font_xref'])[3]) != operation['font_program_sha256']):
                raise ValueError('Source glyph/font provenance differs')
        keys = ('before_r0', 'before_sum', 'after_r0', 'after_rs', 'after_rct', 'after_sum')
        for fact in facts:
            label = fact['sample']['text']
            row_label = [w for w in words if w[4] == label]
            if len(row_label) != 1:
                raise ValueError('Nonunique positioned electrolyte label')
            row = sorted([w for w in words if w[1] == row_label[0][1]], key=lambda w: w[0])
            column = keys.index(fact['property'].removeprefix('fitted_resistance_')) + 1
            if len(row) != 7 or row[column][4] != fact['value']['text']:
                raise ValueError('Raw value differs from positioned table column')
            geometry.append({'sample': label, 'property': fact['property'], 'word': row[column]})
    synthetic = run.read(comparison / 'Peng_06/synthetic.json')['selection']
    claim = synthetic['claims'][0]['text']
    if (claim != record['allowed_claim'] or 'Единица в самой таблице не указана' not in
            _prepared_statement_text(evidence[0].text, evidence[0].source_type) or 'Единица в самой таблице не указана' not in
            render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
        raise ValueError('Claim/unit caveat not preserved by both UI adapters')
    out = run.BASE / 'review_v01'
    out.mkdir(exist_ok=False)

    def link(path, label):
        target = Path(path)
        if not target.is_file():
            raise FileNotFoundError(target)
        return '<a href="' + html.escape(os.path.relpath(target, out).replace('\\', '/'), quote=True) + '">' + html.escape(label) + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
        str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td><td>' +
        str(r['full_result_unchanged']) + '</td></tr>' for r in data['cases'])
    fields = ''.join('<tr><td>' + html.escape(x['sample']['text']) + '</td><td>' + html.escape(x['property']) +
        '</td><td>' + html.escape(x['value']['text']) + '</td><td>' + html.escape(x['conditions']['cycle_state']['text']) +
        '</td><td>' + html.escape(x['value']['source']['text']) + '</td></tr>' for x in facts)
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Peng06 — таблица сопротивлений</title>'
        '<style>body{font:16px system-ui;max-width:1150px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%;margin:20px 0}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}img{max-width:100%}</style>'
        '<h1>Peng06: привязка к таблице источника</h1><p>11 ноября 2026. Готовность входных пакетов 14 → 15 из 30. '
        'Остальные 29 результатов и 14 прежних native inputs точны. Реальных ответов модели нет; научная точность не измерена.</p>'
        '<h2>Детерминированный текст после синтетического выбора F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>В самой таблице единица отсутствует. Подпись ohm на рисунке3 наблюдалась визуально, но не перенесена '
        'в табличные факты. Отдельные значения Rs/Rct до циклирования не создаются.</p>'
        '<p>477 тестов, 81 прежний service case и пять native inputs проверены. Три synthetic API исхода: '
        '200 selection, 200 abstention, 502 unbound prose. Guard not_evaluated. Свежая реальная API подготовка: '
        'read-only/rollback, trace/native exact, registry diagnostics0, реальные model/OAuth/slots0.</p>'
        '<p>' + ' · '.join([link(pdf, 'Оригинальный PDF'), link(run.BASE / 'pdf_probe_v01/page3.png', 'PDF3: EIS'),
        link(run.BASE / 'pdf_probe_v01/page4.png', 'PDF4: таблица1'), link(fresh_path / 'result.json', 'Свежая подготовка'),
        link(comparison / 'Peng_06/source_audit.json', 'Raw-привязки'), link(run.BASE / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>12 полей</h2><table><thead><tr><th>Электролит</th><th>Поле</th><th>Значение</th><th>Состояние</th>'
        '<th>Raw-цитата</th></tr></thead><tbody>' + fields + '</tbody></table>'
        '<h2>Сравнение 30 случаев</h2><table><thead><tr><th>ID</th><th>Вопрос</th><th>До</th><th>После</th>'
        '<th>Полный результат прежний</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<h2>Исходная таблица без исправления raw</h2><pre>' + html.escape(facts[0]['support']['text']) + '</pre>'
        '<p>Ограничения: конечная грамматика шести столбцов; source-specific каталог глифов прежний. '
        'Группировка колонок проверена агентом визуально, не независимым экспертом. Сравнение направления — '
        'Decimal-порядок напечатанных значений. Научная ownership/точность, перенос на новые таблицы, '
        'browser layout, полный test suite и deployment не установлены. Старые live scopes закрыты. '
        'Следующие отдельные задачи: Nambu06 и Peng07.</p></html>')
    f.save(out / 'review.html', body.encode())
    result = {'before_ready': 14, 'after_ready': 15, 'newly_ready': ['Peng_06'], 'other_full_results_exact': 29,
        'prior_ready_native_exact': 14, 'raw_anchor_observations': anchors, 'positioned_fields_checked': len(geometry),
        'glyph_operations_verified': len(proof['operations']), 'affected_tests_passed': tests, 'new_tests': 33,
        'historical_service_executions': 81, 'historical_native_exact': 5, 'fresh_API': fresh,
        'unit_status': 'not_printed_in_table_no_inference', 'scientific_accuracy': None,
        'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'geometry': geometry}
    f.write(out / 'report.json', result)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh_path / 'manifest.json', run.BASE / 'affected_v01.xml', run.BASE / 'pdf_table_words_v01.json', pdf]))
    f.manifest(out)
    print(json.dumps({k: v for k, v in result.items() if k != 'geometry'}))


if __name__ == '__main__':
    main()
