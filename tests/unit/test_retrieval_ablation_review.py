"""Prevent an any-article hit from hiding loss of another labelled article."""

import copy

from scripts.retrieval_ablation import ARMS
from scripts.review_retrieval_ablation import compare_case, unpack


def test_partial_expected_article_loss_is_visible_even_when_case_hit_remains_true():
    baseline = {
        'article_label_retention': {'any_expected_article_present': True, 'matching_article_ids': ['a', 'b']},
        'trace': {'retrieval': {'results': [], 'metadata': {'cross_lingual': {'variants': []}}},
                  'evidence': [], 'metadata': {'evidence_adequacy': {'adequate': True}}},
        'channel_calls': {}, 'boundary_status': 'stopped_before_generation',
    }
    values = {arm: copy.deepcopy(baseline) for arm in ARMS}
    values['ligatures']['article_label_retention']['matching_article_ids'] = ['b']
    comparison = compare_case({'id': 'development', 'query': 'question', 'origin': 'constructed'}, values)
    assert not comparison['arms']['ligatures']['existing_positive_article_loss']
    assert comparison['arms']['ligatures']['matching_labelled_article_ids_lost'] == ['a']


def test_packed_source_corruption_is_rejected_without_mutating_capture():
    import pytest

    value = {'stages': [{'results': [{'chunk_id': 'chunk', 'full_text_sha256': 'wrong'}]}]}
    original = copy.deepcopy(value)
    with pytest.raises(ValueError, match='Packed raw source differs'):
        unpack(value, {'chunk': {'full_text': 'actual source'}})
    assert value == original
