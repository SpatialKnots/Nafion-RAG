from __future__ import annotations

from copy import deepcopy

import pytest

from app.retrieval.search import SearchResponse
from scripts.explicit_reference_retrieval_20261105 import select, tokens


def inventory():
    articles = {"work": {"title": "Smith 2020", "authors": None, "year": None}}
    corpus = {str(i): {"article_id": "work", "chunk_id": str(i), "chunk_index": i, "title": "Smith 2020",
                      "doi": None, "page_start": i + 1, "page_end": i + 1, "source_type": "body",
                      "text_layer": "native", "full_text": text}
              for i, text in enumerate(["Abstract: conductivity of Li₂O.", "References.", "Li₂O conductivity 25 °C."])}
    return corpus, articles


@pytest.mark.parametrize("question", ["Smith (2020)", "Smith and Jones (2020)", "Smith и Jones (2020)",
                                     "Smith & Jones (2020)", "Smith et al. (2020)", "Smith и соавторы (2020)"])
def test_explicit_reference_and_raw_provenance(question):
    corpus, articles = inventory()
    before = deepcopy((corpus, articles))
    baseline = SearchResponse(query=question, results=[], metadata={"baseline": True})
    result, diagnostic = select(question, baseline, corpus, articles, top_k=2)
    assert diagnostic["activated"] is True
    assert diagnostic["bibliographic_identity_verified"] is False
    assert len(result.results) == 2
    assert result.results[0].chunk_id == "0"
    assert all(r.full_text == corpus[r.chunk_id]["full_text"] for r in result.results)
    assert all((r.page_start, r.page_end) == (corpus[r.chunk_id]["page_start"], corpus[r.chunk_id]["page_end"])
               for r in result.results)
    assert (corpus, articles) == before
    assert baseline.results == [] and baseline.metadata == {"baseline": True}


@pytest.mark.parametrize("question,reason", [
    ("Li₂O conductivity?", "no_single_explicit_author_year"),
    ("Smith (2021)", "no_metadata_match"),
    ("Blacksmith (2020)", "no_metadata_match"),
    ("Smith (2020) and Jones (2021)", "no_single_explicit_author_year"),
])
def test_no_silent_activation(question, reason):
    corpus, articles = inventory()
    baseline = SearchResponse(query=question, results=[], metadata={})
    result, diagnostic = select(question, baseline, corpus, articles, top_k=5)
    assert result is baseline and diagnostic["reason"] == reason
    assert not diagnostic["activated"]


def test_body_citation_never_resolves_work():
    corpus, articles = inventory()
    articles["work"]["title"] = "Unrelated work 2020"
    corpus["0"]["full_text"] = "References: Smith (2020)."
    baseline = SearchResponse(query="Smith (2020)", results=[], metadata={})
    result, diagnostic = select(baseline.query, baseline, corpus, articles, top_k=5)
    assert result is baseline and diagnostic["reason"] == "no_metadata_match"


def test_ambiguous_metadata_preserves_baseline():
    corpus, articles = inventory()
    articles["duplicate"] = deepcopy(articles["work"])
    baseline = SearchResponse(query="Smith (2020)", results=[], metadata={})
    result, diagnostic = select(baseline.query, baseline, corpus, articles, top_k=5)
    assert result is baseline and diagnostic["reason"] == "ambiguous_metadata"


def test_empty_source_never_invented():
    _, articles = inventory()
    baseline = SearchResponse(query="Smith (2020)", results=[], metadata={})
    result, diagnostic = select(baseline.query, baseline, {}, articles, top_k=5)
    assert result is baseline and diagnostic["reason"] == "no_usable_source_chunks"


def test_body_token_ranking_excludes_citation_names_and_preserves_conditions():
    corpus, articles = inventory()
    baseline = SearchResponse(query="Smith (2020): Li2O conductivity at 25 °C?", results=[], metadata={})
    result, diagnostic = select(baseline.query, baseline, corpus, articles, top_k=2)
    assert [r.chunk_id for r in result.results] == ["0", "2"]
    assert "smith" not in diagnostic["query_body_tokens"]
    assert "2020" not in diagnostic["query_body_tokens"]
    assert "25 °C" in result.results[1].full_text
    assert tokens("Li₂O") == tokens("Li2O")


def test_author_metadata_and_stable_ties():
    corpus, articles = inventory()
    articles["work"] = {"title": "Oxide layers", "authors": [{"name": "Jane Smith"}], "year": 2020}
    baseline = SearchResponse(query="Smith (2020)", results=[], metadata={})
    one, _ = select(baseline.query, baseline, corpus, articles, top_k=20)
    two, _ = select(baseline.query, baseline, dict(reversed(list(corpus.items()))), articles, top_k=20)
    assert one == two
    assert len(one.results) == 3


def test_invalid_limit_rejected():
    corpus, articles = inventory()
    with pytest.raises(ValueError, match="positive"):
        select("Smith (2020)", SearchResponse(query="q", results=[], metadata={}), corpus, articles, top_k=0)
