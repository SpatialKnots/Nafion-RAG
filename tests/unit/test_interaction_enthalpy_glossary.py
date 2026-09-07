import pytest

from app.retrieval.cross_lingual import build_query_bundle


@pytest.mark.parametrize(
    "query",
    [
        "What is the enthalpy of interaction of lithiated Nafion with aqueous alcohol solutions?",
        "Interaction enthalpy of polymer and solvent",
        "Измерение энтальпии взаимодействия Li-Nafion с раствором",
    ],
)
def test_interaction_enthalpy_survives_cross_language_expansion(query):
    bundle = build_query_bundle(query)
    assert "interaction_enthalpy" in bundle.matched_concepts
    assert any(v.language == "ru" and "энтальпия взаимодействия" in v.text for v in bundle.variants)
    assert any(v.language == "en" and "interaction enthalpy" in v.text for v in bundle.variants)


@pytest.mark.parametrize("query", ["Nafion water conductivity", "Nafion mixing entropy and free energy"])
def test_unrelated_property_does_not_acquire_interaction_enthalpy(query):
    bundle = build_query_bundle(query)
    assert "interaction_enthalpy" not in bundle.matched_concepts
