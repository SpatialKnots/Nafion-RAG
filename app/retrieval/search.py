from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, case, func, literal, or_, select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection

STOPWORDS = {"and", "in", "or", "the", "using", "vs", "with"}
LIGATURES = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"})


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


def _query_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    terms = [term.strip("-").translate(LIGATURES) for term in raw_terms]
    return [term for term in terms if len(term) >= 2 and term.lower() not in STOPWORDS]


def make_snippet(text: str, query: str, radius: int = 140) -> str:
    normalized = re.sub(r"\s+", " ", text.translate(LIGATURES)).strip()
    if not normalized:
        return ""
    match = re.search(re.escape(query), normalized, flags=re.IGNORECASE)
    if match is None:
        for term in _query_terms(query):
            match = re.search(re.escape(term), normalized, flags=re.IGNORECASE)
            if match is not None:
                break
    if match is None:
        return normalized[: radius * 2].strip()
    start = max(0, match.start() - radius)
    end = min(len(normalized), match.end() + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end].strip()}{suffix}"


def _search_statement(query: str, collection: Collection, top_k: int) -> Select[tuple[Chunk, Article, int]]:
    lowered_text = func.lower(Chunk.text)
    phrase_pattern = f"%{_escape_like(query)}%"
    terms = _query_terms(query)
    patterns = [f"%{_escape_like(term)}%" for term in terms]
    filters = [Chunk.text.ilike(phrase_pattern, escape="\\")]
    filters.extend(Chunk.text.ilike(pattern, escape="\\") for pattern in patterns)

    score_expr = case((Chunk.text.ilike(phrase_pattern, escape="\\"), literal(1000)), else_=literal(0))
    for term in terms:
        lowered_term = term.lower()
        score_expr += func.length(lowered_text) - func.length(func.replace(lowered_text, lowered_term, ""))

    if not terms:
        score_expr += func.length(lowered_text) - func.length(func.replace(lowered_text, query.lower(), ""))

    return (
        select(Chunk, Article, score_expr.label("score"))
        .join(Article, Chunk.article_id == Article.id)
        .where(Article.collection_id == collection.id)
        .where(or_(*filters))
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
