"""Verify the catalogue delta and all offline API preparations; export a review."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from html import escape
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from scripts import gigachat_answer_smoke as f
from scripts import repair_kondo_metadata_20261110 as repair


def trace_title_deltas(old, new, path=()):
    """Permit only exact, source-reviewed title substitutions on the corrected article."""
    deltas = []
    if isinstance(old, dict) and isinstance(new, dict) and old.keys() == new.keys():
        for key in old:
            if key == 'title' and old[key] != new[key] and old.get('article_id') == new.get('article_id') == repair.ARTICLE:
                if old[key] != repair.BEFORE['title'] or new[key] != repair.AFTER['title']:
                    raise ValueError('Unplanned title substitution')
                deltas.append({'path': [*path, key], 'article_id': repair.ARTICLE, 'before': old[key], 'after': new[key]})
            else:
                deltas.extend(trace_title_deltas(old[key], new[key], (*path, key)))
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for index, (left, right) in enumerate(zip(old, new, strict=True)):
            deltas.extend(trace_title_deltas(left, right, (*path, index)))
    elif old != new:
        raise ValueError('Unmapped trace change: ' + str(path))
    return deltas


def main():
    from app.db.models import Article
    from app.db.session import SessionLocal
    from app.metadata.bibliography import FIELDS, latest, projection
    from app.retrieval.source_reference import reference, resolve

    old, base = repair.transfer.BASE, repair.BASE
    junit = f.ROOT / 'output/kondo_metadata_repair_tests_20261110.xml'
    suites = ET.fromstring(junit.read_bytes()).findall('testsuite')
    test_count = sum(int(s.attrib['tests']) for s in suites)
    if test_count != 63 or any(int(s.attrib.get(k, '0')) for s in suites for k in ('failures', 'errors', 'skipped')):
        raise ValueError('Unexpected targeted regression test results')
    repair.transfer.fixed_version()
    f.verify_manifest(repair.PLAN)
    f.verify(repair.read(repair.PLAN / 'bindings.json'))
    applied = repair.read(base / 'applied.json')
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        after = repair.snapshot(session)
        article = session.get(Article, UUID(repair.ARTICLE))
        provenance = repair.source(article)
        previous = latest(session, article.id)
        # Even an empty automatic proposal must preserve these explicit source-reviewed values.
        current = {k: getattr(article, k) for k in FIELDS}
        projected = projection(current, {'fields': {k: {'status': 'unresolved'} for k in FIELDS}},
                               previous.payload if previous else None)
        if projected['after_values'] != current or any(v != 'existing_value_preserved' for v in projected['actions'].values()):
            raise ValueError('Existing refresh rules would overwrite source-reviewed metadata')
        session.rollback()
    if after != applied['catalogue_after'] or after != repair.read(repair.PLAN / 'expected_after.json'):
        raise ValueError('Catalogue drift after replay')
    if provenance != repair.read(repair.PLAN / 'source.json'):
        raise ValueError('Original source drift')
    before = repair.read(repair.PLAN / 'before.json')
    probes = {query: resolve(reference(query), after) for query in ('Kondo (2026)', 'Kondo (2025)', 'Kond (2026)')}
    if resolve(reference('Kondo (2026)'), before) or probes != {
            'Kondo (2026)': [repair.ARTICLE], 'Kondo (2025)': [], 'Kond (2026)': []}:
        raise ValueError('Exact bibliographic resolution did not change as planned')
    changes = {aid: [key for key in row if before[aid][key] != row[key]]
               for aid, row in after.items() if row != before[aid]}
    if changes != {repair.ARTICLE: list(repair.FIELDS)}:
        # Canonical JSON key order need not match the field declaration.
        if set(changes) != {repair.ARTICLE} or set(changes[repair.ARTICLE]) != set(repair.FIELDS):
            raise ValueError('Unexpected committed field delta')
    cases = repair.read(old / 'input_freeze_v01/questions.json')['cases']
    results, counts, records, paths = [], {}, [], [Path(__file__), Path(repair.__file__)]
    unchanged_controls, exact_control_traces, mapped_deltas = 0, 0, []
    for case in cases:
        cid = case['id']
        folder = base / 'prepared_v01' / cid
        f.verify_manifest(folder)
        f.verify_manifest(old / 'prepared_v01' / cid)
        f.verify_manifest(old / 'live' / cid)
        result = repair.read(folder / 'result.json')
        if not result['all_selected_match'] or not result['resolved']['resolved'] or result['network_denials']:
            raise ValueError('Unresolved/mixed article scope or network denial')
        if result['transaction_read_only'] != 'on' or result['model_calls'] or result['oauth_calls']:
            raise ValueError('Replay violated read-only/no-call boundary')
        if case['label'] != 'Kondo':
            same = result['exact_previous_files']
            if not all(value for name, value in same.items() if name != 'trace.json'):
                raise ValueError('Non-Kondo preparation changed: ' + cid)
            deltas = trace_title_deltas(repair.read(old / 'prepared_v01' / cid / 'trace.json'),
                                        repair.read(folder / 'trace.json'))
            if same['trace.json']:
                exact_control_traces += 1
            elif not deltas:
                raise ValueError('Unmapped non-Kondo trace byte change')
            mapped_deltas.extend({'id': cid, **delta} for delta in deltas)
            unchanged_controls += 1
        old_contract = repair.read(old / 'prepared_v01' / cid / 'contract.json')
        response = result['baseline_api_response']
        reason = None if response is None else response['body']['answer']['metadata']['evidence_adequacy'].get('reason')
        row = {'id': cid, 'previous_status': old_contract['preparation_status'],
               'resolved_article_id': result['resolved']['article_id'], 'all_selected_match': True,
               'generation_reached': result['generation_reached'], 'refusal_reason': reason,
               'unchanged_previous_files': result['exact_previous_files']}
        results.append(row)
        counts.setdefault(case['label'], Counter())['ready_unsent' if result['generation_reached'] else str(reason)] += 1
        records.append('<tr><td>' + escape(cid) + '</td><td>' + escape(row['previous_status'])
            + '</td><td>Точная статья</td><td>' + escape('Подготовлен, не отправлен' if row['generation_reached'] else str(reason))
            + '</td><td><a href="../prepared_v01/' + cid + '/result.json">Диагностика</a></td></tr>')
        paths.extend([folder / 'manifest.json', old / 'prepared_v01' / cid / 'manifest.json', old / 'live' / cid / 'manifest.json'])
    if len(results) != 30 or unchanged_controls != 20 or exact_control_traces != 19 or len(mapped_deltas) != 2:
        raise ValueError('Incomplete regression scope')
    closure = repair.read(old / 'scope_closed_v01.json')
    if closure['remaining_allowance'] != 0:
        raise ValueError('Historical live scope is not closed')
    report = {'catalogue_delta': changes, 'article_count': len(after), 'case_count': len(results),
        'exact_reference_controls': probes,
        'all_30_exact_article_scope': True, 'unchanged_Nambu_Peng_preparations': unchanged_controls,
        'exact_Nambu_Peng_trace_files': exact_control_traces, 'mapped_candidate_title_deltas': mapped_deltas,
        'counts': counts, 'cases': results, 'dry_run_rolled_back': True,
        'refresh_preserves_corrected_fields': True, 'model_calls': 0, 'oauth_calls': 0,
        'tests_passed': test_count,
        'new_dispatch_authorized': False, 'app_code_changed': False, 'scientific_accuracy': None,
        'browser_layout_verified': False, 'original_scope_remaining_allowance': 0,
        'diagnostics': ['Initial sandbox PostgreSQL read denied; escalated read succeeded.',
                        'Initial plan_v01 stopped before mutation: journal quote appeared twice; '
                        'separate plan_v02 binds the unique full copyright line. Both directories retained.',
                        'Initial reviewer rejected Peng_04 trace: two Kondo candidate title labels changed. '
                        'Failed reviewer preserved; v02 permits only these exact title changes bound to the corrected article. '
                        'Source selection, scores, order, native input and all other trace values are unchanged.',
                        '63 existing tests passed with pytest cache permission warning; no full suite/mypy rerun.']}
    folder = base / 'review_v02'
    folder.mkdir(exist_ok=False)
    f.write(folder / 'report.json', report)
    header = '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Исправление метаданных Kondo</title>'
    body = '<style>body{font:16px system-ui;margin:32px;max-width:1500px}td,th{border:1px solid #ccc;padding:9px}' \
           'table{border-collapse:collapse}pre{white-space:pre-wrap}</style><h1>Исправление метаданных Kondo</h1>'
    body += '<p>Одна запись, четыре поля; исходные значения и источник сохранены. Код приложения, вопросы, '
    body += 'правила поиска и PDF прежние. Все30 запросов выбирают нужную статью; '
    body += 'у20 Nambu/Peng подготовок выбранные источники и native inputs точны прежним. '
    body += '19 полных traces точны; уPeng_04 только две замены названия Kondo в диагностике кандидатов.</p>'
    body += '<p>Это проверка подготовки, без новых ответов модели и без научной оценки. '
    body += 'Лексические отказы остаются отдельной проблемой. Все прежние лимиты закрыты.</p>'
    body += '<h2>Изменение каталога</h2><pre>' + escape(json.dumps({'before': repair.BEFORE, 'after': repair.AFTER},
                                                                               ensure_ascii=False, indent=2)) + '</pre>'
    body += '<p><a href="../plan_v02/source.json">Точные цитаты первой страницы и SHA-256</a> · '
    body += '<a href="../plan_v02/before.json">Каталог до</a> · <a href="../applied.json">Каталог после</a> · '
    body += '<a href="report.json">Полный отчёт</a></p>'
    body += '<h2>Все30 повторных подготовок</h2><table><thead><tr><th>Вопрос</th><th>Ранее</th><th>Статья теперь</th>'
    body += '<th>Подготовка теперь</th><th>Артефакты</th></tr></thead><tbody>' + ''.join(records) + '</tbody></table></html>'
    f.save(folder / 'review.html', (header + body).encode())
    paths.extend([repair.PLAN / 'manifest.json', base / 'applied.json', old / 'scope_closed_v01.json',
                  junit, *[f.ROOT / 'tests/unit' / name for name in (
                      'test_source_reference.py', 'test_bibliography_bridge.py', 'test_reference_quotes.py')]])
    f.write(folder / 'bindings.json', f.bindings(paths))
    f.manifest(folder)
    print(json.dumps({k: report[k] for k in ('case_count', 'counts', 'unchanged_Nambu_Peng_preparations', 'model_calls')}))


if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main()
