"""Independently inspect literal conditions, glyph positions and bounded regressions."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import peng_surface_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation import cathode_surface as conditions
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression = base / 'comparison_v01', base / 'regression_v01'
    fresh = base / 'fresh_api_v01/Peng_10'
    folders = [comparison, regression, fresh, base / 'pdf_probe_v01', base / 'catalogue_audit_v02', base / 'capture_v01']
    for folder in folders:
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result = run.read(comparison / 'result.json')
    history, prepared = run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (22, 23, ['Peng_10']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Peng_10'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 888
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    parent = Evidence(**run.read(comparison / 'Peng_10/after.json')['trace']['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    payload = json.loads(parent.text)
    raw, facts, anchors = payload['raw_source'], record['facts'], 0
    if (len(facts) != 6 or record['arithmetic'] is not None
            or facts[1]['value']['text'] != 'almost disappears'
            or facts[2]['conditions']['carbonyl']['text'] != 'C=O'
            or facts[3]['conditions']['group']['text'] != 'two FEC-contained electrolytes'
            or {'label', 'other2', 'caption_label', 'caption_other2'} & facts[3]['conditions'].keys()
            or facts[4]['value']['text'] != 'LixPOyFz'
            or facts[-1]['conditions']['status']['text'] != 'suggest'
            or any(fact['sample']['text'] != 'LCO' for fact in facts)):
        raise ValueError('Cathode owner, grouping, trend, chemical bond or interpretation differs')
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
    if (len(operations) != 6 or entry['raw_sha256'] != f.sha(raw.encode())
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
    synthetic = run.read(comparison / 'Peng_10/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'в FFT почти исчезают' not in render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
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
    capture = run.read(base / 'capture_v01/result.json')
    if capture['fresh_pool_cases_exact'] != 30:
        raise ValueError('Complete-pool baseline differs')
    ablation = run.read(comparison / 'Peng_10/ablation.json')
    if ablation != {'ranking_only_ready': False, 'contract_only_ready': False, 'both_ready': True}:
        raise ValueError('Ablation differs')
    pool = next(r['rows'] for r in run.read(base / 'capture_v01/cases.json') if r['id'] == 'Peng_10')
    selected = run.read(comparison / 'Peng_10/after.json')['trace']['retrieval']['results']
    if len(selected) != 5 or not all(row in pool for row in selected):
        raise ValueError('Retrieval substituted or mutated a pool object')
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Peng10 — поверхность LCO</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Peng10: SEM/XPS на LCO после cycling</h1>'
        '<p>11 ноября 2026. Подготовленные входы22 → 23 из30, только Peng10. Остальные29 полных результатов '
        'и22 прежних native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>SEM наблюдение почти исчезнувших микротрещин не заменено полным отсутствием дефектов. '
        'XPS сохраняет LCO-владение/подпись Fig7, C–O/C=O назначения, O1s групповой результат для двух '
        'FEC-содержащих электролитов и F1s lower LixPOyFz у FET/FFT относительно EE. '
        'Членство FFT в O1s группе здесь не доказывается по названию/внешнему preparation chunk. '
        'Авторский suggest о CEI не становится независимым причинным доказательством. '
        'LiF/SEI/total-F из соседнего MCMB-абзаца не переносятся.100cycles/4.45V из других страниц '
        'не подставлены в отдельные SEM/XPS facts; quantitative fraction/thickness неизвестны.</p>'
        '<p>Свежий read-only capture до app edits воспроизвёл все30 прежних top5/role metadata. '
        'Нужный полный PDF6/7 raw-parent отсутствовал в старом Peng10 top5. Узкая роль '
        'cycled_cathode_surface сохраняет существующий неизменённый объект полного пула той же статьи. '
        'Top5/scores/filters/число lookup прежние. Ranking-only и contract-only отказывают; вместе ready.</p>'
        '<p>Шесть glyph operations одного raw SHA/article/chunk/page/type: ft, три fi, fl и C]O→C=O. '
        'Все PDF offsets/font/bbox/font-program SHA перепроверены. Визуально просмотрены полные '
        'Poppler PDF5/6/7, включая исходные SEM Fig6 и XPS Fig7; независимой переоценки изображений/fit нет. '
        'Старые catalogues/raw/PDF не изменены. Новый v02 resource добавлен одной package-data строкой.</p>'
        '<p>888 тестов,66 новых; полный mypy app219.81 historical service case/пять native exact. '
        'Четыре synthetic API исхода200/200/502/502; три synthetic service исхода. Guard not_evaluated. '
        'Свежая actual API preparation read-only/rollback, trace/native exact, registry0,14578bytes. '
        'Реальные model/OAuth/newslots0.</p><p>' + ' · '.join([
            link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page5.png', 'Полный PDF5 / SEM'),
            link(base / 'capture_v01/page6.png', 'Полный PDF6'), link(base / 'capture_v01/page7.png', 'Полный PDF7'),
            link(conditions.GLYPHS[0], 'Glyph catalogue'), link(comparison / 'Peng_10/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Шесть записей с точными raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr>'
        '<th>ID</th><th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>До тестов первый source probe отказал: slash/newline в extraction/insertion и literal '
        'O1s comparator without it. Source snapshots сохранены; разрешены только slash whitespace '
        'и точный уже распознанный comparator, прочие negative/status guards сохранены. '
        'Первый glyph catalogue пропустил U+E09D из-за U+E0DD typo;5ops/v01/source snapshot '
        'сохранены вне app runtime, финальный v02 содержит6ops. Focused66passed с первой попытки.</p>'
        '<p>Ограничения: конечная grammar/агентская glyph интерпретация по открытым development источникам. '
        'Не общий semantic/causal validator. Новые статьи, реальные model F-ID ответы, независимая научная '
        'accuracy, browser layout, полный repository suite, wheel/deployment не проверены. Вопросы/'
        'prompt/thresholds/DB/PDF/index/UI прежние; ranking изменён только узкой ролью. '
        'Семь отказов остаются:5объяснение/2ограничения. Все live scopes закрыты; план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 22, 'after_ready': 23, 'newly_ready': ['Peng_10'], 'other_results_exact': 29,
        'old_ready_native_exact': 22, 'facts': 6, 'raw_anchor_observations': anchors, 'glyph_operations_checked': 6,
        'fresh_full_PDF_pages_visually_reviewed': 3, 'tests_passed': 888, 'new_tests': 66,
        'historical_service_cases_exact': 81, 'historical_native_exact': 5, 'fresh_API': prepared,
        'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), *(p / 'manifest.json' for p in folders),
        base / 'affected_v01.xml', pdf, conditions.GLYPHS[0]]))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
