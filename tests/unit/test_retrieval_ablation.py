"""Candidate scope, source immutability and exposed-label metric boundaries."""

from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from app.retrieval.cross_lingual import build_query_bundle
from app.retrieval.search import SearchFilters
from scripts.retrieval_ablation import candidate_bundle, label_retention, normalized_search_statement


@pytest.mark.parametrize('query', [
    'Как меняется морфология частиц дисперсии Nafion в зависимости от природы растворителя?',
    'Как природа растворителя влияет на морфологию частиц дисперсии Nafion?',
    'How does solvent nature affect the morphology of particles in a Nafion dispersion?',
    'Nafion dispersed particle shapes in different solvents',
])
def test_generic_particle_query_adds_both_languages_without_reference_outcomes(query):
    baseline = build_query_bundle(query)
    candidate = candidate_bundle(query)
    assert candidate.variants[:len(baseline.variants)] == baseline.variants
    added = candidate.variants[len(baseline.variants):]
    assert [variant.language for variant in added] == ['ru', 'en']
    assert all(variant.source == 'candidate_lexical' for variant in added)
    assert not any(word in ' '.join(v.text for v in added) for word in ('Kim', 'microgel', 'glycerol', 'cylinder', '2.2'))


@pytest.mark.parametrize('query', [
    'Morphology properties Nafion membranes solution casting',
    'Как меняется проводимость частиц дисперсии Nafion в разных растворителях?',
    'Как меняется морфология частиц дисперсии PBI в разных растворителях?',
    'Как меняется морфология мембраны Nafion в разных растворителях?',
    'Nafion particle morphology dispersion',
    'Nafion solvent-dependent membrane morphology',
    'nafion morphology solvent particle',
    'particless morpholog solvent Nafion dispersion',
])
def test_outside_finite_query_scope_keeps_original_bundle(query):
    assert candidate_bundle(query) == build_query_bundle(query)


def test_candidate_sql_preserves_raw_entity_projection_filters_and_limit():
    collection = type('Collection', (), {'id': UUID(int=1)})()
    statement = normalized_search_statement('Nafion % _', collection, 50, SearchFilters(text_layer='original'))
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert 'SELECT chunks.id' in sql
    assert 'replace(' in sql and 'lower(' in sql
    assert set(('ﬁ', 'ﬂ', 'ﬀ', 'ﬃ', 'ﬄ')).issubset(set(compiled.params.values()))
    assert 'original' in compiled.params.values()
    assert 50 in compiled.params.values()
    assert 'UPDATE' not in sql and 'INSERT' not in sql


@pytest.mark.parametrize('expected', [
    {}, {'expected': {'chunks': [{'text_contains': ['source']}]}}, {'answerable': False},
])
def test_unlabelled_or_negative_fixture_never_becomes_positive_or_negative_article_gold(expected):
    assert label_retention(expected, [], {})['any_expected_article_present'] is None


@pytest.mark.parametrize('case', [
    {'expected_article_dois': ['doi']},
    {'expected': {'articles': [{'doi': 'doi'}]}},
    {'expected_article_checksums': ['sha']},
    {'expected_article_titles': ['title']},
])
def test_each_existing_positive_article_identity_is_supported(case):
    rows = [{'article_id': 'id', 'doi': 'doi', 'title': 'title'}]
    result = label_retention(case, rows, {'id': {'original_pdf_sha256': 'sha'}})
    assert result['has_existing_positive_article_label'] and result['any_expected_article_present']
    assert label_retention(case, [], {})['any_expected_article_present'] is False
