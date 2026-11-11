"""Recheck raw order/concentration, all six reviewed glyph bindings and local report."""

from __future__ import annotations

import html
import json
import os
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts import nambu_order_binding_20261111 as run


def main():
    from app.generation import answer_facts, conductivity_order
    from app.generation.providers import Evidence
    from app.generation.required_fields_guard_routes import render
    from app.ui import _prepared_statement_text

    comparison, regression = run.BASE / 'comparison_v02', run.BASE / 'regression_v01'
    fresh_path = run.BASE / 'fresh_api_v01/Nambu_06'
    for folder in (comparison, regression, fresh_path, run.BASE / 'pdf_probe_v01', run.BASE / 'catalogue_audit_v01'):
        f.verify_manifest(folder)
        f.verify(run.read(folder / 'bindings.json'))
    first = run.BASE / 'comparison_v01'
    f.verify_manifest(first)
    original_driver = run.BASE / 'before_driver_wrap_v01/nambu_order_binding_20261111.py'
    original_bindings = run.read(first / 'bindings.json')
    driver_key = str(f.ROOT / 'scripts/nambu_order_binding_20261111.py')
    if f.sha(original_driver.read_bytes()) != original_bindings.pop(driver_key):
        raise ValueError('Original driver snapshot differs')
    f.verify(original_bindings)
    data, old, fresh = run.read(comparison / 'result.json'), run.read(regression / 'summary.json'), run.read(fresh_path / 'result.json')
    if (data['before_ready'], data['after_ready'], data['newly_ready']) != (15, 16, ['Nambu_06']):
        raise ValueError('Unexpected availability result')
    if data != run.read(first / 'result.json'):
        raise ValueError('Driver formatting/output version changed comparison results')
    for row in data['cases']:
        cid = row['id']
        for name in ('api_request.json', 'before.json', 'after.json', 'result.json'):
            if (comparison / cid / name).read_bytes() != (first / cid / name).read_bytes():
                raise ValueError('Comparison v01/v02 content differs')
        if row['after_ready'] and (comparison / cid / 'request_unsent.json').read_bytes() != (
                first / cid / 'request_unsent.json').read_bytes():
            raise ValueError('Comparison v01/v02 native differs')
    if (old['actual_service_executions'] != 81 or not all(r['full_service_identical'] for r in old['regressions'])
            or not all(r['full_service_identical'] and r['native_identical'] for r in old['current_comparisons'])):
        raise ValueError('Historical service/native regression differs')
    if (not fresh['trace_exact'] or not fresh['native_exact'] or fresh['registry_diagnostics'] or fresh['network_denials']
            or fresh['real_model_calls'] or fresh['real_oauth_calls']):
        raise ValueError('Fresh API preparation not verified')
    suites = list(ET.parse(run.BASE / 'affected_v01.xml').getroot().iter('testsuite'))
    tests = sum(int(s.get('tests', '0')) for s in suites)
    if tests != 529 or any(int(s.get(k, '0')) for s in suites for k in ('failures', 'errors')):
        raise ValueError('Affected tests not all successful')
    trace = run.read(comparison / 'Nambu_06/after.json')['trace']
    evidence = [Evidence(**e) for e in trace['evidence']]
    record = answer_facts.selection_records(evidence)['F1']
    raw = json.loads(evidence[0].text)['raw_source']
    fact = record['facts'][0]
    anchors = 0
    for anchor in [fact['support'], *[v['source'] for v in (fact['sample'], fact['value'], *fact['conditions'].values()) if v]]:
        if raw[anchor['start']:anchor['end']] != anchor['text'] or anchor['raw_chunk_sha256'] != f.sha(raw.encode()):
            raise ValueError('Raw order/concentration/header binding differs')
        anchors += 1
    if (fact['conditions']['concentration_unit']['source']['text'] != 'mol dm¹3'
            or fact['conditions']['concentration_unit']['text'] != 'mol dm−3'
            or 'concentration_reference_temperature' not in fact['conditions']):
        raise ValueError('Raw/decoded unit or temperature ownership differs')
    resource, digest = conductivity_order.GLYPH_CATALOGUE
    if f.sha(resource.read_bytes()) != digest:
        raise ValueError('Trusted catalogue changed')
    catalogue = run.read(resource)
    pdf = f.ROOT / 'data/pdf/5cafe6e931ef4dc7_Nambu_2016.pdf'
    if f.sha(pdf.read_bytes()) != catalogue['pdf_sha256']:
        raise ValueError('Original PDF changed')
    fixture = run.read(f.ROOT / 'tests/fixtures/nambu_order_source_v01.json')
    sources = {s['chunk_id']: s for s in fixture['trace']['evidence']}
    observations = run.read(run.BASE / 'catalogue_audit_v01/observations.json')
    operations = 0
    with fitz.open(pdf) as document:
        page_text = document[1].get_text()
        if page_text != (run.BASE / 'pdf_probe_v01/page2.txt').read_text(encoding='utf-8') or page_text.strip() not in raw:
            raise ValueError('Fresh page2 extraction differs')
        for entry in catalogue['entries']:
            parent = sources[entry['chunk_id']]
            if f.sha(parent['text'].encode()) != entry['raw_sha256'] or any(
                    parent[k] != entry[k] for k in ('article_id', 'page_start', 'page_end', 'source_type')):
                raise ValueError('Raw parent identity differs')
            for operation in entry['operations']:
                if (parent['text'][operation['raw_start']:operation['raw_end']] != operation['raw_character']
                        or page_text[operation['pdf_text_offset']] != operation['raw_character']
                        or f.sha(document.extract_font(operation['font_xref'])[3]) != operation['font_program_sha256']
                        or not any(all(o[k] == operation[k] for k in o) for o in observations)):
                    raise ValueError('PDF offset/font/position observation differs')
                operations += 1
    config = tomllib.loads((f.ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    if 'resources/reviewed_conductivity_glyph_aliases_v01.json' not in config['tool']['setuptools']['package-data']['app']:
        raise ValueError('Resource missing from package data')
    synthetic = run.read(comparison / 'Nambu_06/synthetic.json')['selection']
    claim = record['allowed_claim']
    if (claim != synthetic['claims'][0]['text'] or 'Концентрация указана при 25°C' not in
            _prepared_statement_text(evidence[0].text, evidence[0].source_type) or 'Концентрация указана при 25°C' not in
            render({'answer': synthetic, 'delivery_status': 'not_evaluated', 'review': None})):
        raise ValueError('Source scope not retained by both UI adapters')
    out = run.BASE / 'review_v01'
    out.mkdir(exist_ok=False)

    def link(path, label):
        if not path.is_file():
            raise FileNotFoundError(path)
        return '<a href="' + html.escape(os.path.relpath(path, out).replace('\\', '/'), quote=True) + '">' + label + '</a>'

    rows = ''.join('<tr><td>' + html.escape(r['id']) + '</td><td>' + html.escape(r['question']) + '</td><td>' +
        str(r['before_ready']) + '</td><td>' + str(r['after_ready']) + '</td><td>' +
        str(r['full_result_unchanged']) + '</td></tr>' for r in data['cases'])
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Nambu06 — порядок проводимости</title>'
        '<style>body{font:16px system-ui;max-width:1150px;margin:35px auto;padding:20px;line-height:1.5}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;background:#eef;padding:18px}</style>'
        '<h1>Nambu06: порядок проводимости</h1><p>11 ноября 2026. Готовность входных пакетов15 → 16 из30. '
        'Остальные29 результатов и15 готовых native inputs точны. Реальных ответов модели нет.</p>'
        '<h2>Серверный текст после синтетического выбора F1</h2><p>' + html.escape(claim) + '</p>'
        '<p>25°C относится к заданию концентрации. Численные значения проводимости с графика не считываются. '
        'Два печатных минуса восстанавливаются только по проверенным offsets в трёх точных raw parents. '
        'Нормализация и единичная нотация M/mol dm⁻³ указаны явно. Старый каталог Peng неизменён.</p>'
        '<p>529 тестов, полный mypy app214,81 прежний service case/пять native inputs. Три synthetic API исхода: '
        '200 F1,200 abstention,502 prose. Guard not_evaluated. Свежая actual API подготовка read-only/rollback, '
        'trace/native exact/registry0. Реальные model/OAuth/slots0.</p><p>' + ' · '.join([
        link(pdf, 'Оригинальный PDF'), link(run.BASE / 'pdf_probe_v01/page2.png', 'PDF2: текст'),
        link(run.BASE / 'pdf_probe_v01/page3.png', 'PDF3: рисунки'), link(resource, 'Каталог знаков'),
        link(comparison / 'Nambu_06/source_audit.json', 'Raw-привязки'), link(fresh_path / 'result.json', 'Свежая подготовка'),
        link(run.BASE / 'affected_v01.xml', 'Тесты')]) + '</p><h2>Точный raw-контекст</h2><pre>' +
        html.escape(fact['support']['text']) + '</pre><h2>Сравнение30 случаев</h2><table><thead><tr><th>ID</th>'
        '<th>Вопрос</th><th>До</th><th>После</th><th>Полный результат прежний</th></tr></thead><tbody>' + rows +
        '</tbody></table><p>Ограничения: конечная грамматика по открытым development данным; источниковая '
        'расшифровка знаков проверена агентом, не независимым экспертом. Общая научная accuracy/ownership, '
        'новые статьи, реальные ответы модели, browser layout, полный suite и deployment не оценены. '
        'Все live scopes закрыты. Следующий количественный случай — Peng07.</p></html>')
    f.save(out / 'review.html', body.encode())
    result = {'before_ready': 15, 'after_ready': 16, 'newly_ready': ['Nambu_06'], 'other_full_results_exact': 29,
        'prior_ready_native_exact': 15, 'comparison_v01_v02_case_content_exact': True, 'raw_anchor_observations': anchors,
        'reviewed_glyph_operations_verified': operations, 'positioned_glyph_observations': len(observations),
        'new_tests': 52, 'affected_tests_passed': tests, 'historical_service_executions': 81, 'historical_native_exact': 5,
        'fresh_API': fresh, 'scientific_accuracy': None, 'real_model_calls': 0, 'real_oauth_calls': 0, 'new_slots': 0}
    f.write(out / 'report.json', result)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', regression / 'manifest.json',
        fresh_path / 'manifest.json', run.BASE / 'affected_v01.xml', resource, pdf, f.ROOT / 'pyproject.toml']))
    f.manifest(out)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
