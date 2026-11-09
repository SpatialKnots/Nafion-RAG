"""Bounded raw methods context; attachment cues never establish value ownership."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection
from app.generation.fact_types import SourceView
from app.generation.providers import Evidence
from app.retrieval.requested_context import body_facets, requested_facets
from app.retrieval.search import SearchFilters, SearchResult, _result_from_chunk_article, apply_search_filters

VERSION = "condition_context_completion_v0.2"
MAX_ROWS = 12
PAGE_LOOKBACK = 2
FACET = "equilibrium_swelling_enthalpy_table"

# Deliberately finite ordered source grammar. No numeric condition is extracted.
METHODS = re.compile(
    r"экспериментальная часть\s+объекты исследования\s+"
    r"объектом исследования являлась[^.!?]{1,200}\bмембрана nafion\s+\d+\b"
    r".{1,1600}?замена протона на ион li\+.{1,600}?"
    r"поглощение растворителя\s+равновесную степень набухания.{1,100}?"
    r"мембран li-nafion определяли гравиметрическим методом"
    r".{1,1200}?согласно данным производителя,\s*исходное содержание воды"
    r".{1,500}?(?=специального обезвоживания)", re.I,
)
CONFLICT = re.compile(
    r"\b(?:h|na|k|mg|ca)-nafion\b|не (?:определяли|измеряли|осуществлял)|"
    r"(?:планируется|предстоит|будут)\s+(?:определ|измер|осуществ)|"
    r"\b(?:пвдф|pvdf)\b", re.I,
)


def methods_support(row: SearchResult) -> list[dict[str, Any]]:
    source = Evidence(citation_id="", article_id=row.article_id, chunk_id=row.chunk_id,
        title=row.title, doi=row.doi, page_start=row.page_start, page_end=row.page_end,
        source_type=row.source_type, text=row.full_text or row.snippet, score=row.score,
        retrieval_method=row.retrieval_method, method_scores=row.method_scores, method_ranks=row.method_ranks)
    view = SourceView(source, join_soft_hyphen_lines=True)
    return [asdict(view.support(m)) for m in METHODS.finditer(view.text) if not CONFLICT.search(m.group())]


def load_context_rows(session: Session, query: str, collection: str, filters: SearchFilters,
                      anchor: SearchResult) -> list[SearchResult]:
    """All active filters apply again; overflow is visible to the caller."""
    statement = (select(Chunk, Article).join(Article).join(Collection)
        .where(Collection.name == collection, Article.id == uuid.UUID(anchor.article_id),
               Chunk.text_layer == anchor.text_layer, Chunk.source_type == anchor.source_type,
               Chunk.page_start >= max(1, anchor.page_start - PAGE_LOOKBACK),
               Chunk.page_end <= anchor.page_start)
        .order_by(Chunk.page_start, Chunk.page_end, Chunk.chunk_index, Chunk.id).limit(MAX_ROWS + 1))
    return [_result_from_chunk_article(c, a, query=query, score=0.0, retrieval_method="condition_context")
            for c, a in session.execute(apply_search_filters(statement, filters))]


def complete_context(session: Session, question: str, collection: str, filters: SearchFilters,
                     selected: list[SearchResult]) -> tuple[list[SearchResult], dict[str, Any] | None]:
    if requested_facets(question) != (FACET,):
        return selected, None
    anchors = [r for r in selected if FACET in body_facets(r.full_text or r.snippet, (FACET,))]
    if not anchors:
        return selected, None
    diagnostic: dict[str, Any] = {
        "version": VERSION, "scope": "raw_methods_context_not_value_ownership",
        "extra_evidence_budget": 1, "page_lookback": PAGE_LOOKBACK, "candidate_limit": MAX_ROWS,
        "filters": filters.as_metadata(), "collection": collection, "added_chunk_ids": [],
        "scientific_ownership_verified": False, "values_propagated": False,
        "retrieval_scores_changed": False, "gate_thresholds_changed": False,
    }
    scopes = {(r.article_id, r.text_layer, r.source_type) for r in anchors}
    if len(scopes) != 1:
        return selected, {**diagnostic, "reason": "ambiguous_table_scope"}
    anchor = anchors[0]
    diagnostic.update(article_id=anchor.article_id, anchor_chunk_id=anchor.chunk_id,
                      text_layer=anchor.text_layer, source_type=anchor.source_type)
    existing = [(r, s) for r in selected if (r.article_id, r.text_layer, r.source_type) in scopes
                for s in methods_support(r)]
    if existing:
        reason = "context_already_present" if len({s["text"] for _, s in existing}) == 1 else "ambiguous_methods"
        return selected, {**diagnostic, "reason": reason, "supports": [s for _, s in existing]}
    rows = load_context_rows(session, question, collection, filters, anchor)
    diagnostic["candidate_chunk_ids"] = [r.chunk_id for r in rows]
    if len(rows) > MAX_ROWS:
        return selected, {**diagnostic, "reason": "candidate_overflow"}
    candidates: list[tuple[SearchResult, dict[str, Any]]] = []
    for row in rows:
        if ((row.article_id, row.text_layer, row.source_type) not in scopes
                or row.page_start < max(1, anchor.page_start - PAGE_LOOKBACK)
                or row.page_end > anchor.page_start or row.page_end < row.page_start):
            return selected, {**diagnostic, "reason": "loader_scope_violation"}
        candidates.extend((row, s) for s in methods_support(row))
    if not candidates:
        return selected, {**diagnostic, "reason": "methods_not_resolved"}
    if len({s["text"] for _, s in candidates}) != 1:
        return selected, {**diagnostic, "reason": "ambiguous_methods"}
    row, support = min(candidates, key=lambda rs: (len(rs[0].full_text or rs[0].snippet),
                      rs[0].page_start, rs[0].page_end, rs[0].chunk_id))
    if row.chunk_id in {r.chunk_id for r in selected}:
        raise ValueError("Context candidate duplicated a selected chunk without matching existing methods")
    return [*selected, row], {**diagnostic, "reason": "bounded_methods_context_added",
                              "added_chunk_ids": [row.chunk_id], "supports": [support]}
