from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from scripts.tac_experiment import digest, span
from scripts.tac_review_html import render_table
from scripts.tac_terms import VERSION, normalized_view, propose_article, validate_terms
from tests.unit.test_tac_review_html import fixture


def source_profile(text, kind='A'):
    page = {'page': 1, 'text': text, 'text_sha256': digest(text.encode()), 'layer': 'original', 'layer_id': 'test'}
    profile = {'article_id': 'test', 'original_pdf_sha256': 'a' * 64, 'original_pdf_path': 'test.pdf',
               'sections': [asdict(span(page, kind, 0, len(text), 'synthetic'))]}
    return page, profile


def test_ligatures_and_whitespace_map_to_exact_unicode_source():
    text = '  Naﬁon;\n ionic conductivity.'
    page, profile = source_profile(text)
    row = propose_article(profile, [{'alias': 'nafion', 'concept': 'ionomer', 'language': 'en'}], 12)
    assert page['text'] == text
    nafion = next(t for t in row['terms'] if t['term'] == 'nafion')
    assert nafion['label'] == 'Nafion'
    assert nafion['evidence'][0]['quote'] == 'Naﬁon'
    for term in row['terms']:
        for e in term['evidence']:
            assert text[e['start']:e['end']] == e['quote']
            assert normalized_view(e['quote'])[0] == term['term']


def test_only_TAC_text_is_used_not_filename_or_external_synonym():
    _, profile = source_profile('Ionic conductivity in EC.')
    profile['metadata_title'] = 'Sulfolane swelling Nafion filename'
    row = propose_article(profile, [dict(alias='ionic conductivity', concept='transport', language='en')], 12)
    assert 'ionic conductivity' in {t['term'] for t in row['terms']}
    assert not any('sulfolane' in t['term'] or 'набухание' in t['term'] for t in row['terms'])
    assert all(e['kind'] == 'A' for t in row['terms'] for e in t['evidence'])


def test_formula_case_and_decimal_indices_are_preserved():
    _, profile = source_profile('LiNi0.5Co0.2Mn0.3O2 electrodes; LiCoO2 cathode. PFSA membranes.')
    row = propose_article(profile, [], 12)
    assert any('LiNi0.5Co0.2Mn0.3O2' in t['label'] for t in row['terms'])
    assert any('LiCoO2' in t['label'] for t in row['terms'])
    assert not any(t['term'] == 'lini0' for t in row['terms'])


def test_reporting_prose_units_and_broken_fragments_do_not_become_keywords():
    _, profile = source_profile('We showed ionic conduc-\ntivity at 5 mA cm−2.\nПолучены мем-\nбраны. Сделан вывод.')
    row = propose_article(profile, [], 12)
    assert not any('браны' in t['term'] or 'tivity' in t['term'] or 'cm' in t['term'] for t in row['terms'])
    assert not any('вывод' in t['term'] or 'showed' in t['term'] for t in row['terms'])


def test_plural_scientific_phrase_and_boundaries_do_not_cross_sentences():
    _, profile = source_profile('Secondary lithium batteries. Ionic conductivity; solvent swelling.')
    row = propose_article(profile, [], 12)
    assert any(t['term'] == 'secondary lithium batteries' for t in row['terms'])
    assert not any('batteries ionic' in t['term'] for t in row['terms'])


def test_empty_and_small_scope_have_explicit_diagnostics_and_deterministic_limit():
    _, profile = source_profile('The study was conducted. 2026 12 33.')
    empty = propose_article(profile, [], 12)
    assert empty['terms'] == [] and empty['status'] == 'not_detected'
    _, profile = source_profile('Nafion membranes. Ionic conductivity. Lithium batteries.', 'T')
    original = deepcopy(profile)
    first = propose_article(profile, [], 2)
    assert first == propose_article(profile, [], 2) and len(first['terms']) == 2
    assert first['candidate_count'] > 2 and profile == original
    with pytest.raises(ValueError, match='max_terms'):
        propose_article(profile, [], 0)


def terms_fixture(tmp_path: Path):
    snapshot, profiles, metadata = fixture(tmp_path)
    profile = profiles['profiles'][0]
    profile['sections'][0]['quote'] = 'Nafion membranes'
    page = snapshot['articles'][0]['pages'][0]
    page['text'] = 'Nafion membranes\nOnly body sulfolane.'
    page['text_sha256'] = digest(page['text'].encode())
    profile['sections'] = [asdict(span(page, 'T', 0, len('Nafion membranes'), 'synthetic'))]
    rows = [propose_article(profile, [], 12)]
    terms = {'schema': VERSION, 'state': 'proposed_for_article_review', 'snapshot_sha256': profiles['snapshot_sha256'],
             'profiles_sha256': 'c' * 64, 'glossary_sha256': 'd' * 64, 'settings': {'max_terms': 12}, 'articles': rows}
    return snapshot, profiles, metadata, terms


@pytest.mark.parametrize('mutation', ['hash', 'inventory', 'offset', 'quote', 'body', 'label', 'acceptance', 'limit', 'layer'])
def test_terms_reject_stale_inputs_or_broken_source_identity(tmp_path, mutation):
    snapshot, profiles, _, terms = terms_fixture(tmp_path)
    term = terms['articles'][0]['terms'][0]
    e = term['evidence'][0]
    if mutation == 'hash':
        terms['profiles_sha256'] = 'e' * 64
    elif mutation == 'inventory':
        terms['articles'].append(deepcopy(terms['articles'][0]))
    elif mutation == 'offset':
        e['start'] += 1
    elif mutation == 'quote':
        e['quote'] = 'Invented evidence'
    elif mutation == 'body':
        e['end'] = len(snapshot['articles'][0]['pages'][0]['text'])
    elif mutation == 'label':
        term['label'] = 'Different formula'
    elif mutation == 'acceptance':
        term['status'] = 'accepted'
    elif mutation == 'limit':
        terms['settings']['max_terms'] = 0
    elif mutation == 'layer':
        e['layer_id'] = 'other-layer'
    with pytest.raises(ValueError, match='[Tt]erm'):
        validate_terms(snapshot, profiles, terms, 'c' * 64)


def test_optional_terms_HTML_contains_all_evidence_and_preserves_existing_columns(tmp_path):
    snapshot, profiles, metadata, terms = terms_fixture(tmp_path)
    validate_terms(snapshot, profiles, terms, 'c' * 64)
    result = render_table(snapshot, profiles, metadata, tmp_path, 'c' * 64, terms=terms, terms_sha256='f' * 64)
    assert 'Кандидаты (' in result and 'Nafion membranes' in result
    assert result.count('<th>') == 8 and 'Terms ещё не извлекаются' not in result
    assert 'научное подтверждение не выполнено' in result and 'f' * 64 in result
    assert 'class="term-quote"' in result and '#page=1' in result
    assert 'Only body sulfolane' not in result
