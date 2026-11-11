"""Independently inspect solubility threshold, reference identity, glyph positions and bounded regressions."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import nambu_solubility_limit_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation import solubility_limit as conditions
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression = base / 'comparison_v01', base / 'regression_v01'
    fresh = base / 'fresh_api_v01/Nambu_08'
    folders = [comparison, regression, fresh, base / 'pdf_probe_v01']
    for folder in folders:
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result = run.read(comparison / 'result.json')
    history, prepared = run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (29, 30, ['Nambu_08']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Nambu_08'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 1298
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    parent = Evidence(**run.read(comparison / 'Nambu_08/after.json')['trace']['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    payload = json.loads(parent.text)
    raw, facts, anchors = payload['raw_source'], record['facts'], 0
    if (len(facts) != 3 or record['arithmetic'] is not None
            or facts[0]['sample']['text'] != 'DEE' or facts[0]['value']['text'] != '1,2-diethoxyethane'
            or facts[1]['sample']['text'] != 'LiPF6' or facts[1]['value']['text'] != '1'
            or facts[1]['unit']['text'] != 'mol dm−3'
            or facts[1]['conditions']['concentration_reference_temperature']['text'] != '25'
            or facts[2]['sample']['text'] != 'DEE' or facts[2]['value']['text'] != 'much less than'
            or facts[2]['conditions']['comparison_concentration']['text'] != '1'
            or 'concentration_reference_temperature' in facts[2]['conditions']
            or 'exact_solubility' not in facts[2]['unknown_fields']):
        raise ValueError('Reference identity, concentration, qualitative comparator or temperature scope differs')
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
    if f.sha(conditions.GLYPHS[0].read_bytes()) != conditions.GLYPHS[1]:
        raise ValueError('Glyph catalogue differs')
    entries = [e for e in catalogue['entries'] if e['raw_sha256'] == f.sha(raw.encode())]
    if len(entries) != 1:
        raise ValueError('Nonunique exact original catalogue parent')
    entry = entries[0]
    operations = entry['operations']
    if (len(operations) != 2 or entry['raw_sha256'] != f.sha(raw.encode())
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
    synthetic = run.read(comparison / 'Nambu_08/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'недостаточная растворимость' not in render({
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
        pages = [document[n-1].get_text() for n in (1, 2)]
        if (any(page != (base / f'pdf_probe_v01/page{n}.txt').read_text(encoding='utf-8')
                or page.strip() not in raw for n, page in enumerate(pages, 1))
                or facts[0]['support']['text'] not in pages[0]
                or any(f['support']['text'] not in pages[1] for f in facts[1:])):
            raise ValueError('Fresh full PDF1/2 or source support differs')
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Nambu08 — растворимость</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Nambu08: ограничение растворимости</h1>'
        '<p>11 ноября2026. Подготовленные входы29 → 30 из30, только Nambu08. Остальные29 полных результатов '
        'и29 прежних native точны. Это30 prepared-unsent, не30 реальных или научно правильных ответов.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Три записи: исходное имя/alias DEE; concentration/reference-temperature и список растворителей '
        'сравнения; solubility much less than1mol dm−3. Один полный raw parent PDF1/2. '
        '25°C не присвоено температуре измерения растворимости;1mol dm−3 не выдано за её точное значение. '
        'Не утверждаются полная нерастворимость, нулевая проводимость или неудачный опыт приготовления. '
        'Причина отсутствия в сравнении связана с явным сопоставлением условий, не с отсутствием найденных данных.</p>'
        '<p>Повторно используются две уже reviewed U+00B9→minus операции в единицах. '
        'Все восемь прежних каталогов, package-data/configuration/raw/PDF неизменны; новых aliases нет. '
        'Positioned PDF offsets/font/bbox/font-program SHA и исходный raw SHA/type проверены. '
        'Полные свежие Poppler PDF1/2 визуально просмотрены.</p>'
        '<p>1298affected tests/58new; mypy app226; Ruff6.81historical service cases/five native exact. '
        'Четыре synthetic API исхода200/200/502/502 и три synthetic service исхода. Guard not_evaluated. '
        'FreshactualAPIreadonly/rollback trace/native exact/registry0; realmodel/OAuth/newslots0. '
        'Focused58/affected1298 проходят с первой попытки; без новых typing diagnostics.</p><p>' + ' · '.join([
            link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page1.png', 'Полный PDF1'),
            link(base / 'pdf_probe_v01/page2.png', 'Полный PDF2'), link(conditions.GLYPHS[0], 'Прежний glyph catalogue'),
            link(comparison / 'Nambu_08/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Три записи с raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr>'
        '<th>ID</th><th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Ограничения: конечная source grammar на открытых development вопросах/источниках. '
        'Не общий causal/chemical validator, не независимая научная оценка.30/30 означает готовность '
        'конкретных входов, а не полноту или точность системы на новых статьях. Новые статьи/реальные F-ID '
        'ответы/browser/full repository suite/wheel/deployment не проверены. Retrieval/ranking/questions/'
        'prompt/thresholds/DB/PDF/index/UI/API schema прежние. Старые live scopes закрыты, новых нет; '
        'план75% и независимая оценка прежние. Следующий этап — сводный offline audit/freeze этой '
        'development серии; live measurement и независимые новые задачи требуют отдельного scope.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 29, 'after_ready': 30, 'newly_ready': ['Nambu_08'], 'other_results_exact': 29,
        'old_ready_native_exact': 29, 'facts': 3, 'raw_anchor_observations': anchors, 'glyph_operations_checked': 2,
        'fresh_full_PDF_pages_visually_reviewed': 2, 'tests_passed': 1298, 'new_tests': 58,
        'historical_service_cases_exact': 81, 'historical_native_exact': 5, 'fresh_API': prepared,
        'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), *(p / 'manifest.json' for p in folders),
        base / 'affected_v01.xml', pdf, conditions.GLYPHS[0]]))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
