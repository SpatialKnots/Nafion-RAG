"""Offline-only retrieval candidates; no query/case/article specific promotion."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from sqlalchemy import case, func, literal, or_, select

from app.db.models import Article, Chunk
from app.retrieval import search
from app.retrieval.cross_lingual import QueryBundle, QueryVariant, build_query_bundle

VERSION = "retrieval_ablation_v0.1"
ARMS = ("baseline", "ligatures", "expansion", "combined")
LIGATURE_PAIRS = (("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬀ", "ff"), ("ﬃ", "ffi"), ("ﬄ", "ffl"))
CONCEPT = "dispersion_particle_morphology_solvent_candidate_v0.1"
CUES = (
    r"\b(?:nafion|нафион)\b",
    r"\b(?:дисперс\w*|dispers(?:ion\w*|ing|ed))\b",
    r"\b(?:частиц\w*|particles?)\b",
    r"\b(?:морфолог\w*|morpholog\w*|форм\w*|shapes?)\b",
    r"\b(?:растворител\w*|solvents?)\b",
)


def candidate_bundle(query: str) -> QueryBundle:
    baseline = build_query_bundle(query)
    normalized = query.lower().translate(search.LIGATURES)
    if not all(re.search(pattern, normalized) for pattern in CUES):
        return baseline
    variants = list(baseline.variants)
    for language, text in (
        ("ru", "nafion дисперсия частицы морфология растворитель"),
        ("en", "nafion dispersion particle morphology solvent"),
    ):
        if text not in {variant.text for variant in variants}:
            variants.append(QueryVariant(text=text, language=language, source="candidate_lexical",
                                         concepts=(CONCEPT,)))
    return replace(baseline, variants=variants, matched_concepts=[*baseline.matched_concepts, CONCEPT])


def normalized_search_statement(query: str, collection: Any, top_k: int, filters: Any = None) -> Any:
    """Production exact SQL structure with only its matching/scoring view normalized."""
    view = Chunk.text
    for source, target in LIGATURE_PAIRS:
        view = func.replace(view, source, target)
    lowered = func.lower(view)
    phrase_pattern = f"%{search._escape_like(query)}%"
    terms = search._query_terms(query)
    conditions = [view.ilike(phrase_pattern, escape="\\")]
    conditions.extend(view.ilike(f"%{search._escape_like(term)}%", escape="\\") for term in terms)
    score = case((view.ilike(phrase_pattern, escape="\\"), literal(1000)), else_=literal(0))
    for term in terms:
        score += func.length(lowered) - func.length(func.replace(lowered, term.lower(), ""))
    if not terms:
        score += func.length(lowered) - func.length(func.replace(lowered, query.lower(), ""))
    statement = (select(Chunk, Article, score.label("score")).join(Article, Chunk.article_id == Article.id)
                 .where(Article.collection_id == collection.id).where(or_(*conditions))
                 .order_by(score.desc(), Chunk.chunk_index.asc()).limit(top_k))
    return search.apply_search_filters(statement, filters or search.SearchFilters())


def label_retention(case: dict[str, Any], rows: list[dict[str, Any]], articles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Existing article labels only; unrelated/unlabelled rows are not negative gold."""
    expected = case.get("expected", {})
    wanted = expected.get("articles", [])
    dois = set(case.get("expected_article_dois", []))
    dois.update(row["doi"] for row in wanted if row.get("doi"))
    checksums = set(case.get("expected_article_checksums", []))
    titles = set(case.get("expected_article_titles", []))
    eligible = bool(dois or checksums or titles)
    matches = [row["article_id"] for row in rows if (
        row.get("doi") in dois or articles[row["article_id"]]["original_pdf_sha256"] in checksums or row["title"] in titles)]
    return {"has_existing_positive_article_label": eligible, "any_expected_article_present": bool(matches) if eligible else None,
            "matching_article_ids": sorted(set(matches)), "wanted_dois": sorted(dois),
            "wanted_checksums": sorted(checksums), "wanted_titles": sorted(titles),
            "scope": "article_hit_on_existing_exposed_fixture; not scientific answer accuracy"}
