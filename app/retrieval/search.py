from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection


@dataclass(frozen=True)
class SearchResult:
    article_id: str
    chunk_id: str
    title: str | None
    doi: str | None
    page_start: int
    page_end: int
    snippet: str
    score: float
    retrieval_method: str


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: list[SearchResult]


def _escape_like(query: str) -> str:
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def make_snippet(text: str, query: str, radius: int = 140) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""
    match = re.search(re.escape(query), normalized, flags=re.IGNORECASE)
    if match is None:
        return normalized[: radius * 2].strip()
    start = max(0, match.start() - radius)
    end = min(len(normalized), match.end() + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end].strip()}{suffix}"


def _search_statement(query: str, collection: Collection, top_k: int) -> Select[tuple[Chunk, Article, int]]:
    pattern = f"%{_escape_like(query)}%"
    score_expr = func.length(Chunk.text) - func.length(func.replace(func.lower(Chunk.text), query.lower(), ""))
    return (
        select(Chunk, Article, score_expr.label("score"))
        .join(Article, Chunk.article_id == Article.id)
        .where(Article.collection_id == collection.id)
        .where(Chunk.text.ilike(pattern, escape="\\"))
        .order_by(score_expr.desc(), Chunk.chunk_index.asc())
        .limit(top_k)
    )


def exact_search(session: Session, query: str, collection_name: str = "literature", top_k: int = 10) -> SearchResponse:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")

    rows = session.execute(_search_statement(normalized_query, collection, top_k)).all()
    results: list[SearchResult] = []
    for chunk, article, score in rows:
        results.append(
            SearchResult(
                article_id=str(_as_uuid(article.id)),
                chunk_id=str(_as_uuid(chunk.id)),
                title=article.title,
                doi=article.doi,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                snippet=make_snippet(chunk.text, normalized_query),
                score=float(score or 0),
                retrieval_method="exact_ilike",
            )
        )
    return SearchResponse(query=normalized_query, results=results)


def search_response_to_dict(response: SearchResponse) -> dict[str, object]:
    return {
        "query": response.query,
        "results": [
            {
                "article_id": result.article_id,
                "chunk_id": result.chunk_id,
                "title": result.title,
                "doi": result.doi,
                "page_start": result.page_start,
                "page_end": result.page_end,
                "snippet": result.snippet,
                "score": result.score,
                "retrieval_method": result.retrieval_method,
            }
            for result in response.results
        ],
    }


def _as_uuid(value: uuid.UUID | object) -> uuid.UUID | object:
    return value
