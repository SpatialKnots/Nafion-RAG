from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Chunk
from app.documents.service import (
    PageEvidence,
    PageLayer,
    build_pdf_url,
    get_article_page,
)
from app.retrieval.search import LIGATURES, _query_terms

ChunkRole = Literal["previous", "requested", "next"]


class ContextNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class Highlight:
    start: int
    end: int
    term: str


@dataclass(frozen=True)
class ChunkContextItem:
    chunk_id: str
    chunk_index: int
    role: ChunkRole
    page_start: int
    page_end: int
    source_type: str
    text_layer: str
    text: str
    highlights: list[Highlight]


@dataclass(frozen=True)
class ChunkContext:
    article_id: str
    chunk_id: str
    title: str | None
    doi: str | None
    requested_chunk_index: int
    chunks: list[ChunkContextItem]
    pdf_url: str
    pdf_page_url: str
    truncated: bool


@dataclass(frozen=True)
class PageContextItem:
    page_number: int
    requested_layer: PageLayer
    resolved_layer: str
    has_usable_text: bool
    text: str
    highlights: list[Highlight]


@dataclass(frozen=True)
class PageRangeContext:
    article_id: str
    title: str | None
    layer: PageLayer
    page_start: int
    page_end: int
    pages: list[PageContextItem]
    pdf_url: str
    pdf_page_url: str
    truncated: bool


def get_chunk_context(
    session: Session,
    settings: Settings,
    article: Article,
    chunk_id: uuid.UUID,
    *,
    before: int = 1,
    after: int = 1,
    highlight_query: str | None = None,
    max_chars: int | None = None,
) -> ChunkContext:
    _validate_neighbor_count(before, settings.context_max_neighbor_chunks, "before")
    _validate_neighbor_count(after, settings.context_max_neighbor_chunks, "after")
    char_limit = _effective_char_limit(max_chars, settings.context_max_chars)
    requested = session.scalar(select(Chunk).where(Chunk.id == chunk_id).where(Chunk.article_id == article.id))
    if requested is None:
        raise ContextNotFoundError(f"Unknown chunk {chunk_id} for article {article.id}")

    low_index = requested.chunk_index - before
    high_index = requested.chunk_index + after
    chunks = list(
        session.scalars(
            select(Chunk)
            .where(Chunk.article_id == article.id)
            .where(Chunk.chunk_index >= low_index)
            .where(Chunk.chunk_index <= high_index)
            .order_by(Chunk.chunk_index.asc(), Chunk.id.asc())
        )
    )
    selected_chunks, truncated = _truncate_chunk_rows(chunks, requested.id, char_limit)
    items = [
        ChunkContextItem(
            chunk_id=str(chunk.id),
            chunk_index=chunk.chunk_index,
            role=_chunk_role(chunk.chunk_index, requested.chunk_index),
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            source_type=chunk.source_type,
            text_layer=chunk.text_layer,
            text=text,
            highlights=find_highlights(text, highlight_query, settings.context_highlight_max_terms),
        )
        for chunk, text in selected_chunks
    ]
    return ChunkContext(
        article_id=str(article.id),
        chunk_id=str(requested.id),
        title=article.title,
        doi=article.doi,
        requested_chunk_index=requested.chunk_index,
        chunks=items,
        pdf_url=build_pdf_url(article.id, "original"),
        pdf_page_url=build_pdf_url(article.id, "original", requested.page_start),
        truncated=truncated,
    )


def get_page_range_context(
    session: Session,
    settings: Settings,
    article: Article,
    *,
    page_start: int,
    page_end: int,
    layer: PageLayer = "selected",
    highlight_query: str | None = None,
    max_chars: int | None = None,
) -> PageRangeContext:
    if page_start < 1:
        raise ValueError("page_start must be positive")
    if page_end < page_start:
        raise ValueError("page_end must be greater than or equal to page_start")
    if page_end - page_start + 1 > settings.context_max_pages:
        raise ValueError(f"page range exceeds CONTEXT_MAX_PAGES={settings.context_max_pages}")
    char_limit = _effective_char_limit(max_chars, settings.context_max_chars)

    evidences = [get_article_page(session, settings, article, page_number, layer) for page_number in range(page_start, page_end + 1)]
    selected_pages, truncated = _truncate_pages(evidences, char_limit)
    pages = [
        PageContextItem(
            page_number=evidence.page_number,
            requested_layer=evidence.requested_layer,
            resolved_layer=evidence.resolved_layer,
            has_usable_text=evidence.has_usable_text,
            text=evidence.text,
            highlights=find_highlights(evidence.text, highlight_query, settings.context_highlight_max_terms),
        )
        for evidence in selected_pages
    ]
    return PageRangeContext(
        article_id=str(article.id),
        title=article.title,
        layer=layer,
        page_start=page_start,
        page_end=page_end,
        pages=pages,
        pdf_url=build_pdf_url(article.id, "original"),
        pdf_page_url=build_pdf_url(article.id, "original", page_start),
        truncated=truncated,
    )


def find_highlights(text: str, query: str | None, max_terms: int) -> list[Highlight]:
    if not query or not query.strip():
        return []
    terms = _query_terms(query)[:max_terms]
    if not terms:
        terms = [query.strip()[:100]]
    highlights: list[Highlight] = []
    normalized_text = text.translate(LIGATURES)
    for term in terms:
        normalized_term = term.translate(LIGATURES)
        for match in re.finditer(re.escape(normalized_term), normalized_text, flags=re.IGNORECASE):
            if len(highlights) >= max_terms:
                return highlights
            highlights.append(Highlight(start=match.start(), end=match.end(), term=term))
            break
    highlights.sort(key=lambda item: (item.start, item.end, item.term.lower()))
    return highlights


def chunk_context_to_dict(context: ChunkContext) -> dict[str, object]:
    return {
        "article_id": context.article_id,
        "chunk_id": context.chunk_id,
        "title": context.title,
        "doi": context.doi,
        "requested_chunk_index": context.requested_chunk_index,
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "role": chunk.role,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "source_type": chunk.source_type,
                "text_layer": chunk.text_layer,
                "text": chunk.text,
                "highlights": [highlight.__dict__ for highlight in chunk.highlights],
            }
            for chunk in context.chunks
        ],
        "pdf_url": context.pdf_url,
        "pdf_page_url": context.pdf_page_url,
        "truncated": context.truncated,
    }


def page_range_context_to_dict(context: PageRangeContext) -> dict[str, object]:
    return {
        "article_id": context.article_id,
        "title": context.title,
        "layer": context.layer,
        "page_start": context.page_start,
        "page_end": context.page_end,
        "pages": [
            {
                "page_number": page.page_number,
                "requested_layer": page.requested_layer,
                "resolved_layer": page.resolved_layer,
                "has_usable_text": page.has_usable_text,
                "text": page.text,
                "highlights": [highlight.__dict__ for highlight in page.highlights],
            }
            for page in context.pages
        ],
        "pdf_url": context.pdf_url,
        "pdf_page_url": context.pdf_page_url,
        "truncated": context.truncated,
    }


def _validate_neighbor_count(value: int, limit: int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    if value > limit:
        raise ValueError(f"{name} exceeds CONTEXT_MAX_NEIGHBOR_CHUNKS={limit}")


def _effective_char_limit(requested: int | None, configured: int) -> int:
    if requested is None:
        return configured
    if requested <= 0:
        raise ValueError("max_chars must be positive")
    return min(requested, configured)


def _chunk_role(chunk_index: int, requested_index: int) -> ChunkRole:
    if chunk_index < requested_index:
        return "previous"
    if chunk_index > requested_index:
        return "next"
    return "requested"


def _truncate_chunk_rows(chunks: list[Chunk], requested_id: uuid.UUID, max_chars: int) -> tuple[list[tuple[Chunk, str]], bool]:
    requested_chunk = next((chunk for chunk in chunks if chunk.id == requested_id), None)
    if requested_chunk is None:
        return [], True
    requested_text = requested_chunk.text
    truncated = False
    if len(requested_text) > max_chars:
        requested_text = requested_text[:max_chars]
        truncated = True

    remaining = max_chars - len(requested_text)
    selected_by_id: dict[uuid.UUID, tuple[Chunk, str]] = {requested_chunk.id: (requested_chunk, requested_text)}
    for chunk in chunks:
        if chunk.id == requested_id:
            continue
        if len(chunk.text) <= remaining:
            selected_by_id[chunk.id] = (chunk, chunk.text)
            remaining -= len(chunk.text)
        else:
            truncated = True
    selected = [selected_by_id[chunk.id] for chunk in chunks if chunk.id in selected_by_id]
    return selected, truncated


def _truncate_pages(pages: list[PageEvidence], max_chars: int) -> tuple[list[PageEvidence], bool]:
    total = 0
    selected: list[PageEvidence] = []
    truncated = False
    for page in pages:
        text = page.text
        if total + len(text) <= max_chars:
            selected.append(page)
            total += len(text)
            continue
        remaining = max_chars - total
        if remaining > 0:
            selected.append(
                PageEvidence(
                    article_id=page.article_id,
                    title=page.title,
                    page_number=page.page_number,
                    requested_layer=page.requested_layer,
                    resolved_layer=page.resolved_layer,
                    has_usable_text=page.has_usable_text,
                    text=text[:remaining],
                    pdf_url=page.pdf_url,
                    pdf_page_url=page.pdf_page_url,
                    layer_pdf_url=page.layer_pdf_url,
                )
            )
        truncated = True
        break
    return selected, truncated
