"""Source mapping and controls for an offline diagnostic, not semantic admission."""

from types import SimpleNamespace

import pytest

from app.generation.evidence_adequacy import LIGATURES, assess_evidence_adequacy
from scripts.review_kim_retrieval_audit import raw_hits
from scripts.run_kim_retrieval_audit import article_presence


@pytest.mark.parametrize(('text', 'term', 'spans'), [
    ('xx Naﬁon yy Nafion', 'nafion', [(3, 8), (12, 18)]),
    ('ﬃ and ﬄ', 'ffi', [(0, 1)]),
    ('Как меняется', 'морфология', []),
    ('xx ЧАСТИЦ yy', 'частиц', [(3, 9)]),
])
def test_normalized_matches_have_exact_raw_spans(text, term, spans):
    hits = raw_hits(text, term)
    assert [(hit['start'], hit['end']) for hit in hits] == spans
    for hit in hits:
        assert hit['exact_text'] == text[hit['start']:hit['end']]
        assert term in hit['exact_text'].lower().translate(LIGATURES)


def test_article_membership_does_not_filter_by_page_or_claim_source():
    rows = [dict(article_id=article, chunk_id=str(i), page_start=i + 1, page_end=i + 1)
            for i, article in enumerate(('other', 'target', 'target'))]
    assert [hit['rank'] for hit in article_presence(rows, 'target')] == [2, 3]
    assert article_presence(rows, 'missing') == []


@pytest.mark.parametrize('term', ['', '  '])
def test_empty_terms_do_not_create_false_source_hits(term):
    with pytest.raises(ValueError, match='Nonblank'):
        raw_hits('not an exact anchor', term)


@pytest.mark.parametrize('text', [
    'Вопрос о том, как меняется поведение дисперсии Nafion в зависимости от природы растворителя, '
    'здесь обсуждается только через температуру разложения мембран.',
    'Морфология частиц дисперсии Nafion в зависимости от природы растворителя не исследована.',
    'Как меняется морфология частиц дисперсии Nafion в зависимости от природы растворителя?',
])
def test_current_gate_admission_of_non_answers_remains_explicit(text):
    # Exposes current behavior; does not endorse it as scientific adequacy.
    question = 'Как меняется морфология частиц дисперсии Nafion в зависимости от природы растворителя?'
    result = assess_evidence_adequacy(question, [SimpleNamespace(text=text)])
    assert result.adequate
    assert result.required_concepts.required == []
    assert result.relation_requirements['required'] == []
