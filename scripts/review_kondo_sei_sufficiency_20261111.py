"""Recheck source definitions, direction anchors and unchanged old preparations."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import kondo_sei_sufficiency_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression, fresh = base / 'comparison_v03', base / 'regression_v02', base / 'fresh_api_v01/Kondo_09'
    for folder in (comparison, regression, fresh, base / 'capture_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result, history, prepared = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (25, 26, ['Kondo_09']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Kondo_09'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 1079
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    trace = run.read(comparison / 'Kondo_09/after.json')['trace']
    parent = Evidence(**trace['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    raw = json.loads(parent.text)['raw_source']
    facts, anchors = record['facts'], 0
    if (len(facts) != 5 or record['arithmetic'] is not None
            or facts[0]['conditions']['status']['text'] != 'we suppose'
            or 'to some extent' not in facts[1]['value']['text']
            or facts[2]['conditions']['similar']['text'] != 'similar FSI anion-derived SEI'
            or facts[3]['value']['text'] != 'could not be suppressed'
            or facts[3]['conditions']['formed']['text'] != '1/2'
            or facts[3]['conditions']['challenge']['text'] != '1/3'
            or facts[4]['value']['text'] != 'may not be the only dominant factor'
            or any(f['scientific_ownership_verified'] for f in facts)):
        raise ValueError('SEI role, origin, sequence, partial contribution or modality differs')
    for fact in facts:
        for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], *fact['conditions'].values()) if v]]:
            if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
                raise ValueError('Raw definition/ion/direction binding drift')
            anchors += 1
    pdf = f.ROOT / 'data/pdf/615828f87ad5a0d9_Kond_2025.pdf'
    with fitz.open(pdf) as doc:
        page3, page4 = doc[2].get_text(), doc[3].get_text()
        if (page3 != (base / 'capture_v01/page3.txt').read_text(encoding='utf-8')
                or page4 != (base / 'capture_v01/page4.txt').read_text(encoding='utf-8')
                or any(p.strip() not in raw for p in (page3, page4))
                or any(f['support']['text'] not in page3 for f in facts[:4])
                or facts[4]['support']['text'] not in page4):
            raise ValueError('Observations/conclusion or complete source differs from PDF3/4')
    synthetic = run.read(comparison / 'Kondo_09/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'может быть не единственным' not in render(
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
        raise ValueError('Fresh complete-pool baseline differs')
    ablation = run.read(comparison / 'Kondo_09/ablation.json')
    if ablation != {'ranking_only_ready': False, 'contract_only_ready': False, 'both_ready': True}:
        raise ValueError('Ablation differs')
    pools = {c['id']: c['rows'] for c in run.read(base / 'capture_v01/cases.json')}
    retrieved = trace['retrieval']['results']
    if len(retrieved) != 5 or not all(row in pools['Kondo_09'] for row in retrieved):
        raise ValueError('Retained source changed or not in existing article pool')
    # Preserve and validate historical source versions without rebinding their manifests.
    historical = [('comparison_v01', 'section_probe_v01/original.py', 'comparison_reader_v01/original_driver.py'),
                  ('comparison_v02', 'section_guard_v02/original.py', 'section_guard_v02/original_driver.py')]
    for name, module, driver in historical:
        folder = base / name
        f.verify_manifest(folder)
        bound = run.read(folder / 'bindings.json')
        for original, saved in [('app/generation/sei_sufficiency.py', module),
                                ('scripts/kondo_sei_sufficiency_20261111.py', driver)]:
            if bound[str(f.ROOT / original)] != f.sha((base / saved).read_bytes()):
                raise ValueError('Historical source mapping differs')
        f.verify({p: h for p, h in bound.items() if p not in {
            str(f.ROOT / 'app/generation/sei_sufficiency.py'), str(f.ROOT / 'scripts/kondo_sei_sufficiency_20261111.py')}})
        for row in result['cases']:
            for source in (folder / row['id']).glob('*.json'):
                if source.name not in ('manifest.json',) and source.read_bytes() != (comparison / row['id'] / source.name).read_bytes():
                    raise ValueError('Valid case/native changed across scope-guard refinement')
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Kondo09 — достаточность SEI</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Kondo09: частичный вклад и достаточность SEI</h1>'
        '<p>11 ноября 2026. Подготовленные входы25 → 26 из30; новый Kondo09. Остальные29 полных результатов '
        'и25 прежних native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Пять записей: we suppose механизмы, частичный вклад SEI, похожая SEI при разных реакциях, '
        'challenge1/3 после preformation1/2 с higher μ и essential-but-may-not-be-sole-factor. '
        'Необходимость подавления разложения электролита не переименована в гарантию подавления '
        'cointercalation. Not-suppressed и may not сохраняются в source records. Нулевая роль SEI не выводится.</p>'
        '<p>Свежий readonly capture до app edits воспроизводит30 прежних top5/role metadata. '
        'Полный PDF3/4 parent был вне top5. Узкая anion_sei_sufficiency роль сохраняет неизменённый '
        'объект существующего пула той же статьи, без новых lookup/scores/filters/top5 budget. '
        'Ranking-only/contract-only отказывают, вместе ready. Допуск точного sufficiency question '
        'и status exceptions ограничен распознанными non-change/non-suppression/modal clauses.</p>'
        '<p>1079 тестов,72 новых; полный mypy app222.81 historical cases/five native exact в финальной '
        'regression_v02. Четыре synthetic API200/200/502/502 и три service исхода, guard not_evaluated. '
        'Свежая actual API readonly/rollback preparation trace/native exact, registry0; реальные model/OAuth/slots0.</p><p>'
        + ' · '.join([link(pdf, 'Исходный PDF'), link(base / 'capture_v01/page3.png', 'Полный PDF3'),
            link(base / 'capture_v01/page4.png', 'Полный PDF4'),
            link(comparison / 'Kondo_09/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Пять записей с raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr><th>ID</th>'
        '<th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Initial focused71passed. Constructed subsection probe до conclusion допускался; исходный '
        'module/probe сохранены, добавлен single-subsection guard с учётом whitespace/PDF reading order '
        'и72-й контроль. Comparison_v01/v02 сохранены, все30 valid cases/26native точны к финальномуv03; '
        'старые manifests не переписывались, source snapshots hash-mapped. Final affected1079passed.</p>'
        '<p>Ограничения: конечная source grammar на открытых development источниках, не общий semantic/causal '
        'validator. Source supplementary pointers S23/S24 сохранены, сами SI заново не проверялись. '
        'Полные Poppler PDF3/4 визуально просмотрены; новые статьи/реальные F-ID ответы/независимая scientific '
        'accuracy/browser/full repository suite/wheel/deployment не проверены. Вопросы/prompt/thresholds/UI/'
        'DB/PDF/index/resources/config прежние; ranking изменён узкой ролью. Четыре отказа остаются: '
        '3объяснение/1ограничения. Live scopes закрыты, план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 25, 'after_ready': 26, 'newly_ready': ['Kondo_09'], 'other_results_exact': 29,
        'old_ready_native_exact': 25, 'facts': 5, 'raw_anchor_observations': anchors, 'fresh_full_PDF_pages_reviewed': 2,
        'tests_passed': 1079, 'new_tests': 72, 'historical_service_cases_exact': 81, 'historical_native_exact': 5,
        'fresh_API': prepared, 'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh / 'manifest.json', base / 'affected_v01.xml', pdf, base / 'capture_v01/manifest.json']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
