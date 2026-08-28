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

from app.documents.context import ChunkContext, ChunkContextItem
from app.retrieval.search import SearchFilters
from app.ui import (
    _truncate,
    answer_action,
    answer_page,
    answer_result_action,
    article_detail,
    article_text_layers,
    chunk_context_page,
    dashboard,
    ingestion_page,
    retrieval_report_page,
    search_page,
    text_quality_report_page,
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

    def scalar(self, statement: object) -> object:
        text = str(statement)
        if "WHERE articles.id" in text:
            return self.article
        if "count" in text:
            return 1
        return self.article

    def scalars(self, statement: object) -> FakeScalarResult:
        text = str(statement)
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
    assert "Corpus Dashboard" in response.body.decode()
    assert "ARIADNE Research Workbench" in response.body.decode()
    assert "Tables / Facts diagnostics" in response.body.decode()
    assert "Articles" in response.body.decode()
    assert "Retrieval Evaluation" in response.body.decode()


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


def test_answer_page_renders_form() -> None:
    response = answer_page()
    body = response.body.decode()

    assert response.status_code == 200
    assert "Question" in body
    assert "/ui/answer" in body
    assert 'data-async-result="/ui/answer/result"' in body
    assert 'id="answer-result"' in body
    assert "progress-steps" in body
    assert "Prepare request parameters" in body
    assert "Wait for retrieval, evidence check, and generation" in body
    assert "Render answer and citations" in body
    assert "form.requestSubmit()" in body
    assert "value='hybrid_cross_lingual' selected" in body
    assert "hybrid_cross_lingual_v2" not in body
    assert "Answer language" in body
    assert "value='auto' selected" in body


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
    ) -> object:
        assert question == "What is Li-Nafion conductivity?"
        assert collection == "literature"
        assert top_k == 5
        assert method == "hybrid"
        assert answer_style == "mini_review"
        assert answer_language == "ru"
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
    assert ">Evidence</a>" in body
    assert "highlight_query=Nafion+conductivity+evidence." in body
    assert "highlight_mode=phrase" in body
    assert "Mini-review by article" in body
    assert "Possible query typo" in body
    assert "litation -&gt; lithiation" in body
    assert "data-suggested-query='What protocol of Nafion lithiation?'" in body
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
    assert "upload.pdf" in body
    assert "(legacy CLI job)" not in body
    assert "data\\processed" not in body


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
    report_path.write_text(
        json.dumps(
            {
                "created_at": "2026-07-02T00:00:00+00:00",
                "settings": {"retrieval_method": "exact_ilike"},
                "summary": {"total": 1, "passed": 0, "failed": 1, "empty_result_queries": 0},
                "questions": [
                    {
                        "id": "q01",
                        "query": "Li-Nafion conductivity",
                        "passed": False,
                        "missing_article_dois": [],
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
    assert "Li-Nafion conductivity evidence" in body
    assert "NMP" in body


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
