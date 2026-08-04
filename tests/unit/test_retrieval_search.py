from __future__ import annotations

import uuid
from types import SimpleNamespace

import numpy as np
import pytest

from app.retrieval.search import (
    SearchFilters,
    SearchGroup,
    SearchResponse,
    SearchResult,
    _query_terms,
    exact_search,
    hybrid_search,
    make_snippet,
    normalize_retrieval_method,
    search_chunks,
    search_response_to_dict,
    semantic_search,
)
from app.retrieval.vector_index import LoadedVectorIndex


class FakeSession:
    def __init__(self, collection: object | None = None) -> None:
        self.collection = collection
        self.rows: list[tuple[object, object, int]] = []

    def scalar(self, statement: object) -> object | None:
        return self.collection

    def execute(self, statement: object) -> object:
        return SimpleNamespace(all=lambda: self.rows)


def test_exact_search_returns_source_linked_chunks() -> None:
    collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
    article = SimpleNamespace(id=uuid.uuid4(), title="Li-Nafion paper", doi="10.1000/example")
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        article_id=article.id,
        page_start=2,
        page_end=3,
        source_type="method",
        text_layer="original",
        text="Conductivity of Li-Nafion in NMP depends on temperature.",
        chunk_index=0,
    )
    session = FakeSession(collection)
    session.rows = [(chunk, article, 12)]

    response = exact_search(session, "Li-Nafion", "literature", 5)  # type: ignore[arg-type]

    assert response.query == "Li-Nafion"
    assert len(response.results) == 1
    result = response.results[0]
    assert result.article_id == str(article.id)
    assert result.chunk_id == str(chunk.id)
    assert result.page_start == 2
    assert result.page_end == 3
    assert result.source_type == "method"
    assert result.text_layer == "original"
    assert result.retrieval_method == "exact_ilike"
    assert "Li-Nafion" in result.snippet


def test_search_chunks_dispatches_exact_method() -> None:
    collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
    article = SimpleNamespace(id=uuid.uuid4(), title="Li-Nafion paper", doi="10.1000/example")
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        article_id=article.id,
        page_start=2,
        page_end=3,
        source_type="method",
        text_layer="original",
        text="Conductivity of Li-Nafion in NMP depends on temperature.",
        chunk_index=0,
    )
    session = FakeSession(collection)
    session.rows = [(chunk, article, 12)]

    response = search_chunks(session, "Li-Nafion", "literature", 5, method="exact")  # type: ignore[arg-type]

    assert response.results[0].retrieval_method == "exact_ilike"


def test_search_response_serializes_text_layer_and_pdf_urls() -> None:
    result = _search_result(uuid.UUID(int=7), score=1.5, method="exact_ilike")
    response = SearchResponse(query="query", results=[result])

    payload = search_response_to_dict(response)
    serialized = payload["results"][0]

    assert serialized["text_layer"] == "original"
    assert serialized["pdf_url"] == f"/articles/{result.article_id}/pdf?layer=original"
    assert serialized["pdf_page_url"] == f"/articles/{result.article_id}/pdf?layer=original#page=1"
    assert serialized["context_url"] == f"/articles/{result.article_id}/chunks/{result.chunk_id}/context?before=1&after=1"
    assert serialized["page_context_url"] == f"/articles/{result.article_id}/pages/context?page_start=1&page_end=2&layer=selected"


def test_search_filters_normalize_empty_strings_and_reject_mixed_year_filters() -> None:
    filters = SearchFilters.normalize(doi=" 10.1000/example ", source_type=" ", year_from=2010)

    assert filters.doi == "10.1000/example"
    assert filters.source_type is None
    assert filters.as_metadata() == {"doi": "10.1000/example", "year_from": 2010}
    with pytest.raises(ValueError, match="year cannot be combined"):
        SearchFilters.normalize(year=2020, year_to=2024)


def test_search_response_serializes_grouped_results() -> None:
    result_a = _search_result(uuid.UUID(int=1), score=2.0, method="exact_ilike")
    result_b = _search_result(uuid.UUID(int=2), score=1.0, method="exact_ilike")
    group = SearchGroup(
        article_id=result_a.article_id,
        title=result_a.title,
        doi=result_a.doi,
        year=2020,
        journal="Journal",
        best_score=result_a.score,
        best_page_start=result_a.page_start,
        best_page_end=result_a.page_end,
        result_count=1,
        total_result_count=2,
        results=[result_a],
    )

    payload = search_response_to_dict(SearchResponse(query="query", results=[result_b], groups=[group], metadata={"group_by": "article"}))

    assert "results" not in payload
    assert payload["groups"][0]["result_count"] == 1
    assert payload["groups"][0]["total_result_count"] == 2
    assert payload["groups"][0]["results"][0]["chunk_id"] == result_a.chunk_id
    assert payload["groups"][0]["results"][0]["context_url"].endswith("/context?before=1&after=1")


def test_search_chunks_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="Unsupported retrieval method"):
        search_chunks(FakeSession(), "Nafion", method="weighted")  # type: ignore[arg-type]


def test_search_chunks_rejects_top_k_above_configured_limit() -> None:
    with pytest.raises(ValueError, match="top_k must be <= 2"):
        search_chunks(
            FakeSession(),  # type: ignore[arg-type]
            "Nafion",
            top_k=3,
            settings=SimpleNamespace(search_max_top_k=2),
        )


def test_hybrid_search_rejects_candidate_k_above_configured_limit() -> None:
    with pytest.raises(ValueError, match="hybrid candidate_k must be <= 4"):
        hybrid_search(
            FakeSession(),  # type: ignore[arg-type]
            "query",
            top_k=2,
            settings=SimpleNamespace(hybrid_rrf_k=60, hybrid_candidate_multiplier=3, hybrid_max_candidate_k=4),  # type: ignore[arg-type]
        )


def test_normalize_retrieval_method_accepts_exact_case_insensitive() -> None:
    assert normalize_retrieval_method(" Exact ") == "exact"


def test_normalize_retrieval_method_accepts_semantic_case_insensitive() -> None:
    assert normalize_retrieval_method(" Semantic ") == "semantic"


def test_normalize_retrieval_method_accepts_hybrid_case_insensitive() -> None:
    assert normalize_retrieval_method(" Hybrid ") == "hybrid"


def test_hybrid_search_fuses_component_ranks_and_preserves_diagnostics(monkeypatch) -> None:
    result_a = _search_result(uuid.UUID(int=1), score=100.0, method="exact_ilike")
    result_b_exact = _search_result(uuid.UUID(int=2), score=50.0, method="exact_ilike")
    result_b_semantic = _search_result(uuid.UUID(int=2), score=0.9, method="semantic_cosine")
    result_c = _search_result(uuid.UUID(int=3), score=0.8, method="semantic_cosine")

    def fake_exact(session, query, collection_name, top_k, source_type=None, filters=None):
        assert top_k == 10
        assert filters.source_type == "method"
        return SearchResponse(query=query, results=[result_a, result_b_exact])

    def fake_semantic(
        session,
        query,
        collection_name,
        top_k,
        source_type=None,
        filters=None,
        *,
        settings=None,
        enforce_top_k_limit=True,
    ):
        assert top_k == 10
        assert filters.source_type == "method"
        assert enforce_top_k_limit is False
        return SearchResponse(
            query=query,
            results=[result_b_semantic, result_c],
            metadata={"embedding_model": "test/model", "manifest_sha256": "abc"},
        )

    monkeypatch.setattr("app.retrieval.search.exact_search", fake_exact)
    monkeypatch.setattr("app.retrieval.search.semantic_search", fake_semantic)
    settings = SimpleNamespace(hybrid_rrf_k=60, hybrid_candidate_multiplier=5)

    response = hybrid_search(
        FakeSession(),  # type: ignore[arg-type]
        "query",
        top_k=2,
        source_type="method",
        settings=settings,  # type: ignore[arg-type]
    )

    assert [result.chunk_id for result in response.results] == [str(uuid.UUID(int=2)), str(uuid.UUID(int=1))]
    assert response.results[0].score == pytest.approx((1 / 62) + (1 / 61))
    assert response.results[0].method_ranks == {"exact_ilike": 2, "semantic_cosine": 1}
    assert response.results[0].method_scores == {"exact_ilike": 50.0, "semantic_cosine": 0.9}
    assert response.results[1].method_ranks == {"exact_ilike": 1}
    assert response.metadata["fusion"] == "reciprocal_rank_fusion"
    assert response.metadata["candidate_k"] == 10


def test_hybrid_search_prefers_exact_result_when_single_method_rrf_scores_tie(monkeypatch) -> None:
    exact_result = _search_result(uuid.UUID(int=2), score=20.0, method="exact_ilike")
    semantic_result = _search_result(uuid.UUID(int=1), score=0.8, method="semantic_cosine")
    monkeypatch.setattr(
        "app.retrieval.search.exact_search",
        lambda *args, **kwargs: SearchResponse(query="query", results=[exact_result]),
    )
    monkeypatch.setattr(
        "app.retrieval.search.semantic_search",
        lambda *args, **kwargs: SearchResponse(query="query", results=[semantic_result]),
    )

    response = hybrid_search(
        FakeSession(),  # type: ignore[arg-type]
        "query",
        top_k=2,
        settings=SimpleNamespace(hybrid_rrf_k=60, hybrid_candidate_multiplier=5),  # type: ignore[arg-type]
    )

    assert [result.chunk_id for result in response.results] == [exact_result.chunk_id, semantic_result.chunk_id]


def test_hybrid_search_does_not_fall_back_when_semantic_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.retrieval.search.exact_search",
        lambda *args, **kwargs: SearchResponse(query="query", results=[]),
    )

    def fail_semantic(*args, **kwargs):
        raise ValueError("Invalid local vector index")

    monkeypatch.setattr("app.retrieval.search.semantic_search", fail_semantic)

    with pytest.raises(ValueError, match="Invalid local vector index"):
        hybrid_search(
            FakeSession(),  # type: ignore[arg-type]
            "query",
            settings=SimpleNamespace(hybrid_rrf_k=60, hybrid_candidate_multiplier=5),  # type: ignore[arg-type]
        )


def test_semantic_search_ranks_cosine_similarity_and_preserves_evidence() -> None:
    index, chunks = _semantic_index()

    response = semantic_search(
        FakeSession(),  # type: ignore[arg-type]
        "conductivity without exact terms",
        top_k=2,
        settings=SimpleNamespace(embedding_model="test/model", data_root=None),  # type: ignore[arg-type]
        loaded_index=index,
        query_embedder=lambda query, model: [0.9, 0.1],
    )

    assert [result.chunk_id for result in response.results] == [str(chunks[0].id), str(chunks[1].id)]
    assert response.results[0].retrieval_method == "semantic_cosine"
    assert response.results[0].page_start == 2
    assert response.results[0].source_type == "body"
    assert response.results[0].snippet
    assert response.metadata["embedding_model"] == "test/model"
    assert response.metadata["manifest_sha256"] == "manifest-checksum"


def test_semantic_search_filters_source_type_before_top_k() -> None:
    index, chunks = _semantic_index()

    response = semantic_search(
        FakeSession(),  # type: ignore[arg-type]
        "method evidence",
        top_k=1,
        source_type="method",
        settings=SimpleNamespace(embedding_model="test/model", data_root=None),  # type: ignore[arg-type]
        loaded_index=index,
        query_embedder=lambda query, model: [1.0, 0.0],
    )

    assert [result.chunk_id for result in response.results] == [str(chunks[1].id)]


def test_semantic_search_filters_doi_before_top_k() -> None:
    index, chunks = _semantic_index()

    response = semantic_search(
        FakeSession(),  # type: ignore[arg-type]
        "doi filtered",
        top_k=1,
        filters=SearchFilters.normalize(doi="10.1000/semantic"),
        settings=SimpleNamespace(embedding_model="test/model", data_root=None),  # type: ignore[arg-type]
        loaded_index=index,
        query_embedder=lambda query, model: [1.0, 0.0],
    )

    assert [result.chunk_id for result in response.results] == [str(chunks[0].id)]


def test_semantic_search_uses_chunk_id_to_break_equal_score_ties() -> None:
    index, chunks = _semantic_index()
    index.embeddings[:] = np.asarray([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)

    response = semantic_search(
        FakeSession(),  # type: ignore[arg-type]
        "equal",
        top_k=2,
        settings=SimpleNamespace(embedding_model="test/model", data_root=None),  # type: ignore[arg-type]
        loaded_index=index,
        query_embedder=lambda query, model: [1.0, 0.0],
    )

    assert [result.chunk_id for result in response.results] == sorted(str(chunk.id) for chunk in chunks)


def test_semantic_search_rejects_query_dimension_mismatch() -> None:
    index, _chunks = _semantic_index()

    with pytest.raises(ValueError, match="dimension mismatch"):
        semantic_search(
            FakeSession(),  # type: ignore[arg-type]
            "query",
            settings=SimpleNamespace(embedding_model="test/model", data_root=None),  # type: ignore[arg-type]
            loaded_index=index,
            query_embedder=lambda query, model: [1.0, 0.0, 0.0],
        )


def test_semantic_search_rejects_zero_query_vector() -> None:
    index, _chunks = _semantic_index()

    with pytest.raises(ValueError, match="zero length"):
        semantic_search(
            FakeSession(),  # type: ignore[arg-type]
            "query",
            settings=SimpleNamespace(embedding_model="test/model", data_root=None),  # type: ignore[arg-type]
            loaded_index=index,
            query_embedder=lambda query, model: [0.0, 0.0],
        )


def test_exact_search_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        exact_search(FakeSession(), "   ")  # type: ignore[arg-type]


def test_exact_search_rejects_unknown_collection() -> None:
    with pytest.raises(ValueError, match="Unknown collection"):
        exact_search(FakeSession(None), "Nafion")  # type: ignore[arg-type]


def test_make_snippet_is_derived_from_chunk_text() -> None:
    snippet = make_snippet("alpha beta gamma Nafion conductivity delta", "Nafion", radius=20)

    assert "Nafion" in snippet
    assert "conductivity" in snippet


def test_make_snippet_supports_russian_query_text() -> None:
    snippet = make_snippet("Мембраны Нафион показывают ионную проводимость после гидратации.", "ионная проводимость", radius=20)

    assert "ионную проводимость" in snippet


def test_make_snippet_falls_back_to_query_terms() -> None:
    snippet = make_snippet(
        "Li-Nafion membranes show conductivity after solvent casting.",
        "Li-Nafion in NMP: conductivity and temperature dependence",
        radius=40,
    )

    assert "Li-Nafion" in snippet
    assert "conductivity" in snippet


def test_query_terms_preserve_scientific_hyphenated_terms() -> None:
    assert _query_terms("Li-Nafion in NMP: conductivity and temperature dependence") == [
        "Li-Nafion",
        "NMP",
        "conductivity",
        "temperature",
        "dependence",
    ]


def test_make_snippet_normalizes_common_pdf_ligatures() -> None:
    snippet = make_snippet("Li-Naﬁon conductivity", "Li-Nafion", radius=20)

    assert "Li-Nafion" in snippet


def _semantic_index() -> tuple[LoadedVectorIndex, list[object]]:
    article = SimpleNamespace(id=uuid.uuid4(), title="Semantic paper", doi="10.1000/semantic")
    chunks = [
        SimpleNamespace(
            id=uuid.UUID(int=1),
            article_id=article.id,
            page_start=2,
            page_end=3,
            source_type="body",
            text_layer="original",
            text="Proton transport increases after hydration.",
            chunk_index=0,
        ),
        SimpleNamespace(
            id=uuid.UUID(int=2),
            article_id=article.id,
            page_start=4,
            page_end=4,
            source_type="method",
            text_layer="ocr",
            text="Conductivity was measured by impedance spectroscopy.",
            chunk_index=1,
        ),
    ]
    chunk_ids = [str(chunk.id) for chunk in chunks]
    return (
        LoadedVectorIndex(
            embeddings=np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
            chunk_ids=chunk_ids,
            rows_by_chunk_id={chunk_id: (chunk, article) for chunk_id, chunk in zip(chunk_ids, chunks, strict=True)},  # type: ignore[dict-item]
            manifest={
                "backend": "local_vector_index",
                "embedding_model": "test/model",
                "embedding_dimension": 2,
                "chunk_count": 2,
            },
            manifest_sha256="manifest-checksum",
        ),
        chunks,
    )


def _search_result(chunk_id: uuid.UUID, *, score: float, method: str) -> SearchResult:
    return SearchResult(
        article_id=str(uuid.UUID(int=100)),
        chunk_id=str(chunk_id),
        title="Hybrid paper",
        doi="10.1000/hybrid",
        year=2020,
        journal="Journal",
        page_start=1,
        page_end=2,
        source_type="method",
        text_layer="original",
        snippet="hybrid evidence",
        score=score,
        retrieval_method=method,
    )
