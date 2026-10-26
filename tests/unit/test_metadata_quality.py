"""Evaluation failures remain visible; agreement is not scientific confirmation."""

from copy import deepcopy
from pathlib import Path

import pytest

from app.records.schema import text_hash
from app.records.sources import file_hash
from scripts import metadata_quality as quality


def fixture():
    text = 'Alice Smith, Bob Jones\nExample Journal 2024\n'
    region = {'page_number': 1, 'page_text': text, 'page_text_sha256': text_hash(text)}
    snapshot = {'algorithm': {'algorithm': 'test'}, 'articles': [{'article_id': 'one', 'sources': {'regions': [region]}}]}
    evidence = {'page': 1, 'start': 0, 'end': len(text), 'quote': text, 'page_text_sha256': text_hash(text)}
    refs = {'origin': 'assistant_source_annotation_before_new_predictions', 'independent_human_confirmation': False,
        'articles': [{'article_id': 'one', 'fields': {f: {'status': 'known', 'accepted_values': [v],
            'evidence': [deepcopy(evidence)], 'rationale': 'Printed source byline or citation.'}
            for f, v in zip(quality.FIELDS, (['Alice Smith', 'Bob Jones'], 2024, 'Example Journal'), strict=True)}}]}
    return snapshot, refs


def test_valid_references_cover_exact_sources_and_all_fields():
    quality.validate_references(*fixture())


@pytest.mark.parametrize('variant', ['missing', 'duplicate', 'extra', 'field', 'human', 'empty', 'quote', 'hash', 'offset', 'page', 'type'])
def test_reference_scope_origin_types_and_evidence_cannot_be_silently_repaired(variant):
    snapshot, refs = fixture()
    row = refs['articles'][0]
    year = row['fields']['year']
    if variant == 'missing':
        refs['articles'] = []
    elif variant == 'duplicate':
        refs['articles'].append(deepcopy(row))
    elif variant == 'extra':
        refs['articles'].append({**deepcopy(row), 'article_id': 'other'})
    elif variant == 'field':
        del row['fields']['year']
    elif variant == 'human':
        refs['independent_human_confirmation'] = True
    elif variant == 'empty':
        year['evidence'] = []
    elif variant == 'quote':
        year['evidence'][0]['quote'] = 'different'
    elif variant == 'hash':
        year['evidence'][0]['page_text_sha256'] = '0' * 64
    elif variant == 'offset':
        year['evidence'][0]['start'] = -1
    elif variant == 'page':
        year['evidence'][0]['page'] = 3
    else:
        year['accepted_values'] = [True]
    with pytest.raises(ValueError):
        quality.validate_references(snapshot, refs)


@pytest.mark.parametrize(('value', 'expected'), [
    (['Alice Smith', 'Bob Jones'], 'correct'),
    (['  ALICE Smith', 'Bob\nJones'], 'correct'),
    (['Alice Smith'], 'wrong'),
    (['Bob Jones', 'Alice Smith'], 'wrong'),
    (['Alice Smith', 'Bob Jones', 'Other Person'], 'wrong'),
    (['A. Smith', 'Bob Jones'], 'wrong'),
])
def test_full_byline_comparison_preserves_names_order_and_punctuation(value, expected):
    _, refs = fixture()
    assert quality.compare({'status': 'proposed', 'value': value}, refs['articles'][0]['fields']['authors']) == expected


def test_explicit_prefrozen_alias_is_accepted_without_fuzzy_matching():
    reference = {'status': 'known', 'accepted_values': ['Example Journal', 'Ex. J.']}
    assert quality.compare({'status': 'proposed', 'value': 'EX. J.'}, reference) == 'correct'
    assert quality.compare({'status': 'proposed', 'value': 'Ex J'}, reference) == 'wrong'


@pytest.mark.parametrize(('reference', 'prediction', 'expected'), [
    ('known', 'not_found', 'abstention'), ('known', 'ambiguous', 'abstention'),
    ('known', 'not_applicable', 'wrong_status'),
    ('unknown', 'proposed', 'unscored_proposal_unknown'), ('unknown', 'not_found', 'unknown_reference'),
    ('ambiguous', 'proposed', 'ambiguous_reference_unscored'),
    ('not_applicable', 'proposed', 'wrong_not_applicable_status'),
    ('not_applicable', 'not_found', 'wrong_not_applicable_status'),
    ('not_applicable', 'not_applicable', 'correct_not_applicable'),
])
def test_unknown_references_do_not_become_successes_or_false_errors(reference, prediction, expected):
    assert quality.compare({'status': prediction, 'value': 2024},
        {'status': reference, 'accepted_values': [2024] if reference == 'known' else []}) == expected


def test_summary_distinguishes_proposal_agreement_coverage_and_abstention():
    rows = [{'comparison': dict.fromkeys(quality.FIELDS, outcome),
        'reference': {'fields': {f: {'status': status} for f in quality.FIELDS}}}
        for status, outcome in [('known', 'correct'), ('known', 'wrong'), ('known', 'abstention'),
            ('known', 'wrong_status'), ('unknown', 'unscored_proposal_unknown')]]
    summary = quality.summarize(rows)
    for value in summary['fields'].values():
        assert value['correct_over_known'] == {'numerator': 1, 'denominator': 4}
        assert value['correct_over_proposed_on_known'] == {'numerator': 1, 'denominator': 2}
    assert summary['independent_human_confirmation'] is False


def test_capture_and_reference_drift_are_rejected_and_directories_are_exclusive(tmp_path, monkeypatch):
    snapshot, refs = fixture()
    captured, frozen = tmp_path / 'captured', tmp_path / 'frozen'
    quality.save(captured, {'snapshot.json': snapshot}, {}, 'captured_before_references_and_predictions')
    reference_path = tmp_path / 'references.json'
    quality.write(reference_path, refs)
    monkeypatch.setattr(quality, 'CODE', ())
    quality.freeze(captured, reference_path, frozen)
    quality.load(frozen, 'references_frozen_before_predictions')
    with pytest.raises(FileExistsError):
        quality.freeze(captured, reference_path, frozen)
    reference_path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='hash|Hash|SHA|changed|mismatch'):
        quality.load(frozen, 'references_frozen_before_predictions')


def test_code_drift_after_reference_freeze_is_rejected(tmp_path, monkeypatch):
    snapshot, refs = fixture()
    captured, frozen = tmp_path / 'captured', tmp_path / 'frozen'
    code = tmp_path / 'algorithm.py'
    code.write_text('before', encoding='utf-8')
    quality.save(captured, {'snapshot.json': snapshot}, {}, 'captured_before_references_and_predictions')
    reference_path = tmp_path / 'references.json'
    quality.write(reference_path, refs)
    monkeypatch.setattr(quality, 'CODE', (code,))
    quality.freeze(captured, reference_path, frozen)
    code.write_text('after', encoding='utf-8')
    with pytest.raises(ValueError):
        quality.load(frozen, 'references_frozen_before_predictions')


def test_manifest_path_escape_rejected(tmp_path):
    directory = tmp_path / 'capture'
    directory.mkdir()
    quality.write(directory / 'manifest.json', {'version': quality.VERSION, 'phase': 'test',
        'inputs': {}, 'outputs': {'../escape.json': '0' * 64}})
    with pytest.raises(ValueError, match='escapes'):
        quality.load(directory, 'test')


def report_fixture():
    snapshot, refs = fixture()
    ref = refs['articles'][0]
    fields = {f: {'status': 'proposed', 'value': ref['fields'][f]['accepted_values'][0], 'diagnostics': ['<unsafe>']}
        for f in quality.FIELDS}
    return {'algorithm': {'algorithm': 'test'}, 'summary': {}, 'articles': [{**snapshot['articles'][0],
        'title': '<script>alert(1)</script>', 'reference': ref, 'prediction': {'extracted': {'fields': fields}},
        'comparison': dict.fromkeys(quality.FIELDS, 'correct'),
        'sources': {'original_pdf_path': str(Path.cwd() / 'a & b.pdf')},
        'historical_tac': {'sections': [{'kind': 'A', 'quote': '<full abstract>', 'current_source_valid': True}]}}]}


def test_html_escapes_sources_keeps_all_main_columns_and_full_sections():
    rendered = quality.render(report_fixture())
    assert '<script>alert(1)</script>' not in rendered and '&lt;script&gt;alert(1)&lt;/script&gt;' in rendered
    assert '&lt;unsafe&gt;' in rendered and '&lt;full abstract&gt;' in rendered
    assert rendered.count('<tr data-article>') == 1 and 'type="search"' in rendered
    assert 'file:///' in rendered and 'a%20%26%20b.pdf' in rendered
    for name in ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms', 'Original file'):
        assert '<th>' + name + '</th>' in rendered
    assert '<form' not in rendered


def test_offline_exports_are_identical_and_tampered_report_is_rejected(tmp_path):
    original, first, second = [tmp_path / name for name in ('original', 'first', 'second')]
    report = report_fixture()
    quality.save(original, {'report.json': report, 'review.html': quality.render(report)}, {}, 'evaluated_without_database_writes')
    quality.export(original, first)
    quality.export(original, second)
    for name in ('report.json', 'review.html', 'manifest.json'):
        assert file_hash(original / name) == file_hash(first / name) == file_hash(second / name)
    (original / 'report.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError):
        quality.export(original, tmp_path / 'third')


def test_native_pdf_end_to_end_freeze_evaluate_replay_and_source_drift(tmp_path, monkeypatch):
    from tests.unit.test_bibliography_bridge import native

    region = native(tmp_path)
    original_bytes = Path(region.original_pdf_path).read_bytes()
    source = {'article_id': str(region.article_id), 'original_pdf_path': region.original_pdf_path,
        'original_pdf_sha256': region.original_pdf_sha256, 'regions': [region.model_dump(mode='json')],
        'empty_pages': [], 'diagnostics': [], 'profile_sections': []}
    snapshot, refs = fixture()
    snapshot['algorithm'] = quality.implementation()
    snapshot['articles'] = [{'article_id': source['article_id'], 'title': 'Native example',
        'sources': source, 'historical_tac': {'sections': []}}]
    refs['articles'][0]['article_id'] = source['article_id']
    for field in refs['articles'][0]['fields'].values():
        field['evidence'] = [{'page': 1, 'start': 0, 'end': len(region.page_text), 'quote': region.page_text,
            'page_text_sha256': region.page_text_sha256}]
    captured, frozen, evaluated = [tmp_path / name for name in ('captured', 'frozen', 'evaluated')]
    quality.save(captured, {'snapshot.json': snapshot}, {region.original_pdf_path: region.original_pdf_sha256},
        'captured_before_references_and_predictions')
    reference_path = tmp_path / 'references.json'
    quality.write(reference_path, refs)
    monkeypatch.setattr(quality, 'CODE', ())
    quality.freeze(captured, reference_path, frozen)
    summary = quality.evaluate(frozen, evaluated)
    assert all(v['outcomes'] == {'correct': 1} for v in summary['fields'].values())
    quality.export(evaluated, tmp_path / 'export')
    assert (evaluated / 'review.html').read_bytes() == (tmp_path / 'export/review.html').read_bytes()
    assert Path(region.original_pdf_path).read_bytes() == original_bytes
    Path(region.original_pdf_path).write_bytes(b'source drift')
    with pytest.raises(ValueError):
        quality.evaluate(frozen, tmp_path / 'rejected')
