"""Independently inspect literal conditions, glyph positions and bounded regressions."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import peng_oxidation_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation import oxidation_comparison as conditions
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression = base / 'comparison_v01', base / 'regression_v01'
    fresh = base / 'fresh_api_v01/Peng_02'
    folders = [comparison, regression, fresh, base / 'pdf_probe_v01', base / 'catalogue_audit_v01']
    for folder in folders:
        f.verify_manifest(folder)
        bound = run.read(folder / 'bindings.json')
        if folder.name == 'catalogue_audit_v01':
            mapping_folder = base / 'generator_docstring_v02'
            f.verify_manifest(mapping_folder)
            mapping = run.read(mapping_folder / 'mapping.json')
            if (bound[mapping['original_path']] != f.sha(Path(mapping['original_snapshot']).read_bytes())
                    or mapping['current_sha256'] != f.sha(Path(mapping['original_path']).read_bytes())):
                raise ValueError('Generator docstring-only mapping differs')
            bound = {p: h for p, h in bound.items() if p != mapping['original_path']}
        f.verify(bound)
    result = run.read(comparison / 'result.json')
    history, prepared = run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (21, 22, ['Peng_02']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Peng_02'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 822
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    parent = Evidence(**run.read(comparison / 'Peng_02/after.json')['trace']['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    payload = json.loads(parent.text)
    raw, facts, anchors = payload['raw_source'], record['facts'], 0
    if (len(facts) != 7 or record['arithmetic'] is not None
            or [(fact['sample']['text'], fact['value']['text']) for fact in facts[:2]] != [
                ('EE', 'EC/EMC'), ('FFT', 'FEC/FEMC/TFEE')]
            or facts[2]['value']['text'] != '4.6' or facts[2]['conditions']['time']['text'] != '20'
            or facts[3]['unit']['text'] != 'mV s−1' or facts[3]['value']['text'] != '5'
            or facts[-2]['value']['text'] != '5.5' or facts[-1]['value']['text'] != '6.4'
            or facts[-2]['conditions']['base_approx']['text'] != '~' or facts[-1]['conditions']['approx']['text'] != '~'
            or 'suggesting' not in facts[4]['conditions']['interpretation']['text']):
        raise ValueError('Methods, approximation, reported status or comparison differs')
    for fact in facts:
        if fact['scientific_ownership_verified'] or fact['epistemic_status'] != 'source_reported_conditions_or_observation':
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
    if (len(operations) != 10 or entry['raw_sha256'] != f.sha(raw.encode())
            or any(entry[k] != getattr(parent, k) for k in ('article_id', 'chunk_id', 'page_start', 'page_end'))
            or entry['source_type'] != payload['raw_source_type']):
        raise ValueError('Glyph source identity differs')
    pdf = f.ROOT / 'data/pdf/6ab4542d9156e377_Peng_2021.pdf'
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
    synthetic = run.read(comparison / 'Peng_02/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'примерно до 6.4 V' not in render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
        raise ValueError('Conditions lost by UI adapters')
    out = base / 'review_v02'
    out.mkdir(exist_ok=False)

    def link(path, label):
        if not path.is_file():
            raise FileNotFoundError(path)
        return '<a href="' + html.escape(os.path.relpath(path, out).replace('\\', '/'), quote=True) + '">' + label + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
                   str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td></tr>' for r in result['cases'])
    details = ''.join('<details><summary>' + html.escape(fact['property'] + ': ' + (fact['sample']['text'] if fact['sample'] else 'LSV')) +
                      '</summary><pre>' + html.escape(json.dumps(fact, ensure_ascii=False, indent=2)) +
                      '</pre></details>' for fact in facts)
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Peng02 — окислительная устойчивость</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Peng02: LSV и float-test</h1>'
        '<p>11 ноября 2026. Подготовленные входы21 → 22 из30, только Peng02. Остальные29 полных результатов '
        'и21 прежний native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Два состава, float-режим, LSV-метод, сравнение токов утечки и два приблизительных LSV '
        'наблюдения представлены семью записями. Трактовка decomposition сохраняет suggesting; '
        'численные токи утечки и разность порогов не вычисляются. LSV-предел не переносится на рабочее '
        'напряжение полной ячейки. Отдельные причинные вклады компонентов не устанавливаются.</p>'
        '<p>Десять glyph operations одного raw SHA/article/chunk/page/type: один минус в scan unit, '
        'два знака приближения и семь ligatures fl/fi. Все PDF offsets/font/bbox/font-program SHA '
        'перепроверены; значение установлено агентом по полным Poppler PDF2/3, не по имени шрифта. '
        'Старые catalogues/raw/PDF не изменены. Новый resource добавлен одной package-data строкой.</p>'
        '<p>822 теста,79 новых; полный mypy app218.81 historical service case/пять native exact. '
        'Четыре synthetic API исхода200/200/502/502; три synthetic service исхода. Guard not_evaluated. '
        'Свежая actual API preparation read-only/rollback, trace/native exact, registry0,11863bytes. '
        'Реальные model/OAuth/newslots0.</p><p>' + ' · '.join([
            link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page2.png', 'Полный PDF2'),
            link(base / 'pdf_probe_v01/page3.png', 'Полный PDF3'), link(conditions.GLYPHS[0], 'Glyph catalogue'),
            link(comparison / 'Peng_02/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Семь записей с точными raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr>'
        '<th>ID</th><th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Focused79passed с первой попытки. Начальная разведка ошиблась в Unicode code point '
        'лигатуры, locator остановился до извлечения/изменений; исправлено на фактический U+E104. '
        'Генератор унаследовал неточный module docstring от предыдущего инструмента: исправлена '
        'только строка документации, non-docstring AST точен; исходный script snapshot/hash и '
        'mapping сохранены. Дополнительные пустые строки от text write дали Ruff I001; восстановлены исходные CRLF. '
        'Intermediate script/старый review script/review_v01 сохранены; финальный review_v02. '
        'Catalogue не регенерирован, старые manifests не переписаны.</p>'
        '<p>Ограничения: конечная grammar по открытым development источникам; glyph interpretations агента, '
        'не независимая научная экспертиза. Не общий causal validator. Новые статьи, реальные model F-ID '
        'ответы, browser layout, полный repository suite, wheel/deployment не проверены. Retrieval/'
        'вопросы/prompt/thresholds/DB/PDF/index/UI не менялись. Восемь отказов остаются:1контекст '
        '(Peng10)/5объяснение/2ограничения. Все live scopes закрыты; независимая оценка открыта, план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 21, 'after_ready': 22, 'newly_ready': ['Peng_02'], 'other_results_exact': 29,
        'old_ready_native_exact': 21, 'facts': 7, 'raw_anchor_observations': anchors, 'glyph_operations_checked': 10,
        'fresh_full_PDF_pages_visually_reviewed': 2, 'tests_passed': 822, 'new_tests': 79,
        'historical_service_cases_exact': 81, 'historical_native_exact': 5, 'fresh_API': prepared,
        'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), *(p / 'manifest.json' for p in folders),
        base / 'affected_v01.xml', pdf, conditions.GLYPHS[0], base / 'generator_docstring_v02/manifest.json',
        f.ROOT / 'scripts/build_peng_oxidation_catalogue_20261111.py']))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
