from __future__ import annotations

from app.retrieval.query_normalization import normalize_query, normalized_query_metadata


def test_normalize_query_preserves_original_and_protected_tokens() -> None:
    query = "Как EC и SL влияют на ионную проводимость Li-Nafion при 25 °C?"

    normalized = normalize_query(query)

    assert normalized.original == query
    assert normalized.language == "mixed"
    assert "EC" in normalized.protected_tokens
    assert "SL" in normalized.protected_tokens
    assert "Li-Nafion" in normalized.protected_tokens
    assert "25 °C" in normalized.protected_tokens
    assert "EC" in normalized.lexical_normalized
    assert "SL" in normalized.lexical_normalized
    assert "Li-Nafion" in normalized.lexical_normalized
    assert "ионн" in normalized.lexical_normalized
    assert "проводимост" in normalized.lexical_normalized


def test_normalize_query_maps_russian_case_variants_to_same_stems() -> None:
    variants = [
        "ионная проводимость",
        "ионной проводимости",
        "ионную проводимость",
    ]

    normalized_forms = [normalize_query(variant).lexical_normalized for variant in variants]

    assert normalized_forms == ["ионн проводимост", "ионн проводимост", "ионн проводимост"]


def test_normalized_query_metadata_is_explicitly_derived() -> None:
    normalized = normalize_query("Как замещение H+ на Li+ влияет на Nafion?")

    metadata = normalized_query_metadata(normalized)

    assert metadata["original"] == "Как замещение H+ на Li+ влияет на Nafion?"
    assert metadata["lexical_normalized"] != metadata["original"]
    assert metadata["diagnostics"]["normalization"] == "ru_suffix_stem_substring"  # type: ignore[index]
