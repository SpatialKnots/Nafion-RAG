"""Synthetic identity-coverage fixtures; these are not measured scientific facts."""

from types import SimpleNamespace

import pytest

from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.required_concepts import assess_required_concepts


def assess(query, *texts, **kwargs):
    return assess_evidence_adequacy(query, [SimpleNamespace(text=text) for text in texts], **kwargs)


def test_general_topic_cannot_replace_material_or_reagent():
    result = assess(
        "polybenzimidazole phosphoric acid anhydrous fuel cell Nafion composite",
        "Nafion acid composite membranes for anhydrous fuel cells.",
    )
    assert result.coverage >= 0.6
    assert result.top_coverage >= 0.5
    assert not result.adequate
    assert result.reason == "missing_required_concepts"
    assert result.required_concepts.missing == ["polybenzimidazole", "phosphoric_acid"]


@pytest.mark.parametrize(
    "evidence,missing",
    [
        ("PBI Nafion acid composite anhydrous fuel cells", ["phosphoric_acid"]),
        ("Phosphoric acid Nafion composite anhydrous fuel cells", ["polybenzimidazole"]),
    ],
)
def test_partial_identity_coverage_still_refuses(evidence, missing):
    result = assess("PBI phosphoric acid Nafion composite anhydrous fuel cells", evidence)
    assert not result.adequate
    assert result.required_concepts.missing == missing


@pytest.mark.parametrize(
    "query,evidence",
    [
        ("PBI phosphoric acid", "Polybenzimidazole with H₃PO₄."),
        ("H₃PO₄", "phosphoric acid"),
        ("polybenzimidazole phosphoric acid", "Полибензимидазол с фосфорной кислотой."),
        ("Полибензимидазол с фосфорной кислотой", "PBI phosphoric-acid membrane."),
        ("DMF", "диметилформамид"),
        ("DMSO", "dimethyl sulphoxide"),
        ("EC/SL", "ethylene carbonate and sulfolane"),
    ],
)
def test_positive_identity_aliases_in_both_languages(query, evidence):
    result = assess(query, evidence)
    # Two-letter EC/SL is tracked by the guard but the old lexical gate has no
    # distinctive terms. Presence alone must not silently bypass that gate.
    if query != "EC/SL":
        assert result.adequate
    assert result.required_concepts.required
    assert not result.required_concepts.missing


def test_topical_concept_fallback_cannot_bypass_missing_substance():
    result = assess(
        "DMF conductivity Nafion",
        "Nafion conductivity in water",
        concept_terms={
            "transport": {"en": ["conductivity"]},
        },
    )
    assert result.concept_coverage["coverage"] == 1.0
    assert not result.adequate
    assert result.required_concepts.missing == ["dimethylformamide"]


def test_no_substring_or_cross_fragment_identity_matches():
    coverage = assess_required_concepts(
        "PBI phosphoric acid EC/SL",
        [
            "XPBIY spectator sledge phosphoric",
            "acid",
        ],
    )
    assert coverage.matched == []
    assert len(coverage.missing) == 4
    assert assess_required_concepts("special spectator sledge", []).required == []


def test_ec_and_sl_are_independent_requirements():
    result = assess("EC/SL Nafion conductivity", "Ethylene carbonate Nafion conductivity")
    assert result.required_concepts.missing == ["sulfolane"]
    assert not result.adequate


def test_empty_evidence_retains_required_identity_diagnostics():
    result = assess("PBI")
    assert result.reason == "no_evidence"
    assert result.required_concepts.missing == ["polybenzimidazole"]


def test_queries_without_catalogue_entities_keep_existing_gate():
    result = assess("Nafion morphology", "Nafion morphology")
    assert result.adequate
    assert result.required_concepts.required == []
