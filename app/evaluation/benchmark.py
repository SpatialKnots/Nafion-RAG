from __future__ import annotations

import json
import os
import platform
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Chunk, Collection, VectorIndexState
from app.evaluation.retrieval import load_questions
from app.retrieval.search import SearchFilters, normalize_retrieval_method, search_chunks


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def hardware_report() -> dict[str, object]:
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "cpu_count_logical": os.cpu_count(),
        "cpu_count_physical": None,
        "memory_total_bytes": None,
    }


def corpus_report(session: Session, collection: str, embedding_model: str) -> dict[str, object]:
    db_collection = session.scalar(select(Collection).where(Collection.name == collection))
    if db_collection is None:
        raise ValueError(f"Unknown collection: {collection}")
    article_count = session.scalar(select(func.count(Article.id)).where(Article.collection_id == db_collection.id))
    chunk_count = session.scalar(
        select(func.count(Chunk.id)).join(Article, Chunk.article_id == Article.id).where(Article.collection_id == db_collection.id)
    )
    state = session.scalar(
        select(VectorIndexState)
        .where(VectorIndexState.collection_id == db_collection.id)
        .where(VectorIndexState.embedding_model == embedding_model)
    )
    vector_state = None
    if state is not None:
        vector_state = {
            "status": state.status,
            "desired_revision": state.desired_revision,
            "active_revision": state.active_revision,
            "active_generation_id": state.active_generation_id,
            "active_manifest_sha256": state.active_manifest_sha256,
        }
    return {
        "collection": collection,
        "collection_id": str(db_collection.id),
        "article_count": int(article_count or 0),
        "chunk_count": int(chunk_count or 0),
        "vector_index_state": vector_state,
    }


def run_search_benchmark(
    session: Session,
    settings: Settings,
    questions_path: Path,
    *,
    collection: str,
    methods: list[str],
    warmup: int = 3,
    runs: int = 10,
    top_k: int = 10,
    filters: SearchFilters | None = None,
) -> dict[str, Any]:
    if warmup < 0:
        raise ValueError("warmup must be non-negative")
    if runs <= 0:
        raise ValueError("runs must be positive")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    questions = load_questions(questions_path)
    normalized_methods = [normalize_retrieval_method(method) for method in methods]
    normalized_filters = filters or SearchFilters()
    method_reports: dict[str, dict[str, object]] = {}

    for method in normalized_methods:
        latencies_ms: list[float] = []
        result_counts: list[int] = []
        error: dict[str, str] | None = None
        try:
            for _ in range(warmup):
                for question in questions:
                    search_chunks(
                        session,
                        question.query,
                        collection,
                        top_k,
                        method=method,
                        filters=normalized_filters,
                        settings=settings,
                    )
            for _ in range(runs):
                for question in questions:
                    started = time.perf_counter()
                    response = search_chunks(
                        session,
                        question.query,
                        collection,
                        top_k,
                        method=method,
                        filters=normalized_filters,
                        settings=settings,
                    )
                    latencies_ms.append((time.perf_counter() - started) * 1000)
                    result_counts.append(len(response.results))
        except Exception as exc:
            error = {"error_type": type(exc).__name__, "error": str(exc)}

        method_reports[method] = {
            "query_count": len(questions),
            "warmup_runs_per_query": warmup,
            "measured_runs_per_query": runs,
            "total_measured_searches": len(latencies_ms),
            "latency_ms": {
                "p50": percentile(latencies_ms, 0.50),
                "p95": percentile(latencies_ms, 0.95),
                "max": max(latencies_ms) if latencies_ms else None,
                "mean": statistics.fmean(latencies_ms) if latencies_ms else None,
            },
            "result_count": {
                "min": min(result_counts) if result_counts else None,
                "max": max(result_counts) if result_counts else None,
                "mean": statistics.fmean(result_counts) if result_counts else None,
            },
        }
        if error is not None:
            method_reports[method]["error"] = error

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "hardware": hardware_report(),
        "corpus": corpus_report(session, collection, settings.embedding_model),
        "settings": {
            "collection": collection,
            "questions_path": str(questions_path),
            "methods": normalized_methods,
            "top_k": top_k,
            "warmup": warmup,
            "runs": runs,
            "filters": normalized_filters.as_metadata(),
            "embedding_model": settings.embedding_model,
            "vector_index_cache_enabled": settings.vector_index_cache_enabled,
            "vector_index_use_mmap": settings.vector_index_use_mmap,
        },
        "methods": method_reports,
    }


def write_benchmark_report(report: dict[str, Any], data_root: Path, output_path: Path | None = None) -> Path:
    resolved_output = output_path
    if resolved_output is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        resolved_output = data_root / "exports" / f"backend_benchmark_{timestamp}.json"
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return resolved_output
