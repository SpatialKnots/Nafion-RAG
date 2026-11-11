"""Verify natural context retention, bounded comparison and source provenance."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import peng_best_ce_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression, fresh = base / 'comparison_v02', base / 'regression_v02', base / 'fresh_api_v02/Peng_07'
    for folder in (comparison, regression, fresh, base / 'capture_v02', base / 'glyph_audit_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result, history, prepared = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (16, 17, ['Peng_07']):
        raise ValueError('Unexpected availability')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Peng_07'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical regression differs')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    ablation = run.read(comparison / 'Peng_07/ablation.json')
    if ablation != {'ranking_only_ready': False, 'contract_only_ready': False, 'both_ready': True}:
        raise ValueError('Ablation differs')
    suites = list(ET.parse(base / 'affected_v02.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 570
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Tests not all successful')
    trace = run.read(comparison / 'Peng_07/after.json')['trace']
    parent = Evidence(**trace['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    raw = json.loads(parent.text)['raw_source']
    facts, anchors = record['facts'], 0
    if 'approximation' not in facts[0]['conditions'] or 'approximation' in facts[1]['conditions']:
        raise ValueError('Approximation owner differs')
    for fact in facts:
        for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], fact['unit'],
                                                             *fact['conditions'].values()) if v]]:
            if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
                raise ValueError('Raw field binding differs')
            anchors += 1
    pools = {c['id']: c['rows'] for c in run.read(base / 'capture_v02/cases.json')}
    selected = trace['retrieval']['results']
    if len(selected) != 5 or any(r not in pools['Peng_07'] for r in selected):
        raise ValueError('New ranking did not retain original source objects/top5')
    resource = f.ROOT / 'app/resources/reviewed_best_ce_glyph_aliases_v01.json'
    catalogue = run.read(resource)
    proof = record['source_grammar']['glyph_decoding']
    if f.sha(resource.read_bytes()) != proof['catalogue_sha256']:
        raise ValueError('Catalogue changed')
    pdf = f.ROOT / 'data/pdf/6ab4542d9156e377_Peng_2021.pdf'
    if f.sha(pdf.read_bytes()) != catalogue['pdf_sha256']:
        raise ValueError('Original PDF changed')
    operations = 0
    by_chunk = {r['chunk_id']: r for r in pools['Peng_07']}
    with fitz.open(pdf) as document:
        text = document[4].get_text()
        if text != (base / 'capture_v02/page5.txt').read_text(encoding='utf-8') or text.strip() not in raw:
            raise ValueError('Fresh page5 differs from selected raw')
        for entry in catalogue['entries']:
            row = by_chunk[entry['chunk_id']]
            if f.sha(row['full_text'].encode()) != entry['raw_sha256']:
                raise ValueError('Catalogue parent drift')
            for op in entry['operations']:
                if (row['full_text'][op['raw_start']:op['raw_end']] != op['raw_character']
                        or text[op['pdf_text_offset']] != op['raw_character']
                        or f.sha(document.extract_font(op['font_xref'])[3]) != op['font_program_sha256']):
                    raise ValueError('PDF glyph/font binding drift')
                operations += 1
    synthetic = run.read(comparison / 'Peng_07/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (synthetic['claims'][0]['text'] != claim or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'приблизительно 95.3%' not in render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
        raise ValueError('UI scope/approximation drift')
    out = base / 'review_v01'
    out.mkdir(exist_ok=False)

    def link(path, label):
        if not path.is_file():
            raise FileNotFoundError(path)
        return '<a href="' + html.escape(os.path.relpath(path, out).replace('\\', '/'), quote=True) + '">' + label + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
        str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td></tr>' for r in result['cases'])
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Peng07 — контекст и CE</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Peng07: контекст сравнения электролитов</h1>'
        '<p>11 ноября 2026. Готовность входов16 → 17 из30. Остальные29 полных результатов и16 ready native точны. '
        'Реальных ответов модели нет; scientific accuracy не измерена.</p><h2>Серверный текст после synthetic F1</h2><p>' +
        html.escape(claim) + '</p><p>Нужная страница отсутствовала в старом top5. Узкая роль сравнения для запрошенной '
        'полуячейки сохраняет исходный фрагмент из существующего полного пула разрешённой статьи; top5/фильтры/'
        'scores/число lookup прежние. Контекст и контракт по отдельности сохраняют отказ; вместе готовый вход.</p>'
        '<p>570 тестов,41 новый; mypy app214.81 исторический service case/пять native exact. Три synthetic API исхода '
        '200/200/502. Guard not_evaluated. Свежий actual API read-only/rollback: trace/native exact, registry0. '
        'Реальные model/OAuth/slots0.</p><p>' + ' · '.join([
        link(pdf, 'Исходный PDF'), link(base / 'capture_v02/page5.png', 'Полный PDF5'),
        link(comparison / 'Peng_07/ablation.json', 'Аblation'), link(comparison / 'Peng_07/source_audit.json', 'Raw-привязки'),
        link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v02.xml', 'Тесты')]) + '</p>'
        '<h2>Точный raw-фрагмент</h2><pre>' + html.escape(facts[0]['support']['text']) + '</pre><h2>Все30 случаев</h2>'
        '<table><thead><tr><th>ID</th><th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Ограничения: finite exposed grammar, заявленное авторами сравнение среди рассмотренных вариантов; '
        'не установлен универсальный максимум, причинный SEI механизм или независимая научная точность. '
        'Glyph interpretation проверена агентом, новые raw не исправляются автоматически. Реальные ответы модели, '
        'browser layout, полный suite/wheel/deployment не проверены. Остаются13 отказов других групп; '
        'все восемь исходных количественных случаев готовы-unsent. Live scopes закрыты.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 16, 'after_ready': 17, 'newly_ready': ['Peng_07'], 'other_results_exact': 29,
        'old_ready_native_exact': 16, 'full_pool_old_rank_cases_exact': 30, 'top_k': 5, 'additional_lookups': 0,
        'raw_anchor_observations': anchors, 'glyph_operations_verified': operations, 'physical_glyph_observations': 1,
        'tests_passed': 570, 'new_tests': 41, 'historical_service_cases_exact': 81, 'historical_native_exact': 5,
        'ablation': ablation, 'fresh_API': prepared, 'real_model_calls': 0, 'real_oauth_calls': 0,
        'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh / 'manifest.json', base / 'affected_v02.xml', pdf, resource, base / 'capture_v02/manifest.json']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
