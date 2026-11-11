"""Independently inspect literal conditions, glyph positions and bounded regressions."""
from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import nambu_pure_concentration_20261111 as run


def main():
    from app.generation import answer_facts
    from app.generation import pure_concentration as conditions
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    base = run.BASE
    comparison, regression = base / 'comparison_v01', base / 'regression_v01'
    fresh = base / 'fresh_api_v01/Nambu_05'
    folders = [comparison, regression, fresh, base / 'pdf_probe_v01', base / 'catalogue_audit_v01']
    for folder in folders:
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    result = run.read(comparison / 'result.json')
    history, prepared = run.read(regression / 'summary.json'), run.read(fresh / 'result.json')
    if (result['before_ready'], result['after_ready'], result['newly_ready']) != (27, 28, ['Nambu_05']):
        raise ValueError('Unexpected availability result')
    if not all(r['full_result_unchanged'] and r['native_unchanged'] for r in result['cases'] if r['id'] != 'Nambu_05'):
        raise ValueError('Other cohort cases changed')
    if (history['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in history['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in history['current_comparisons'])):
        raise ValueError('Historical service/native changed')
    if (not prepared['trace_exact'] or not prepared['native_exact'] or prepared['registry_diagnostics']
            or prepared['network_denials'] or prepared['real_model_calls'] or prepared['real_oauth_calls']):
        raise ValueError('Fresh preparation differs')
    suites = list(ET.parse(base / 'affected_v01.xml').getroot().iter('testsuite'))
    if (sum(int(s.get('tests', '0')) for s in suites) != 1185
            or any(int(s.get(k, '0')) for s in suites for k in ('errors', 'failures'))):
        raise ValueError('Affected tests not all successful')
    parent = Evidence(**run.read(comparison / 'Nambu_05/after.json')['trace']['evidence'][0])
    record = answer_facts.selection_records([parent])['F1']
    payload = json.loads(parent.text)
    raw, facts, anchors = payload['raw_source'], record['facts'], 0
    if (len(facts) != 3 or record['arithmetic'] is not None
            or [(f['sample']['text'], f['value']['text'], f['conditions']['molar_mass']['text']) for f in facts[:2]] != [
                ('FETFEE', '6.50', '190.14'), ('ETFEE', '6.38', '172.15')]
            or any(f['unit']['text'] != 'mol dm−3' or f['conditions']['molar_mass_unit']['text'] != 'g mol−1' for f in facts[:2])
            or facts[2]['value']['text'] != 'may contract to some extent'
            or any(f['conditions']['specimen_state']['text'] != 'single solvents' for f in facts)
            or record['source_grammar']['density_calculation'] != 'not_performed'):
        raise ValueError('Pure state, pair, quantities/units or possible explanation differs')
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
    if (len(operations) != 4 or entry['raw_sha256'] != f.sha(raw.encode())
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
    synthetic = run.read(comparison / 'Nambu_05/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or claim not in _prepared_statement_text(parent.text, parent.source_type)
            or 'может в некоторой степени сжиматься' not in render({
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
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Nambu05 — чистые растворители</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style><h1>Nambu05: молярная концентрация чистой жидкости</h1>'
        '<p>11 ноября 2026. Подготовленные входы27 → 28 из30, только Nambu05. Остальные29 полных результатов '
        'и27 прежних native точны. Реальных ответов модели нет; scientific accuracy не измерена.</p>'
        '<h2>Серверный текст после synthetic F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>Две записи связывают каждый растворитель с концентрацией, молярной массой, обеими единицами '
        'и температурой25°C; single-solvents frame подтверждает состояние чистой жидкости. Третья запись '
        'сохраняет may contract to some extent как авторское возможное объяснение. '
        'Численная плотность, доля сокращения объёма и независимое структурное измерение не добавлены; '
        'формула c=ρ/M и производные числа этим контрактом не рассчитываются. Концентрация LiPF6 из '
        'другого подраздела не переносится. Связь с сильным межмолекулярным притяжением дана как авторская интерпретация.</p>'
        '<p>Четыре reviewed glyph operations одного полного PDF2 raw SHA/article/chunk/page/type: '
        'U+00B9→minus в двух mol dm−3 и двух g mol−1. Все PDF offsets/font/bbox/font-program SHA '
        'перепроверены. Полный Poppler PDF2 визуально просмотрен; это интерпретация агента, не '
        'автоматическая семантика имени шрифта. Старые catalogues/raw/PDF прежние; package-data одна новая строка.</p>'
        '<p>1185 тестов,58 новых; полный mypy app224.81 historical service case/пять native exact. '
        'Четыре synthetic API исхода200/200/502/502; три synthetic service исхода. Guard not_evaluated. '
        'Свежая actual API readonly/rollback preparation trace/native exact, registry0; '
        'реальные model/OAuth/newslots0.</p><p>' + ' · '.join([
            link(pdf, 'Исходный PDF'), link(base / 'pdf_probe_v01/page2.png', 'Полный PDF2'),
            link(conditions.GLYPHS[0], 'Glyph catalogue'), link(comparison / 'Nambu_05/source_audit.json', 'Raw-привязки'),
            link(fresh / 'result.json', 'Свежая API подготовка'), link(base / 'affected_v01.xml', 'Тесты')]) + '</p>'
        '<h2>Три записи с точными raw anchors</h2>' + details + '<h2>Все30 случаев</h2><table><thead><tr>'
        '<th>ID</th><th>Вопрос</th><th>До</th><th>После</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>Initial source probe eligible; focused58passed с первой попытки. Catalogue binding/source '
        'проверены после formatting; старые manifests не переписывались.</p>'
        '<p>Ограничения: finite grammar/точечная source glyph repair на открытых development источниках. '
        'Не общий причинный validator, не измерение плотности или структуры. Новые статьи/реальные F-ID '
        'ответы/независимая scientific accuracy/browser/full repository suite/wheel/deployment не проверены. '
        'Retrieval/ranking/вопросы/prompt/thresholds/DB/PDF/index/UI прежние. Остались2explanation refusals '
        'Nambu07/08. Live scopes закрыты; независимая оценка открыта, план75% прежний.</p></html>')
    f.save(out / 'review.html', body.encode())
    report = {'before_ready': 27, 'after_ready': 28, 'newly_ready': ['Nambu_05'], 'other_results_exact': 29,
        'old_ready_native_exact': 27, 'facts': 3, 'raw_anchor_observations': anchors, 'glyph_operations_checked': 4,
        'fresh_full_PDF_pages_visually_reviewed': 1, 'tests_passed': 1185, 'new_tests': 58,
        'historical_service_cases_exact': 81, 'historical_native_exact': 5, 'fresh_API': prepared,
        'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0, 'scientific_accuracy': None}
    f.write(out / 'report.json', report)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), *(p / 'manifest.json' for p in folders),
        base / 'affected_v01.xml', pdf, conditions.GLYPHS[0]]))
    f.manifest(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
