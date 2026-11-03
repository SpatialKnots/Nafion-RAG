"""Reverify one external-reference case and record a late authorship declaration."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402

STAGE = ROOT / 'output/user_reference_20261030_01'
SCOPE = ROOT / 'docs/records/independent_answer_review_scope_v0.1.md'
DRIFT = ROOT / 'docs/records/independent_answer_review_dependency_drift_v0.1.json'
VERSION = 'external_reference_review_readiness_v0.1'


def run(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    import fitz

    folders = [STAGE / name for name in ('preparation_v01', 'review_v01', 'live_review_v01',
                                        'authorized_run_v01/authorized_inputs', 'authorized_run_v01/live')]
    for folder in folders:
        files.verify_manifest(folder)
    previous = json.loads((STAGE / 'live_review_v01/report.json').read_bytes())
    drift = json.loads(DRIFT.read_bytes())['observed_drift']
    excluded = {row['path'] for row in drift}
    for row in drift:
        if (previous['bindings'].get(row['path']) != row['historical_sha256']
                or files.sha(Path(row['path']).read_bytes()) != row['current_sha256']):
            raise ValueError('Undeclared historical dependency drift')
    unchanged = {name: digest for name, digest in previous['bindings'].items() if name not in excluded}
    files.verify(unchanged)
    raw_reference = (STAGE / 'preparation_v01/user_reference_original.json').read_bytes()
    if raw_reference != (STAGE / 'authorized_run_v01/authorized_inputs/user_reference_original.json').read_bytes():
        raise ValueError('Original external reference drift')
    original = json.loads(raw_reference)
    case, = original['cases']
    api = previous['original_api']
    live = STAGE / 'authorized_run_v01/live'
    if api != json.loads((live / 'api_response.json').read_bytes()):
        raise ValueError('Original API response differs')
    if files.sha((live / 'response.bin').read_bytes()) != previous['summary']['native_response_sha256']:
        raise ValueError('Native response hash differs')
    if files.sha((live / 'request.json').read_bytes()) != previous['summary']['request_sha256']:
        raise ValueError('Native request hash differs')
    windows = previous['separate_assistant_source_notes']
    for window in windows:
        with fitz.open(window['original_pdf_path']) as pdf:
            text = pdf[window['pdf_page'] - 1].get_text('text')
        if text[window['start']:window['end']] != window['exact_text'] or files.sha(text.encode()) != window['page_text_sha256']:
            raise ValueError('Exact reference window differs')
    for page in previous['original_sources']['pages'].values():
        with fitz.open(page['original_pdf_path']) as pdf:
            text = pdf[page['page_number'] - 1].get_text('text')
        if text != page['page_text'] or files.sha(text.encode()) != page['page_text_sha256']:
            raise ValueError('Original selected page differs')
    inventory_path = ROOT / 'output/retrieval_ablation_20261031/capture_v02/articles.json'
    inventory = json.loads(inventory_path.read_bytes())
    articles = []
    scoped_paths = {Path(row['original_pdf_path']).resolve() for row in previous['articles']}
    for article in inventory.values():
        path = Path(article['original_pdf_path']).resolve()
        if path in scoped_paths:
            if files.sha(path.read_bytes()) != article['original_pdf_sha256']:
                raise ValueError('Original PDF differs')
            articles.append(article)
    if len(articles) != len(scoped_paths):
        raise ValueError('Scoped TAC inventory incomplete')
    provenance = {'user_authorship_statement_verbatim': 'я составил',
        'user_available_cases_statement_verbatim': 'Пока есть только эталон Kim',
        'declaration_timing': 'received_after_original_model_output_and_prior_assistant_review',
        'declared_author': 'user_in_this_chat', 'authorship_external_authentication': 'not_performed',
        'annotation_method': None, 'llm_assistance': None, 'separate_scientific_reviewer': None,
        'original_annotation_prediction_exposure': None,
        'reference_content_identity_before_original_dispatch': 'preserved_preparation_and_authorized_input_bytes_identical',
        'prior_topic_source_exposure': previous['known_topic_overlap'],
        'independent_scientific_verification': 'not_established'}
    summary = {'version': VERSION, 'available_external_reference_cases': 1, 'saved_model_answers': 1,
        'original_http_status': api['http_status'], 'original_runtime_status': api['body']['status'],
        'original_claims': len(api['body']['claims']), 'original_reference_items': len(previous['assessment']['reference_item_review']),
        'prior_assistant_not_addressed_observations': sum(row['assessment'] == 'not_addressed'
                                                       for row in previous['assessment']['reference_item_review']),
        'independent_human_adjudications_received': 0, 'independent_scientific_metrics': None,
        'scientific_acceptance': 'not_established', 'scoped_tac_works': len(articles),
        'fresh_reference_windows_verified': len(windows),
        'fresh_selected_pages_verified': len(previous['original_sources']['pages']),
        'new_model_calls': 0, 'new_oauth_calls': 0, 'new_db_calls': 0, 'new_slots': 0,
        'original_slot': 'consumed_closed_no_resend', 'broader_evaluation_scope': 'not_complete',
        'single_case_stage4_scope_change': 'not_yet_authorized', 'plan_completion_percent': 75}
    summary.update(historical_dependency_drifts=len(drift), unchanged_historical_bindings_verified=len(unchanged),
                   identical_historical_pdf_rendering='not_reverified')
    bindings = {**unchanged, **files.bindings([
        Path(__file__), SCOPE, DRIFT, STAGE / 'live_review_v01/report.json', inventory_path,
        *[Path(row['path']) for row in drift],
        *[Path(article['original_pdf_path']) for article in articles]])}
    files.verify(bindings)
    if policy.denied:
        raise ValueError('Unexpected network attempt')
    output.mkdir(parents=True, exist_ok=False)
    links = {'original_live_review': str((STAGE / 'live_review_v01/review.html').resolve()),
             'original_api_response': str((live / 'api_response.json').resolve()),
             'original_native_response': str((live / 'response.bin').resolve()),
             'original_trace': str((live / 'trace.json').resolve()),
             'original_source_registry': str((live / 'sources.json').resolve())}
    report = {'summary': summary, 'bindings': bindings, 'late_provenance_declaration': provenance,
        'historical_dependency_drift': drift, 'original_historical_input_bindings_unchanged': previous['bindings'],
        'user_original_unchanged': original, 'original_api_response': api,
        'prior_assistant_comparison_not_independent_adjudication': previous['assessment'],
        'reference_windows_and_separate_source_caveats': windows, 'articles': articles, 'artifact_paths': links}
    files.save(output / 'user_reference_original.json', raw_reference)
    files.write(output / 'late_authorship_declaration.json', provenance)
    files.write(output / 'report.json', report)
    render(report, output)
    (output / 'source_snapshot').mkdir()
    for path in (Path(__file__), SCOPE, DRIFT):
        files.save(output / 'source_snapshot' / path.name, path.read_bytes())
    files.verify(bindings)
    files.manifest(output)
    return summary


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(raw) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: внешний эталон n=1</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '[hidden]{display:none!important}</style><h1>Внешний пользовательский эталон: ограниченный случай n=1</h1>'
        '<p>Пользователь указал «я составил»; пока имеется только Kim. Это позднее указание авторства, '
        'не подтверждение метода подготовки, отсутствия LLM или независимой научной проверки. '
        'Исходный reference и модельный ответ сохранены без изменений.</p>'
        '<p>Оригинал: HTTP200/answered; два claims о термосвойствах и набухании. Прежнее сравнение ассистента '
        'отмечает все четыре пункта reference как not_addressed. Это не независимая экспертная оценка и '
        'не измерение общей accuracy. Новых model/OAuth/DB/slots:0; прежний слот закрыт. '
        'Пункт4 общего плана остаётся открыт,75%.</p>'
        + detail('Итоговые статусы, включая неизвестное', report['summary'])
        + detail('Обнаруженное изменение исторического rendering binary; старый guard сохранён', report['historical_dependency_drift'])
        + detail('Позднее указание авторства; поля, которые не были сообщены', report['late_provenance_declaration'])
        + detail('Исходный пользовательский вопрос и эталон, дословно', report['user_original_unchanged'])
        + detail('Исходный полный API ответ', report['original_api_response'])
        + detail('Прежнее сравнение ассистента; не human adjudication',
                 report['prior_assistant_comparison_not_independent_adjudication'])
        + '<p>' + ' · '.join('<a href="' + esc(Path(path).as_uri()) + '">' + esc(label) + '</a>'
                             for label, path in report['artifact_paths'].items()) + '</p>')
    for window in report['reference_windows_and_separate_source_caveats']:
        body += ('<p><a href="' + esc(Path(window['original_pdf_path']).as_uri() + '#page=' + str(window['pdf_page']))
                 + '">' + esc(window['label']) + ', PDF с.' + str(window['pdf_page']) + '</a></p>'
                 + detail('Exact source; separate assistant caveat', window))
    body += ('<h2>TAC: все выбранные работы и источник эталона</h2><p>Registered metadata snapshot '
        '31 октября; независимо не проверены. Неизвестные и несобранные поля сохранены.</p>'
        '<label>Поиск по TAC <input id="q" type="search"></label><table id="tac"><thead><tr>'
        + ''.join('<th>' + label + '</th>' for label in ('Title', 'Authors', 'Journal', 'Year', 'Abstract',
                                                       'Conclusions', 'Terms', 'hyperlink to original file'))
        + '</tr></thead><tbody>')
    for article in report['articles']:
        body += '<tr data-row>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            body += '<td>' + ('Неизвестно / не собрано' if article[key] is None else detail('Полное значение', article[key])) + '</td>'
        body += ('<td><a href="' + esc(Path(article['original_pdf_path']).as_uri()) + '">Оригинальный PDF</a>'
                 + detail('Метаданные и происхождение', article) + '</td></tr>')
    body += ('</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});'
             '</script></html>')
    files.save(output / 'review.html', body.encode('utf-8'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(args.output, policy), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
