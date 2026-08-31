from __future__ import annotations

import re
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import numpy as np
from sqlalchemy import Select, case, exists, func, literal, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings, get_settings
from app.db.models import Article, ArticleTag, Chunk, Collection
from app.documents.service import build_pdf_url
from app.retrieval.cross_lingual import QueryBundle, build_query_bundle, detect_query_language, query_bundle_metadata
from app.retrieval.reranking import rerank_cross_lingual_results as feature_rerank_cross_lingual_results
from app.retrieval.vector_index import LoadedVectorIndex, embed_query_with_fastembed, load_current_vector_index_generation

STOPWORDS = {"and", "in", "or", "the", "using", "vs", "with"}
LIGATURES = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"})
MANDATORY_SCIENTIFIC_TERMS = {
    "ACN",
    "DEC",
    "DMA",
    "DMAC",
    "DMF",
    "DME",
    "DMSO",
    "EC",
    "EMC",
    "GBL",
    "IPA",
    "MeOH",
    "NMP",
    "PC",
    "PFSA",
    "SL",
    "THF",
}
RetrievalMethod = Literal["exact", "semantic", "semantic_multilingual", "hybrid", "hybrid_cross_lingual"]
SUPPORTED_RETRIEVAL_METHODS: tuple[RetrievalMethod, ...] = (
    "exact",
    "semantic",
    "semantic_multilingual",
    "hybrid",
    "hybrid_cross_lingual",
)
CONCRETE_RETRIEVAL_METHODS: dict[RetrievalMethod, str] = {
    "exact": "exact_ilike",
    "semantic": "semantic_cosine",
    "semantic_multilingual": "semantic_multilingual_cosine",
    "hybrid": "hybrid_rrf",
    "hybrid_cross_lingual": "hybrid_cross_lingual_rrf",
}
QueryEmbeddingProvider = Callable[[str, str], Any]
GroupBy = Literal["none", "article"]


@dataclass(frozen=True)
class SearchFilters:
    article_id: uuid.UUID | None = None
    doi: str | None = None
    year: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    journal: str | None = None
    source_type: str | None = None
    text_layer: str | None = None
    tag_type: str | None = None
    tag_value: str | None = None

    @classmethod
    def normalize(
        cls,
        *,
        article_id: uuid.UUID | str | None = None,
        doi: str | None = None,
        year: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        journal: str | None = None,
        source_type: str | None = None,
        text_layer: str | None = None,
        tag_type: str | None = None,
        tag_value: str | None = None,
    ) -> SearchFilters:
        if year is not None and (year_from is not None or year_to is not None):
            raise ValueError("year cannot be combined with year_from or year_to")
        normalized_article_id = uuid.UUID(str(article_id)) if article_id is not None else None
        return cls(
            article_id=normalized_article_id,
            doi=_blank_to_none(doi),
            year=year,
            year_from=year_from,
            year_to=year_to,
            journal=_blank_to_none(journal),
            source_type=_blank_to_none(source_type),
            text_layer=_blank_to_none(text_layer),
            tag_type=_blank_to_none(tag_type),
            tag_value=_blank_to_none(tag_value),
        )

    def as_metadata(self) -> dict[str, object]:
        values = {
            "article_id": str(self.article_id) if self.article_id is not None else None,
            "doi": self.doi,
            "year": self.year,
            "year_from": self.year_from,
            "year_to": self.year_to,
            "journal": self.journal,
            "source_type": self.source_type,
            "text_layer": self.text_layer,
            "tag_type": self.tag_type,
            "tag_value": self.tag_value,
        }
        return {key: value for key, value in values.items() if value is not None}


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
    full_text: str | None = None
    text_layer: str = "original"
    year: int | None = None
    journal: str | None = None
    method_scores: dict[str, float] = field(default_factory=dict)
    method_ranks: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchGroup:
    article_id: str
    title: str | None
    doi: str | None
    year: int | None
    journal: str | None
    best_score: float
    best_page_start: int
    best_page_end: int
    result_count: int
    total_result_count: int
    results: list[SearchResult]


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: list[SearchResult]
    metadata: dict[str, object] = field(default_factory=dict)
    groups: list[SearchGroup] = field(default_factory=list)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def apply_search_filters(statement: Select[Any], filters: SearchFilters) -> Select[Any]:
    if filters.article_id is not None:
        statement = statement.where(Article.id == filters.article_id)
    if filters.doi is not None:
        statement = statement.where(func.lower(Article.doi) == filters.doi.lower())
    if filters.year is not None:
        statement = statement.where(Article.year == filters.year)
    if filters.year_from is not None:
        statement = statement.where(Article.year >= filters.year_from)
    if filters.year_to is not None:
        statement = statement.where(Article.year <= filters.year_to)
    if filters.journal is not None:
        statement = statement.where(func.lower(Article.journal) == filters.journal.lower())
    if filters.source_type is not None:
        statement = statement.where(Chunk.source_type == filters.source_type)
    if filters.text_layer is not None:
        statement = statement.where(Chunk.text_layer == filters.text_layer)
    if filters.tag_type is not None or filters.tag_value is not None:
        tag_clause = select(ArticleTag.id).where(ArticleTag.article_id == Article.id)
        if filters.tag_type is not None:
            tag_clause = tag_clause.where(ArticleTag.tag_type == filters.tag_type)
        if filters.tag_value is not None:
            tag_clause = tag_clause.where(ArticleTag.tag_value == filters.tag_value)
        statement = statement.where(exists(tag_clause))
    return statement


def _escape_like(query: str) -> str:
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _query_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    terms = [term.strip("-").translate(LIGATURES) for term in raw_terms]
    return [term for term in terms if len(term) >= 2 and term.lower() not in STOPWORDS]


def _mandatory_query_terms(query: str) -> list[str]:
    required: list[str] = []
    for term in _query_terms(query):
        normalized = term.upper()
        if normalized in {item.upper() for item in MANDATORY_SCIENTIFIC_TERMS} and normalized not in required:
            required.append(normalized)
    return required


def _text_contains_mandatory_terms(text: str, terms: list[str]) -> bool:
    if not terms:
        return True
    normalized_text = text.translate(LIGATURES)
    return all(re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", normalized_text, flags=re.IGNORECASE) for term in terms)


def _candidate_limit_for_mandatory_terms(top_k: int, mandatory_terms: list[str]) -> int:
    if not mandatory_terms:
        return top_k
    return top_k * 20


def make_snippet(text: str, query: str, radius: int = 140) -> str:
    normalized = re.sub(r"\s+", " ", text.translate(LIGATURES)).strip()
    if not normalized:
        return ""
    match = re.search(re.escape(query), normalized, flags=re.IGNORECASE)
    if match is None:
        for term in [*_mandatory_query_terms(query), *_query_terms(query)]:
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


def _search_statement(
    query: str,
    collection: Collection,
    top_k: int,
    filters: SearchFilters | None = None,
) -> Select[tuple[Chunk, Article, int]]:
    lowered_text = func.lower(Chunk.text)
    phrase_pattern = f"%{_escape_like(query)}%"
    terms = _query_terms(query)
    patterns = [f"%{_escape_like(term)}%" for term in terms]
    text_filters = [Chunk.text.ilike(phrase_pattern, escape="\\")]
    text_filters.extend(Chunk.text.ilike(pattern, escape="\\") for pattern in patterns)

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
        .where(or_(*text_filters))
        .order_by(score_expr.desc(), Chunk.chunk_index.asc())
        .limit(top_k)
    )
    return apply_search_filters(statement, filters or SearchFilters())


def _result_from_chunk_article(
    chunk: Chunk,
    article: Article,
    *,
    query: str,
    score: float,
    retrieval_method: str,
    method_scores: dict[str, float] | None = None,
    method_ranks: dict[str, int] | None = None,
) -> SearchResult:
    return SearchResult(
        article_id=str(_as_uuid(article.id)),
        chunk_id=str(_as_uuid(chunk.id)),
        title=article.title,
        doi=article.doi,
        year=getattr(article, "year", None),
        journal=getattr(article, "journal", None),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        source_type=chunk.source_type,
        text_layer=chunk.text_layer,
        snippet=make_snippet(chunk.text, query),
        full_text=chunk.text,
        score=score,
        retrieval_method=retrieval_method,
        method_scores=method_scores or {},
        method_ranks=method_ranks or {},
    )


def _metadata(filters: SearchFilters, extra: dict[str, object] | None = None) -> dict[str, object]:
    metadata = dict(extra or {})
    metadata["filters"] = filters.as_metadata()
    return metadata


def normalize_group_by(group_by: str) -> GroupBy:
    normalized = group_by.strip().lower()
    if normalized in {"none", "article"}:
        return cast(GroupBy, normalized)
    raise ValueError("group_by must be one of: none, article")


def group_results_by_article(results: list[SearchResult], *, chunks_per_article: int | None = None) -> list[SearchGroup]:
    if chunks_per_article is not None and chunks_per_article <= 0:
        raise ValueError("chunks_per_article must be positive")
    grouped: OrderedDict[str, list[SearchResult]] = OrderedDict()
    for result in results:
        grouped.setdefault(result.article_id, []).append(result)

    groups: list[SearchGroup] = []
    for article_id, article_results in grouped.items():
        visible_results = article_results[:chunks_per_article] if chunks_per_article is not None else article_results
        if not visible_results:
            continue
        best = article_results[0]
        groups.append(
            SearchGroup(
                article_id=article_id,
                title=best.title,
                doi=best.doi,
                year=best.year,
                journal=best.journal,
                best_score=best.score,
                best_page_start=best.page_start,
                best_page_end=best.page_end,
                result_count=len(visible_results),
                total_result_count=len(article_results),
                results=visible_results,
            )
        )
    return groups


def exact_search(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    source_type: str | None = None,
    filters: SearchFilters | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
) -> SearchResponse:
    normalized_query = query.strip()
    normalized_filters = filters or SearchFilters.normalize(source_type=source_type)
    normalized_group_by = normalize_group_by(group_by)
    if not normalized_query:
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")

    mandatory_terms = _mandatory_query_terms(normalized_query)
    rows = session.execute(
        _search_statement(normalized_query, collection, _candidate_limit_for_mandatory_terms(top_k, mandatory_terms), normalized_filters)
    ).all()
    results: list[SearchResult] = []
    for chunk, article, score in rows:
        if not _text_contains_mandatory_terms(chunk.text, mandatory_terms):
            continue
        results.append(
            _result_from_chunk_article(
                chunk,
                article,
                query=normalized_query,
                score=float(score or 0),
                retrieval_method="exact_ilike",
            )
        )
        if len(results) >= top_k:
            break
    metadata = _metadata(normalized_filters, {"mandatory_terms": mandatory_terms} if mandatory_terms else None)
    if normalized_group_by == "article":
        groups = group_results_by_article(results, chunks_per_article=chunks_per_article)
        metadata.update(
            {
                "group_by": "article",
                "chunks_per_article": chunks_per_article,
                "candidate_count_before_grouping": len(results),
                "group_count": len(groups),
            }
        )
        return SearchResponse(query=normalized_query, results=[], metadata=metadata, groups=groups)
    return SearchResponse(query=normalized_query, results=results, metadata=metadata)


def semantic_search(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    source_type: str | None = None,
    filters: SearchFilters | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
    *,
    settings: Settings | None = None,
    loaded_index: LoadedVectorIndex | None = None,
    query_embedder: QueryEmbeddingProvider | None = None,
    enforce_top_k_limit: bool = True,
    embedding_model_override: str | None = None,
    retrieval_method: str = "semantic_cosine",
    semantic_role: str = "default",
) -> SearchResponse:
    normalized_query = query.strip()
    normalized_filters = filters or SearchFilters.normalize(source_type=source_type)
    normalized_group_by = normalize_group_by(group_by)
    if not normalized_query:
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    active_settings = settings or get_settings()
    if enforce_top_k_limit:
        _validate_top_k(top_k, active_settings)
    embedding_model = embedding_model_override or active_settings.embedding_model
    index = loaded_index or load_current_vector_index_generation(
        session,
        data_root=active_settings.data_root,
        collection=collection_name,
        embedding_model=embedding_model,
        cache_enabled=getattr(active_settings, "vector_index_cache_enabled", False),
        cache_max_items=getattr(active_settings, "vector_index_cache_max_items", 2),
        use_mmap=getattr(active_settings, "vector_index_use_mmap", False),
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
    db_filtered_chunk_ids = _semantic_filtered_chunk_ids(session, collection_name, normalized_filters)
    mandatory_terms = _mandatory_query_terms(normalized_query)

    candidates = []
    for position, chunk_id in enumerate(index.chunk_ids):
        chunk, _article = index.rows_by_chunk_id[chunk_id]
        if (
            (db_filtered_chunk_ids is None or chunk_id in db_filtered_chunk_ids)
            and _index_row_matches_filters(chunk, _article, normalized_filters)
            and _text_contains_mandatory_terms(chunk.text, mandatory_terms)
        ):
            candidates.append((float(scores[position]), chunk_id))
    candidates.sort(key=lambda item: (-item[0], item[1]))

    results: list[SearchResult] = []
    for score, chunk_id in candidates[:top_k]:
        chunk, article = index.rows_by_chunk_id[chunk_id]
        results.append(_result_from_chunk_article(chunk, article, query=normalized_query, score=score, retrieval_method=retrieval_method))
    metadata: dict[str, object] = {
        "backend": index.manifest["backend"],
        "embedding_model": embedding_model,
        "embedding_dimension": expected_dimension,
        "manifest_sha256": index.manifest_sha256,
        "chunk_count": index.manifest["chunk_count"],
        "similarity": "cosine",
        "semantic_role": semantic_role,
    }
    if mandatory_terms:
        metadata["mandatory_terms"] = mandatory_terms
    metadata = _metadata(normalized_filters, metadata)
    if normalized_group_by == "article":
        groups = group_results_by_article(results, chunks_per_article=chunks_per_article)
        metadata.update(
            {
                "group_by": "article",
                "chunks_per_article": chunks_per_article,
                "candidate_count_before_grouping": len(results),
                "group_count": len(groups),
            }
        )
        return SearchResponse(query=normalized_query, results=[], metadata=metadata, groups=groups)
    return SearchResponse(query=normalized_query, results=results, metadata=metadata)


def semantic_multilingual_search(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    source_type: str | None = None,
    filters: SearchFilters | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
    *,
    settings: Settings | None = None,
    loaded_index: LoadedVectorIndex | None = None,
    query_embedder: QueryEmbeddingProvider | None = None,
    enforce_top_k_limit: bool = True,
) -> SearchResponse:
    active_settings = settings or get_settings()
    multilingual_model = getattr(active_settings, "multilingual_embedding_model", None)
    if not isinstance(multilingual_model, str) or not multilingual_model.strip():
        raise ValueError("multilingual_embedding_model must not be empty")
    return semantic_search(
        session,
        query,
        collection_name,
        top_k,
        source_type=source_type,
        filters=filters,
        group_by=group_by,
        chunks_per_article=chunks_per_article,
        settings=active_settings,
        loaded_index=loaded_index,
        query_embedder=query_embedder,
        enforce_top_k_limit=enforce_top_k_limit,
        embedding_model_override=multilingual_model,
        retrieval_method="semantic_multilingual_cosine",
        semantic_role="multilingual",
    )


def hybrid_search(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    source_type: str | None = None,
    filters: SearchFilters | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
    *,
    settings: Settings | None = None,
) -> SearchResponse:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    normalized_filters = filters or SearchFilters.normalize(source_type=source_type)
    normalized_group_by = normalize_group_by(group_by)
    active_settings = settings or get_settings()
    _validate_top_k(top_k, active_settings)
    candidate_k = top_k * active_settings.hybrid_candidate_multiplier
    max_candidate_k = getattr(active_settings, "hybrid_max_candidate_k", 500)
    if candidate_k > max_candidate_k:
        raise ValueError(f"hybrid candidate_k must be <= {max_candidate_k}; got {candidate_k}")
    exact_response = exact_search(session, query, collection_name, candidate_k, filters=normalized_filters)
    semantic_response = semantic_search(
        session,
        query,
        collection_name,
        candidate_k,
        filters=normalized_filters,
        settings=active_settings,
        enforce_top_k_limit=False,
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
                text_layer=evidence.text_layer,
                snippet=evidence.snippet,
                full_text=evidence.full_text,
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
    limited_results = fused_results[:top_k]
    metadata = _metadata(normalized_filters, metadata)
    if normalized_group_by == "article":
        groups = group_results_by_article(limited_results, chunks_per_article=chunks_per_article)
        metadata.update(
            {
                "group_by": "article",
                "chunks_per_article": chunks_per_article,
                "candidate_count_before_grouping": len(limited_results),
                "group_count": len(groups),
            }
        )
        return SearchResponse(query=exact_response.query, results=[], metadata=metadata, groups=groups)
    return SearchResponse(query=exact_response.query, results=limited_results, metadata=metadata)


def hybrid_cross_lingual_search(
    session: Session,
    query: str,
    collection_name: str = "literature",
    top_k: int = 10,
    source_type: str | None = None,
    filters: SearchFilters | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
    *,
    settings: Settings | None = None,
) -> SearchResponse:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    normalized_filters = filters or SearchFilters.normalize(source_type=source_type)
    normalized_group_by = normalize_group_by(group_by)
    active_settings = settings or get_settings()
    _validate_top_k(top_k, active_settings)
    bundle = build_query_bundle(query)

    variant_responses: list[SearchResponse] = []
    variant_hits: list[dict[str, object]] = []
    variant_top_k = _cross_lingual_variant_top_k(bundle, top_k=top_k, settings=active_settings)
    for variant_index, variant in enumerate(bundle.variants):
        if variant.source == "original":
            response = hybrid_search(
                session,
                variant.text,
                collection_name,
                variant_top_k,
                filters=normalized_filters,
                settings=active_settings,
            )
        else:
            response = exact_search(session, variant.text, collection_name, variant_top_k, filters=normalized_filters)
        variant_responses.append(response)
        variant_hits.append(
            {
                "variant_index": variant_index,
                "language": variant.language,
                "source": variant.source,
                "result_count": len(response.results),
            }
        )

    component_results: dict[str, dict[str, tuple[int, SearchResult]]] = {}
    for variant_index, response in enumerate(variant_responses):
        variant = bundle.variants[variant_index]
        method_name = f"{variant.source}_{variant.language}_{variant_index}"
        for rank, result in enumerate(response.results, start=1):
            component_results.setdefault(result.chunk_id, {})[method_name] = (rank, result)

    rrf_k = active_settings.hybrid_rrf_k
    fused_results: list[SearchResult] = []
    for chunk_id, components in component_results.items():
        method_ranks = {method: rank_result[0] for method, rank_result in components.items()}
        method_scores = {method: rank_result[1].score for method, rank_result in components.items()}
        fused_score = sum(1.0 / (rrf_k + rank) for rank in method_ranks.values())
        best_component = min(components.values(), key=lambda item: item[0])
        evidence = best_component[1]
        fused_results.append(
            SearchResult(
                article_id=evidence.article_id,
                chunk_id=chunk_id,
                title=evidence.title,
                doi=evidence.doi,
                page_start=evidence.page_start,
                page_end=evidence.page_end,
                source_type=evidence.source_type,
                text_layer=evidence.text_layer,
                snippet=evidence.snippet,
                full_text=evidence.full_text,
                score=fused_score,
                retrieval_method="hybrid_cross_lingual_rrf",
                method_scores=method_scores,
                method_ranks=method_ranks,
            )
        )

    reranked = _rerank_cross_lingual_results(
        fused_results,
        bundle,
        window_size=_cross_lingual_rerank_window_size(bundle, top_k=top_k, candidate_window=variant_top_k),
    )
    fused_results = reranked.results
    diversified_results = _diversify_cross_lingual_results(fused_results, preferred_per_article=2)
    language_diverse_results, language_diversity_metadata = _ensure_cross_language_presence(
        diversified_results,
        query_language=bundle.language,
        top_k=top_k,
    )
    limited_results = language_diverse_results[:top_k]
    metadata = _metadata(
        normalized_filters,
        {
            "fusion": "reciprocal_rank_fusion",
            "retrieval_method": "hybrid_cross_lingual_rrf",
            "rrf_k": rrf_k,
            "component_methods": ["hybrid_rrf", "exact_ilike_glossary"],
            "cross_lingual": query_bundle_metadata(bundle, variant_hits),
            "reranking": reranked.metadata,
            "language_diversity": language_diversity_metadata,
        },
    )
    if normalized_group_by == "article":
        groups = group_results_by_article(limited_results, chunks_per_article=chunks_per_article)
        metadata.update(
            {
                "group_by": "article",
                "chunks_per_article": chunks_per_article,
                "candidate_count_before_grouping": len(limited_results),
                "group_count": len(groups),
            }
        )
        return SearchResponse(query=bundle.original, results=[], metadata=metadata, groups=groups)
    return SearchResponse(query=bundle.original, results=limited_results, metadata=metadata)


def _cross_lingual_variant_top_k(bundle: QueryBundle, *, top_k: int, settings: Settings) -> int:
    wide_window_concepts = {
        "casting_annealing",
        "ec_sl_solvents",
        "mixing_temperature",
        "phase_diagram",
        "physicochemical_properties",
        "solution_casting_morphology",
        "transport",
    }
    if "swelling_degree_comparison" in bundle.matched_concepts:
        multiplier = 20
    elif _has_standalone_water_thermodynamics_query(bundle):
        multiplier = 5
    elif wide_window_concepts.intersection(bundle.matched_concepts):
        multiplier = 5
    else:
        multiplier = 2
    return min(top_k * multiplier, getattr(settings, "search_max_top_k", 100))


def _fuse_cross_lingual_channel_results(
    channel_responses: list[tuple[str, SearchResponse]],
    *,
    rrf_k: int,
    retrieval_method: str,
) -> list[SearchResult]:
    component_results: dict[str, dict[str, tuple[int, SearchResult]]] = {}
    for method_name, response in channel_responses:
        for rank, result in enumerate(response.results, start=1):
            component_results.setdefault(result.chunk_id, {})[method_name] = (rank, result)

    fused_results: list[SearchResult] = []
    for chunk_id, components in component_results.items():
        method_ranks = {method: rank_result[0] for method, rank_result in components.items()}
        method_scores = {method: rank_result[1].score for method, rank_result in components.items()}
        fused_score = sum(1.0 / (rrf_k + rank) for rank in method_ranks.values())
        best_component = min(components.values(), key=lambda item: item[0])
        evidence = best_component[1]
        fused_results.append(
            SearchResult(
                article_id=evidence.article_id,
                chunk_id=chunk_id,
                title=evidence.title,
                doi=evidence.doi,
                page_start=evidence.page_start,
                page_end=evidence.page_end,
                source_type=evidence.source_type,
                text_layer=evidence.text_layer,
                snippet=evidence.snippet,
                full_text=evidence.full_text,
                score=fused_score,
                retrieval_method=retrieval_method,
                method_scores=method_scores,
                method_ranks=method_ranks,
            )
        )
    return fused_results


def _rerank_cross_lingual_results(results: list[SearchResult], bundle: QueryBundle, *, window_size: int) -> Any:
    legacy_ordered = _legacy_rerank_cross_lingual_results(results, bundle)
    feature_ordered = _diversify_cross_lingual_results(legacy_ordered, preferred_per_article=2)
    window = feature_ordered[:window_size]
    tail = feature_ordered[window_size:]
    reranked_window = feature_rerank_cross_lingual_results(
        window,
        original_query=bundle.original,
        query_language=bundle.language,
        query_variants=[(variant.source, variant.text) for variant in bundle.variants],
    )
    return reranked_window.__class__(
        results=[*reranked_window.results, *tail],
        metadata={
            **reranked_window.metadata,
            "legacy_window_preserved": True,
            "window_size": window_size,
            "feature_window_selection": "article_diverse",
        },
    )


def _cross_lingual_rerank_window_size(bundle: QueryBundle, *, top_k: int, candidate_window: int) -> int:
    if "swelling_degree_comparison" in bundle.matched_concepts:
        return candidate_window
    if {
        "casting_annealing",
        "mixing_temperature",
        "phase_diagram",
        "physicochemical_properties",
        "solution_casting_morphology",
        "transport",
    }.intersection(bundle.matched_concepts):
        return candidate_window
    if _has_standalone_water_thermodynamics_query(bundle):
        return candidate_window
    if bundle.language == "mixed" or _mandatory_query_terms(bundle.original):
        return candidate_window
    return top_k


def _has_standalone_water_thermodynamics_query(bundle: QueryBundle) -> bool:
    return (
        "water_interaction" in bundle.matched_concepts
        and "thermodynamic_interaction" in bundle.matched_concepts
        and "lithium_form" not in bundle.matched_concepts
    )


def _legacy_rerank_cross_lingual_results(results: list[SearchResult], bundle: QueryBundle) -> list[SearchResult]:
    variant_terms = [
        (variant.source, set(_query_terms(variant.text)))
        for variant in bundle.variants
        if _query_terms(variant.text)
    ]
    article_variant_hits: dict[str, set[int]] = {}
    article_glossary_hits: dict[str, set[int]] = {}
    article_term_hits: dict[str, set[str]] = {}
    result_term_hits: dict[str, set[str]] = {}
    result_language_bonus: dict[str, int] = {}
    original_positions = {result.chunk_id: index for index, result in enumerate(results)}
    for result in results:
        text = _cross_lingual_result_text(result)
        result_language_bonus[result.chunk_id] = _cross_language_result_bonus(bundle.language, result)
        matched_terms: set[str] = set()
        for variant_index, (source, terms) in enumerate(variant_terms):
            terms_in_result = {term for term in terms if _cross_lingual_term_matches(term, text)}
            if not terms_in_result:
                continue
            article_variant_hits.setdefault(result.article_id, set()).add(variant_index)
            if source == "glossary":
                article_glossary_hits.setdefault(result.article_id, set()).add(variant_index)
            matched_terms.update(terms_in_result)
        result_term_hits[result.chunk_id] = matched_terms
        article_term_hits.setdefault(result.article_id, set()).update(matched_terms)

    return sorted(
        results,
        key=lambda result: (
            -len(article_glossary_hits.get(result.article_id, set())),
            -len(article_variant_hits.get(result.article_id, set())),
            -len(article_term_hits.get(result.article_id, set())),
            -len(result_term_hits.get(result.chunk_id, set())),
            -result_language_bonus.get(result.chunk_id, 0),
            min(result.method_ranks.values()) if result.method_ranks else len(results) + 1,
            -result.score,
            original_positions[result.chunk_id],
        ),
    )


def _cross_lingual_result_text(result: SearchResult) -> str:
    return "\n".join(
        item
        for item in (
            result.title or "",
            result.snippet,
            result.full_text or "",
        )
        if item
    ).lower().translate(LIGATURES)


def _cross_language_result_bonus(query_language: str, result: SearchResult) -> int:
    if query_language not in {"en", "ru"}:
        return 0
    result_language, _diagnostics = detect_query_language(
        "\n".join(item for item in (result.title or "", result.snippet) if item)
    )
    if query_language == "en" and result_language == "ru":
        return 1
    if query_language == "ru" and result_language == "en":
        return 1
    return 0


def _cross_lingual_term_matches(term: str, text: str) -> bool:
    normalized = term.lower().translate(LIGATURES)
    if normalized in text:
        return True
    if "-" in normalized:
        return normalized.replace("-", " ") in text
    return False


def _diversify_cross_lingual_results(results: list[SearchResult], *, preferred_per_article: int) -> list[SearchResult]:
    selected: list[SearchResult] = []
    deferred: list[SearchResult] = []
    article_counts: dict[str, int] = {}
    for result in results:
        count = article_counts.get(result.article_id, 0)
        if count < preferred_per_article:
            selected.append(result)
        else:
            deferred.append(result)
        article_counts[result.article_id] = count + 1
    return [*selected, *deferred]


def _ensure_cross_language_presence(
    results: list[SearchResult],
    *,
    query_language: str,
    top_k: int,
) -> tuple[list[SearchResult], dict[str, object]]:
    if query_language not in {"en", "ru"} or top_k <= 1 or len(results) <= top_k:
        return results, {"applied": False, "reason": "not_applicable"}
    visible = results[:top_k]
    if any(_cross_language_result_bonus(query_language, result) for result in visible):
        return results, {"applied": False, "reason": "already_present"}
    replacement_index = next(
        (index for index, result in enumerate(results[top_k:], start=top_k) if _cross_language_result_bonus(query_language, result)),
        None,
    )
    if replacement_index is None:
        return results, {"applied": False, "reason": "no_cross_language_candidate"}

    replacement = results[replacement_index]
    adjusted = [*visible[:-1], replacement, *results[top_k:replacement_index], visible[-1], *results[replacement_index + 1 :]]
    return adjusted, {
        "applied": True,
        "query_language": query_language,
        "inserted_chunk_id": replacement.chunk_id,
        "inserted_article_id": replacement.article_id,
        "inserted_from_rank": replacement_index + 1,
        "inserted_at_rank": top_k,
    }


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
    filters: SearchFilters | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
    settings: Settings | None = None,
) -> SearchResponse:
    normalized_method = normalize_retrieval_method(method)
    normalized_filters = filters or SearchFilters.normalize(source_type=source_type)
    _validate_top_k(top_k, settings or get_settings())
    if normalized_method == "exact":
        return exact_search(
            session,
            query,
            collection_name,
            top_k,
            filters=normalized_filters,
            group_by=group_by,
            chunks_per_article=chunks_per_article,
        )
    if normalized_method == "semantic":
        return semantic_search(
            session,
            query,
            collection_name,
            top_k,
            filters=normalized_filters,
            group_by=group_by,
            chunks_per_article=chunks_per_article,
            settings=settings,
        )
    if normalized_method == "semantic_multilingual":
        return semantic_multilingual_search(
            session,
            query,
            collection_name,
            top_k,
            filters=normalized_filters,
            group_by=group_by,
            chunks_per_article=chunks_per_article,
            settings=settings,
        )
    if normalized_method == "hybrid":
        return hybrid_search(
            session,
            query,
            collection_name,
            top_k,
            filters=normalized_filters,
            group_by=group_by,
            chunks_per_article=chunks_per_article,
            settings=settings,
        )
    if normalized_method == "hybrid_cross_lingual":
        return hybrid_cross_lingual_search(
            session,
            query,
            collection_name,
            top_k,
            filters=normalized_filters,
            group_by=group_by,
            chunks_per_article=chunks_per_article,
            settings=settings,
        )
    raise AssertionError(f"unhandled retrieval method: {normalized_method}")


def _validate_top_k(top_k: int, settings: Settings) -> None:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    max_top_k = getattr(settings, "search_max_top_k", 100)
    if top_k > max_top_k:
        raise ValueError(f"top_k must be <= {max_top_k}; got {top_k}")


def search_response_to_dict(response: SearchResponse) -> dict[str, object]:
    def result_to_payload(result: SearchResult) -> dict[str, object]:
        result_payload: dict[str, object] = {
            "article_id": result.article_id,
            "chunk_id": result.chunk_id,
            "title": result.title,
            "doi": result.doi,
            "year": result.year,
            "journal": result.journal,
            "page_start": result.page_start,
            "page_end": result.page_end,
            "source_type": result.source_type,
            "text_layer": result.text_layer,
            "pdf_url": build_pdf_url(result.article_id, "original"),
            "pdf_page_url": build_pdf_url(result.article_id, "original", result.page_start),
            "context_url": (
                f"/articles/{result.article_id}/chunks/{result.chunk_id}/context"
                "?before=1&after=1"
            ),
            "page_context_url": (
                f"/articles/{result.article_id}/pages/context"
                f"?page_start={result.page_start}&page_end={result.page_end}&layer=selected"
            ),
            "snippet": result.snippet,
            "score": result.score,
            "retrieval_method": result.retrieval_method,
        }
        if result.method_scores:
            result_payload["method_scores"] = result.method_scores
        if result.method_ranks:
            result_payload["method_ranks"] = result.method_ranks
        return result_payload

    results = []
    for result in response.results:
        results.append(result_to_payload(result))
    payload: dict[str, object] = {
        "query": response.query,
        "results": results,
    }
    if response.groups:
        payload.pop("results")
        payload["groups"] = [
            {
                "article_id": group.article_id,
                "title": group.title,
                "doi": group.doi,
                "year": group.year,
                "journal": group.journal,
                "best_score": group.best_score,
                "best_page_start": group.best_page_start,
                "best_page_end": group.best_page_end,
                "result_count": group.result_count,
                "total_result_count": group.total_result_count,
                "results": [result_to_payload(result) for result in group.results],
            }
            for group in response.groups
        ]
    if response.metadata:
        payload["metadata"] = response.metadata
    return payload


def _index_row_matches_filters(chunk: Chunk, article: Article, filters: SearchFilters) -> bool:
    if filters.article_id is not None and _as_uuid(article.id) != filters.article_id:
        return False
    if filters.doi is not None and (article.doi is None or article.doi.lower() != filters.doi.lower()):
        return False
    if filters.year is not None and article.year != filters.year:
        return False
    if filters.year_from is not None and (article.year is None or article.year < filters.year_from):
        return False
    if filters.year_to is not None and (article.year is None or article.year > filters.year_to):
        return False
    if filters.journal is not None and (article.journal is None or article.journal.lower() != filters.journal.lower()):
        return False
    if filters.source_type is not None and chunk.source_type != filters.source_type:
        return False
    if filters.text_layer is not None and chunk.text_layer != filters.text_layer:
        return False
    if filters.tag_type is not None or filters.tag_value is not None:
        tags = getattr(article, "tags", None)
        if tags is None:
            return True
        if not any(
            (filters.tag_type is None or tag.tag_type == filters.tag_type)
            and (filters.tag_value is None or tag.tag_value == filters.tag_value)
            for tag in tags
        ):
            return False
    return True


def _semantic_filtered_chunk_ids(session: Session, collection_name: str, filters: SearchFilters) -> set[str] | None:
    if filters.tag_type is None and filters.tag_value is None:
        return None
    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")
    statement = select(Chunk.id).join(Article, Chunk.article_id == Article.id).where(Article.collection_id == collection.id)
    statement = apply_search_filters(statement, filters)
    return {str(_as_uuid(chunk_id)) for chunk_id in session.scalars(statement)}


def _as_uuid(value: uuid.UUID | object) -> uuid.UUID | object:
    return value
