import pytest

from app.evaluation.retrieval import EvaluationQuestion, ExtendedExpectedChunk, _evaluate_question, _result_matches_extended_chunk
from app.retrieval.search import SearchResponse


@pytest.mark.parametrize('text,expected', [('Li-Naﬁon EC/SL conductivity', 'Li-Nafion'), ('Li-Nafion', 'Li-Naﬁon')])
def test_typographic_ligatures_match_without_changing_evidence(text, expected):
    result = {'article_id': 'article', 'chunk_id': 'chunk', 'doi': '10.1/example', 'snippet': ''}
    texts = {'chunk': text}
    gold = ExtendedExpectedChunk(article_doi='10.1/example', text_contains=[expected])
    assert _result_matches_extended_chunk(result, gold, {}, texts)
    assert texts == {'chunk': text}


@pytest.mark.parametrize('text,expected', [('H-Nafion', 'Li-Nafion'), ('cm−1', 'cm1'), ('Li⁺', 'Li+'), ('αLi', 'aLi')])
def test_scientific_distinctions_remain_strict(text, expected):
    result = {'article_id': 'article', 'chunk_id': 'chunk', 'snippet': text}
    assert not _result_matches_extended_chunk(result, ExtendedExpectedChunk(text_contains=[expected]), {})


def test_ligature_matching_preserves_article_constraint():
    result = {'article_id': 'article', 'chunk_id': 'chunk', 'doi': '10.1/wrong', 'snippet': 'Li-Naﬁon'}
    gold = ExtendedExpectedChunk(article_doi='10.1/expected', text_contains=['Li-Nafion'])
    assert not _result_matches_extended_chunk(result, gold, {})


def test_legacy_keywords_use_same_matching_and_keep_original_snippet(monkeypatch):
    payload = [{'article_id': 'article', 'chunk_id': 'chunk', 'doi': '10.1/example',
                'title': 'Example', 'snippet': 'Li-Naﬁon conductivity'}]
    monkeypatch.setattr('app.evaluation.retrieval._result_payloads_from_response', lambda response: payload)
    question = EvaluationQuestion('q', 'Li-Nafion', ['10.1/example'], [], [], ['Li-Nafion'])
    report = _evaluate_question(question, SearchResponse(query='Li-Nafion', results=[]), {})
    assert report['passed']
    assert report['top_result']['snippet'] == 'Li-Naﬁon conductivity'
