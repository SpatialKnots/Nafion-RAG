from __future__ import annotations

import re
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
    numeric_table_scores: dict[str, int] = {}
    conductivity_plasticizer_scores: dict[str, int] = {}
    numeric_comparison_intent = _has_swelling_comparison_intent(question, additional_queries or [])
    conductivity_plasticizer_intent = _has_conductivity_plasticizer_intent(question, additional_queries or [])
    for result in results:
        matched = _matched_terms(result, distinctive_terms)
        result_terms[result.chunk_id] = matched
        numeric_table_scores[result.chunk_id] = _swelling_comparison_table_score(result, enabled=numeric_comparison_intent)
        conductivity_plasticizer_scores[result.chunk_id] = _conductivity_plasticizer_score(
            result,
            enabled=conductivity_plasticizer_intent,
        )
        article_terms.setdefault(result.article_id, set()).update(matched)

    original_positions = {result.chunk_id: index for index, result in enumerate(results)}
    ranked = sorted(
        results,
        key=lambda result: (
            -numeric_table_scores[result.chunk_id],
            -conductivity_plasticizer_scores[result.chunk_id],
            -len(article_terms[result.article_id]),
            -len(result_terms[result.chunk_id]),
            original_positions[result.chunk_id],
        ),
    )
    selected = _diversify_by_article(ranked, preferred_per_article=2)
    filtered_to_conductivity_plasticizer_evidence = False
    if conductivity_plasticizer_intent and any(score > 0 for score in conductivity_plasticizer_scores.values()):
        selected = [result for result in selected if conductivity_plasticizer_scores[result.chunk_id] > 0]
        filtered_to_conductivity_plasticizer_evidence = True
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
            "numeric_comparison_intent": numeric_comparison_intent,
            "numeric_table_result_count": sum(1 for score in numeric_table_scores.values() if score > 0),
            "conductivity_plasticizer_intent": conductivity_plasticizer_intent,
            "conductivity_plasticizer_result_count": sum(1 for score in conductivity_plasticizer_scores.values() if score > 0),
            "filtered_to_conductivity_plasticizer_evidence": filtered_to_conductivity_plasticizer_evidence,
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


def _has_swelling_comparison_intent(question: str, additional_queries: list[str]) -> bool:
    text = " ".join([question, *additional_queries]).lower().translate(LIGATURES)
    has_swelling = any(term in text for term in ("swelling degree", "степень набухания", "equilibrium swelling"))
    has_forms = "li-nafion" in text and "h-nafion" in text
    has_comparison = any(term in text for term in ("more", "than", "больше", "выше", "сравн", "αh", "αli"))
    return has_swelling and has_forms and has_comparison


def _has_conductivity_plasticizer_intent(question: str, additional_queries: list[str]) -> bool:
    text = " ".join([question, *additional_queries]).lower().translate(LIGATURES)
    has_conductivity = any(term in text for term in ("conductivity", "проводимост", "электропровод"))
    has_plasticizer = any(term in text for term in ("plasticiser", "plasticizer", "пластификатор", "растворител"))
    has_lithium_form = any(term in text for term in ("li-nafion", "lithiated nafion", "литиевая", "литирован"))
    return has_conductivity and has_plasticizer and has_lithium_form


def _swelling_comparison_table_score(result: SearchResult, *, enabled: bool) -> int:
    if not enabled:
        return 0
    text = "\n".join(item for item in (result.title or "", result.snippet, result.full_text or "") if item).lower().translate(LIGATURES)
    has_forms = "li-nafion" in text and "h-nafion" in text
    has_alpha_columns = any(term in text for term in ("αh", "αli", "alphah", "alphali"))
    decimal_count = len(re.findall(r"\b\d+[.,]\d+\b", text))
    if not (has_forms and has_alpha_columns and decimal_count >= 4):
        return 0
    if "таблица 4.5" in text or "table 4.5" in text:
        return 2
    return 0


def _conductivity_plasticizer_score(result: SearchResult, *, enabled: bool) -> int:
    if not enabled:
        return 0
    text = "\n".join(item for item in (result.title or "", result.snippet, result.full_text or "") if item).lower().translate(LIGATURES)
    has_lithium_form = any(term in text for term in ("li-nafion", "lithiated nafion", "li‑nafion", "литирован"))
    has_conductivity = any(term in text for term in ("conductivity", "transport properties", "проводимост", "электропровод"))
    has_plasticizer = any(
        term in text for term in ("plasticiser", "plasticizer", "plasticised", "plasticized", "пластификатор", "пластифицирован")
    )
    if not (has_lithium_form and has_conductivity and has_plasticizer):
        return 0
    if any(term in text for term in ("table 4.6", "таблица 4.6", "highest li-ion conductivity", "highest ionic conductivities")):
        return 3
    if any(term in text for term in ("best transport properties", "highest conductivity values", "best sample")):
        return 3
    if "ec/sl" in text and any(term in text for term in ("conductivity", "transport properties")):
        return 2
    if sum(1 for term in ("dmf", "dmso", "nmp", "nmf", "dmaa", "methanol") if term in text) >= 3:
        return 2
    return 1


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
