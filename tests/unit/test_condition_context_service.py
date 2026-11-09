"""Actual service/API source delivery; all provider replies here are synthetic."""

from dataclasses import asdict
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.generation import context_completion as context
from app.generation import service
from app.generation.providers import GeneratedClaim, ProviderResult
from app.retrieval.search import SearchResponse, SearchResult
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_condition_context_20261106 import completion_inventory, replay
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE

CURRENT = files.ROOT / "output/structured_answers_20261105/review_v02"


@pytest.fixture(scope="module")
def data():
    return (files.configure(), read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json"))


def test_actual_frozen_channel_service_appends_raw_context_and_keeps_all_old_evidence(data):
    settings, corpus, articles = data
    source = read(CORPUS_BASE / "Q03/boundaries.json")
    before, _ = replay(source, settings, corpus, articles, baseline=True)
    after, calls = replay(source, settings, corpus, articles)
    assert before == read(CURRENT / "Q03_repaired.json")
    assert after["trace"]["evidence"][:-1] == before["trace"]["evidence"]
    assert after["trace"]["retrieval"] == before["trace"]["retrieval"]
    assert after["trace"]["metadata"]["evidence_adequacy"] == before["trace"]["metadata"]["evidence_adequacy"]
    assert len(calls) == 1
    added = after["trace"]["evidence"][-1]
    assert added["text"] == corpus[added["chunk_id"]]["full_text"]
    assert added["citation_id"] == "E6" and "Nafion 115" in added["text"]


@pytest.mark.parametrize("cid", ["Q01", "Q02", "Q04", "Q05"])
def test_outside_scope_current_service_and_native_inputs_unchanged(cid, data):
    settings, corpus, articles = data
    after, calls = replay(read(CORPUS_BASE / cid / "boundaries.json"), settings, corpus, articles)
    assert after == read(CURRENT / f"{cid}_repaired.json")
    assert calls == []


def test_service_passes_library_scope_to_both_search_and_completion(data):
    settings, corpus, articles = data
    baseline = read(CURRENT / "Q03_repaired.json")["trace"]["retrieval"]
    retrieval = SearchResponse(query=baseline["query"], metadata=baseline["metadata"],
                               results=[SearchResult(**r) for r in baseline["results"]])
    library, calls = uuid4(), []

    def load(_s, q, collection, filters, anchor):
        calls.append((collection, filters))
        return []

    class Abstain:
        def generate(self, question, evidence, **kwargs):
            return ProviderResult(False, [], "SYNTHETIC_ABSTENTION", None)

    with patch.object(service, "search_chunks", return_value=retrieval) as search, \
            patch.object(context, "load_context_rows", load):
        result = service.answer_question(None, settings, retrieval.query, collection="limited",
                                         library_source_id=library, provider=Abstain())
    assert search.call_args.kwargs["filters"].library_source_id == library
    assert calls[0][0] == "limited" and calls[0][1].library_source_id == library
    assert result.metadata["condition_context_completion"]["reason"] == "methods_not_resolved"
    assert result.status == "insufficient_evidence"


@pytest.mark.parametrize("abstain", [False, True])
def test_actual_http_and_ui_keep_context_citation_raw_source_and_abstention(data, abstain):
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

    from app import ui
    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation.presentation import capture_sources
    from app.main import app

    settings, corpus, articles = data
    baseline = read(CURRENT / "Q03_repaired.json")["trace"]["retrieval"]
    retrieval = SearchResponse(query=baseline["query"], metadata=baseline["metadata"],
                               results=[SearchResult(**r) for r in baseline["results"]])
    observed = []

    class Synthetic:
        def generate(self, question, evidence, **kwargs):
            observed.extend(evidence)
            return ProviderResult(not abstain, [] if abstain else [GeneratedClaim(
                "Синтетическая проверка доставки контекста, не научный ответ.", [evidence[-1].citation_id])],
                "SYNTHETIC_SOURCE_DELIVERY", None)

    def no_session():
        yield None

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = no_session
    try:
        with patch.object(service, "search_chunks", return_value=retrieval), \
                patch.object(service, "build_answer_provider", return_value=Synthetic()), \
                completion_inventory(corpus, articles), \
                patch.object(Engine, "connect", side_effect=AssertionError("Offline API forbids DB")):
            with TestClient(app) as client:
                response = client.post("/answer", json=read(CORPUS_BASE / "Q03/boundaries.json")["api"])
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ("insufficient_evidence" if abstain else "answered")
    assert len(observed) == 6
    added = observed[-1]
    assert added.text == corpus[added.chunk_id]["full_text"]
    assert body["metadata"]["condition_context_completion"]["added_chunk_ids"] == [added.chunk_id]
    if abstain:
        assert body["claims"] == []
    else:
        citation = next(c for c in body["citations"] if c["citation_id"] == added.citation_id)
        assert citation["article_id"] == added.article_id and citation["page_start"] == added.page_start
        assert citation["pdf_page_url"] and citation["context_url"]
        fragment = ui._answer_payload_panel(body, body["query"], capture_sources(retrieval, observed))
        assert "Nafion 115" in fragment and added.chunk_id in fragment
        assert "Синтетическая проверка" in fragment
        assert asdict(added)["text"] == corpus[added.chunk_id]["full_text"]
