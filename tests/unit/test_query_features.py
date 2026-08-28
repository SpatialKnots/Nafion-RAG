from __future__ import annotations

from app.retrieval.query_features import extract_query_features, query_features_metadata


def test_extract_query_features_protects_scientific_tokens_and_conditions() -> None:
    features = extract_query_features("Как EC/SL влияют на Li-Nafion при 25 °C и Li+? DOI 10.1016/j.electacta.2021.137914")

    assert features.language == "mixed"
    assert "EC" in features.protected_tokens
    assert "SL" in features.protected_tokens
    assert "Li-Nafion" in features.protected_tokens
    assert "Li+" in features.protected_tokens
    assert "25 °C" in features.protected_tokens
    assert "10.1016/j.electacta.2021.137914" in features.protected_tokens
    assert features.numeric_conditions == ["25 °C"]


def test_query_features_metadata_is_serializable() -> None:
    features = extract_query_features("Nafion conductivity in EC")

    metadata = query_features_metadata(features)

    assert metadata["original"] == "Nafion conductivity in EC"
    assert metadata["language"] == "en"
    assert metadata["protected_tokens"] == ["EC"]
