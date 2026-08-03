from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import main
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
    ) -> SearchResponse:
        assert query == "Nafion"
        assert collection_name == "literature"
        assert top_k == 3
        assert method == "exact"
        assert source_type == "method"
        return SearchResponse(query=query, results=[])

    monkeypatch.setattr(main, "search_chunks", fake_search_chunks)

    assert main.search(object(), q="Nafion", top_k=3, source_type="method", method="exact") == {"query": "Nafion", "results": []}


def test_search_endpoint_rejects_unknown_method() -> None:
    with pytest.raises(HTTPException) as exc_info:
        main.search(object(), q="Nafion", method="semantic")

    assert exc_info.value.status_code == 400
    assert "Unsupported retrieval method" in str(exc_info.value.detail)
