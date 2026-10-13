from copy import deepcopy

import pytest

from scripts.tac_boundary_review import SCHEMA, review_counts, validate_review
from scripts.tac_review_html import render_table
from tests.unit.test_tac_review_html import fixture


def audit_fixture(tmp_path):
    snapshot, profiles, metadata = fixture(tmp_path)
    page = snapshot['articles'][0]['pages'][0]
    review = {
        'schema': SCHEMA, 'independent': False, 'human_confirmation': 'pending',
        'reviewer': 'assistant_development_audit', 'policy': {'scope': 'Synthetic boundary test'},
        'snapshot_sha256': profiles['snapshot_sha256'], 'profiles_sha256': 'c' * 64,
        'articles': [{
            'article_id': 'synthetic', 'original_pdf_sha256': 'a' * 64,
            'reviewed_pages': [dict(page=1, layer=page['layer'], layer_id=page['layer_id'],
                                    text_sha256=page['text_sha256'], image='render.png', image_sha256='d' * 64)],
            'assessments': {
                k: dict(status='pass' if k == 'T' else 'not_separately_delimited',
                        note='<script>review note</script>',
                        proposals=deepcopy([s for s in profiles['profiles'][0]['sections'] if s['kind'] == k]))
                for k in ('T', 'A', 'C')
            },
        }],
    }
    return snapshot, profiles, metadata, review


@pytest.mark.parametrize('change', ['hash', 'inventory', 'pdf', 'layer', 'proposals', 'pages', 'status', 'note', 'human', 'missing_kind'])
def test_stale_or_inconsistent_annotation_is_rejected(tmp_path, change):
    snapshot, profiles, _, review = audit_fixture(tmp_path)
    record = review['articles'][0]
    if change == 'hash':
        review['profiles_sha256'] = 'e' * 64
    elif change == 'inventory':
        review['articles'].append(deepcopy(record))
    elif change == 'pdf':
        record['original_pdf_sha256'] = 'e' * 64
    elif change == 'layer':
        record['reviewed_pages'][0]['layer_id'] = 'stale'
    elif change == 'proposals':
        record['assessments']['T']['proposals'][0]['quote'] = 'Different title'
    elif change == 'pages':
        record['reviewed_pages'] = []
    elif change == 'status':
        record['assessments']['A']['status'] = 'pass'
    elif change == 'note':
        record['assessments']['T']['note'] = ''
    elif change == 'human':
        review['human_confirmation'] = 'accepted'
    elif change == 'missing_kind':
        del record['assessments']['C']
    with pytest.raises(ValueError, match='Boundary review'):
        validate_review(snapshot, profiles, review, 'c' * 64)


def test_counts_keep_structural_exclusions_in_raw_denominator(tmp_path):
    snapshot, profiles, _, review = audit_fixture(tmp_path)
    validate_review(snapshot, profiles, review, 'c' * 64)
    counts = review_counts(review)
    assert counts['slots'] == 3 and counts['applicable_slots'] == 1
    assert counts['total'] == {'pass': 1, 'not_separately_delimited': 2}
    assert counts['independent'] is False


def test_review_badges_are_escaped_and_do_not_repair_algorithm_text(tmp_path):
    snapshot, profiles, metadata, review = audit_fixture(tmp_path)
    before = deepcopy(profiles)
    review['articles'][0]['assessments']['T']['status'] = 'boundary_error'
    result = render_table(snapshot, profiles, metadata, tmp_path, 'c' * 64,
                          boundary_review=review, boundary_review_sha256='f' * 64)
    assert profiles == before
    assert result.count('class="boundary-review ') == 3
    assert '&lt;script&gt;review note&lt;/script&gt;' in result
    assert '<script>review note</script>' not in result
    assert 'Ошибка границ' in result and 'data-problems="true"' in result
    assert 'id="issues"' in result and 'f' * 64 in result
    assert (tmp_path / 'render.png').as_uri() in result
    assert 'A title &lt;script&gt;alert(1)&lt;/script&gt;' in result


def test_missing_and_structural_assessments_cannot_hide_existing_proposal(tmp_path):
    snapshot, profiles, _, review = audit_fixture(tmp_path)
    for status in ('missed', 'not_separately_delimited'):
        review['articles'][0]['assessments']['T']['status'] = status
        with pytest.raises(ValueError, match='conflicts with proposal'):
            validate_review(snapshot, profiles, review, 'c' * 64)
