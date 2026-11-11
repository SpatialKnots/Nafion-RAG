"""Independently inspect ionic roles, modal chain, glyph positions and bounded regressions."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import nambu_conductivity_explanation_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation import conductivity_explanation as conditions
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression = base / 'comparison_v02', base / 'regression_v02'
    fresh = base / 'fresh_api_v01/Nambu_07'
    folders = [comparison, regression, fresh, base / 'pdf_probe_v01', base / 'catalogue_audit_v01']
    for folder in folders:
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    f.verify_manifest(base / 'typing_equivalence_v01')
    f.verify(run.read(base / 'typing_equivalence_v01/bindings.json'))
    if run.read(base / 'typing_equivalence_v01/result.json')['native_exact'] != 29:
        raise ValueError('Typing-only replay proof differs')
    f.verify_manifest(base / 'test_expectation_v01')
    result = run.read(comparison / 'result.json')
    history, prepared = run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (28, 29, ['Nambu_07']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Nambu_07'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v02.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 1240
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    parent = Evidence(**run.read(comparison / 'Nambu_07/after.json')['trace']['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    payload = json.loads(parent.text)
    raw, facts, anchors = payload['raw_source'], record['facts'], 0
    if (len(facts) != 4 or record['arithmetic'] is not None
            or facts[0]['value']['text'] != 'EFEE > FETFEE > ETFEE'
            or facts[0]['conditions']['concentration']['text'] != '1'
            or facts[0]['conditions']['concentration_unit']['text'] != 'mol dm−3'
            or facts[1]['value']['text'] != 'can increase the ability of the solvent molecules to form hydrogen bonds'
            or not facts[2]['value']['text'].startswith('may result in the increased solvation of PF6−')
            or facts[2]['sample']['text'] != 'PF6' or facts[2]['conditions']['ion_charge']['text'] != '−'
            or facts[3]['value']['text'] != 'may serve as an anion-attracting group'
            or facts[3]['conditions']['formula']['text'] != 'CH2F-'):
        raise ValueError('Order, electrolyte units, anion role, modal chain or fluoromethyl group differs')
    for fact in facts:
        if fact['scientific_ownership_verified']:
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
    if (len(operations) != 3 or entry['raw_sha256'] != f.sha(raw.encode())
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
    synthetic = run.read(comparison / 'Nambu_07/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'сольватацию анионов PF6−' not in render({
                'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
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
    with fitz.open(pdf) as document:
        page = document[1].get_text()
        if (page != (base / 'pdf_probe_v01/page2.txt').read_text(encoding='utf-8') or page.strip() not in raw
                or any(f['support']['text'] not in page for f in facts)):
            raise ValueError('Fresh full PDF2 or source support differs')
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Nambu07 — проводимость</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Nambu07: проводимость и возможная сольватация аниона</h1>'
        '<p>11 ноября2026. Подготовленные входы28 → 29 из30, только Nambu07. Остальные29 полных результатов '
        'и28 прежних native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Четыре записи: source conductivity order с concentration/reference-temperature; partial fluorination '
        'can increase hydrogen-bond ability и electron-pair acceptability; increased PF6− solvation may lead '
        'to greater ionic dissociation; CH2F- may serve as anion-attracting group. Анион не подменён катионом '
        'лития; can/may не превращены в измеренное или доказанное единственное объяснение. '
        'Численная степень диссоциации, абсолютная проводимость и transport numbers не рассчитываются.</p>'
        '<p>Три reviewed glyph operations одного полного PDF2/3 raw SHA/article/chunk/page/type: U+00B9→minus '
        'в двух mol dm−3 и одном PF6−. PDF offsets/font/bbox/font-program SHA перепроверены. Полный свежий '
        'Poppler PDF2 визуально просмотрен. Это интерпретация агента, не автоматическая семантика шрифта '
        'или независимая экспертная приёмка. Семь старых каталогов/raw/PDF прежние; package-data одна новая строка.</p>'
        '<p>Финальные1240тестов/55новых; mypy app225; Ruff7.81 historical service cases/five native exact. '
        'Четыре synthetic API исхода200/200/502/502 и три synthetic service исхода; guard not_evaluated. '
        'Свежая actual API readonly/rollback trace/native exact/registry0, реальные model/OAuth/newslots0.</p>'
        '<p>Сохранены initial53pass/1fail: ошибочное ожидание отказа для другого валидного порядка, '
        'сохраняющего запрошенную пару. Тест исправлен, добавлен positive control; код приложения прежний. '
        'Initial mypy1arg-type diagnostic также сохранён: SourceView inference vs ReviewedGlyphView. '
        'Финальная typing-only поправка и повтор проверок не меняют научную логику; comparison v01/v02 '
        'полные case JSON/native побайтно равны.</p><p>' + ' · '.join([
            link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page2.png', 'Полный PDF2'),
            link(conditions.GLYPHS[0], 'Glyph catalogue'), link(comparison / 'Nambu_07/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v02.xml', 'Тесты')]) + '</p>'
        '<h2>Четыре записи с raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr>'
        '<th>ID</th><th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Ограничения: finite grammar на открытом development источнике; не общий causal/chemical '
        'validator и не независимое доказательство механизма. Новые статьи/реальные F-ID ответы/accuracy/'
        'browser/full repository suite/wheel/deployment не проверены. Retrieval/ranking/вопросы/prompt/'
        'thresholds/DB/PDF/index/UI/API schema прежние. Остался Nambu08 explanation refusal. '
        'Live scopes закрыты; независимая оценка открыта, план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 28, 'after_ready': 29, 'newly_ready': ['Nambu_07'], 'other_results_exact': 29,
        'old_ready_native_exact': 28, 'facts': 4, 'raw_anchor_observations': anchors, 'glyph_operations_checked': 3,
        'fresh_full_PDF_pages_visually_reviewed': 1, 'tests_passed': 1240, 'new_tests': 55,
        'historical_service_cases_exact': 81, 'historical_native_exact': 5, 'fresh_API': prepared,
        'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), *(p / 'manifest.json' for p in folders),
        base / 'affected_v02.xml', pdf, conditions.GLYPHS[0]]))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
