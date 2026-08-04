from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import main
from app.generation.providers import GenerationOutputError, GenerationUnavailableError
from app.generation.service import AnswerResponse
from app.retrieval.search import SearchResponse


def test_search_endpoint_returns_exact_results(monkeypatch) -> None:
    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str = "exact",
        source_type: str | None = None,
        settings: object | None = None,
    ) -> SearchResponse:
        assert query == "Nafion"
        assert collection_name == "literature"
        assert top_k == 3
        assert method == "exact"
        assert source_type == "method"
        assert settings is not None
        return SearchResponse(query=query, results=[])

    monkeypatch.setattr(main, "search_chunks", fake_search_chunks)

    assert main.search(object(), q="Nafion", top_k=3, source_type="method", method="exact") == {"query": "Nafion", "results": []}


def test_search_endpoint_rejects_unknown_method() -> None:
    with pytest.raises(HTTPException) as exc_info:
        main.search(object(), q="Nafion", method="weighted")

    assert exc_info.value.status_code == 400
    assert "Unsupported retrieval method" in str(exc_info.value.detail)


def test_search_endpoint_dispatches_semantic_method(monkeypatch) -> None:
    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str = "exact",
        source_type: str | None = None,
        settings: object | None = None,
    ) -> SearchResponse:
        assert method == "semantic"
        assert settings is not None
        return SearchResponse(query=query, results=[], metadata={"embedding_model": "test/model"})

    monkeypatch.setattr(main, "search_chunks", fake_search_chunks)

    payload = main.search(object(), q="proton transport", method="semantic")

    assert payload["metadata"] == {"embedding_model": "test/model"}


def test_search_endpoint_dispatches_hybrid_method(monkeypatch) -> None:
    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str = "exact",
        source_type: str | None = None,
        settings: object | None = None,
    ) -> SearchResponse:
        assert method == "hybrid"
        return SearchResponse(query=query, results=[], metadata={"retrieval_method": "hybrid_rrf"})

    monkeypatch.setattr(main, "search_chunks", fake_search_chunks)

    payload = main.search(object(), q="proton transport", method="hybrid")

    assert payload["metadata"] == {"retrieval_method": "hybrid_rrf"}


def test_answer_endpoint_returns_grounded_response(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "answer_question",
        lambda *args, **kwargs: AnswerResponse(
            query="question",
            status="insufficient_evidence",
            answer=None,
            claims=[],
            citations=[],
            retrieval_method="hybrid",
            generation_provider="extractive",
            generation_model=None,
            metadata={},
        ),
    )

    payload = main.answer(object(), main.AnswerRequest(question="question"))

    assert payload["status"] == "insufficient_evidence"
    assert payload["retrieval_method"] == "hybrid"


@pytest.mark.parametrize(
    ("error", "status_code"),
    [(GenerationUnavailableError("offline"), 503), (GenerationOutputError("invalid"), 502)],
)
def test_answer_endpoint_maps_generation_errors(monkeypatch, error: Exception, status_code: int) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise error

    monkeypatch.setattr(main, "answer_question", fail)

    with pytest.raises(HTTPException) as exc_info:
        main.answer(object(), main.AnswerRequest(question="question"))

    assert exc_info.value.status_code == status_code
