from __future__ import annotations

from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

from app import main
from app.documents.context import ChunkContext, ChunkContextItem, ContextNotFoundError, PageRangeContext
from app.documents.service import PageEvidence, ResolvedPdf
from app.generation.providers import GenerationOutputError, GenerationUnavailableError
from app.generation.service import AnswerResponse
from app.retrieval.search import SearchFilters, SearchResponse
from app.retrieval.vector_index import VectorIndexUnavailableError


def test_search_endpoint_returns_exact_results(monkeypatch) -> None:
    library_id = main.UUID("66666666-6666-6666-6666-666666666666")

    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str = "exact",
        source_type: str | None = None,
        filters: object | None = None,
        group_by: str = "none",
        chunks_per_article: int | None = None,
        settings: object | None = None,
    ) -> SearchResponse:
        assert query == "Nafion"
        assert collection_name == "literature"
        assert top_k == 3
        assert method == "exact"
        assert cast(SearchFilters, filters).source_type == "method"
        assert cast(SearchFilters, filters).library_source_id == library_id
        assert group_by == "none"
        assert chunks_per_article is None
        assert settings is not None
        return SearchResponse(query=query, results=[])

    monkeypatch.setattr(main, "search_chunks", fake_search_chunks)

    assert main.search(object(), q="Nafion", top_k=3, source_type="method", method="exact", library_source_id=library_id) == {
        "query": "Nafion",
        "results": [],
    }


def test_search_endpoint_rejects_unknown_method() -> None:
    with pytest.raises(HTTPException) as exc_info:
        main.search(object(), q="Nafion", method="weighted")

    assert exc_info.value.status_code == 400
    assert "Unsupported retrieval method" in str(exc_info.value.detail)


def test_search_endpoint_rejects_top_k_above_configured_limit(monkeypatch) -> None:
    monkeypatch.setattr(main, "get_settings", lambda: object_with(search_max_top_k=2))

    with pytest.raises(HTTPException) as exc_info:
        main.search(object(), q="Nafion", top_k=3)

    assert exc_info.value.status_code == 400
    assert "top_k must be <= 2" in str(exc_info.value.detail)


def test_search_endpoint_dispatches_semantic_method(monkeypatch) -> None:
    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str = "exact",
        source_type: str | None = None,
        filters: object | None = None,
        group_by: str = "none",
        chunks_per_article: int | None = None,
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
        filters: object | None = None,
        group_by: str = "none",
        chunks_per_article: int | None = None,
        settings: object | None = None,
    ) -> SearchResponse:
        assert method == "hybrid"
        return SearchResponse(query=query, results=[], metadata={"retrieval_method": "hybrid_rrf"})

    monkeypatch.setattr(main, "search_chunks", fake_search_chunks)

    payload = main.search(object(), q="proton transport", method="hybrid")

    assert payload["metadata"] == {"retrieval_method": "hybrid_rrf"}


def test_search_endpoint_maps_vector_index_unavailable_to_503(monkeypatch) -> None:
    def fail_search(*args: object, **kwargs: object) -> object:
        raise VectorIndexUnavailableError("Vector index is unavailable for collection 'literature'")

    monkeypatch.setattr(main, "search_chunks", fail_search)

    with pytest.raises(HTTPException) as exc_info:
        main.search(object(), q="proton transport", method="semantic")

    assert exc_info.value.status_code == 503
    assert "Vector index is unavailable" in str(exc_info.value.detail)


def test_pdf_endpoint_returns_inline_file_response(monkeypatch, tmp_path) -> None:
    article = object()
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(main, "_get_article_or_404", lambda session, article_id: article)
    monkeypatch.setattr(
        main,
        "resolve_article_pdf",
        lambda article_arg, settings, layer: ResolvedPdf(
            path=pdf_path,
            layer=layer,
            media_type="application/pdf",
            download_name="source_original.pdf",
        ),
        raising=False,
    )

    response = main.article_pdf(object(), main.UUID("11111111-1111-1111-1111-111111111111"))

    assert isinstance(response, FileResponse)
    assert response.media_type == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "inline" in response.headers["content-disposition"]


def test_pdf_endpoint_maps_missing_pdf_to_404(monkeypatch) -> None:
    monkeypatch.setattr(main, "_get_article_or_404", lambda session, article_id: object())

    def fail(*args: object, **kwargs: object) -> object:
        raise main.PdfNotFoundError("PDF file is unavailable")

    monkeypatch.setattr(main, "resolve_article_pdf", fail)

    with pytest.raises(HTTPException) as exc_info:
        main.article_pdf(object(), main.UUID("11111111-1111-1111-1111-111111111111"))

    assert exc_info.value.status_code == 404


def test_page_endpoint_returns_stored_page_evidence(monkeypatch) -> None:
    monkeypatch.setattr(main, "_get_article_or_404", lambda session, article_id: object())
    monkeypatch.setattr(
        main,
        "get_article_page",
        lambda *args, **kwargs: PageEvidence(
            article_id="11111111-1111-1111-1111-111111111111",
            title="Article title",
            page_number=7,
            requested_layer="selected",
            resolved_layer="ocr",
            has_usable_text=True,
            text="Exact stored page text",
            pdf_url="/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original",
            pdf_page_url="/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original#page=7",
            layer_pdf_url="/articles/11111111-1111-1111-1111-111111111111/pdf?layer=ocr",
        ),
        raising=False,
    )

    payload = main.article_page_text(object(), main.UUID("11111111-1111-1111-1111-111111111111"), 7)

    assert payload["text"] == "Exact stored page text"
    assert payload["resolved_layer"] == "ocr"
    assert payload["pdf_page_url"] == "/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original#page=7"
    assert payload["layer_pdf_url"] == "/articles/11111111-1111-1111-1111-111111111111/pdf?layer=ocr"


def test_chunk_context_endpoint_returns_context(monkeypatch) -> None:
    monkeypatch.setattr(main, "_get_article_or_404", lambda session, article_id: object())
    monkeypatch.setattr(
        main,
        "get_chunk_context",
        lambda *args, **kwargs: ChunkContext(
            article_id="11111111-1111-1111-1111-111111111111",
            chunk_id="22222222-2222-2222-2222-222222222222",
            title="Article title",
            doi="10.1000/example",
            requested_chunk_index=1,
            chunks=[
                ChunkContextItem(
                    chunk_id="22222222-2222-2222-2222-222222222222",
                    chunk_index=1,
                    role="requested",
                    page_start=2,
                    page_end=2,
                    source_type="method",
                    text_layer="original",
                    text="Nafion context",
                    highlights=[],
                )
            ],
            pdf_url="/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original",
            pdf_page_url="/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original#page=2",
            truncated=False,
        ),
    )

    payload = main.article_chunk_context(
        object(),
        main.UUID("11111111-1111-1111-1111-111111111111"),
        main.UUID("22222222-2222-2222-2222-222222222222"),
    )

    assert payload["requested_chunk_index"] == 1
    assert payload["chunks"][0]["text"] == "Nafion context"
    assert payload["pdf_page_url"].endswith("#page=2")


def test_chunk_context_endpoint_maps_missing_chunk_to_404(monkeypatch) -> None:
    monkeypatch.setattr(main, "_get_article_or_404", lambda session, article_id: object())
    monkeypatch.setattr(main, "get_chunk_context", lambda *args, **kwargs: (_ for _ in ()).throw(ContextNotFoundError("missing")))

    with pytest.raises(HTTPException) as exc_info:
        main.article_chunk_context(
            object(),
            main.UUID("11111111-1111-1111-1111-111111111111"),
            main.UUID("22222222-2222-2222-2222-222222222222"),
        )

    assert exc_info.value.status_code == 404


def test_page_range_context_endpoint_returns_pages(monkeypatch) -> None:
    monkeypatch.setattr(main, "_get_article_or_404", lambda session, article_id: object())
    monkeypatch.setattr(
        main,
        "get_page_range_context",
        lambda *args, **kwargs: PageRangeContext(
            article_id="11111111-1111-1111-1111-111111111111",
            title="Article title",
            layer="selected",
            page_start=2,
            page_end=3,
            pages=[],
            pdf_url="/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original",
            pdf_page_url="/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original#page=2",
            truncated=False,
        ),
    )

    payload = main.article_page_range_context(
        object(),
        main.UUID("11111111-1111-1111-1111-111111111111"),
        page_start=2,
        page_end=3,
    )

    assert payload["page_start"] == 2
    assert payload["page_end"] == 3
    assert payload["pdf_page_url"].endswith("#page=2")


def test_answer_endpoint_returns_grounded_response(monkeypatch) -> None:
    captured_kwargs = {}
    library_id = main.UUID("66666666-6666-6666-6666-666666666666")

    def fake_answer_question(*args: object, **kwargs: object) -> AnswerResponse:
        captured_kwargs.update(kwargs)
        return AnswerResponse(
            query="question",
            status="insufficient_evidence",
            answer=None,
            claims=[],
            citations=[],
            retrieval_method="hybrid_cross_lingual",
            generation_provider="openai",
            generation_model=None,
            metadata={},
        )

    monkeypatch.setattr(
        main,
        "answer_question",
        fake_answer_question,
    )

    payload = main.answer(
        object(),
        main.AnswerRequest(question="question", answer_style="mini_review", library_source_id=library_id),
    )

    assert payload["status"] == "insufficient_evidence"
    assert payload["retrieval_method"] == "hybrid_cross_lingual"
    assert captured_kwargs["method"] == "hybrid_cross_lingual"
    assert captured_kwargs["answer_style"] == "mini_review"
    assert captured_kwargs["answer_language"] == "auto"
    assert captured_kwargs["library_source_id"] == library_id


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


def object_with(**values: object) -> object:
    return type("ObjectWith", (), values)()
