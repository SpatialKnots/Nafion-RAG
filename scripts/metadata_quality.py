"""Read-only, source-bound metadata evaluation, separate from runtime extraction."""

from __future__ import annotations

import argparse
import html
import json
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.models import Article, ArticleMetadataExtraction
from app.db.session import SessionLocal
from app.metadata.bibliography import FIELDS, article_values, canonical, extract_registered, front_sources, implementation
from app.records.multi_run import verify_hashes
from app.records.schema import text_hash
from app.records.sources import file_hash, source_region_from_page

VERSION = 'metadata_quality_audit_v0.1'
PROTOCOL = Path('docs/records/metadata_quality_protocol_v0.1.md')
CODE = (Path(__file__), PROTOCOL, Path('tests/unit/test_metadata_quality.py'))


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def write(path: Path, value: Any) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def save(output: Path, files: dict[str, Any], bindings: dict[str, str], phase: str) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        if name.endswith('.html'):
            with (output / name).open('x', encoding='utf-8', newline='\n') as handle:
                handle.write(value)
        else:
            write(output / name, value)
    write(output / 'manifest.json', {'version': VERSION, 'phase': phase, 'inputs': bindings,
        'outputs': {name: file_hash(output / name) for name in files}})


def load(directory: Path, phase: str) -> tuple[dict[str, Any], dict[str, str]]:
    manifest = read(directory / 'manifest.json')
    if manifest['version'] != VERSION or manifest['phase'] != phase:
        raise ValueError('Metadata quality phase/version mismatch')
    bindings = dict(manifest['inputs'])
    for name, checksum in manifest['outputs'].items():
        path = (directory / name).resolve()
        if path.parent != directory.resolve():
            raise ValueError('Metadata quality output path escapes directory')
        bindings[str(path)] = checksum
    bindings[str((directory / 'manifest.json').resolve())] = file_hash(directory / 'manifest.json')
    verify_hashes(bindings)
    return manifest, bindings


def db_state(session: Any) -> dict[str, Any]:
    articles = [{'article_id': str(a.id), 'title': a.title, **article_values(a)}
        for a in session.scalars(select(Article).order_by(Article.id))]
    histories = [{'id': str(r.id), 'article_id': str(r.article_id), 'sequence_no': r.sequence_no,
        'payload_sha256': r.payload_sha256, 'actual_payload_sha256': text_hash(canonical(r.payload))}
        for r in session.scalars(select(ArticleMetadataExtraction).order_by(ArticleMetadataExtraction.sequence_no))]
    return {'article_count': len(articles), 'metadata_history_count': len(histories),
        'article_metadata_sha256': text_hash(canonical(articles)), 'history_sha256': text_hash(canonical(histories))}


def capture(parent: Path, corpus: Path, profiles: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    # Stage35's source/code archive is checked before selecting disjoint articles.
    from app.records.condition_transfer_export import read_frozen

    parent_manifest, _ = read_frozen(parent, 'registered_tac_metadata_v0.1', Path.cwd())
    if parent_manifest['phase'] != 'applied_metadata_proposals':
        raise ValueError('Quality scope requires applied stage35 parent')
    parent_report, snapshot, tac = read(parent / 'report.json'), read(corpus), read(profiles)
    from app.metadata.bibliography import tac_experiment

    tac_experiment.validate_profiles(snapshot, tac, file_hash(corpus))
    excluded = {r['article_id'] for r in parent_report['articles']}
    expected = {r['article_id'] for r in snapshot['articles']}
    if len(excluded) != 10 or len(expected) != 33 or not excluded < expected:
        raise ValueError('Quality scope differs from prospective 33 minus 10 articles')
    historical = {r['article_id']: r for r in tac['profiles']}
    bindings = {str(p.resolve()): file_hash(p) for p in (corpus, profiles, PROTOCOL, parent / 'manifest.json', parent / 'report.json')}
    algorithm = implementation()
    for relative in ('app/metadata/bibliography.py', 'scripts/tac_metadata.py', 'scripts/tac_experiment.py'):
        path = Path(relative).resolve()
        bindings[str(path)] = file_hash(path)
    rows = []
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        articles = list(session.scalars(select(Article).order_by(Article.id)))
        if {str(a.id) for a in articles} != expected:
            raise ValueError('Current article IDs differ from frozen corpus')
        state = db_state(session)
        for article in articles:
            name = str(article.id)
            if name in excluded:
                continue
            sources = front_sources(session, get_settings(), article)
            previous = historical.get(name)
            sections = []
            for section in previous['sections'] if previous else []:
                region = source_region_from_page(session, get_settings(), article.id, section['page'],
                    layer=section['layer'], start=section['start'], end=section['end'],
                    selection_basis='fixed_page', selection_note='Stage36 historical TAC validation only')
                if (region.quote != section['quote'] or str(region.text_layer_id) != section['layer_id']
                        or region.page_text_sha256 != section['page_text_sha256']):
                    raise ValueError('Historical TAC source differs; no silent repair')
                sections.append({**section, 'current_source_valid': True, 'registered_source': region.model_dump(mode='json')})
            for region in sources['regions'] + [s['registered_source'] for s in sections]:
                for prefix in ('original', 'layer'):
                    path, checksum = region[prefix + '_pdf_path'], region[prefix + '_pdf_sha256']
                    if path in bindings and bindings[path] != checksum:
                        raise ValueError('Conflicting quality PDF binding')
                    bindings[path] = checksum
            bindings[sources['original_pdf_path']] = sources['original_pdf_sha256']
            rows.append({'article_id': name, 'title': article.title, 'sources': sources,
                'historical_tac': {'schema': tac['schema'], 'snapshot_sha256': tac['snapshot_sha256'],
                    'state': 'historical_proposals_not_confirmed' if previous else 'not_in_snapshot', 'sections': sections}})
        if db_state(session) != state:
            raise ValueError('Metadata changed during read-only capture')
    snapshot_out = {'version': VERSION, 'algorithm': algorithm, 'excluded_stage35_article_ids': sorted(excluded),
        'database_metadata_before': state, 'articles': rows, 'created_at': datetime.now(UTC).isoformat(),
        'new_predictions_run': False, 'independent_human_confirmation': False}
    save(output, {'snapshot.json': snapshot_out}, bindings, 'captured_before_references_and_predictions')
    return {'articles': len(rows), 'excluded': len(excluded), 'predictions_run': False, 'database': state}


def normalize(value: Any) -> Any:
    if isinstance(value, str):
        return ' '.join(unicodedata.normalize('NFC', value).casefold().split())
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def validate_references(snapshot: dict[str, Any], references: dict[str, Any]) -> None:
    rows = {r['article_id']: r for r in snapshot['articles']}
    annotations = references['articles']
    ids = [r['article_id'] for r in annotations]
    if len(ids) != len(set(ids)) or set(ids) != set(rows):
        raise ValueError('Reference article scope incomplete, duplicate or extra')
    if (references['origin'] != 'assistant_source_annotation_before_new_predictions'
            or references['independent_human_confirmation'] is not False):
        raise ValueError('Reference origin must not claim independent human confirmation')
    for annotation in annotations:
        if set(annotation['fields']) != set(FIELDS):
            raise ValueError('Reference must cover all three fields')
        pages = {r['page_number']: r for r in rows[annotation['article_id']]['sources']['regions']}
        for field, ref in annotation['fields'].items():
            if ref['status'] not in {'known', 'unknown', 'ambiguous', 'not_applicable'}:
                raise ValueError('Unsupported reference state')
            values = ref['accepted_values']
            if ref['status'] in {'known', 'ambiguous'}:
                if not values or (ref['status'] == 'ambiguous' and len(values) < 2):
                    raise ValueError('Known reference needs a value; ambiguity needs alternatives')
                if field == 'year' and ref['status'] == 'known' and len(values) != 1:
                    raise ValueError('Known reference year must have one value')
                for value in values:
                    if field == 'year' and (type(value) is not int or not 1800 <= value <= 2099):
                        raise ValueError('Reference year must be integer')
                    if field == 'journal' and (not isinstance(value, str) or not value.strip()):
                        raise ValueError('Reference journal must be text')
                    if field == 'authors' and (not isinstance(value, list) or not value
                            or any(not isinstance(n, str) or not n.strip() for n in value)):
                        raise ValueError('Reference authors must be complete ordered names')
            elif values:
                raise ValueError('Unknown/not-applicable reference cannot assert a value')
            if not ref['rationale'].strip() or not ref['evidence']:
                raise ValueError('Every reference requires source evidence and rationale')
            for evidence in ref['evidence']:
                page = pages.get(evidence['page'])
                if page is None:
                    raise ValueError('Reference evidence outside captured front pages')
                start, end = evidence['start'], evidence['end']
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(page['page_text']):
                    raise ValueError('Reference span outside source text')
                if page['page_text'][start:end] != evidence['quote'] or page['page_text_sha256'] != evidence['page_text_sha256']:
                    raise ValueError('Reference evidence quote/hash mismatch')


def freeze(captured: Path, reference_path: Path, output: Path) -> dict[str, Any]:
    _, bindings = load(captured, 'captured_before_references_and_predictions')
    snapshot, references = read(captured / 'snapshot.json'), read(reference_path)
    validate_references(snapshot, references)
    bindings[str(reference_path.resolve())] = file_hash(reference_path)
    bindings.update({str(p.resolve()): file_hash(p) for p in CODE})
    for annotation in references['articles']:
        if 'visual_evidence' in annotation:
            visual = annotation['visual_evidence']
            bindings[visual['path']] = visual['sha256']
    for resource in references.get('annotation_resources', []):
        bindings[resource['path']] = resource['sha256']
    save(output, {'references.json': references, 'freeze.json': {'captured': str(captured.resolve()),
        'reference_sha256': file_hash(reference_path), 'created_at': datetime.now(UTC).isoformat(),
        'algorithm': snapshot['algorithm'], 'predictions_run': False}}, bindings, 'references_frozen_before_predictions')
    return {'references': len(references['articles']), 'predictions_run': False}


def compare(prediction: dict[str, Any], reference: dict[str, Any]) -> str:
    state, proposed = reference['status'], prediction['status'] == 'proposed'
    if state == 'unknown':
        return 'unscored_proposal_unknown' if proposed else 'unknown_reference'
    if state == 'ambiguous':
        return 'ambiguous_reference_unscored'
    if state == 'not_applicable':
        return 'correct_not_applicable' if prediction['status'] == 'not_applicable' else 'wrong_not_applicable_status'
    if not proposed:
        return 'wrong_status' if prediction['status'] == 'not_applicable' else 'abstention'
    return 'correct' if any(normalize(prediction['value']) == normalize(v) for v in reference['accepted_values']) else 'wrong'


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {'articles': len(rows), 'fields': {}, 'independent_human_confirmation': False,
        'new_model_retrieval_embedding_requests': 0, 'database_writes': 0}
    for field in FIELDS:
        counts = Counter(r['comparison'][field] for r in rows)
        known = sum(r['reference']['fields'][field]['status'] == 'known' for r in rows)
        correct, wrong = counts['correct'], counts['wrong']
        result['fields'][field] = {'outcomes': dict(sorted(counts.items())), 'known_references': known,
            'correct_over_known': {'numerator': correct, 'denominator': known},
            'correct_over_proposed_on_known': {'numerator': correct, 'denominator': correct + wrong}}
    return result


def render(report: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), quote=True)

    def detail(label: str, value: Any) -> str:
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(value) + '</pre></details>'

    rows = []
    for row in report['articles']:
        sections = row['historical_tac']['sections']
        cells = {}
        for kind in ('T', 'A', 'C'):
            quotes = [s['quote'] for s in sections if s['kind'] == kind and s['current_source_valid']]
            cells[kind] = (detail('Полный исторический текст ' + kind, '\n\n'.join(quotes))
                if quotes else 'Не обнаружено в историческом snapshot')
        metadata = ''
        for field in ('authors', 'journal', 'year'):
            predicted, reference = row['prediction']['extracted']['fields'][field], row['reference']['fields'][field]
            metadata += '<td><strong>' + esc(row['comparison'][field]) + '</strong><p>Алгоритм: ' + esc(predicted['value'])
            metadata += ' (' + esc(predicted['status']) + ')</p><p>Источник: ' + esc(reference['accepted_values']) + ' ('
            metadata += esc(reference['status']) + ')</p>' + detail('Эталон, точные цитаты, объяснение', reference)
            metadata += detail('Предсказание, альтернативы, диагностика', predicted) + '</td>'
        original = Path(row['sources']['original_pdf_path']).resolve().as_uri()
        rows.append('<tr data-article><td>' + esc(row['title'] or 'Название в БД неизвестно') + cells['T'] + '</td>' + metadata
            + '<td>' + cells['A'] + '</td><td>' + cells['C'] + '</td><td>Не пересчитывались; не подтверждены.</td>'
            + '<td><a href="' + esc(original) + '">Оригинальный PDF</a>'
            + detail('Полные источники, версии, исторические TAC', row) + '</td></tr>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: проверка метаданных</title>'
        '<style>body{font:15px system-ui;margin:20px;color:#182b37;background:#fafafa}'
        '.table{overflow:auto}table{border-collapse:collapse;width:100%}th,td{border:1px solid #9aa;'
        'padding:10px;vertical-align:top;min-width:180px}th{background:#dde9ee}pre{white-space:pre-wrap;'
        'overflow-wrap:anywhere;max-height:60vh;overflow:auto}details{margin:8px 0}[hidden]{display:none!important}</style>'
        '<h1>Проверка метаданных по источникам</h1><p>' + VERSION + ' · '
        + esc(report['algorithm']['algorithm']) + '</p>' + detail('Версии и хеши алгоритма', report['algorithm'])
        + '<p>Документов вне scope этапа 35: ' + str(len(report['articles'])) + '. Эталоны: аннотация ассистента '
        'до новых предсказаний; независимой проверки человеком нет. Корпус уже использовался в TAC-разработке.</p>'
        '<p>T/A/C — полные исторические предложения с проверенными текущими источниками. Terms не пересчитывались. '
        'Значения не применялись к БД.</p>' + detail('Итоги и явные знаменатели', report['summary'])
        + '<a href="report.json">Полный JSON</a> · <a href="manifest.json">Manifest</a>'
        '<p><label>Поиск <input id="q" type="search"></label> <output id="count"></output></p>'
        '<div class="table"><table><thead><tr>' + ''.join('<th>' + s + '</th>' for s in
            ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms', 'Original file'))
        + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
        '<script>const q=document.getElementById("q"),rows=[...document.querySelectorAll("[data-article]")];'
        'function filter(){let n=0;for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes('
        'q.value.toLocaleLowerCase());if(!r.hidden)n++}document.getElementById("count").textContent=n+" / "+rows.length}'
        'q.addEventListener("input",filter);filter();</script></html>\n')


def evaluate(frozen: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    _, bindings = load(frozen, 'references_frozen_before_predictions')
    info = read(frozen / 'freeze.json')
    captured = Path(info['captured'])
    _, capture_bindings = load(captured, 'captured_before_references_and_predictions')
    bindings.update(capture_bindings)
    snapshot, references = read(captured / 'snapshot.json'), read(frozen / 'references.json')
    if implementation() != snapshot['algorithm']:
        raise ValueError('Frozen metadata extractor implementation changed')
    validate_references(snapshot, references)
    by_id = {r['article_id']: r for r in references['articles']}
    rows = []
    for row in snapshot['articles']:
        prediction = extract_registered(row['sources'])
        reference = by_id[row['article_id']]
        rows.append({**row, 'prediction': prediction, 'reference': reference,
            'comparison': {f: compare(prediction['extracted']['fields'][f], reference['fields'][f]) for f in FIELDS}})
    report = {'version': VERSION, 'algorithm': snapshot['algorithm'], 'reference_origin': references['origin'],
        'reference_sha256': file_hash(frozen / 'references.json'), 'articles': rows, 'summary': summarize(rows)}
    save(output, {'report.json': report, 'review.html': render(report)}, bindings, 'evaluated_without_database_writes')
    return dict(report['summary'])


def export(captured: Path, output: Path) -> dict[str, Any]:
    _, bindings = load(captured, 'evaluated_without_database_writes')
    # Do not bind the capture's own outputs: repeated exports share the exact inputs.
    manifest = read(captured / 'manifest.json')
    verify_hashes(bindings)
    report = read(captured / 'report.json')
    save(output, {'report.json': report, 'review.html': render(report)}, manifest['inputs'], 'evaluated_without_database_writes')
    return dict(report['summary'])


def verify_database(captured: Path) -> dict[str, Any]:
    load(captured, 'captured_before_references_and_predictions')
    expected = read(captured / 'snapshot.json')['database_metadata_before']
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        actual = db_state(session)
    if actual != expected:
        raise ValueError('Database article metadata/history differs from pre-audit state')
    return {'database_metadata_unchanged': True, **actual}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    c, f, e, x, v = [sub.add_parser(n) for n in ('capture', 'freeze', 'evaluate', 'export', 'verify-database')]
    c.add_argument('--parent', type=Path, default=Path('output/records_stage35_20261022/applied_v01'))
    c.add_argument('--corpus', type=Path, default=Path('data/experiments/tac/20261012_v01/corpus.json'))
    c.add_argument('--profiles', type=Path, default=Path('data/experiments/tac/20261012_stage06/profiles_final.json'))
    f.add_argument('--references', type=Path, required=True)
    for p in (f, x, v):
        p.add_argument('--captured', type=Path, required=True)
    e.add_argument('--frozen', type=Path, required=True)
    for p in (c, f, e, x):
        p.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'capture':
        result = capture(args.parent, args.corpus, args.profiles, args.output_dir)
    elif args.action == 'freeze':
        result = freeze(args.captured, args.references, args.output_dir)
    elif args.action == 'evaluate':
        result = evaluate(args.frozen, args.output_dir)
    elif args.action == 'export':
        result = export(args.captured, args.output_dir)
    else:
        result = verify_database(args.captured)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
