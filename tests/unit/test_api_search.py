from __future__ import annotations

from app import main
from app.retrieval.search import SearchResponse


def test_search_endpoint_returns_exact_results(monkeypatch) -> None:
    def fake_exact_search(session: object, query: str, collection_name: str, top_k: int) -> SearchResponse:
        assert query == "Nafion"
        assert collection_name == "literature"
        assert top_k == 3
        return SearchResponse(query=query, results=[])

    monkeypatch.setattr(main, "exact_search", fake_exact_search)

    assert main.search(object(), q="Nafion", top_k=3) == {"query": "Nafion", "results": []}
