from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.documents.context import (
    ContextNotFoundError,
    chunk_context_to_dict,
    find_highlights,
    get_chunk_context,
    get_page_range_context,
    page_range_context_to_dict,
)
from app.documents.service import PageEvidence


class FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self, requested: object | None, chunks: list[object]) -> None:
        self.requested = requested
        self.chunks = chunks

    def scalar(self, statement: object) -> object | None:
        return self.requested

    def scalars(self, statement: object) -> FakeScalarResult:
        return FakeScalarResult(self.chunks)


def test_chunk_context_returns_previous_requested_and_next() -> None:
    article = _article()
    chunks = _chunks(article.id)
    session = FakeSession(chunks[1], chunks)

    context = get_chunk_context(session, _settings(), article, chunks[1].id, before=1, after=1, highlight_query="Nafion")  # type: ignore[arg-type]

    assert [item.role for item in context.chunks] == ["previous", "requested", "next"]
    assert [item.chunk_index for item in context.chunks] == [0, 1, 2]
    assert context.chunks[1].highlights[0].term == "Nafion"
    assert context.pdf_page_url.endswith("#page=2")


def test_chunk_context_missing_chunk_raises_not_found() -> None:
    article = _article()

    with pytest.raises(ContextNotFoundError):
        get_chunk_context(FakeSession(None, []), _settings(), article, uuid.uuid4())  # type: ignore[arg-type]


def test_chunk_context_validates_neighbor_limits() -> None:
    article = _article()
    chunks = _chunks(article.id)

    with pytest.raises(ValueError, match="before exceeds"):
        get_chunk_context(FakeSession(chunks[0], chunks), _settings(context_max_neighbor_chunks=1), article, chunks[0].id, before=2)  # type: ignore[arg-type]


def test_chunk_context_truncates_without_mutating_stored_text() -> None:
    article = _article()
    chunks = _chunks(article.id)
    original_text = chunks[1].text

    context = get_chunk_context(FakeSession(chunks[1], chunks), _settings(), article, chunks[1].id, before=0, after=0, max_chars=8)  # type: ignore[arg-type]

    assert context.truncated is True
    assert context.chunks[0].text == original_text[:8]
    assert chunks[1].text == original_text


def test_chunk_context_keeps_requested_chunk_when_previous_exceeds_limit() -> None:
    article = _article()
    chunks = _chunks(article.id)
    chunks[0].text = "x" * 200

    context = get_chunk_context(FakeSession(chunks[1], chunks), _settings(), article, chunks[1].id, before=1, after=0, max_chars=50)  # type: ignore[arg-type]

    assert context.truncated is True
    assert [chunk.role for chunk in context.chunks] == ["requested"]
    assert context.chunks[0].text == chunks[1].text


def test_page_range_context_uses_stored_page_evidence(monkeypatch) -> None:
    article = _article()

    def fake_get_article_page(session, settings, article_arg, page_number, layer):
        return PageEvidence(
            article_id=str(article_arg.id),
            title=article_arg.title,
            page_number=page_number,
            requested_layer=layer,
            resolved_layer="ocr" if page_number == 2 else "original",
            has_usable_text=True,
            text=f"Stored Nafion page {page_number}",
            pdf_url=f"/articles/{article_arg.id}/pdf?layer=original",
            pdf_page_url=f"/articles/{article_arg.id}/pdf?layer=original#page={page_number}",
        )

    monkeypatch.setattr("app.documents.context.get_article_page", fake_get_article_page)

    context = get_page_range_context(object(), _settings(context_max_pages=2), article, page_start=1, page_end=2, highlight_query="Nafion")  # type: ignore[arg-type]
    payload = page_range_context_to_dict(context)

    assert payload["page_start"] == 1
    assert payload["page_end"] == 2
    assert payload["pages"][1]["resolved_layer"] == "ocr"
    assert payload["pages"][0]["highlights"][0]["term"] == "Nafion"


def test_page_range_context_validates_page_count() -> None:
    with pytest.raises(ValueError, match="CONTEXT_MAX_PAGES"):
        get_page_range_context(object(), _settings(context_max_pages=1), _article(), page_start=1, page_end=2)  # type: ignore[arg-type]


def test_find_highlights_does_not_mutate_text() -> None:
    text = "Li-Nafion conductivity."

    highlights = find_highlights(text, "Nafion conductivity", 12)

    assert text == "Li-Nafion conductivity."
    assert [(highlight.start, highlight.end, highlight.term) for highlight in highlights] == [(3, 22, "Nafion conductivity")]


def test_find_highlights_matches_evidence_across_whitespace() -> None:
    text = "Nafion conductivity\nin NMP was measured."

    highlights = find_highlights(text, "conductivity in NMP", 12)

    assert len(highlights) == 1
    assert text[highlights[0].start : highlights[0].end] == "conductivity\nin NMP"


def test_find_highlights_phrase_mode_does_not_fallback_to_terms() -> None:
    text = "Thermogravimetric analysis was performed."

    highlights = find_highlights(text, "swelling degree in DMF", 12, mode="phrase")

    assert highlights == []


def test_find_highlights_phrase_mode_ignores_snippet_ellipses() -> None:
    text = "The degree of swelling in DMF was measured after drying."

    highlights = find_highlights(text, "...degree of swelling in DMF was measured...", 12, mode="phrase")

    assert len(highlights) == 1
    assert text[highlights[0].start : highlights[0].end] == "degree of swelling in DMF was measured"


def test_chunk_context_serializes_bounded_payload() -> None:
    article = _article()
    chunks = _chunks(article.id)
    context = get_chunk_context(FakeSession(chunks[0], chunks[:1]), _settings(), article, chunks[0].id, before=0, after=0)  # type: ignore[arg-type]

    payload = chunk_context_to_dict(context)

    assert payload["chunks"][0]["text"] == chunks[0].text
    assert payload["chunks"][0]["role"] == "requested"


def _article() -> object:
    return SimpleNamespace(id=uuid.UUID("11111111-1111-1111-1111-111111111111"), title="Context paper", doi="10.1000/context")


def _chunks(article_id: uuid.UUID) -> list[object]:
    return [
        SimpleNamespace(
            id=uuid.UUID("22222222-2222-2222-2222-222222222220"),
            article_id=article_id,
            chunk_index=0,
            page_start=1,
            page_end=1,
            source_type="body",
            text_layer="original",
            text="Previous Nafion context.",
        ),
        SimpleNamespace(
            id=uuid.UUID("22222222-2222-2222-2222-222222222221"),
            article_id=article_id,
            chunk_index=1,
            page_start=2,
            page_end=2,
            source_type="method",
            text_layer="original",
            text="Requested Nafion conductivity context.",
        ),
        SimpleNamespace(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            article_id=article_id,
            chunk_index=2,
            page_start=3,
            page_end=3,
            source_type="body",
            text_layer="ocr",
            text="Next context.",
        ),
    ]


def _settings(**overrides: object) -> object:
    values = {
        "context_max_neighbor_chunks": 3,
        "context_max_chars": 30000,
        "context_max_pages": 5,
        "context_highlight_max_terms": 12,
    }
    values.update(overrides)
    return SimpleNamespace(**values)
