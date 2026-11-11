"""Recheck source definitions, direction anchors and unchanged old preparations."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import kondo_threshold_scope_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression, fresh = base / 'comparison_v02', base / 'regression_v03', base / 'fresh_api_v02/Kondo_10'
    for folder in (comparison, regression, fresh, base / 'capture_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result, history, prepared = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (26, 27, ['Kondo_10']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Kondo_10'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v03.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 1127
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    trace = run.read(comparison / 'Kondo_10/after.json')['trace']
    parent = Evidence(**trace['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    raw = json.loads(parent.text)['raw_source']
    facts, anchors = record['facts'], 0
    if (len(facts) != 6 or record['arithmetic'] is not None
            or facts[0]['value']['text'] != 'various types of LiFSI-based electrolytes'
            or facts[0]['conditions']['applicability']['text'] != 'generally applicable'
            or facts[1]['value']['text'] != 'may be shifted'
            or [fact['value']['text'] for fact in facts[2:]] != ['SEI forming additives',
                'extremely unstable solvent/salt for reduction', 'passivating binders', 'functional surface coatings']
            or any(fact['scientific_ownership_verified'] or fact['unit'] is not None for fact in facts)
            or record['source_grammar']['shift_direction'] != 'not_asserted'
            or record['source_grammar']['shift_magnitude'] != 'not_asserted'):
        raise ValueError('Applicability, modality, four conditions or shift assertion differs')
    for fact in facts:
        for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], *fact['conditions'].values()) if v]]:
            if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
                raise ValueError('Raw definition/ion/direction binding drift')
            anchors += 1
    pdf = f.ROOT / 'data/pdf/615828f87ad5a0d9_Kond_2025.pdf'
    with fitz.open(pdf) as doc:
        page = doc[4].get_text()
        if (page != (base / 'capture_v01/page5.txt').read_text(encoding='utf-8') or page.strip() not in raw
                or any(f['support']['text'] not in page for f in facts)):
            raise ValueError('Complete PDF5 source or bound applicability/caveat differs')
    synthetic = run.read(comparison / 'Kondo_10/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'порог может сдвигаться' not in render(
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
    if run.read(base / 'capture_v01/result.json')['fresh_pool_cases_exact'] != 30:
        raise ValueError('Pre-edit complete article-pool baseline differs')
    if run.read(comparison / 'Kondo_10/ablation.json') != {
            'ranking_only_ready': False, 'contract_only_ready': False, 'both_ready': True}:
        raise ValueError('Ablation differs')
    pool = next(r['rows'] for r in run.read(base / 'capture_v01/cases.json') if r['id'] == 'Kondo_10')
    selected = trace['retrieval']['results']
    if len(selected) != 5 or not all(row in pool for row in selected):
        raise ValueError('Retained context changed or is not an original pool object')
    old = base / 'comparison_v01'
    f.verify_manifest(old)
    bound = run.read(old / 'bindings.json')
    for original, snapshot in [('app/generation/quantitative_facts.py', 'quantitative_facts.py'),
                               ('scripts/kondo_threshold_scope_20261111.py', 'original_driver.py')]:
        if bound[str(f.ROOT / original)] != f.sha((base / 'typing_attempt_v01' / snapshot).read_bytes()):
            raise ValueError('Pre-typing source mapping differs')
    f.verify({p: h for p, h in bound.items() if p not in {
        str(f.ROOT / 'app/generation/quantitative_facts.py'), str(f.ROOT / 'scripts/kondo_threshold_scope_20261111.py')}})
    for row in result['cases']:
        for source in (old / row['id']).glob('*.json'):
            if source.name != 'manifest.json' and source.read_bytes() != (comparison / row['id'] / source.name).read_bytes():
                raise ValueError('Valid input or outcome changed after typing-only name correction')
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Kondo10 — область порога μ</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Kondo10: область применимости и возможный сдвиг</h1>'
        '<p>11 ноября 2026. Подготовленные входы26 → 27 из30; новый Kondo10. Остальные29 полных результатов '
        'и26 прежних native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Шесть записей: generally applicable в пределах разных типов LiFSI-based электролитов; '
        'may be shifted при существенно изменённой SEI и четыре названных контекста. Знак/величина сдвига '
        'и численное универсальное значение порога не добавляются. Возможность не превращена в '
        'обязательное наблюдаемое изменение; LiFSI scope не расширен на все соли.</p>'
        '<p>До app edits fresh readonly capture воспроизводит все30 oldtop5/role metadata. Conclusion '
        'PDF5 отсутствовал в прежнем top5. Узкая threshold_transfer_limits роль сохраняет неизменённый '
        'объект существующего пула статьи, same top5/scores/filters/lookupcount. Ranking-only и '
        'contract-only отказывают; вместе ready. Query proof/universal exception только для точного '
        'fullmatch исходного вопроса; status exception — literal may be shifted в полностью bound block.</p>'
        '<p>Финальные1127 тестов,48 новых; mypy app223 и Ruff8.81 historical service cases/five native exact '
        'в final regression_v03. Четыре synthetic actual API200/200/502/502 и три service исхода, '
        'guard not_evaluated. Final fresh actual API readonly/rollback trace/native exact, registry0; '
        'реальные model/OAuth/slots0.</p><p>' + ' · '.join([link(pdf, 'Исходный PDF'),
            link(base / 'capture_v01/page5.png', 'Полный PDF5'),
            link(comparison / 'Kondo_10/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v03.xml', 'Тесты')]) + '</p>'
        '<h2>Шесть записей с raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr><th>ID</th>'
        '<th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Initial focused48passed, affected1127passed, но mypy дал57 diagnostics: новый плоский matches '
        'переиспользовал имя вложенного списка в других ветках. Исправлено уникальным threshold_candidates; '
        'AST после отображения имени точно совпадает, научная логика/текст прежние. Исходник, полный log '
        'и failed maintenance assertion сохранены: первая нормализация затрагивала уже существующее имя, '
        'остановилась до writes. Старый comparison безопасно отказался перезаписатьv01; intermediate '
        'regression/affected outputs сохранены. Финальные comparison_v02/regression_v03/affected_v03/'
        'fresh_api_v02 проверены заново; все30caseJSON/27native byte-exact к исходномуv01.</p>'
        '<p>Ограничения: finite source grammar, не общий proof/semantic/causal validator. Полный Poppler '
        'PDF5 визуально просмотрен, raw/PDFhash сохранены; новые статьи/реальные F-ID ответы/независимая '
        'scientific accuracy/browser/full repository suite/wheel/deployment не проверены. '
        'Вопросы/prompt/thresholds/UI/DB/PDF/index/resources/config прежние; ranking изменён узкой ролью. '
        'Остаются3explanation refusals Nambu05/07/08. Live scopes закрыты; план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 26, 'after_ready': 27, 'newly_ready': ['Kondo_10'], 'other_results_exact': 29,
        'old_ready_native_exact': 26, 'facts': 6, 'raw_anchor_observations': anchors, 'fresh_full_PDF_pages_reviewed': 1,
        'tests_passed': 1127, 'new_tests': 48, 'historical_service_cases_exact': 81, 'historical_native_exact': 5,
        'fresh_API': prepared, 'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh / 'manifest.json', base / 'affected_v03.xml', pdf, base / 'capture_v01/manifest.json']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
