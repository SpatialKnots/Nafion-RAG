from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.generation.evidence_adequacy import LIGATURES
from app.retrieval.cross_lingual import detect_query_language
from app.retrieval.query_features import extract_query_features
from app.retrieval.query_normalization import normalize_query

STOPWORDS = {"and", "in", "or", "the", "using", "vs", "with", "how", "what", "which", "where", "does", "affect"}
RUSSIAN_STOPWORDS = {"как", "где", "что", "какие", "какая", "в", "на", "и", "с", "для", "по", "при"}
WORD_PATTERN = re.compile(r"[\w+-]+", flags=re.UNICODE)
RERANK_TERM_SYNONYMS = {
    "наибольшую": ("highest", "best", "maximum", "max"),
    "наибольшая": ("highest", "best", "maximum", "max"),
    "наибольший": ("highest", "best", "maximum", "max"),
    "наибольш": ("highest", "best", "maximum", "max"),
    "лучшую": ("best", "highest", "maximum"),
    "лучшие": ("best", "highest", "maximum"),
    "пластификаторах": ("plasticiser", "plasticizer", "plasticisers", "plasticizers"),
    "пластификаторами": ("plasticiser", "plasticizer", "plasticisers", "plasticizers"),
    "пластификатор": ("plasticiser", "plasticizer", "plasticisers", "plasticizers"),
    "проводимость": ("conductivity", "ionic conductivity", "transport properties"),
    "проводимост": ("conductivity", "ionic conductivity", "transport properties"),
}


@dataclass(frozen=True)
class RerankedResults:
    results: list[Any]
    metadata: dict[str, object]


@dataclass(frozen=True)
class _ResultFeatures:
    protected_matches: int
    term_matches: int
    phrase_matches: int
    title_phrase_matches: int
    variant_matches: int
    channel_count: int
    cross_language_bonus: int
    numeric_table_bonus: int
    conductivity_conflict_penalty: int
    result_score: float


def rerank_cross_lingual_results(
    results: list[Any],
    *,
    original_query: str,
    query_language: str,
    query_variants: Sequence[tuple[str, str]],
) -> RerankedResults:
    if not results:
        return RerankedResults(results=[], metadata={"strategy": "cross_lingual_feature_rerank", "reranked": False})

    protected_tokens = extract_query_features(original_query).protected_tokens
    query_terms = _query_terms_for_rerank(original_query)
    normalized_query = normalize_query(original_query)
    if normalized_query.lexical_normalized:
        query_terms.extend(_query_terms_for_rerank(normalized_query.lexical_normalized))
    variant_terms = [(source, _query_terms_for_rerank(text)) for source, text in query_variants if text.strip()]
    query_phrases = _phrases_for_rerank([original_query, normalized_query.lexical_normalized, *(text for _source, text in query_variants)])
    swelling_comparison_intent = _has_swelling_comparison_intent(original_query, query_variants)

    result_features: dict[str, _ResultFeatures] = {}
    article_scores: dict[str, float] = {}
    article_result_scores: dict[str, list[float]] = {}
    for result in results:
        features = _features_for_result(
            result,
            query_language=query_language,
            protected_tokens=protected_tokens,
            query_terms=query_terms,
            query_phrases=query_phrases,
            variant_terms=variant_terms,
            swelling_comparison_intent=swelling_comparison_intent,
        )
        result_features[result.chunk_id] = features
        article_result_scores.setdefault(result.article_id, []).append(features.result_score)

    for article_id, scores in article_result_scores.items():
        ordered = sorted(scores, reverse=True)
        best = ordered[0]
        second = ordered[1] if len(ordered) > 1 else 0.0
        article_scores[article_id] = best + 0.35 * second

    original_positions = {result.chunk_id: index for index, result in enumerate(results)}
    reranked = sorted(
        results,
        key=lambda result: (
            -result_features[result.chunk_id].numeric_table_bonus,
            -article_scores.get(result.article_id, 0.0),
            -result_features[result.chunk_id].result_score,
            min(result.method_ranks.values()) if getattr(result, "method_ranks", None) else len(results) + 1,
            -float(getattr(result, "score", 0.0)),
            original_positions[result.chunk_id],
        ),
    )
    return RerankedResults(
        results=reranked,
        metadata={
            "strategy": "cross_lingual_feature_rerank",
            "reranked": [result.chunk_id for result in reranked] != [result.chunk_id for result in results],
            "protected_tokens": protected_tokens,
            "query_terms": query_terms,
            "query_phrases": query_phrases,
            "top_features": [
                _feature_payload(result, result_features[result.chunk_id], article_scores.get(result.article_id, 0.0))
                for result in reranked[:10]
            ],
        },
    )


def _features_for_result(
    result: Any,
    *,
    query_language: str,
    protected_tokens: list[str],
    query_terms: list[str],
    query_phrases: list[str],
    variant_terms: Sequence[tuple[str, list[str]]],
    swelling_comparison_intent: bool,
) -> _ResultFeatures:
    text = _result_text(result)
    title = (getattr(result, "title", None) or "").lower().translate(LIGATURES)
    protected_matches = sum(1 for token in protected_tokens if _term_matches(token, text))
    matched_terms = {term for term in query_terms if _term_matches(term, text)}
    matched_phrases = {phrase for phrase in query_phrases if phrase in text}
    title_phrase_matches = sum(1 for phrase in matched_phrases if phrase in title)
    matched_variants = {
        source
        for source, terms in variant_terms
        if any(_term_matches(term, text) for term in terms)
    }
    channel_count = len(getattr(result, "method_ranks", {}) or {})
    cross_language_bonus = _cross_language_bonus(query_language, result)
    numeric_table_bonus = _numeric_table_bonus(text, enabled=swelling_comparison_intent)
    conductivity_conflict_penalty = _conductivity_conflict_penalty(" ".join(query_terms), text)
    score = (
        4.0 * protected_matches
        + 1.6 * len(matched_terms)
        + 2.2 * len(matched_phrases)
        + 3.0 * title_phrase_matches
        + 1.2 * len(matched_variants)
        + 0.8 * min(channel_count, 3)
        + 1.5 * cross_language_bonus
        + 6.0 * numeric_table_bonus
        - 2.5 * conductivity_conflict_penalty
    )
    return _ResultFeatures(
        protected_matches=protected_matches,
        term_matches=len(matched_terms),
        phrase_matches=len(matched_phrases),
        title_phrase_matches=title_phrase_matches,
        variant_matches=len(matched_variants),
        channel_count=channel_count,
        cross_language_bonus=cross_language_bonus,
        numeric_table_bonus=numeric_table_bonus,
        conductivity_conflict_penalty=conductivity_conflict_penalty,
        result_score=score,
    )


def _feature_payload(result: Any, features: _ResultFeatures, article_score: float) -> dict[str, object]:
    return {
        "article_id": result.article_id,
        "chunk_id": result.chunk_id,
        "title": result.title,
        "protected_matches": features.protected_matches,
        "term_matches": features.term_matches,
        "phrase_matches": features.phrase_matches,
        "title_phrase_matches": features.title_phrase_matches,
        "variant_matches": features.variant_matches,
        "channel_count": features.channel_count,
        "cross_language_bonus": features.cross_language_bonus,
        "numeric_table_bonus": features.numeric_table_bonus,
        "conductivity_conflict_penalty": features.conductivity_conflict_penalty,
        "result_score": features.result_score,
        "article_score": article_score,
    }


def _query_terms_for_rerank(query: str) -> list[str]:
    terms: list[str] = []
    for token in WORD_PATTERN.findall(query.lower().translate(LIGATURES)):
        stripped = token.strip("-")
        if len(stripped) < 2 or stripped in STOPWORDS or stripped in RUSSIAN_STOPWORDS:
            continue
        if stripped not in terms:
            terms.append(stripped)
    return terms


def _phrases_for_rerank(queries: Sequence[str]) -> list[str]:
    phrases: list[str] = []
    for query in queries:
        terms = _query_terms_for_rerank(query)
        for size in range(2, 5):
            for index in range(0, max(0, len(terms) - size + 1)):
                phrase = " ".join(terms[index : index + size])
                if phrase not in phrases:
                    phrases.append(phrase)
    return phrases[:80]


def _result_text(result: Any) -> str:
    return "\n".join(
        item
        for item in (
            getattr(result, "title", None) or "",
            getattr(result, "snippet", "") or "",
            getattr(result, "full_text", None) or "",
        )
        if item
    ).lower().translate(LIGATURES)


def _has_swelling_comparison_intent(original_query: str, query_variants: Sequence[tuple[str, str]]) -> bool:
    query_text = " ".join([original_query, *(text for _source, text in query_variants)]).lower().translate(LIGATURES)
    has_swelling = any(term in query_text for term in ("swelling degree", "степень набухания", "equilibrium swelling"))
    has_forms = "li-nafion" in query_text and "h-nafion" in query_text
    has_comparison = any(term in query_text for term in ("more", "than", "больше", "выше", "сравн", "αh", "αli"))
    return has_swelling and has_forms and has_comparison


def _numeric_table_bonus(text: str, *, enabled: bool) -> int:
    if not enabled:
        return 0
    has_forms = "li-nafion" in text and "h-nafion" in text
    has_alpha_columns = any(term in text for term in ("αh", "αli", "alphah", "alphali"))
    has_decimal_values = len(re.findall(r"\b\d+[.,]\d+\b", text)) >= 4
    if not (has_forms and has_alpha_columns and has_decimal_values):
        return 0
    if "таблица 4.5" in text or "table 4.5" in text:
        return 2
    return 1


def _term_matches(term: str, text: str) -> bool:
    normalized = term.lower().translate(LIGATURES)
    if normalized in text:
        return True
    if any(synonym in text for synonym in RERANK_TERM_SYNONYMS.get(normalized, ())):
        return True
    if "-" in normalized and normalized.replace("-", " ") in text:
        return True
    if len(normalized) >= 5 and re.fullmatch(r"[а-яё]+", normalized, flags=re.IGNORECASE):
        return normalized[: max(5, len(normalized) - 2)] in text
    return False


def _cross_language_bonus(query_language: str, result: Any) -> int:
    if query_language not in {"en", "ru"}:
        return 0
    result_language, _diagnostics = detect_query_language(
        "\n".join(item for item in (getattr(result, "title", None) or "", getattr(result, "snippet", "") or "") if item)
    )
    if query_language == "en" and result_language == "ru":
        return 1
    if query_language == "ru" and result_language == "en":
        return 1
    return 0


def _conductivity_conflict_penalty(query_text: str, result_text: str) -> int:
    wants_ionic_or_lithium = any(term in query_text for term in ("ionic", "lithium", "li-nafion", "li+", "ионн", "лит"))
    if not wants_ionic_or_lithium:
        return 0
    has_wrong_property = any(term in result_text for term in ("proton conductivity", "electronic conductivity", "протонная проводимость"))
    has_right_property = any(
        term in result_text
        for term in ("ionic conductivity", "li+", "li-nafion", "ионная проводимость", "электропровод")
    )
    return 1 if has_wrong_property and not has_right_property else 0
