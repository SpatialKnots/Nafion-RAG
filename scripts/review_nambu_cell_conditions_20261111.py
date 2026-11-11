"""Independently inspect literal conditions, glyph positions and bounded regressions."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import nambu_cell_conditions_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation import cell_solution_conditions as conditions
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression = base / 'comparison_v01', base / 'regression_v01'
    fresh = base / 'fresh_api_v01/Nambu_09'
    folders = [comparison, regression, fresh, base / 'pdf_probe_v01', base / 'catalogue_audit_v01']
    for folder in folders:
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result = run.read(comparison / 'result.json')
    history, prepared = run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (20, 21, ['Nambu_09']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Nambu_09'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 743
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    parent = Evidence(**run.read(comparison / 'Nambu_09/after.json')['trace']['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    payload = json.loads(parent.text)
    raw, facts, anchors = payload['raw_source'], record['facts'], 0
    if (len(facts) != 5 or record['arithmetic'] is not None
            or [(fact['sample']['text'], fact['value']['text']) for fact in facts[:4]] != [
                ('EC–FETFEE', '1'), ('EC–EFEE', '1'), ('EC–DEE', '1'), ('EC–ETFEE', '0.5')]
            or facts[-1]['conditions']['minC']['text'] != '−5'
            or facts[-1]['conditions']['maxC']['text'] != '60'):
        raise ValueError('Mixture concentrations or separate conductivity conditions differ')
    for fact in facts:
        if fact['scientific_ownership_verified'] or fact['epistemic_status'] != 'source_reported_conditions':
            raise ValueError('Scientific acceptance asserted')
        values = (fact['sample'], fact['value'], fact['unit'], fact['method'], *fact['conditions'].values())
        for anchor in [fact['support'], *[v['source'] for v in values if v]]:
            if (raw[anchor['start']:anchor['end']] != anchor['text']
                    or anchor['raw_chunk_sha256'] != f.sha(raw.encode())):
                raise ValueError('Raw condition/field anchor drift')
            anchors += 1
    catalogue = run.read(conditions.GLYPHS[0])
    if f.sha(conditions.GLYPHS[0].read_bytes()) != conditions.GLYPHS[1] or len(catalogue['entries']) != 1:
        raise ValueError('Glyph catalogue differs')
    entry = catalogue['entries'][0]
    operations = entry['operations']
    if (len(operations) != 6 or entry['raw_sha256'] != f.sha(raw.encode())
            or any(entry[k] != getattr(parent, k) for k in ('article_id', 'chunk_id', 'page_start', 'page_end'))
            or entry['source_type'] != payload['raw_source_type']):
        raise ValueError('Glyph source identity differs')
    pdf = f.ROOT / 'data/pdf/5cafe6e931ef4dc7_Nambu_2016.pdf'
    if f.sha(pdf.read_bytes()) != catalogue['pdf_sha256']:
        raise ValueError('Original PDF changed')
    with fitz.open(pdf) as document:
        for op in operations:
            page = document[op['pdf_page'] - 1]
            text = page.get_text()
            if (text.strip() not in raw or text[op['pdf_text_offset']] != op['raw_character']
                    or raw[op['raw_start']:op['raw_end']] != op['raw_character']
                    or raw.index(text.strip()) + op['pdf_text_offset'] - (len(text) - len(text.lstrip())) != op['raw_start']
                    or f.sha(document.extract_font(op['font_xref'])[3]) != op['font_program_sha256']):
                raise ValueError('PDF glyph offset/font program or raw address differs')
            chars = [(span['font'], char) for block in page.get_text('rawdict')['blocks']
                     for line in block.get('lines', []) for span in line['spans'] for char in span['chars']]
            if len([char for font, char in chars if font == op['font'] and char['c'] == op['raw_character']
                    and list(char['bbox']) == op['bbox']]) != 1:
                raise ValueError('Positioned glyph bbox is missing or ambiguous')
    synthetic = run.read(comparison / 'Nambu_09/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'EC–ETFEE — 0.5' not in render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
        raise ValueError('Conditions lost by UI adapters')
    out = base / 'review_v01'
    out.mkdir(exist_ok=False)

    def link(path, label):
        if not path.is_file():
            raise FileNotFoundError(path)
        return '<a href="' + html.escape(os.path.relpath(path, out).replace('\\', '/'), quote=True) + '">' + label + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
                   str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td></tr>' for r in result['cases'])
    details = ''.join('<details><summary>' + html.escape(fact['property'] + ': ' + fact['sample']['text']) +
                      '</summary><pre>' + html.escape(json.dumps(fact, ensure_ascii=False, indent=2)) +
                      '</pre></details>' for fact in facts)
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Nambu09 — условия растворов</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Nambu09: условия двух экспериментов</h1>'
        '<p>11 ноября 2026. Подготовленные входы20 → 21 из30, только Nambu09. Остальные29 полных результатов '
        'и20 прежних native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Четыре смеси связаны со своими концентрациями и температурой cycling; отдельная запись '
        'проводимости сохраняет концентрацию при25°C и диапазон измерения. Мольная эквимолярность '
        'не превращается в объёмную. K/°C не пересчитываются. Методологическая оговорка ограничена '
        'различием условий; отдельный причинный эффект концентрации не утверждается.</p>'
        '<p>Шесть glyph operations привязаны к одному полному raw SHA/типу/article/chunk/page и '
        'PDF offset/font/bbox/font-program SHA: пять знаков минуса и один разделитель ячейки. '
        'Значение glyph установлено агентом по полным Poppler PDF2/3; имя шрифта не задаёт семантику. '
        'Подпись читается после библиографии в PDF text order; допускается лишь полная (a)/(b) '
        'caption grammar с локальной проверкой статуса и согласованным body.</p>'
        '<p>743 теста,41 новый; полный mypy app217.81 historical service case/пять native exact. '
        'Четыре synthetic API исхода200/200/502/502; три synthetic service исхода. Guard not_evaluated. '
        'Свежая actual API preparation read-only/rollback, trace/native exact, registry0, '
        '9120bytes. Реальные model/OAuth/newslots0.</p><p>' + ' · '.join([
            link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page2.png', 'Полный PDF2'),
            link(base / 'pdf_probe_v01/page3.png', 'Полный PDF3'), link(conditions.GLYPHS[0], 'Glyph catalogue'),
            link(comparison / 'Nambu_09/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Пять записей с точными raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr>'
        '<th>ID</th><th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Initial focused41passed. Comparison preflight дважды остановился на pyproject hash: '
        'добавление resource и нормализация смешанных переводов строк. Исходный hash восстановлен точно, '
        'оригинальные окончания строк сохранены, добавлена только одна package-data строка. '
        'Старые manifests не переписывались; диагностика сохранена.</p>'
        '<p>Ограничения: конечная grammar по открытым development источникам; glyph interpretations агента, '
        'не независимая научная экспертиза. Новые статьи, реальные model F-ID ответы, browser layout, '
        'полный repository suite, wheel/deployment не проверены. Retrieval/вопросы/prompt/thresholds/DB/'
        'PDF/index/UI не менялись. Девять отказов остаются:2контекст/5объяснение/2ограничения. '
        'Все live scopes закрыты; независимая оценка открыта, план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 20, 'after_ready': 21, 'newly_ready': ['Nambu_09'], 'other_results_exact': 29,
        'old_ready_native_exact': 20, 'facts': 5, 'raw_anchor_observations': anchors, 'glyph_operations_checked': 6,
        'fresh_full_PDF_pages_visually_reviewed': 2, 'tests_passed': 743, 'new_tests': 41,
        'historical_service_cases_exact': 81, 'historical_native_exact': 5, 'fresh_API': prepared,
        'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), *(p / 'manifest.json' for p in folders),
        base / 'affected_v01.xml', pdf, conditions.GLYPHS[0]]))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
