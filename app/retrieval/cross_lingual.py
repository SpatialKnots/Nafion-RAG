from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from app.generation.evidence_adequacy import LIGATURES


@dataclass(frozen=True)
class GlossaryEntry:
    concept: str
    en: tuple[str, ...]
    ru: tuple[str, ...]


@dataclass(frozen=True)
class QueryVariant:
    text: str
    language: str
    source: str
    concepts: tuple[str, ...]


@dataclass(frozen=True)
class QueryBundle:
    original: str
    language: str
    variants: list[QueryVariant]
    matched_concepts: list[str]
    language_detection: dict[str, object]


@lru_cache(maxsize=1)
def _load_glossary_entries() -> tuple[GlossaryEntry, ...]:
    path = Path(__file__).resolve().parents[2] / "docs" / "cross_lingual_glossary.yaml"
    if not path.is_file():
        # Installed wheels carry the exact source glossary beside this module.
        path = Path(__file__).with_name("cross_lingual_glossary.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("cross-lingual glossary must contain a mapping")
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise ValueError("cross-lingual glossary entries must be a list")
    loaded: list[GlossaryEntry] = []
    seen: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError(f"cross-lingual glossary entry {index} must be a mapping")
        concept = item.get("concept")
        en = _term_list(item.get("en"), concept, "en")
        ru = _term_list(item.get("ru"), concept, "ru")
        if not isinstance(concept, str) or not concept.strip():
            raise ValueError(f"cross-lingual glossary entry {index} has invalid concept")
        if concept in seen:
            raise ValueError(f"duplicate cross-lingual glossary concept: {concept}")
        if not en and not ru:
            raise ValueError(f"cross-lingual glossary concept has no terms: {concept}")
        seen.add(concept)
        loaded.append(GlossaryEntry(concept=concept, en=tuple(en), ru=tuple(ru)))
    return tuple(loaded)


def _term_list(value: Any, concept: object, language: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"cross-lingual glossary {concept}.{language} must be a list of non-empty strings")
    return [item.strip() for item in value]


GLOSSARY: tuple[GlossaryEntry, ...] = _load_glossary_entries()


def detect_query_language(query: str) -> tuple[str, dict[str, object]]:
    cyrillic_chars = sum(1 for char in query if "а" <= char.lower() <= "я" or char.lower() == "ё")
    latin_chars = sum(1 for char in query if "a" <= char.lower() <= "z")
    total_letters = cyrillic_chars + latin_chars
    if total_letters == 0:
        language = "unknown"
    elif cyrillic_chars and latin_chars and min(cyrillic_chars, latin_chars) / total_letters >= 0.15:
        language = "mixed"
    elif cyrillic_chars > latin_chars:
        language = "ru"
    else:
        language = "en"
    return language, {
        "cyrillic_chars": cyrillic_chars,
        "latin_chars": latin_chars,
        "decision": language,
    }


def build_query_bundle(query: str) -> QueryBundle:
    normalized_query = query.strip()
    language, detection = detect_query_language(normalized_query)
    matched = _matched_entries(normalized_query)
    matched_concepts = [entry.concept for entry in matched]
    variants = [QueryVariant(text=normalized_query, language=language, source="original", concepts=tuple(matched_concepts))]
    for variant in _glossary_variants(matched, language):
        if _variant_is_new(variants, variant.text):
            variants.append(variant)
    return QueryBundle(
        original=normalized_query,
        language=language,
        variants=variants,
        matched_concepts=matched_concepts,
        language_detection=detection,
    )


def query_bundle_metadata(bundle: QueryBundle, variant_hits: list[dict[str, object]] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "enabled": True,
        "query_language": bundle.language,
        "language_detection": bundle.language_detection,
        "matched_concepts": bundle.matched_concepts,
        "variants": [
            {
                "index": index,
                "text": variant.text,
                "language": variant.language,
                "source": variant.source,
                "concepts": list(variant.concepts),
            }
            for index, variant in enumerate(bundle.variants)
        ],
    }
    if variant_hits is not None:
        payload["variant_hits"] = variant_hits
    return payload


def glossary_terms_for_concepts(concepts: list[str]) -> dict[str, dict[str, list[str]]]:
    requested = set(concepts)
    return {
        entry.concept: {"en": list(entry.en), "ru": list(entry.ru)}
        for entry in GLOSSARY
        if entry.concept in requested
    }


def _matched_entries(query: str) -> list[GlossaryEntry]:
    normalized = query.lower().translate(LIGATURES)
    matched: list[GlossaryEntry] = []
    for entry in GLOSSARY:
        if any(_term_matches_query(term, normalized) for term in (*entry.en, *entry.ru)):
            matched.append(entry)
    return matched


def _term_matches_query(term: str, normalized_query: str) -> bool:
    normalized_term = term.lower().translate(LIGATURES)
    if " " in normalized_term:
        return _ordered_tokens_match_query(normalized_term.split(), normalized_query)
    return _single_token_matches_query(normalized_term, normalized_query)


def _ordered_tokens_match_query(tokens: list[str], normalized_query: str) -> bool:
    pattern = ".*?".join(_token_pattern(token) for token in tokens)
    return re.search(pattern, normalized_query) is not None


def _token_pattern(token: str) -> str:
    if len(token) <= 3 and token.isalnum():
        return rf"(?<![a-zа-яё0-9]){re.escape(token)}(?![a-zа-яё0-9])"
    return re.escape(token)


def _single_token_matches_query(normalized_term: str, normalized_query: str) -> bool:
    if len(normalized_term) <= 3 and normalized_term.isalnum():
        return re.search(_token_pattern(normalized_term), normalized_query) is not None
    return normalized_term in normalized_query


def _glossary_variants(entries: list[GlossaryEntry], language: str) -> list[QueryVariant]:
    if not entries:
        return []
    target_languages = ("ru", "en")
    variants: list[QueryVariant] = []
    for target_language in target_languages:
        phrases: list[str] = []
        for entry in entries:
            terms = entry.ru if target_language == "ru" else entry.en
            phrases.extend(terms[:4])
        if phrases:
            variants.append(
                QueryVariant(
                    text=" ".join(dict.fromkeys(phrases)),
                    language=target_language,
                    source="glossary",
                    concepts=tuple(entry.concept for entry in entries),
                )
            )
    return variants


def _variant_is_new(variants: list[QueryVariant], text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return all(" ".join(variant.text.lower().split()) != normalized for variant in variants)
