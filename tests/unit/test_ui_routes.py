from __future__ import annotations

import uuid
from collections.abc import Iterable
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.ui import _truncate, article_detail, article_text_layers, dashboard, search_page


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
            SimpleNamespace(page_number=1, layer_type="ocr", has_usable_text=True, quality_score=Decimal("0.70"), source_pdf_path="ocr.pdf"),
            SimpleNamespace(
                page_number=1,
                layer_type="original",
                has_usable_text=True,
                quality_score=Decimal("0.90"),
                source_pdf_path="original.pdf",
            ),
        ]

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
    response = dashboard(_override_session())

    assert response.status_code == 200
    assert "Corpus Dashboard" in response.body.decode()
    assert "Articles" in response.body.decode()


def test_search_page_returns_results(monkeypatch) -> None:
    def fake_exact_search(session: object, query: str, collection_name: str, top_k: int) -> object:
        result = SimpleNamespace(
            article_id=str(ARTICLE_ID),
            title="Li-Nafion evidence paper",
            doi="10.1000/example",
            page_start=1,
            page_end=1,
            score=5.0,
            snippet="Nafion conductivity in NMP.",
        )
        return SimpleNamespace(results=[result])

    monkeypatch.setattr("app.ui.exact_search", fake_exact_search)
    response = search_page(_override_session(), q="Nafion")

    assert response.status_code == 200
    body = response.body.decode()
    assert "Li-Nafion evidence paper" in body
    assert "Nafion conductivity in NMP" in body


def test_article_pages_return_html() -> None:
    session = _override_session()
    article_response = article_detail(session, ARTICLE_ID)
    layers_response = article_text_layers(session, ARTICLE_ID)

    assert article_response.status_code == 200
    article_body = article_response.body.decode()
    assert "Inspect page text layers" in article_body
    assert "conductivity" in article_body
    assert layers_response.status_code == 200
    layer_body = layers_response.body.decode()
    assert "original" in layer_body
    assert "ocr" in layer_body


def test_unknown_article_returns_404() -> None:
    class MissingSession(FakeSession):
        def scalar(self, statement: object) -> object:
            if "WHERE articles.id" in str(statement):
                return None
            return super().scalar(statement)

    with pytest.raises(HTTPException) as exc:
        article_detail(MissingSession(), uuid.uuid4())

    assert exc.value.status_code == 404
