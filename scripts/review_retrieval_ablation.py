"""Replay all frozen retrieval arms and report exposed-fixture/source retention."""

from __future__ import annotations

import argparse
import copy
import html
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.retrieval_ablation import ARMS, VERSION, candidate_bundle  # noqa: E402
from scripts.retrieval_ablation_labels import VERSION as LABEL_VERSION  # noqa: E402
from scripts.retrieval_ablation_labels import label_retention  # noqa: E402
from scripts.retrieval_loss_audit import anchor_presence  # noqa: E402
from scripts.review_swelling_retrieval_audit import replay  # noqa: E402
from scripts.run_retrieval_ablation import PRIOR  # noqa: E402


def unpack(value: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    restored = copy.deepcopy(value)
    for stage in restored['stages']:
        for row in stage['results']:
            if 'full_text_sha256' in row:
                raw = corpus[row['chunk_id']]['full_text']
                if files.sha(raw.encode()) != row.pop('full_text_sha256'):
                    raise ValueError('Packed raw source differs')
                row['full_text'] = raw
    return restored


def replay_arm(value: dict[str, Any], corpus: dict[str, Any], settings: Any) -> dict[str, Any]:
    from app.retrieval import cross_lingual, search

    restored = unpack(value, corpus)
    with ExitStack() as stack:
        stack.enter_context(patch.object(search, '_cross_lingual_variant_top_k', return_value=value['limits']['variant_top_k']))
        stack.enter_context(patch.object(search, '_cross_lingual_rerank_window_size', return_value=value['limits']['feature_window']))
        if value['arm'] in {'expansion', 'combined'}:
            stack.enter_context(patch.object(search, 'build_query_bundle', candidate_bundle))
            stack.enter_context(patch.object(cross_lingual, 'build_query_bundle', candidate_bundle))
        return replay(restored, settings)


def evidence_identity(trace: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(row['article_id'], row['chunk_id'], files.sha(row['text'].encode())) for row in trace['evidence']]


def compare_case(case: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    baseline = values['baseline']
    base_label = baseline['article_label_retention']['any_expected_article_present']
    changes = {}
    for arm in ARMS:
        value = values[arm]
        label = value['article_label_retention']['any_expected_article_present']
        changes[arm] = {
            'article_label_retention': value['article_label_retention'],
            'legacy_capture_article_label_retention': value.get('legacy_capture_article_label_retention'),
            'existing_positive_article_gain': base_label is False and label is True,
            'existing_positive_article_loss': base_label is True and label is False,
            'matching_labelled_article_ids_lost': sorted(set(baseline['article_label_retention']['matching_article_ids'])
                                                        - set(value['article_label_retention']['matching_article_ids'])),
            'matching_labelled_article_ids_gained': sorted(set(value['article_label_retention']['matching_article_ids'])
                                                          - set(baseline['article_label_retention']['matching_article_ids'])),
            'retrieval_order_changed': [r['chunk_id'] for r in value['trace']['retrieval']['results']]
                                       != [r['chunk_id'] for r in baseline['trace']['retrieval']['results']],
            'evidence_changed': evidence_identity(value['trace']) != evidence_identity(baseline['trace']),
            'adequacy': value['trace']['metadata']['evidence_adequacy'],
            'adequacy_changed': value['trace']['metadata']['evidence_adequacy']['adequate']
                                != baseline['trace']['metadata']['evidence_adequacy']['adequate'],
            'channel_calls': value['channel_calls'], 'boundary_status': value['boundary_status'],
            'additional_query_variants_vs_baseline': (
                len(value['trace']['retrieval']['metadata']['cross_lingual']['variants'])
                - len(baseline['trace']['retrieval']['metadata']['cross_lingual']['variants'])),
            'retrieval': [{key: row[key] for key in ('article_id', 'chunk_id', 'title', 'page_start', 'page_end', 'text_layer')}
                          for row in value['trace']['retrieval']['results']],
        }
    return {'id': case['id'], 'query': case['query'], 'origin': case['origin'],
            'fixture_answerable_label': case.get('answerable'), 'arms': changes}


def source_observations(value: dict[str, Any], corpus: dict[str, Any], prior: dict[str, Any]) -> list[dict[str, Any]]:
    restored = unpack(value, corpus)
    observations = []
    for stage in restored['stages']:
        retained = []
        for window in prior['reference_windows']:
            presence = anchor_presence(stage['results'], article_id=prior['target_article_id'],
                                       page_number=window['pdf_page'], exact_text=window['exact_text'])
            retained.append({'label': window['label'], **presence})
        observations.append({'name': stage['name'], 'count': len(stage['results']), 'anchors': retained,
                             'exact_windows_present': [row['label'] for row in retained if row['anchor_present']]})
    return observations


def review(captured: Path, output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    files.verify_manifest(captured)
    capture = json.loads((captured / 'capture.json').read_bytes())
    files.verify(capture['bindings'])
    corpus = json.loads((captured / 'corpus.json').read_bytes())
    articles = json.loads((captured / 'articles.json').read_bytes())
    dataset = json.loads((captured / 'cases.json').read_bytes())
    prior = json.loads((PRIOR / 'capture_v02/capture.json').read_bytes())
    paths = [Path(__file__), ROOT / 'scripts/review_swelling_retrieval_audit.py', ROOT / 'scripts/retrieval_loss_audit.py',
             ROOT / 'tests/unit/test_retrieval_ablation_review.py',
             ROOT / 'scripts/retrieval_ablation_labels.py', ROOT / 'tests/unit/test_retrieval_ablation_labels.py',
             ROOT / 'docs/records/retrieval_ablation_label_accounting_v0.2.md',
             captured / 'manifest.json', captured / 'capture.json', captured / 'cases.json',
             captured / 'corpus.json', captured / 'articles.json']
    comparisons = []
    morphologies = []
    replays = []
    partial_comparisons = []
    for index, case in enumerate(dataset['cases']):
        values = {arm: json.loads((captured / f'cases/{index:03d}_{arm}.json').read_bytes()) for arm in ARMS}
        limits = [value['limits'] for value in values.values()]
        if any(value != limits[0] for value in limits):
            raise ValueError('Arm limits differ')
        for arm, value in values.items():
            # Preserve the first capture's limited counter; recompute from the
            # unchanged raw retrieval with the existing repository fixture parser.
            value['legacy_capture_article_label_retention'] = value['article_label_retention']
            value['article_label_retention'] = label_retention(case, value['trace']['retrieval']['results'], articles)
            result = replay_arm(value, corpus, settings)
            replays.append({'id': case['id'], 'arm': arm, **result})
            earlier_path = captured.parent / 'capture_v01' / f'cases/{index:03d}_{arm}.json'
            if earlier_path.is_file():
                earlier = json.loads(earlier_path.read_bytes())
                partial_comparisons.append({'id': case['id'], 'arm': arm,
                    'full_trace_identical': value['trace'] == earlier['trace'],
                    'all_boundaries_identical': value['stages'] == earlier['stages']})
        if case['id'] == 'morphology_original':
            corrupted = copy.deepcopy(values['baseline'])
            boundary = next(stage for stage in corrupted['stages']
                            if stage['name'] == '_diversify_cross_lingual_results:2:output')
            boundary['results'].reverse()
            try:
                replay_arm(corrupted, corpus, settings)
            except ValueError as exc:
                if str(exc) != 'Replay differs at _diversify_cross_lingual_results:2:output':
                    raise
            else:
                raise ValueError('Corrupted boundary accepted')
        comparisons.append(compare_case(case, values))
        if case.get('evaluate_reference_windows'):
            morphologies.append({'id': case['id'], 'query': case['query'], 'origin': case['origin'],
                'generation_evidence_by_arm': {arm: value['trace']['evidence'] for arm, value in values.items()},
                'arms': {arm: source_observations(value, corpus, prior) for arm, value in values.items()}})
        print(json.dumps({'replayed_case': index + 1, 'total_cases': len(dataset['cases'])}), flush=True)
    summary = {'version': VERSION, **capture['summary'], 'replayed_arm_runs': len(replays),
        'article_label_metric_version': LABEL_VERSION,
        'legacy_capture_positive_article_label_cases': sum(
            row['arm'] == 'baseline' and row['article_label_retention']['has_existing_positive_article_label']
            for row in capture['outcomes']),
        'legacy_capture_metric_limitation': 'Nested checksum/title/identity targets were absent from the first counter; '
                                           'raw captures unchanged; final review recomputes all existing target types.',
        'partial_attempt_comparisons': partial_comparisons,
        'corrupted_boundary_control': 'rejected_at_expected_boundary',
        'existing_positive_article_label_cases': sum(row['arms']['baseline']['article_label_retention']
                                                   ['has_existing_positive_article_label'] for row in comparisons),
        'independent_accuracy': None, 'retrieval_candidates_only': True}
    summary['arms'] = {}
    for arm in ARMS:
        rows = [row['arms'][arm] for row in comparisons]
        summary['arms'][arm] = {
            'existing_positive_article_hits_at_5': sum(row['article_label_retention']['any_expected_article_present'] is True
                                                      for row in rows),
            'article_label_gains_vs_baseline': [case['id'] for case in comparisons if case['arms'][arm]['existing_positive_article_gain']],
            'article_label_losses_vs_baseline': [case['id'] for case in comparisons if case['arms'][arm]['existing_positive_article_loss']],
            'any_labelled_article_identity_loss_cases': [case['id'] for case in comparisons
                                                        if case['arms'][arm]['matching_labelled_article_ids_lost']],
            'retrieval_order_changed_cases': sum(row['retrieval_order_changed'] for row in rows),
            'evidence_changed_cases': sum(row['evidence_changed'] for row in rows),
            'adequacy_changed_cases': [case['id'] for case in comparisons if case['arms'][arm]['adequacy_changed']],
            'exact_channel_calls': sum(row['channel_calls']['exact_search'] for row in rows),
            'expansion_activated_cases': [case['id'] for case in comparisons
                                          if case['arms'][arm]['additional_query_variants_vs_baseline'] > 0],
            'semantic_channel_calls_including_cache_hits': sum(row['channel_calls']['semantic_search'] for row in rows),
        }
    import fitz

    for window in prior['reference_windows']:
        with fitz.open(window['original_pdf_path']) as pdf:
            text = pdf[window['pdf_page'] - 1].get_text('text')
        if (files.sha(text.encode()) != window['page_text_sha256']
                or text[window['start']:window['end']] != window['exact_text']):
            raise ValueError('Reference window differs from fresh source extraction')
    for article in articles.values():
        pdf = Path(article['original_pdf_path'])
        if files.sha(pdf.read_bytes()) != article['original_pdf_sha256']:
            raise ValueError('Original PDF differs')
    if policy.denied:
        raise ValueError('Unexpected network attempt')
    bindings = {**capture['bindings'], **files.bindings(paths)}
    files.verify(bindings)
    report = {'summary': summary, 'bindings': bindings, 'comparisons': comparisons, 'morphology_sources': morphologies,
        'replays': replays, 'reference_windows': prior['reference_windows'], 'articles': list(articles.values()),
        'artifact_paths': {'capture': str((captured / 'capture.json').resolve()),
                           'corpus': str((captured / 'corpus.json').resolve()),
                           'frozen_cases': str((captured / 'cases.json').resolve())},
        'limitations': ['Exposed overlapping fixtures and constructed paraphrases; no independent scientific accuracy.',
            'Article/window retention is not semantic answer validity. No new model output.',
            'Candidate arms are offline monkeypatches; no runtime rollout or gate fix.',
            'SQL ties may change order; semantic cache/order preclude unbiased latency comparison.',
            'Browser, full suite and mypy untested this iteration.'], 'plan_completion_percent': 75}
    output.mkdir(parents=True, exist_ok=False)
    files.write(output / 'report.json', report)
    render(report, output)
    for name in ('scripts/retrieval_ablation.py', 'scripts/run_retrieval_ablation.py',
                 'scripts/review_retrieval_ablation.py', 'tests/unit/test_retrieval_ablation.py',
                 'tests/unit/test_retrieval_ablation_review.py',
                 'scripts/retrieval_ablation_labels.py', 'tests/unit/test_retrieval_ablation_labels.py',
                 'docs/records/retrieval_ablation_protocol_v0.1.md', 'docs/records/retrieval_ablation_cases_v0.1.json',
                 'docs/records/retrieval_ablation_label_accounting_v0.2.md'):
        destination = output / 'source_snapshot' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        files.save(destination, (ROOT / name).read_bytes())
    files.verify(bindings)
    files.manifest(output)
    return summary


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(raw) + '</pre></details>'

    summary = report['summary']
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: offline retrieval ablation</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '[hidden]{display:none!important}</style><h1>Четыре варианта поиска: offline-сравнение</h1><p>'
        + esc(VERSION) + '. Cases: ' + str(summary['case_count']) + '; unique queries: ' + str(summary['unique_queries'])
        + '. Исходные per-query windows и final top-5 сохранены. Expansion добавляет каналы; их число учитывается. '
        'Рабочий код/индекс/PDF не менялись. Model/OAuth/slots:0. План75%, независимая оценка открыта.</p>'
        '<p>Existing article hits и exact source windows — ограниченные метрики exposed fixtures. Это не научная '
        'точность ответов. Все потери/изменения ниже сохранены; candidate не внедрён.</p>'
        + detail('Полные итоги и бюджеты', summary) + detail('Ограничения', report['limitations'])
        + '<p>' + ' · '.join('<a href="' + esc(Path(path).as_uri()) + '">' + esc(label) + '</a>'
                             for label, path in report['artifact_paths'].items()) + '</p>'
        '<h2>Существующие положительные article labels</h2><table><thead><tr><th>Arm</th><th>Hits@5 / labelled cases</th>'
        '<th>Gains</th><th>Losses</th><th>Evidence changed</th><th>Exact channels</th></tr></thead><tbody>')
    for arm, value in summary['arms'].items():
        body += ('<tr><td>' + esc(arm) + '</td><td>' + str(value['existing_positive_article_hits_at_5']) + '/'
            + str(summary['existing_positive_article_label_cases']) + '</td><td>'
            + detail('Случаи', value['article_label_gains_vs_baseline']) + '</td><td>'
            + detail('Полные и частичные потери ожидаемых работ', {
                'case_hit_lost': value['article_label_losses_vs_baseline'],
                'any_expected_article_identity_lost': value['any_labelled_article_identity_loss_cases']}) + '</td><td>'
            + str(value['evidence_changed_cases']) + '</td><td>' + str(value['exact_channel_calls']) + '</td></tr>')
    body += '</tbody></table><h2>Точные source windows: оригинальный morphology case и development paraphrases</h2>'
    for case in report['morphology_sources']:
        body += '<h3>' + esc(case['query']) + '</h3><p>' + esc(case['origin']) + '</p>'
        for arm, stages in case['arms'].items():
            final = next(row for row in stages if row['name'] == 'generation_evidence')
            body += ('<p><strong>' + esc(arm) + '</strong>: generation evidence содержит '
                     + str(len(final['exact_windows_present'])) + '/8 точных окон.</p>'
                     + detail('Полные actual generation evidence; не новый ответ модели', case['generation_evidence_by_arm'][arm])
                     + detail('Все стадии и raw anchors', stages))
    body += '<h2>Каждый случай: сохранённые изменения, gate и top-5</h2>'
    for case in report['comparisons']:
        body += detail(case['id'] + ': ' + case['query'], case)
    body += '<h2>Точные PDF источники диагностических окон</h2>'
    for window in report['reference_windows']:
        body += ('<p><a href="' + esc(Path(window['original_pdf_path']).as_uri() + '#page=' + str(window['pdf_page']))
                 + '">' + esc(window['label']) + ', PDF с.' + str(window['pdf_page']) + '</a></p>'
                 + detail('Точный source fragment; separate assistant source notes', window))
    body += ('<h2>TAC: все документы корпуса сравнения</h2><p>Fresh read-only DB metadata. Неизвестные поля '
        'и несобранные Conclusions/Terms сохранены. PDF checksums проверены; metadata не прошли независимую экспертизу.</p>'
        '<label>Поиск по TAC <input id="q" type="search"></label><table id="tac"><thead><tr>'
        + ''.join('<th>' + label + '</th>' for label in ('Title', 'Authors', 'Journal', 'Year', 'Abstract',
                                                       'Conclusions', 'Terms', 'hyperlink to original file'))
        + '</tr></thead><tbody>')
    for article in report['articles']:
        body += '<tr data-row>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            body += '<td>' + ('Неизвестно / не собрано' if article[key] is None else detail('Полное значение', article[key])) + '</td>'
        body += ('<td><a href="' + esc(Path(article['original_pdf_path']).as_uri()) + '">Оригинальный PDF</a>'
                 + detail('Происхождение и диагностика', article) + '</td></tr>')
    body += ('</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});'
             '</script></html>')
    files.save(output / 'review.html', body.encode('utf-8'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captured', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(review(args.captured, args.output, policy), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
