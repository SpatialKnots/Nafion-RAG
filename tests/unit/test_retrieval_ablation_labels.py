"""Nested fixture targets must not disappear from the diagnostic denominator."""

import pytest

from scripts.retrieval_ablation_labels import label_retention


@pytest.mark.parametrize('target', [
    {'checksum': 'sha'}, {'title': '  KNOWN  title '}, {'title_contains': 'KNOWN'}, {'article_id': 'id'},
])
def test_all_nested_repository_identity_types_are_accounted_for(target):
    case = {'id': 'fixture', 'answerable': True, 'expected': {'articles': [target]}}
    rows = [{'article_id': 'id', 'doi': None, 'title': 'Known title'}]
    result = label_retention(case, rows, {'id': {'original_pdf_sha256': 'sha'}})
    assert result['has_existing_positive_article_label']
    assert result['any_expected_article_present'] and result['matching_article_ids'] == ['id']
    assert label_retention(case, [], {})['any_expected_article_present'] is False


def test_unsupported_nested_target_fails_instead_of_silently_shrinking_denominator():
    with pytest.raises(ValueError, match='stable article target'):
        label_retention({'expected': {'articles': [{'unsupported': 'value'}]}}, [], {})


def test_unlabelled_user_question_and_declared_negative_have_no_positive_article_score():
    for case in ({'question': 'user'}, {'answerable': False, 'expected': {'articles': []}}):
        assert label_retention(case, [], {})['any_expected_article_present'] is None


def test_inconsistent_negative_fixture_is_rejected():
    with pytest.raises(ValueError, match='declared negative'):
        label_retention({'answerable': False, 'expected': {'articles': [{'doi': 'doi'}]}}, [], {})
