"""Verify and publish a local development comparison; no inference or dispatch."""

from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import gigachat_answer_smoke as f
from scripts import quantitative_binding_20261111 as run

PDFS = {
    'Kondo': ('615828f87ad5a0d9_Kond_2025.pdf', '615828f87ad5a0d95872524c2bf3e96e5fed696f18b31a9f6903a128728950f3'),
    'Nambu': ('5cafe6e931ef4dc7_Nambu_2016.pdf', '5cafe6e931ef4dc7922f7625027f4ed4cec510da87259f7d1e0e6483b05d0147'),
    'Peng': ('6ab4542d9156e377_Peng_2021.pdf', '6ab4542d9156e3777972b59f12f16dbb32770d00b8e258d1b1bb3390b55a4a88'),
}
REASONS = {
    'complete_source_bound_quantitative_bundle': 'Готов: полный набор полей привязан к исходному фрагменту',
    'concentration_unit_and_order_binding_not_supported': 'Нужна проверка единицы концентрации и привязка порядка проводимости',
    'table_column_condition_and_explicit_unit_binding_not_supported':
        'Нужна привязка столбцов, условий и явно подтверждённой единицы сопротивления',
    'best_electrolyte_ranking_and_context_binding_not_supported': 'Нужны контекст полуячейки и проверка сравнительного максимума CE',
    'raw_quantity_unit_or_approximation_encoding_unresolved':
        'В исходном тексте повреждены единица или знак приближения; автоматического исправления нет',
}


def main():
    from app.generation import answer_facts
    from app.generation.providers import Evidence
    from app.ui import _prepared_statement_text

    comparison, regression = run.BASE / 'comparison_v05', run.BASE / 'regression_v03'
    for folder in (comparison, regression):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result = run.read(comparison / 'result.json')
    history = run.read(regression / 'summary.json')
    fresh = run.read(run.BASE / 'fresh_api_v02/batch.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (9, 12, ['Kondo_05', 'Kondo_06', 'Kondo_08']):
        raise ValueError('Unexpected comparison')
    if history['actual_service_executions'] != 81 or history['old_cases'] != 76:
        raise ValueError('Incomplete historical regression')
    if not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons']):
        raise ValueError('Current five historical cases differ')
    if len(fresh) != 3 or {r['id'] for r in fresh} != set(result['newly_ready']):
        raise ValueError('Missing fresh preparations')
    for row in fresh:
        folder = run.BASE / 'fresh_api_v02' / row['id']
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
        if (not row['native_exact'] or not row['trace_exact'] or row['registry_diagnostics']
                or row['network_denials'] or row['model_calls'] or row['oauth_calls']):
            raise ValueError('Fresh binding failed')
    tests = ET.parse(f.ROOT / 'output/quantitative_tests_v06_20261111.xml').getroot()
    suites = list(tests.iter('testsuite'))
    if sum(int(s.get('tests', '0')) for s in suites) != 411 or any(
            int(s.get(k, '0')) for s in suites for k in ('errors', 'failures')):
        raise ValueError('Tests not all successful')
    pdfs = []
    for name, (filename, digest) in PDFS.items():
        path = f.ROOT / 'data/pdf' / filename
        if f.sha(path.read_bytes()) != digest:
            raise ValueError('Original PDF changed')
        pdfs.append({'name': name, 'path': str(path), 'sha256': digest})
    folder = run.BASE / 'review_v01'
    folder.mkdir(exist_ok=False)
    links, rows, sections, anchors, ui_records = [], [], [], 0, 0

    def link(path, label, fragment=''):
        href = Path(os.path.relpath(path, folder)).as_posix() + fragment
        if not path.exists():
            raise FileNotFoundError(path)
        links.append({'path': str(path), 'fragment': fragment})
        return f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'

    for row in result['cases']:
        cid, quantitative = row['id'], row['quantitative']
        out = comparison / cid
        f.verify_manifest(out)
        if row['before_ready'] and not (row['native_unchanged'] and row['full_result_unchanged']):
            raise ValueError('Prior ready result drift')
        reason = REASONS.get(quantitative['reason'], quantitative['reason']) if quantitative else 'Прежний путь подготовки'
        rows.append('<tr>' + ''.join('<td>' + text + '</td>' for text in (
            html.escape(cid), html.escape(row['question']), 'Готов' if row['before_ready'] else 'Отказ',
            'Готов, не отправлен' if row['after_ready'] else 'Отказ', html.escape(reason),
            link(out / 'result.json', 'Диагностика'))) + '</tr>')
        if not quantitative:
            continue
        body = '<h2>' + html.escape(cid) + '</h2><p>' + html.escape(row['question']) + '</p><p>' + html.escape(reason) + '</p>'
        if row['newly_ready']:
            trace = run.read(out / 'after.json')['trace']
            evidence = [Evidence(**e) for e in trace['evidence']]
            records = answer_facts.selection_records(evidence)
            payload = json.loads(evidence[0].text)
            raw = run.read(run.CAPTURE / 'chunks.json')[evidence[0].chunk_id]
            answer_facts.verify_raw_binding(evidence[0].text, raw['text'], article_id=evidence[0].article_id,
                chunk_id=evidence[0].chunk_id, citation_id=evidence[0].citation_id, page_start=evidence[0].page_start,
                page_end=evidence[0].page_end, source_type=raw['source_type'])
            rendered = _prepared_statement_text(evidence[0].text, evidence[0].source_type)
            for record in records.values():
                if record['allowed_claim'] not in rendered:
                    raise ValueError('UI summary omitted server statement')
                for fact in record['facts']:
                    addresses = [fact['support'], *[v['source'] for v in
                        (fact['value'], fact['unit'], fact['sample'], *fact['conditions'].values()) if v]]
                    for a in addresses:
                        if raw['text'][a['start']:a['end']] != a['text'] or f.sha(raw['text'].encode()) != a['raw_chunk_sha256']:
                            raise ValueError('Raw field anchor changed')
                        anchors += 1
                    if fact['support']['text'] not in rendered:
                        raise ValueError('UI omitted exact supporting quotation')
                ui_records += 1
            pdf = f.ROOT / 'data/pdf' / PDFS[cid.split('_')[0]][0]
            body += ('<p>Серверный текст после SYNTHETIC выбора F1; это не ответ реальной модели.</p><pre>'
                     + html.escape(rendered) + '</pre>' + link(pdf, f'PDF: диапазон chunk {raw["page_start"]}–{raw["page_end"]}',
                                                               f'#page={raw["page_start"]}')
                     + ' · ' + link(out / 'request_unsent.json', 'Подготовленный запрос, не отправлен')
                     + '<details><summary>Поля и точные адреса источника</summary><pre>'
                     + html.escape(json.dumps(records, ensure_ascii=False, indent=2)) + '</pre></details>')
            if payload['raw_source'] != raw['text']:
                raise ValueError('Displayed raw source mismatch')
        else:
            body += '<pre>' + html.escape(json.dumps(quantitative['diagnostics'], ensure_ascii=False, indent=2)) + '</pre>'
        sections.append(body)
    report = {'comparison': result, 'historical': history, 'fresh': fresh, 'PDF_hashes': pdfs,
        'verified_raw_anchor_observations': anchors, 'UI_summary_records': ui_records,
        'tests_passed': 411, 'new_tests': 70, 'all_cases': len(rows), 'quantitative_cases': len(sections),
        'links': links, 'model_calls': 0, 'oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None,
        'browser_layout': 'not_verified', 'full_test_suite': 'not_run'}
    document = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — количественные отказы</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#17202a}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #bbb;padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;'
        'overflow-wrap:anywhere;background:#f2f4f6;padding:16px}h2{margin-top:36px}</style>'
        '<h1>Начало исправления количественных отказов · 11 ноября 2026</h1>'
        '<p>Готовность 9→12/30. Сняты три из восьми количественных отказов. Осталось 18 отказов, из них пять количественных.</p>'
        '<p>411 тестов; 81 прежний результат и пять native inputs сохранены. Три свежие API подготовки: read-only/rollback, '
        'источники и native inputs точны. Модель/OAuth/новые слоты: 0. Все вопросы уже открыты для разработки; '
        'готовность не измеряет научную точность. Расширение конечное, самостоятельной оценки нет.</p>'
        '<table><thead><tr><th>ID</th><th>Вопрос</th><th>До</th><th>После</th><th>Причина</th><th>Данные</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table>' + ''.join(sections) + '</html>')
    f.save(folder / 'review.html', document.encode())
    f.write(folder / 'report.json', report)
    f.write(folder / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        f.ROOT / 'output/quantitative_tests_v06_20261111.xml', run.BASE / 'fresh_api_v02/batch.json',
        *[Path(p['path']) for p in pdfs]]))
    f.manifest(folder)
    print(json.dumps({k: report[k] for k in ('all_cases', 'quantitative_cases', 'verified_raw_anchor_observations',
                                           'UI_summary_records', 'tests_passed', 'model_calls')}))


if __name__ == '__main__':
    main()
