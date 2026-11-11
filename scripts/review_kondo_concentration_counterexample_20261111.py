"""Recheck source definitions, direction anchors and unchanged old preparations."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import kondo_concentration_counterexample_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression, fresh = base / 'comparison_v01', base / 'regression_v01', base / 'fresh_api_v01/Kondo_07'
    for folder in (comparison, regression, fresh, base / 'pdf_probe_v01', base / 'basis_probe_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result, history, prepared = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (24, 25, ['Kondo_07']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Kondo_07'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 1007
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    trace = run.read(comparison / 'Kondo_07/after.json')['trace']
    parent = Evidence(**trace['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    raw = json.loads(parent.text)['raw_source']
    facts, anchors = record['facts'], 0
    if (len(facts) != 4 or record['arithmetic'] is not None
            or facts[0]['value']['text'] != 'cannot be defined by the salt concentration'
            or [(f['sample']['text'], f['value']['text'], f['conditions']['mu']['text']) for f in facts[1:3]] != [
                ('LiFSI/DEE', '1/1.6', '23.2'), ('LiFSI/F3MEE', '1/4.4', '24.1')]
            or any(f['conditions']['mu_unit']['text'] != 'kJ mol−1' or
                   f['conditions']['reference_ratio']['text'] != '1/10' for f in facts[1:3])
            or facts[3]['value']['text'] != 'can be a descriptor of graphite reactions'
            or record['source_grammar']['similarity'] != 'source_reported_not_independent_tolerance'
            or any(f['scientific_ownership_verified'] for f in facts)):
        raise ValueError('Molar ratio/value respectively binding, reference or interpretation differs')
    for fact in facts:
        for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], *fact['conditions'].values()) if v]]:
            if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
                raise ValueError('Raw definition/ion/direction binding drift')
            anchors += 1
    pdf = f.ROOT / 'data/pdf/615828f87ad5a0d9_Kond_2025.pdf'
    with fitz.open(pdf) as doc:
        page2, page3 = doc[1].get_text(), doc[2].get_text()
        if (page2 != (base / 'basis_probe_v01/page2.txt').read_text(encoding='utf-8')
                or page3 != (base / 'pdf_probe_v01/page3.txt').read_text(encoding='utf-8')
                or any(p.strip() not in raw for p in (page2, page3))
                or any(fact['support']['text'] not in page3 for fact in facts)
                or any(value['source']['text'] not in page2 for fact in facts[1:3]
                       for key, value in fact['conditions'].items() if key.startswith('reference_'))):
            raise ValueError('Counterexample/reference raw or PDF2/3 extraction differs')
    synthetic = run.read(comparison / 'Kondo_07/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'может служить дескриптором' not in render(
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
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Kondo07 — контрпример концентрации</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Kondo07: концентрация и растворитель</h1>'
        '<p>11 ноября 2026. Подготовленные входы24 → 25 из30; новый Kondo07. Остальные29 полных результатов '
        'и24 прежних native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Четыре записи: source limitation, два salt/solvent ratio→μ сопоставления и modal descriptor '
        'interpretation. Сохранены respectively, общая печатная kJ mol−1 единица, by-mol basis, '
        'относительная база LiFSI/DME1/10 и can be. Similar передаётся как оценка авторов, без придуманного '
        'допуска близости. Различие положительных мольных отношений проверяется точными рациональными '
        'числами: эквивалентные1/1.6 и2/3.2 не проходят как разные концентрации. Новые значения не вычисляются '
        'и в молярность не переводятся. Из контрпримера не следует отсутствие эффекта концентрации.</p>'
        '<p>Только точный шаблон вопроса о неуниверсальности концентрации получает отдельную ветку до '
        'общего why/negative veto. После удаления единственной библиографической ссылки и стандартного '
        'preamble требуется fullmatch всего тела; лишние условия/отрицания/каузальные вопросы отказывают. '
        'Исходный вопрос и prompt прежние. Source reference и весь пример требуются в одном complete parent.</p>'
        '<p>1007 тестов,59 новых; полный mypy app221.81 historical service case/пять native exact. '
        'Четыре synthetic API исхода200/200/502/502 и три synthetic service исхода; guard not_evaluated. '
        'Свежая actual API preparation read-only/rollback, trace/native exact, registry0,8976bytes. '
        'Реальные model/OAuth/newslots0.</p><p>' + ' · '.join([
            link(pdf, 'Исходный PDF'), link(base / 'basis_probe_v01/page2.png', 'Полный PDF2 / база μ'),
            link(base / 'pdf_probe_v01/page3.png', 'Полный PDF3 / контрпример'),
            link(comparison / 'Kondo_07/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Четыре записи с raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr><th>ID</th>'
        '<th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Focused59passed с первой попытки. Initial source probe eligible. Новые glyph aliases/resources/'
        'configuration/ranking не потребовались. Все raw тексты прежние. SI figure IDs сохранены как '
        'печатные указатели источника; сами supplementary материалы заново не проверялись.</p>'
        '<p>Ограничения: конечная grammar по открытым development источникам, не общий semantic/causal '
        'или theorem validator. Названная авторами близость μ не является независимой оценкой погрешности; '
        'metal-prefix binding соли не заменяет chemical formula validation. Свежо просмотрены полные '
        'Poppler PDF2/3; новые статьи/реальные F-ID ответы/browser layout/полный repository suite/wheel/'
        'deployment не проверены. Retrieval/ranking/вопросы/thresholds/prompt/DB/PDF/index/UI/resources/config '
        'прежние. Пять отказов остаются:3объяснение/2ограничения. Live scopes закрыты; независимая оценка '
        'открыта, план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 24, 'after_ready': 25, 'newly_ready': ['Kondo_07'], 'other_results_exact': 29,
        'old_ready_native_exact': 24, 'facts': 4, 'raw_anchor_observations': anchors, 'fresh_full_PDF_pages_reviewed': 2,
        'tests_passed': 1007, 'new_tests': 59, 'historical_service_cases_exact': 81, 'historical_native_exact': 5,
        'fresh_API': prepared, 'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh / 'manifest.json', base / 'affected_v01.xml', pdf, base / 'pdf_probe_v01/manifest.json',
        base / 'basis_probe_v01/manifest.json']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
