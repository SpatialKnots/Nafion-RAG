"""Independently recheck glyph addresses and publish the exposed-case comparison."""

from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import peng_glyph_binding_20261111 as run
from scripts.peng_glyph_probe_20261111 import PDF


def main():
    from app.generation import answer_facts, reviewed_glyphs
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    comparison, regression = run.BASE / 'comparison_v02', run.BASE / 'regression_v02'
    for folder in (comparison, regression, run.BASE / 'pdf_probe_v01', run.BASE / 'catalogue_audit_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    data = run.read(comparison / 'result.json')
    old = run.read(regression / 'summary.json')
    fresh = run.read(run.BASE / 'fresh_api_v02/batch.json')
    if ((data['before_ready'], data['after_ready'], data['newly_ready']) != (12, 14, ['Peng_05', 'Peng_08'])
            or old['actual_service_executions'] != 81 or old['old_cases'] != 76):
        raise ValueError('Unexpected comparison counts')
    if not all(r['full_service_identical'] and r['native_identical'] for r in old['current_comparisons']):
        raise ValueError('Prior current cases changed')
    for row in fresh:
        directory = run.BASE / 'fresh_api_v02' / row['id']
        f.verify_manifest(directory)
        f.verify(run.read(directory / 'bindings.json'))
        if (not row['trace_exact'] or not row['native_exact'] or row['registry_diagnostics']
                or row['network_denials'] or row['model_calls'] or row['oauth_calls']):
            raise ValueError('Fresh source/native verification failed')
    if {r['id'] for r in fresh} != {'Peng_05', 'Peng_08'}:
        raise ValueError('Two fresh preparations required')
    suites = ET.parse(f.ROOT / 'output/peng_glyph_tests_v03_20261111.xml').getroot().iter('testsuite')
    tests = list(suites)
    if sum(int(s.get('tests', '0')) for s in tests) != 444 or any(
            int(s.get(k, '0')) for s in tests for k in ('failures', 'errors')):
        raise ValueError('Final tests not all successful')
    catalogue = run.read(reviewed_glyphs.CATALOGUE)
    if f.sha(PDF.read_bytes()) != catalogue['pdf_sha256']:
        raise ValueError('PDF identity changed')
    chunks = run.read(run.old_run.CAPTURE / 'chunks.json')
    observations = run.read(run.BASE / 'pdf_probe_v01/observations.json')
    operations = 0
    with fitz.open(PDF) as document:
        for entry in catalogue['entries']:
            raw = chunks[entry['chunk_id']]
            if f.sha(raw['text'].encode()) != entry['raw_sha256']:
                raise ValueError('Catalogue chunk hash mismatch')
            for operation in entry['operations']:
                if raw['text'][operation['raw_start']:operation['raw_end']] != operation['raw_character']:
                    raise ValueError('Catalogue raw address mismatch')
                page = document[operation['pdf_page'] - 1]
                if page.get_text()[operation['pdf_text_offset']] != operation['raw_character']:
                    raise ValueError('Original-page glyph address mismatch')
                if f.sha(document.extract_font(operation['font_xref'])[3]) != operation['font_program_sha256']:
                    raise ValueError('Embedded font changed')
                matching = [o for o in observations if all(o[k] == operation[k] for k in
                    ('font', 'font_xref', 'bbox', 'raw_character', 'font_program_sha256')) and o['page'] == operation['pdf_page']]
                if len(matching) != 1:
                    raise ValueError('Nonunique positioned glyph witness')
                operations += 1
    folder = run.BASE / 'review_v01'
    folder.mkdir(exist_ok=False)
    links, rows, details, anchors = [], [], [], 0

    def link(path, label, fragment=''):
        if not path.exists():
            raise FileNotFoundError(path)
        links.append({'path': str(path), 'fragment': fragment})
        url = Path(os.path.relpath(path, folder)).as_posix() + fragment
        return '<a href="' + html.escape(url, quote=True) + '">' + html.escape(label) + '</a>'

    for row in data['cases']:
        cid, directory = row['id'], comparison / row['id']
        f.verify_manifest(directory)
        if row['before_ready'] and not (row['native_unchanged'] and row['full_result_unchanged']):
            raise ValueError('Prior ready case changed')
        rows.append('<tr>' + ''.join('<td>' + text + '</td>' for text in (
            html.escape(cid), html.escape(row['question']), 'Готов' if row['before_ready'] else 'Отказ',
            'Готов, не отправлен' if row['after_ready'] else 'Отказ', link(directory / 'result.json', 'Результат'))) + '</tr>')
        if not row['newly_ready']:
            continue
        current = run.read(directory / 'after.json')
        parent = Evidence(**current['trace']['evidence'][0])
        record = answer_facts.selection_records([parent])['F1']
        payload = json.loads(parent.text)
        for fact in record['facts']:
            for anchor in [fact['support'], *[v['source'] for v in
                (fact['sample'], fact['value'], fact['unit'], *fact['conditions'].values()) if v]]:
                if (payload['raw_source'][anchor['start']:anchor['end']] != anchor['text']
                        or f.sha(payload['raw_source'].encode()) != anchor['raw_chunk_sha256']):
                    raise ValueError('Field raw anchor changed')
                anchors += 1
        summary = _prepared_statement_text(parent.text, parent.source_type)
        synthetic = run.read(directory / 'synthetic_selection.json')
        ui = render({'answer': synthetic['selected'], 'delivery_status': 'not_evaluated', 'review': None})
        if ('исходной кодировкой' not in summary or 'исходной кодировкой' not in ui
                or record['allowed_claim'] not in summary or html.escape(record['allowed_claim']) not in ui):
            raise ValueError('Both UI adapters must show decoding and server text')
        f.save(folder / (cid + '_UI_fragment.html'), ui.encode())
        pno = next(o['pdf_page'] for o in record['source_grammar']['glyph_decoding']['operations']
                   if any(fact['support']['start'] <= o['raw_start'] < fact['support']['end'] for fact in record['facts']))
        details.append('<h2>' + html.escape(cid) + '</h2><p>SYNTHETIC выбор F1, не ответ реальной модели.</p>' + ui
            + '<p>' + link(PDF, 'Оригинальный PDF', f'#page={pno}') + ' · '
            + link(run.BASE / f'pdf_probe_v01/page{pno}.png', 'Свежая полная страница') + ' · '
            + link(directory / 'request_unsent.json', 'Подготовленный запрос, не отправлен') + '</p>'
            + '<details><summary>Поля, raw адреса и расшифровка (управляющие символы в JSON escape)</summary><pre>'
            + html.escape(json.dumps(record, ensure_ascii=False, indent=2)) + '</pre></details>')
    report = {'comparison': data, 'historical': old, 'fresh': fresh, 'tests_passed': 444, 'new_tests': 33,
        'reviewed_PDF_pages': [4, 5], 'PDF_sha256': catalogue['pdf_sha256'], 'catalogue_entries': len(catalogue['entries']),
        'catalogue_operations_verified': operations, 'positioned_glyph_observations': len(observations),
        'raw_field_anchor_observations': anchors, 'UI_adapters': 2, 'new_case_UI_fragments': len(details), 'links': links,
        'scope': 'two_exact_reviewed_raw_chunks_not_general_glyph_normalization', 'model_calls': 0, 'oauth_calls': 0,
        'accuracy': None, 'browser_layout': 'not_verified', 'full_test_suite': 'not_run'}
    document = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — Peng: кодировка знаков</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#17202a}table{border-collapse:collapse;width:100%}'
        'th,td{border:1px solid #aaa;padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;'
        'overflow-wrap:anywhere;background:#f2f4f6;padding:16px}</style><h1>Расшифровка символов Peng05/08 · 11 ноября 2026</h1>'
        '<p>Готовность12→14/30, ещё два количественных отказа сняты. Осталось16 отказов, из них три количественных: '
        'Nambu06 (порядок и единица концентрации), Peng06 (таблица и единицы), Peng07 (контекст и сравнение CE).</p>'
        '<p>Это исправление данных двух точных исходных фрагментов: исходный текст, PDF и индекс не изменены. '
        'Расшифровка подтверждена полными страницами PDF и привязана к хешам и адресам; неизвестные случаи остаются отказом. '
        '444 теста,81 прежний результат и пять native inputs сохранены;12 прежних ready inputs точны. '
        'Две свежие API подготовки read-only/rollback точны. Реальные модель/OAuth/слоты0. '
        'Вопросы открыты для разработки; научная точность и переносимость на новые документы не измерены.</p>'
        '<table><thead><tr><th>ID</th><th>Вопрос</th><th>До</th><th>После</th><th>Данные</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table>' + ''.join(details) + '</html>')
    f.save(folder / 'review.html', document.encode())
    f.write(folder / 'report.json', report)
    f.write(folder / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        reviewed_glyphs.CATALOGUE, PDF, run.BASE / 'fresh_api_v02/batch.json',
        f.ROOT / 'output/peng_glyph_tests_v03_20261111.xml']))
    f.manifest(folder)
    print(json.dumps({k: report[k] for k in ('tests_passed', 'catalogue_operations_verified',
                                            'raw_field_anchor_observations', 'new_case_UI_fragments', 'model_calls')}))


if __name__ == '__main__':
    main()
