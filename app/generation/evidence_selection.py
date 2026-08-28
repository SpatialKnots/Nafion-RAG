from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from app.generation.evidence_adequacy import LIGATURES, distinctive_query_terms, term_matches_text
from app.retrieval.search import SearchResult


@dataclass(frozen=True)
class EvidenceSelection:
    results: list[SearchResult]
    metadata: dict[str, object]


def select_answer_evidence(question: str, results: list[SearchResult], *, additional_queries: list[str] | None = None) -> EvidenceSelection:
    distinctive_terms = _selection_terms(question, additional_queries or [])
    if not results or not distinctive_terms:
        return EvidenceSelection(
            results=results,
            metadata={
                "strategy": "article_distinctive_term_coverage",
                "distinctive_terms": distinctive_terms,
                "reordered": False,
            },
        )

    article_terms: OrderedDict[str, set[str]] = OrderedDict()
    result_terms: dict[str, set[str]] = {}
    for result in results:
        matched = _matched_terms(result, distinctive_terms)
        result_terms[result.chunk_id] = matched
        article_terms.setdefault(result.article_id, set()).update(matched)

    original_positions = {result.chunk_id: index for index, result in enumerate(results)}
    ranked = sorted(
        results,
        key=lambda result: (
            -len(article_terms[result.article_id]),
            -len(result_terms[result.chunk_id]),
            original_positions[result.chunk_id],
        ),
    )
    selected = _diversify_by_article(ranked, preferred_per_article=2)
    reordered = [result.chunk_id for result in selected] != [result.chunk_id for result in results]
    return EvidenceSelection(
        results=selected,
        metadata={
            "strategy": "article_distinctive_term_coverage",
            "distinctive_terms": distinctive_terms,
            "reordered": reordered,
            "article_term_coverage": [
                {
                    "article_id": article_id,
                    "matched_terms": sorted(terms),
                    "matched_count": len(terms),
                }
                for article_id, terms in article_terms.items()
            ],
        },
    )


def _matched_terms(result: SearchResult, distinctive_terms: list[str]) -> set[str]:
    text = "\n".join(
        item
        for item in (
            result.title or "",
            result.snippet,
            result.full_text or "",
        )
        if item
    )
    normalized_text = text.lower().translate(LIGATURES)
    return {term for term in distinctive_terms if term_matches_text(term, normalized_text)}


def _selection_terms(question: str, additional_queries: list[str]) -> list[str]:
    terms: list[str] = []
    for source in (question, *additional_queries):
        for term in distinctive_query_terms(source):
            if term not in terms:
                terms.append(term)
    return terms


def _diversify_by_article(results: list[SearchResult], *, preferred_per_article: int) -> list[SearchResult]:
    first_pass: list[SearchResult] = []
    deferred: list[SearchResult] = []
    counts: dict[str, int] = {}
    for result in results:
        count = counts.get(result.article_id, 0)
        if count < preferred_per_article:
            first_pass.append(result)
        else:
            deferred.append(result)
        counts[result.article_id] = count + 1
    return [*first_pass, *deferred]
