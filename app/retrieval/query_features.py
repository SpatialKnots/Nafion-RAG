from __future__ import annotations

import re
from dataclasses import dataclass

from app.retrieval.cross_lingual import detect_query_language

SCIENTIFIC_ABBREVIATIONS = {
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
    "NMP",
    "PC",
    "PFSA",
    "SL",
    "THF",
}
MATERIAL_FORM_PATTERN = re.compile(r"\b(?:Li|H|Na|K|Cs|Ag|Cu|Zn|Mg|Ca)-Nafion\b", flags=re.IGNORECASE)
ION_PATTERN = re.compile(r"\b[A-Z][a-z]?\d*\+")
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s,;]+", flags=re.IGNORECASE)
TEMPERATURE_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:°\s*C|°C|K)\b", flags=re.IGNORECASE)
PERCENT_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:wt\s*%|vol\s*%|mol\s*%|%)", flags=re.IGNORECASE)
WORD_PATTERN = re.compile(r"[\w+-]+", flags=re.UNICODE)


@dataclass(frozen=True)
class QueryFeatures:
    original: str
    language: str
    protected_tokens: list[str]
    chemical_like_tokens: list[str]
    numeric_conditions: list[str]
    diagnostics: dict[str, object]


def extract_query_features(query: str) -> QueryFeatures:
    original = query.strip()
    language, language_detection = detect_query_language(original)
    protected_tokens: list[str] = []
    chemical_like_tokens: list[str] = []
    numeric_conditions: list[str] = []

    for pattern in (DOI_PATTERN, MATERIAL_FORM_PATTERN, ION_PATTERN):
        for match in pattern.finditer(original):
            _append_unique(protected_tokens, match.group(0).rstrip("."))
            _append_unique(chemical_like_tokens, match.group(0).rstrip("."))

    for token in WORD_PATTERN.findall(original):
        normalized = token.strip(".,;:()[]{}")
        if normalized.upper() in SCIENTIFIC_ABBREVIATIONS:
            _append_unique(protected_tokens, normalized)
            _append_unique(chemical_like_tokens, normalized)

    for pattern in (TEMPERATURE_PATTERN, PERCENT_PATTERN):
        for match in pattern.finditer(original):
            _append_unique(protected_tokens, match.group(0))
            _append_unique(numeric_conditions, match.group(0))

    return QueryFeatures(
        original=original,
        language=language,
        protected_tokens=protected_tokens,
        chemical_like_tokens=chemical_like_tokens,
        numeric_conditions=numeric_conditions,
        diagnostics={
            "language_detection": language_detection,
            "protected_token_count": len(protected_tokens),
            "chemical_like_token_count": len(chemical_like_tokens),
            "numeric_condition_count": len(numeric_conditions),
        },
    )


def query_features_metadata(features: QueryFeatures) -> dict[str, object]:
    return {
        "original": features.original,
        "language": features.language,
        "protected_tokens": features.protected_tokens,
        "chemical_like_tokens": features.chemical_like_tokens,
        "numeric_conditions": features.numeric_conditions,
        "diagnostics": features.diagnostics,
    }


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)
