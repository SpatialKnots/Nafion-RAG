from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import numpy as np
from sqlalchemy import Select, case, func, literal, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings, get_settings
from app.db.models import Article, Chunk, Collection
from app.retrieval.vector_index import LoadedVectorIndex, embed_query_with_fastembed, load_local_vector_index

STOPWORDS = {"and", "in", "or", "the", "using", "vs", "with"}
LIGATURES = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"})
RetrievalMethod = Literal["exact", "semantic", "hybrid"]
SUPPORTED_RETRIEVAL_METHODS: tuple[RetrievalMethod, ...] = ("exact", "semantic", "hybrid")
CONCRETE_RETRIEVAL_METHODS: dict[RetrievalMethod, str] = {
    "exact": "exact_ilike",
    "semantic": "semantic_cosine",
    "hybrid": "hybrid_rrf",
}
QueryEmbeddingProvider = Callable[[str, str], Any]


@dataclass(frozen=True)
class SearchResult:
    article_id: str
    chunk_id: str
    title: str | None
    doi: str | None
    page_start: int
    page_end: int
    source_type: str
    snippet: str
    score: float
    retrieval_method: str
    method_scores: dict[str, float] = field(default_factory=dict)
    method_ranks: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: list[SearchResult]
    metadata: dict[str, object] = field(default_factory=dict)


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


def _search_statement(query: str, collection: Collection, top_k: int, source_type: str | None = None) -> Select[tuple[Chunk, Article, int]]:
    lowered_text = func.lower(Chunk.text)
    phrase_pattern = f"%{_escape_like(query)}%"
    terms = _query_terms(query)
    patterns = [f"%{_escape_like(term)}%" for term in terms]
    filters = [Chunk.text.ilike(phrase_pattern, escape="\\")]
    filters.extend(Chunk.text.ilike(pattern, escape="\\") for pattern in patterns)

    score_expr = cast(ColumnElement[int], case((Chunk.text.ilike(phrase_pattern, escape="\\"), literal(1000)), else_=literal(0)))
    for term in terms:
        lowered_term = term.lower()
        score_expr += func.length(lowered_text) - func.length(func.replace(lowered_text, lowered_term, ""))

    if not terms:
        score_expr += func.length(lowered_text) - func.length(func.replace(lowered_text, query.lower(), ""))

    statement = (
        select(Chunk, Article, score_expr.label("score"))
        .join(Article, Chunk.article_id == Article.id)
        .where(Article.collection_id == collection.id)
        .where(or_(*filters))
        .order_by(score_expr.desc(), Chunk.chunk_index.asc())
        .limit(top_k)
    )
    if source_type is not None:
        statement = statement.where(Chunk.source_type == source_type)
    return statement


def exact_search(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    source_type: str | None = None,
) -> SearchResponse:
    normalized_query = query.strip()
    normalized_source_type = source_type.strip() if source_type else None
    if not normalized_query:
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")

    rows = session.execute(_search_statement(normalized_query, collection, top_k, normalized_source_type)).all()
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
                source_type=chunk.source_type,
                snippet=make_snippet(chunk.text, normalized_query),
                score=float(score or 0),
                retrieval_method="exact_ilike",
            )
        )
    return SearchResponse(query=normalized_query, results=results)


def semantic_search(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    source_type: str | None = None,
    *,
    settings: Settings | None = None,
    loaded_index: LoadedVectorIndex | None = None,
    query_embedder: QueryEmbeddingProvider | None = None,
) -> SearchResponse:
    normalized_query = query.strip()
    normalized_source_type = source_type.strip() if source_type else None
    if not normalized_query:
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    active_settings = settings or get_settings()
    embedding_model = active_settings.embedding_model
    index = loaded_index or load_local_vector_index(
        session,
        data_root=active_settings.data_root,
        collection=collection_name,
        embedding_model=embedding_model,
    )
    manifest_model = index.manifest.get("embedding_model")
    if manifest_model != embedding_model:
        raise ValueError(f"Semantic index model mismatch: expected {embedding_model}, got {manifest_model}")

    provider = query_embedder or embed_query_with_fastembed
    query_vector = np.asarray(provider(normalized_query, embedding_model), dtype=np.float32)
    expected_dimension = int(index.manifest["embedding_dimension"])
    if query_vector.ndim != 1 or query_vector.shape[0] != expected_dimension:
        raise ValueError(f"query embedding dimension mismatch: expected {expected_dimension}, got shape {query_vector.shape}")
    if not np.isfinite(query_vector).all():
        raise ValueError("query embedding contains NaN or infinite values")
    query_norm = float(np.linalg.norm(query_vector))
    if query_norm == 0:
        raise ValueError("query embedding has zero length")
    normalized_vector = query_vector / query_norm
    scores = index.embeddings @ normalized_vector

    candidates = []
    for position, chunk_id in enumerate(index.chunk_ids):
        chunk, _article = index.rows_by_chunk_id[chunk_id]
        if normalized_source_type is None or chunk.source_type == normalized_source_type:
            candidates.append((float(scores[position]), chunk_id))
    candidates.sort(key=lambda item: (-item[0], item[1]))

    results: list[SearchResult] = []
    for score, chunk_id in candidates[:top_k]:
        chunk, article = index.rows_by_chunk_id[chunk_id]
        results.append(
            SearchResult(
                article_id=str(_as_uuid(article.id)),
                chunk_id=str(_as_uuid(chunk.id)),
                title=article.title,
                doi=article.doi,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                source_type=chunk.source_type,
                snippet=make_snippet(chunk.text, normalized_query),
                score=score,
                retrieval_method="semantic_cosine",
            )
        )
    metadata: dict[str, object] = {
        "backend": index.manifest["backend"],
        "embedding_model": embedding_model,
        "embedding_dimension": expected_dimension,
        "manifest_sha256": index.manifest_sha256,
        "chunk_count": index.manifest["chunk_count"],
        "similarity": "cosine",
    }
    return SearchResponse(query=normalized_query, results=results, metadata=metadata)


def hybrid_search(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    source_type: str | None = None,
    *,
    settings: Settings | None = None,
) -> SearchResponse:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    active_settings = settings or get_settings()
    candidate_k = top_k * active_settings.hybrid_candidate_multiplier
    exact_response = exact_search(session, query, collection_name, candidate_k, source_type=source_type)
    semantic_response = semantic_search(
        session,
        query,
        collection_name,
        candidate_k,
        source_type=source_type,
        settings=active_settings,
    )

    component_results: dict[str, dict[str, tuple[int, SearchResult]]] = {}
    for method_name, response in (
        ("exact_ilike", exact_response),
        ("semantic_cosine", semantic_response),
    ):
        for rank, result in enumerate(response.results, start=1):
            component_results.setdefault(result.chunk_id, {})[method_name] = (rank, result)

    fused_results: list[SearchResult] = []
    for chunk_id, components in component_results.items():
        method_ranks = {method: rank_result[0] for method, rank_result in components.items()}
        method_scores = {method: rank_result[1].score for method, rank_result in components.items()}
        fused_score = sum(1.0 / (active_settings.hybrid_rrf_k + rank) for rank in method_ranks.values())
        evidence_component = components.get("exact_ilike") or components["semantic_cosine"]
        evidence = evidence_component[1]
        fused_results.append(
            SearchResult(
                article_id=evidence.article_id,
                chunk_id=chunk_id,
                title=evidence.title,
                doi=evidence.doi,
                page_start=evidence.page_start,
                page_end=evidence.page_end,
                source_type=evidence.source_type,
                snippet=evidence.snippet,
                score=fused_score,
                retrieval_method="hybrid_rrf",
                method_scores=method_scores,
                method_ranks=method_ranks,
            )
        )

    missing_rank = candidate_k + 1
    fused_results.sort(
        key=lambda result: (
            -result.score,
            result.method_ranks.get("exact_ilike", missing_rank),
            result.method_ranks.get("semantic_cosine", missing_rank),
            result.chunk_id,
        )
    )
    metadata = dict(semantic_response.metadata)
    metadata.update(
        {
            "fusion": "reciprocal_rank_fusion",
            "retrieval_method": "hybrid_rrf",
            "rrf_k": active_settings.hybrid_rrf_k,
            "candidate_multiplier": active_settings.hybrid_candidate_multiplier,
            "candidate_k": candidate_k,
            "component_methods": ["exact_ilike", "semantic_cosine"],
        }
    )
    return SearchResponse(query=exact_response.query, results=fused_results[:top_k], metadata=metadata)


def concrete_retrieval_method(method: str) -> str:
    return CONCRETE_RETRIEVAL_METHODS[normalize_retrieval_method(method)]


def normalize_retrieval_method(method: str) -> RetrievalMethod:
    normalized = method.strip().lower()
    if normalized in SUPPORTED_RETRIEVAL_METHODS:
        return normalized
    supported = ", ".join(SUPPORTED_RETRIEVAL_METHODS)
    raise ValueError(f"Unsupported retrieval method: {method}. Supported methods: {supported}")


def search_chunks(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    *,
    method: str = "exact",
    source_type: str | None = None,
    settings: Settings | None = None,
) -> SearchResponse:
    normalized_method = normalize_retrieval_method(method)
    if normalized_method == "exact":
        return exact_search(session, query, collection_name, top_k, source_type=source_type)
    if normalized_method == "semantic":
        return semantic_search(
            session,
            query,
            collection_name,
            top_k,
            source_type=source_type,
            settings=settings,
        )
    if normalized_method == "hybrid":
        return hybrid_search(
            session,
            query,
            collection_name,
            top_k,
            source_type=source_type,
            settings=settings,
        )
    raise AssertionError(f"unhandled retrieval method: {normalized_method}")


def search_response_to_dict(response: SearchResponse) -> dict[str, object]:
    results = []
    for result in response.results:
        result_payload: dict[str, object] = {
            "article_id": result.article_id,
            "chunk_id": result.chunk_id,
            "title": result.title,
            "doi": result.doi,
            "page_start": result.page_start,
            "page_end": result.page_end,
            "source_type": result.source_type,
            "snippet": result.snippet,
            "score": result.score,
            "retrieval_method": result.retrieval_method,
        }
        if result.method_scores:
            result_payload["method_scores"] = result.method_scores
        if result.method_ranks:
            result_payload["method_ranks"] = result.method_ranks
        results.append(result_payload)
    payload: dict[str, object] = {
        "query": response.query,
        "results": results,
    }
    if response.metadata:
        payload["metadata"] = response.metadata
    return payload


def _as_uuid(value: uuid.UUID | object) -> uuid.UUID | object:
    return value
