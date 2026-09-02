from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.models import Article, Chunk, LibrarySource, LibrarySourceFile, StructuredFact
from app.db.session import get_session
from app.documents.context import ChunkContext, ChunkContextItem
from app.generation.providers import GenerationUnavailableError
from app.library.service import DuplicateLibrarySourceError
from app.main import app
from app.retrieval.search import SearchFilters
from app.ui import (
    _truncate,
    answer_action,
    answer_page,
    answer_result_action,
    article_detail,
    article_text_layers,
    chunk_context_page,
    create_library_action,
    dashboard,
    delete_library_action,
    disable_library_action,
    enable_library_action,
    extended_retrieval_report_page,
    ingestion_page,
    libraries_page,
    pick_folder_action,
    retrieval_report_page,
    scan_library_action,
    search_page,
    structured_facts_page,
    text_quality_report_page,
    vector_indexes_page,
)

ARTICLE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class FakeScalarResult:
    def __init__(self, rows: Iterable[object]) -> None:
        self.rows = list(rows)

    def __iter__(self):
        return iter(self.rows)


class FakeExecuteResult:
    def __init__(self, rows: Iterable[tuple[object, ...]]) -> None:
        self.rows = list(rows)

    def all(self) -> list[tuple[object, ...]]:
        return self.rows


class FakeSession:
    def __init__(self) -> None:
        self.article = SimpleNamespace(
            id=ARTICLE_ID,
            title="Li-Nafion evidence paper",
            doi="10.1000/example",
            status="indexed",
            pdf_original_path="data/pdf/original.pdf",
            pdf_ocr_path="data/processed/ocr/ocr.pdf",
        )
        self.page = SimpleNamespace(page_number=1, selected_text_layer="original")
        self.tag = SimpleNamespace(article_id=ARTICLE_ID, tag_type="method", tag_value="conductivity")
        self.section = SimpleNamespace(
            article_id=ARTICLE_ID,
            normalized_name="experimental",
            name="Experimental",
            page_start=1,
            page_end=1,
            source_type="main_text",
        )
        self.chunk = SimpleNamespace(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            article_id=ARTICLE_ID,
            chunk_index=0,
            page_start=1,
            page_end=1,
            source_type="main_text",
            text_layer="original",
            text="Nafion conductivity in NMP was measured.",
        )
        self.fact = StructuredFact(
            id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
            article_id=ARTICLE_ID,
            source_chunk_id=self.chunk.id,
            entity_type="numeric_measurement",
            field_name="conductivity",
            field_value_text="1.2e-3 S cm-1",
            field_value_numeric=Decimal("0.0012"),
            unit="S cm-1",
            confidence=Decimal("0.80"),
            source="rule_based_numeric_v1",
        )
        self.layers = [
            SimpleNamespace(
                page_number=1, layer_type="ocr", has_usable_text=True, quality_score=Decimal("0.70"), source_pdf_path="ocr.pdf"
            ),
            SimpleNamespace(
                page_number=1,
                layer_type="original",
                has_usable_text=True,
                quality_score=Decimal("0.90"),
                source_pdf_path="original.pdf",
            ),
        ]
        self.upload_job = SimpleNamespace(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            article_id=ARTICLE_ID,
            collection_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            original_filename="upload.pdf",
            checksum_sha256="a" * 64,
            file_size_bytes=123,
            force_ocr=False,
            attempt_count=1,
            worker_id="worker",
            error_type=None,
            error_message=None,
            status="indexed",
            created_at="2026-08-04T00:00:00+00:00",
            updated_at=None,
            started_at=None,
            finished_at=None,
        )
        self.legacy_job = SimpleNamespace(
            id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
            article_id=None,
            collection_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            original_filename=None,
            checksum_sha256=None,
            file_size_bytes=None,
            force_ocr=False,
            attempt_count=0,
            worker_id=None,
            error_type=None,
            error_message="legacy path data\\processed\\ocr\\bad.pdf",
            status="failed",
            created_at="2026-07-01T00:00:00+00:00",
            updated_at=None,
            started_at=None,
            finished_at=None,
        )
        self.library_source = LibrarySource(
            id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
            name="Nafion Library",
            path="D:\\Research\\Nafion",
            collection_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            enabled=True,
            watch_enabled=True,
            recursive=True,
            status="active",
        )
        self.library_file = LibrarySourceFile(
            id=uuid.UUID("77777777-7777-7777-7777-777777777777"),
            library_source_id=self.library_source.id,
            external_path="D:\\Research\\Nafion\\paper.pdf",
            relative_path="paper.pdf",
            filename="paper.pdf",
            content_hash_sha256="a" * 64,
            file_size_bytes=123,
            mtime_ns=1,
            status="queued",
        )
        self.commits = 0

    def scalar(self, statement: object) -> object:
        text = str(statement)
        if "WHERE articles.id" in text:
            return self.article
        if "count" in text:
            return 1
        return self.article

    def scalars(self, statement: object) -> FakeScalarResult:
        text = str(statement)
        if "FROM library_source_files" in text:
            return FakeScalarResult([self.library_file])
        if "FROM structured_facts" in text:
            return FakeScalarResult([self.fact])
        if "FROM library_sources" in text:
            return FakeScalarResult([self.library_source])
        if "FROM articles" in text:
            return FakeScalarResult([self.article])
        if "FROM article_tags" in text:
            return FakeScalarResult([self.tag])
        if "FROM sections" in text:
            return FakeScalarResult([self.section])
        if "FROM chunks" in text:
            return FakeScalarResult([self.chunk])
        if "FROM page_text_layers" in text:
            return FakeScalarResult(self.layers)
        if "FROM collections" in text:
            return FakeScalarResult([SimpleNamespace(name="literature")])
        if "FROM ingestion_jobs" in text and "original_filename IS NOT NULL" in text:
            return FakeScalarResult([self.upload_job])
        if "FROM ingestion_jobs" in text:
            return FakeScalarResult([self.upload_job, self.legacy_job])
        if "FROM pages" in text:
            return FakeScalarResult([self.page])
        return FakeScalarResult([])

    def get(self, model: type[object], row_id: object) -> object | None:
        if model is LibrarySource and row_id == self.library_source.id:
            return self.library_source
        if model is Article and row_id == ARTICLE_ID:
            return self.article
        if model is Chunk and row_id == self.chunk.id:
            return self.chunk
        return None

    def add(self, value: object) -> None:
        return None

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def execute(self, statement: object) -> FakeExecuteResult:
        text = str(statement)
        if "pages.selected_text_layer" in text:
            return FakeExecuteResult([("original", 1)])
        if "chunks.source_type" in text:
            return FakeExecuteResult([("main_text", 1)])
        if "chunks.text_layer" in text:
            return FakeExecuteResult([("original", 1)])
        if "pages.page_number" in text:
            return FakeExecuteResult([(1, "original")])
        return FakeExecuteResult([])


def _override_session() -> FakeSession:
    return FakeSession()


def test_truncate_shortens_long_text() -> None:
    assert _truncate("a" * 12, limit=5) == "aaaaa..."


def test_dashboard_returns_html(monkeypatch) -> None:
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace(data_root=Path("missing-data-root")))
    response = dashboard(_override_session())

    assert response.status_code == 200
    body = response.body.decode()
    assert "Corpus Dashboard" in body
    assert "ARIADNE Research Workbench" in body
    assert "Nafion profile" not in body
    assert "Evidence library" in body
    assert "data-library-toggle" in body
    assert "ariadne:selectedLibraries" in body
    assert 'method="post" action="/ui/answer"' in body
    assert 'data-async-result="/ui/answer/result"' in body
    assert 'name="question"' in body
    assert 'value="mini_review"' in body
    assert 'id="home-answer-result"' in body
    assert "Prepare request parameters" in body
    assert "Render answer and citations" in body
    assert ">Home</a>" in body
    assert ">Search</a>" not in body
    assert "main_text" not in body
    assert "Main text" in body
    assert "Tables / Facts diagnostics" in body
    assert "Articles" in body
    assert "Analysis Progress" in body
    assert "Text/OCR ready" in body
    assert "Retrieval Evaluation" in body
    assert "Extended Retrieval Evaluation" in body


def test_ui_root_route_returns_dashboard(monkeypatch) -> None:
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace(data_root=Path("missing-data-root")))
    app.dependency_overrides[get_session] = _override_session
    try:
        response = TestClient(app).get("/ui/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "ARIADNE Research Workbench" in response.text


def test_search_page_returns_results(monkeypatch) -> None:
    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str,
        source_type: str | None = None,
        filters: object | None = None,
        group_by: str = "none",
        chunks_per_article: int | None = None,
        settings: object | None = None,
    ) -> object:
        assert cast(SearchFilters, filters).source_type == "method"
        assert group_by == "none"
        assert chunks_per_article is None
        assert method == "hybrid"
        assert cast(SearchFilters, filters).library_source_id is None
        assert settings is not None
        result = SimpleNamespace(
            article_id=str(ARTICLE_ID),
            chunk_id="22222222-2222-2222-2222-222222222222",
            title="Li-Nafion evidence paper",
            doi="10.1000/example",
            page_start=1,
            page_end=1,
            source_type="method",
            text_layer="ocr",
            retrieval_method="hybrid_rrf",
            score=5.0,
            snippet="Nafion conductivity in NMP.",
        )
        return SimpleNamespace(results=[result])

    monkeypatch.setattr("app.ui.search_chunks", fake_search_chunks)
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    response = search_page(_override_session(), q="Nafion", source_type="method", method="hybrid")

    assert response.status_code == 200
    body = response.body.decode()
    assert "Li-Nafion evidence paper" in body
    assert "Nafion conductivity in NMP" in body
    assert "method" in body
    assert "ocr" in body
    assert "/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original#page=1" in body
    assert "/ui/articles/11111111-1111-1111-1111-111111111111/chunks/22222222-2222-2222-2222-222222222222/context" in body
    assert "hybrid_rrf" in body
    assert "value='hybrid' selected" in body
    assert "data-library-scoped" in body


def test_search_page_ignores_blank_numeric_filters(monkeypatch) -> None:
    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str,
        source_type: str | None = None,
        filters: object | None = None,
        group_by: str = "none",
        chunks_per_article: int | None = None,
        settings: object | None = None,
    ) -> object:
        normalized = cast(SearchFilters, filters)
        assert normalized.year is None
        assert normalized.year_from is None
        assert normalized.year_to is None
        assert chunks_per_article is None
        return SimpleNamespace(results=[])

    monkeypatch.setattr("app.ui.search_chunks", fake_search_chunks)
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    response = search_page(
        _override_session(),
        q="Термодинамика Nafion в воде",
        year="",
        year_from="",
        year_to="",
        chunks_per_article="",
    )

    assert response.status_code == 200
    assert "No results" in response.body.decode()


def test_search_page_uses_current_library_cookie(monkeypatch) -> None:
    library_id = uuid.UUID("66666666-6666-6666-6666-666666666666")

    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str,
        source_type: str | None = None,
        filters: object | None = None,
        group_by: str = "none",
        chunks_per_article: int | None = None,
        settings: object | None = None,
    ) -> object:
        assert cast(SearchFilters, filters).library_source_id == library_id
        return SimpleNamespace(results=[])

    monkeypatch.setattr("app.ui.search_chunks", fake_search_chunks)
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())

    response = search_page(_override_session(), q="Nafion", ariadne_library_id=str(library_id))
    body = response.body.decode()

    assert response.status_code == 200
    assert f'value="{library_id}"' in body


def test_answer_page_renders_form() -> None:
    response = answer_page()
    body = response.body.decode()

    assert response.status_code == 200
    assert "Question" in body
    assert "/ui/answer" in body
    assert 'data-async-result="/ui/answer/result"' in body
    assert 'name="library_source_id"' in body
    assert 'id="answer-result"' in body
    assert "progress-steps" in body
    assert 'data-result-status="error"' in body
    assert "result.querySelector('[data-result-status=\"error\"]')" in body
    assert "Prepare request parameters" in body
    assert "Wait for retrieval, evidence check, and generation" in body
    assert "Render answer and citations" in body
    assert "form.requestSubmit()" in body
    assert "value='hybrid_cross_lingual' selected" in body
    assert "hybrid_cross_lingual_v2" not in body
    assert "Answer language" in body
    assert "value='auto' selected" in body


def test_answer_page_uses_current_library_cookie() -> None:
    response = answer_page(ariadne_library_id="66666666-6666-6666-6666-666666666666")
    body = response.body.decode()

    assert 'name="library_source_id"' in body
    assert 'value="66666666-6666-6666-6666-666666666666"' in body


def test_vector_indexes_page_marks_only_settings_nav_active(monkeypatch) -> None:
    monkeypatch.setattr("app.ui.list_vector_index_states", lambda session: [])

    response = vector_indexes_page(_override_session())
    body = response.body.decode()

    assert response.status_code == 200
    assert "class='active' href='/ui/vector-indexes'>Settings</a>" in body
    assert "class='active' href='/ui/ingestion'>Sessions</a>" not in body
    assert body.count("class='active'") == 1


def test_answer_action_renders_claims_and_citations(monkeypatch) -> None:
    def fake_answer_question(
        session: object,
        settings: object,
        question: str,
        *,
        collection: str | None = None,
        top_k: int | None = None,
        method: str | None = None,
        answer_style: str = "claims",
        answer_language: str = "auto",
        library_source_id: uuid.UUID | None = None,
    ) -> object:
        assert question == "What is Li-Nafion conductivity?"
        assert collection == "literature"
        assert top_k == 5
        assert method == "hybrid"
        assert answer_style == "mini_review"
        assert answer_language == "ru"
        assert library_source_id is None
        return SimpleNamespace()

    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr("app.ui.answer_question", fake_answer_question)
    monkeypatch.setattr(
        "app.ui.answer_response_to_dict",
        lambda response: {
            "query": "What is Li-Nafion conductivity?",
            "status": "answered",
            "answer": "Li-Nafion conductivity was measured. [E1]",
            "claims": [{"text": "Li-Nafion conductivity was measured.", "citation_ids": ["E1"]}],
            "citations": [
                {
                    "citation_id": "E1",
                    "article_id": str(ARTICLE_ID),
                    "chunk_id": "22222222-2222-2222-2222-222222222222",
                    "title": "Li-Nafion evidence paper",
                    "doi": "10.1000/example",
                    "page_start": 1,
                    "page_end": 1,
                    "pdf_page_url": f"/articles/{ARTICLE_ID}/pdf?layer=original#page=1",
                    "text": "Nafion conductivity evidence.",
                    "score": 2.5,
                    "original_language": "en",
                    "translation_status": "not_requested",
                }
            ],
            "retrieval_method": "hybrid",
            "generation_provider": "extractive",
            "generation_model": None,
            "metadata": {
                "retrieved_count": 1,
                "evidence_adequacy": {
                    "reason": "ok",
                    "coverage": 1.0,
                    "top_coverage": 1.0,
                    "distinctive_terms": ["nafion", "conductivity"],
                    "matched_terms": ["nafion", "conductivity"],
                },
                "query_assistance": {
                    "corrected_query": "What protocol of Nafion lithiation?",
                    "corrections": [{"original": "litation", "suggestion": "lithiation", "reason": "edit_distance_2"}],
                    "mode": "suggest_only",
                },
                "derived_evidence": {
                    "type": "swelling_comparison_table",
                    "source_article_id": str(ARTICLE_ID),
                    "source_chunk_id": "22222222-2222-2222-2222-222222222222",
                    "source_pages": [96, 97],
                    "matching_row_count": 4,
                    "nonmatching_row_count": 5,
                },
            },
        },
    )

    response = answer_action(_override_session(), "What is Li-Nafion conductivity?", "literature", 5, "hybrid", "mini_review", "ru")  # type: ignore[arg-type]
    body = response.body.decode()

    assert response.status_code == 200
    assert "<strong>Query:</strong> What is Li-Nafion conductivity?" in body
    assert "<strong>Retrieved:</strong> 1" in body
    assert "matched=nafion, conductivity" in body
    assert "missing=none" in body
    assert "Li-Nafion conductivity was measured" in body
    assert "Nafion conductivity evidence" in body
    assert "claim-card" in body
    assert "source-fragment" in body
    assert "translation=not_requested" in body
    assert ">[E1]</a>" in body
    assert f"href='/articles/{ARTICLE_ID}/pdf?layer=original#page=1'" in body
    assert ">Evidence</a>" in body
    assert "highlight_query=Nafion+conductivity+evidence." in body
    assert "highlight_mode=phrase" in body
    assert "Mini-review by article" in body
    assert "Possible query typo" in body
    assert "litation -&gt; lithiation" in body
    assert "data-suggested-query='What protocol of Nafion lithiation?'" in body
    assert "Derived evidence" in body
    assert "swelling_comparison_table" in body
    assert "Matching rows:</strong> 4" in body
    assert "Nonmatching rows:</strong> 5" in body
    assert "Pages:</strong> 96-97" in body
    assert f"/ui/articles/{ARTICLE_ID}/chunks/22222222-2222-2222-2222-222222222222/context" in body
    assert f"/articles/{ARTICLE_ID}/pdf?layer=original#page=1" in body


def test_answer_result_action_returns_fragment_only(monkeypatch) -> None:
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr("app.ui.answer_question", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(
        "app.ui.answer_response_to_dict",
        lambda response: {
            "query": "What is Li-Nafion conductivity?",
            "status": "answered",
            "answer": "Li-Nafion conductivity was measured. [E1]",
            "claims": [{"text": "Li-Nafion conductivity was measured.", "citation_ids": ["E1"]}],
            "citations": [
                {
                    "citation_id": "E1",
                    "article_id": str(ARTICLE_ID),
                    "chunk_id": "22222222-2222-2222-2222-222222222222",
                    "title": "Li-Nafion evidence paper",
                    "doi": "10.1000/example",
                    "page_start": 1,
                    "page_end": 1,
                    "text": "Nafion conductivity evidence.",
                    "score": 2.5,
                    "original_language": "en",
                    "translation_status": "not_requested",
                }
            ],
            "retrieval_method": "hybrid",
            "generation_provider": "extractive",
            "generation_model": None,
            "metadata": {},
        },
    )

    response = answer_result_action(_override_session(), "What is Li-Nafion conductivity?", "literature", 5, "hybrid", "claims", "auto")  # type: ignore[arg-type]
    body = response.body.decode()

    assert response.status_code == 200
    assert "<!doctype html>" not in body
    assert "Li-Nafion conductivity was measured" in body
    assert "Nafion conductivity evidence" in body


def test_answer_result_action_renders_provider_error(monkeypatch) -> None:
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())

    def fake_answer_question(*args, **kwargs) -> object:
        raise GenerationUnavailableError("OpenAI request failed: socket blocked")

    monkeypatch.setattr("app.ui.answer_question", fake_answer_question)

    response = answer_result_action(_override_session(), "What is Li-Nafion conductivity?", "literature", 5, "hybrid", "claims", "auto")  # type: ignore[arg-type]
    body = response.body.decode()

    assert response.status_code == 200
    assert "data-result-status='error'" in body
    assert "Generation provider unavailable" in body
    assert "GenerationUnavailableError" in body
    assert "OpenAI request failed: socket blocked" in body
    assert "Retrieval may have succeeded" in body


def test_chunk_context_page_renders_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.ui.get_chunk_context",
        lambda *args, **kwargs: ChunkContext(
            article_id=str(ARTICLE_ID),
            chunk_id="22222222-2222-2222-2222-222222222222",
            title="Li-Nafion evidence paper",
            doi="10.1000/example",
            requested_chunk_index=0,
            chunks=[
                ChunkContextItem(
                    chunk_id="22222222-2222-2222-2222-222222222222",
                    chunk_index=0,
                    role="requested",
                    page_start=1,
                    page_end=1,
                    source_type="method",
                    text_layer="original",
                    text="Nafion conductivity context.",
                    highlights=[],
                )
            ],
            pdf_url=f"/articles/{ARTICLE_ID}/pdf?layer=original",
            pdf_page_url=f"/articles/{ARTICLE_ID}/pdf?layer=original#page=1",
            truncated=False,
        ),
    )
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())

    response = chunk_context_page(
        _override_session(),  # type: ignore[arg-type]
        ARTICLE_ID,
        uuid.UUID("22222222-2222-2222-2222-222222222222"),
    )
    body = response.body.decode()

    assert response.status_code == 200
    assert "Li-Nafion evidence paper" in body
    assert "Nafion conductivity context" in body
    assert f"/articles/{ARTICLE_ID}/pdf?layer=original#page=1" in body


def test_article_pages_return_html() -> None:
    session = _override_session()
    article_response = article_detail(session, ARTICLE_ID)
    layers_response = article_text_layers(session, ARTICLE_ID)

    assert article_response.status_code == 200
    article_body = article_response.body.decode()
    assert "Inspect page text layers" in article_body
    assert "Open original PDF" in article_body
    assert "Open OCR PDF" in article_body
    assert "/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original#page=1" in article_body
    assert "conductivity" in article_body
    assert layers_response.status_code == 200
    layer_body = layers_response.body.decode()
    assert "original" in layer_body
    assert "ocr" in layer_body


def test_ingestion_page_defaults_to_upload_jobs_only(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.ui.get_settings",
        lambda: SimpleNamespace(upload_max_files_per_request=10, upload_max_file_size_mb=100),
    )
    response = ingestion_page(_override_session())

    body = response.body.decode()

    assert response.status_code == 200
    assert "Recognition And Text Analysis" in body
    assert "Text/OCR indexed" in body
    assert "upload.pdf" in body
    assert "(legacy CLI job)" not in body
    assert "data\\processed" not in body


def test_libraries_page_renders_sources_and_files(monkeypatch) -> None:
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    response = libraries_page(_override_session())
    body = response.body.decode()

    assert response.status_code == 200
    assert "Libraries" in body
    assert "Add Library" in body
    assert "data-current-library" in body
    assert "ariadne:currentLibrary" in body
    assert "Analysis Progress" in body
    assert "Text/OCR ready" in body
    assert "Nafion Library" in body
    assert "D:\\Research\\Nafion" in body
    assert "paper.pdf" in body
    assert "stage-dot running" in body
    assert "Scan Now" in body
    assert "Open Articles" in body
    assert "Open Failed Files" in body
    assert "Save Library" in body
    assert "/ui/libraries/66666666-6666-6666-6666-666666666666/disable" in body
    assert "Delete Source" in body
    assert "Browse Folder" in body
    assert "data-folder-picker" in body
    assert "fetch('/ui/pick-folder'" in body
    assert "class='active' href='/ui/libraries'>Libraries</a>" in body
    assert "Nafion profile" not in body


def test_structured_facts_page_renders_fact_candidates() -> None:
    response = structured_facts_page(_override_session(), field_name="conductivity")
    body = response.body.decode()

    assert response.status_code == 200
    assert "Structured Facts" in body
    assert "Derived numeric evidence candidates" in body
    assert "conductivity" in body
    assert "1.2e-3 S cm-1" in body
    assert "0.0012" in body
    assert "rule_based_numeric_v1" in body
    assert "Li-Nafion evidence paper" in body
    assert f"/ui/articles/{ARTICLE_ID}/chunks/22222222-2222-2222-2222-222222222222/context" in body
    assert f"/articles/{ARTICLE_ID}/pdf?layer=original#page=1" in body
    assert "class='active' href='/ui/facts'>Facts</a>" in body


def test_create_library_action_redirects_after_commit(monkeypatch, tmp_path) -> None:
    session = _override_session()
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        "app.ui.create_library_source",
        lambda active_session, settings, **kwargs: SimpleNamespace(id=uuid.UUID("88888888-8888-8888-8888-888888888888")),
    )

    response = create_library_action(session, "New Library", str(tmp_path), "literature", True)  # type: ignore[arg-type]

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/libraries?library_id=88888888-8888-8888-8888-888888888888"
    assert response.headers["set-cookie"].startswith("ariadne_library_id=88888888-8888-8888-8888-888888888888")
    assert session.commits == 1


def test_create_library_action_redirects_to_existing_duplicate(monkeypatch, tmp_path) -> None:
    session = _override_session()
    existing = session.library_source
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    def duplicate_source(*args: object, **kwargs: object) -> object:
        raise DuplicateLibrarySourceError(existing)

    monkeypatch.setattr("app.ui.create_library_source", duplicate_source)

    response = create_library_action(session, "cellosolve", str(tmp_path), "literature", True)  # type: ignore[arg-type]

    assert response.status_code == 303
    assert response.headers["location"] == f"/ui/libraries?library_id={existing.id}"
    assert response.headers["set-cookie"].startswith(f"ariadne_library_id={existing.id}")
    assert session.commits == 0


def test_pick_folder_action_returns_selected_path(monkeypatch) -> None:
    monkeypatch.setattr("app.ui._pick_local_directory", lambda initial_path="": "D:\\Research\\Nafion")

    payload = pick_folder_action("D:\\Research")

    assert payload == {"path": "D:\\Research\\Nafion"}


def test_scan_library_action_redirects_after_commit(monkeypatch) -> None:
    session = _override_session()
    library_id = uuid.UUID("66666666-6666-6666-6666-666666666666")
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr("app.ui.scan_and_queue_library_source", lambda active_session, settings, active_library_id: None)

    response = scan_library_action(session, library_id)  # type: ignore[arg-type]

    assert response.status_code == 303
    assert response.headers["location"] == f"/ui/libraries?library_id={library_id}"
    assert response.headers["set-cookie"].startswith(f"ariadne_library_id={library_id}")
    assert session.commits == 1


def test_enable_disable_library_actions_redirect_after_commit(monkeypatch) -> None:
    session = _override_session()
    library_id = uuid.UUID("66666666-6666-6666-6666-666666666666")
    calls: list[bool] = []
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        "app.ui.update_library_source",
        lambda active_session, settings, active_library_id, **kwargs: calls.append(cast(bool, kwargs["enabled"])),
    )

    disable_response = disable_library_action(session, library_id)  # type: ignore[arg-type]
    enable_response = enable_library_action(session, library_id)  # type: ignore[arg-type]

    assert disable_response.status_code == 303
    assert enable_response.status_code == 303
    assert calls == [False, True]
    assert session.commits == 2


def test_delete_library_action_redirects_after_commit(monkeypatch) -> None:
    session = _override_session()
    library_id = uuid.UUID("66666666-6666-6666-6666-666666666666")
    deleted: list[uuid.UUID] = []
    monkeypatch.setattr("app.ui.delete_library_source", lambda active_session, active_library_id: deleted.append(active_library_id))

    response = delete_library_action(session, library_id)  # type: ignore[arg-type]

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/libraries"
    assert deleted == [library_id]
    assert session.commits == 1


def test_unknown_article_returns_404() -> None:
    class MissingSession(FakeSession):
        def scalar(self, statement: object) -> object:
            if "WHERE articles.id" in str(statement):
                return None
            return super().scalar(statement)

    with pytest.raises(HTTPException) as exc:
        article_detail(MissingSession(), uuid.uuid4())

    assert exc.value.status_code == 404


def test_retrieval_report_page_renders_latest_report(monkeypatch, tmp_path) -> None:
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    report_path = export_dir / "retrieval_eval_20260702T000000Z.json"
    extended_path = export_dir / "retrieval_eval_extended_exact_20260703T000000Z.json"
    extended_path.write_text(
        json.dumps(
            {
                "schema": "retrieval_eval_extended_v1",
                "created_at": "2026-07-03T00:00:00+00:00",
                "settings": {"retrieval_method": "extended_should_not_render"},
                "summary": {"total": 99},
                "questions": [],
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "created_at": "2026-07-02T00:00:00+00:00",
                "settings": {"retrieval_method": "exact_ilike"},
                "summary": {
                    "total": 1,
                    "passed": 0,
                    "top_1_passed": 0,
                    "failed": 1,
                    "recall_at_k": 1.0,
                    "mean_rank": 2.0,
                    "empty_result_queries": 0,
                    "evidence_trace_complete": False,
                },
                "questions": [
                    {
                        "id": "q01",
                        "query": "Li-Nafion conductivity",
                        "passed": False,
                        "top_1_passed": False,
                        "rank_of_expected": 2,
                        "recall_at_k": 1.0,
                        "evidence_trace_complete": False,
                        "missing_article_dois": [],
                        "missing_article_titles": ["missing title"],
                        "missing_article_checksums": ["abc123"],
                        "missing_keywords": ["NMP"],
                        "result_count": 1,
                        "results": [
                            {
                                "title": "Li-Nafion paper",
                                "doi": "10.1000/example",
                                "page_start": 2,
                                "page_end": 3,
                                "source_type": "method",
                                "score": 12.0,
                                "retrieval_method": "exact_ilike",
                                "snippet": "Li-Nafion conductivity evidence.",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace(data_root=tmp_path))

    response = retrieval_report_page()
    body = response.body.decode()

    assert response.status_code == 200
    assert "Retrieval Evaluation Report" in body
    assert "exact_ilike" in body
    assert "extended_should_not_render" not in body
    assert "Li-Nafion conductivity evidence" in body
    assert "NMP" in body
    assert "Top-1 passed" in body
    assert "Mean rank" in body
    assert "Rank:</strong> 2" in body
    assert "Missing title:" in body
    assert "missing title" in body
    assert "Missing checksum:" in body
    assert "abc123" in body
    assert "Trace complete:</strong> no" in body


def test_extended_retrieval_report_page_renders_latest_report(monkeypatch, tmp_path) -> None:
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    report_path = export_dir / "retrieval_eval_extended_hybrid_20260702T000000Z.json"
    report_path.write_text(
        json.dumps(
            {
                "schema": "retrieval_eval_extended_v1",
                "created_at": "2026-07-02T00:00:00+00:00",
                "settings": {"retrieval_method": "hybrid_rrf"},
                "summary": {
                    "total": 2,
                    "answerable": 1,
                    "unanswerable": 1,
                    "passed": 2,
                    "failed": 0,
                    "article_recall_at_k": 1.0,
                    "chunk_recall_at_k": 0.5,
                    "mrr": 0.5,
                    "ndcg_at_k": 0.75,
                    "top_1_passed": 1,
                    "mean_rank": 2.0,
                    "false_answerable": 0,
                    "evidence_trace_complete": True,
                    "p95_latency_ms": 12.5,
                    "by_language": {
                        "ru": {
                            "total": 1,
                            "passed": 1,
                            "article_recall_at_k": 1.0,
                            "mrr": 0.5,
                            "top_1_passed": 0,
                            "mean_rank": 2.0,
                        }
                    },
                    "by_category": {
                        "swelling": {
                            "total": 1,
                            "passed": 1,
                            "article_recall_at_k": 1.0,
                            "mrr": 0.5,
                            "top_1_passed": 0,
                            "mean_rank": 2.0,
                        }
                    },
                },
                "questions": [
                    {
                        "id": "x01",
                        "query": "степень набухания Li-Nafion",
                        "language": "ru",
                        "category": "swelling",
                        "passed": True,
                        "rank_of_first_relevant": 2,
                        "article_recall_at_k": 1.0,
                        "mrr": 0.5,
                        "ndcg_at_k": 0.75,
                        "missing_expected_articles": [],
                        "missing_expected_chunks": [{"text_contains": ["alphaLi"]}],
                        "evidence_trace_complete": True,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace(data_root=tmp_path))

    response = extended_retrieval_report_page()
    body = response.body.decode()

    assert response.status_code == 200
    assert "Extended Retrieval Evaluation Report" in body
    assert "hybrid_rrf" in body
    assert "Article recall@k" in body
    assert "NDCG@k" in body
    assert "False answerable" in body
    assert "Evidence trace complete" in body
    assert "By Language" in body
    assert "By Category" in body
    assert "swelling" in body
    assert "x01" in body
    assert "Missing chunks" in body


def test_text_quality_report_page_renders_latest_report(monkeypatch, tmp_path) -> None:
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    report_path = export_dir / "text_quality_report_20260702T000000Z.json"
    report_path.write_text(
        json.dumps(
            {
                "created_at": "2026-07-02T00:00:00+00:00",
                "collection": "literature",
                "article_count": 1,
                "page_count": 2,
                "empty_original_page_count": 1,
                "short_original_page_count": 0,
                "suspicious_page_count": 1,
                "ocr_used_pages": 1,
                "ocr_available_pages": 1,
                "source_type_distribution": {"main_text": 3},
                "text_layer_distribution": {"ocr": 2, "original": 1},
                "selected_text_layer_distribution": {"ocr": 1, "original": 1},
                "ocr_diagnostics": {"enabled": True, "version_status": "ok"},
                "suspicious_pages": [
                    {
                        "article_id": str(ARTICLE_ID),
                        "title": "Li-Nafion evidence paper",
                        "doi": "10.1000/example",
                        "page_number": 1,
                        "reasons": ["empty_original_text"],
                        "selected_text_layer": "ocr",
                        "selected_char_count": 450,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.ui.get_settings", lambda: SimpleNamespace(data_root=tmp_path))

    response = text_quality_report_page()
    body = response.body.decode()

    assert response.status_code == 200
    assert "Text Quality Report" in body
    assert "empty_original_text" in body
    assert "version_status" in body
    assert f"/ui/articles/{ARTICLE_ID}/pages/context?page_start=1&page_end=1&layer=selected" in body
    assert f"/articles/{ARTICLE_ID}/pdf?layer=original#page=1" in body
