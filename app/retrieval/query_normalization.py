from __future__ import annotations

import re
from dataclasses import dataclass

from app.retrieval.query_features import QueryFeatures, extract_query_features, query_features_metadata

CYRILLIC_WORD_PATTERN = re.compile(r"^[а-яё]+$", flags=re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[\w+-]+", flags=re.UNICODE)
RUSSIAN_STOPWORDS = {
    "а",
    "в",
    "во",
    "и",
    "или",
    "как",
    "к",
    "на",
    "о",
    "об",
    "от",
    "по",
    "при",
    "с",
    "со",
    "что",
}
RUSSIAN_ENDINGS = (
    "иями",
    "ями",
    "ами",
    "его",
    "ого",
    "ему",
    "ому",
    "ией",
    "ия",
    "ию",
    "ии",
    "ие",
    "ые",
    "ой",
    "ый",
    "ий",
    "ая",
    "ую",
    "ого",
    "ому",
    "ых",
    "ым",
    "ой",
    "ей",
    "ам",
    "ах",
    "ом",
    "ем",
    "ов",
    "ев",
    "ю",
    "я",
    "а",
    "е",
    "ы",
    "и",
    "у",
    "о",
)


@dataclass(frozen=True)
class NormalizedQuery:
    original: str
    language: str
    lexical_normalized: str
    protected_tokens: list[str]
    diagnostics: dict[str, object]


def normalize_query(query: str) -> NormalizedQuery:
    features = extract_query_features(query)
    normalized_terms = _normalized_terms(features)
    lexical_normalized = " ".join(normalized_terms)
    return NormalizedQuery(
        original=features.original,
        language=features.language,
        lexical_normalized=lexical_normalized,
        protected_tokens=features.protected_tokens,
        diagnostics={
            "features": query_features_metadata(features),
            "normalization": "ru_suffix_stem_substring",
            "normalized_term_count": len(normalized_terms),
            "changed": lexical_normalized != features.original,
        },
    )


def normalized_query_metadata(query: NormalizedQuery) -> dict[str, object]:
    return {
        "original": query.original,
        "language": query.language,
        "lexical_normalized": query.lexical_normalized,
        "protected_tokens": query.protected_tokens,
        "diagnostics": query.diagnostics,
    }


def _normalized_terms(features: QueryFeatures) -> list[str]:
    protected = set(features.protected_tokens)
    terms: list[str] = []
    for token in TOKEN_PATTERN.findall(features.original):
        stripped = token.strip("-")
        if not stripped:
            continue
        if stripped in protected:
            _append_unique(terms, stripped)
            continue
        lowered = stripped.lower()
        if CYRILLIC_WORD_PATTERN.fullmatch(lowered):
            if lowered in RUSSIAN_STOPWORDS:
                continue
            _append_unique(terms, _russian_stem(lowered))
            continue
        if len(stripped) >= 2:
            _append_unique(terms, stripped)
    return terms


def _russian_stem(word: str) -> str:
    if word.endswith("ью") and len(word) >= 6:
        word = word[:-2] + "ь"
    if word.endswith("ь") and len(word) >= 5:
        return word[:-1]
    for ending in RUSSIAN_ENDINGS:
        if len(word) - len(ending) >= 4 and word.endswith(ending):
            return word[: -len(ending)]
    return word


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)
