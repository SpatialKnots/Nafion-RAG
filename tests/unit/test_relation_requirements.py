from types import SimpleNamespace

import pytest

from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.relation_requirements import assess_relation_requirements

COMPOSITION = "How does mixture composition affect conductivity?"
CYCLES = "How does mixing temperature affect swelling during heating and cooling?"


@pytest.mark.parametrize("query", [COMPOSITION, "Как доля компонента смеси влияет на проводимость?"])
def test_separate_solvent_values_do_not_establish_composition_series(query):
    result = assess_relation_requirements(query, ["Conductivity in solvent A: 1; in solvent B: 2."])
    assert result["missing"] == ["mixture_composition_conductivity"]


def test_context_cannot_be_assembled_from_unrelated_fragments():
    result = assess_relation_requirements(CYCLES, ["Mixing temperature influences swelling.", "Heating and cooling cycles."])
    assert result["missing"] == ["mixing_temperature_swelling_cycles"]


def test_fixed_temperature_conductivity_experiment_lacks_heating_cycle():
    text = "Mixture conductivity at mixing temperature 40 C; solvent uptake changes on cooling."
    assert assess_relation_requirements(CYCLES, [text])["missing"]


def test_source_line_breaks_and_ligatures_preserve_context():
    text = "Conductivity isotherms in binary mixtures with varying ra- \n tios; highest values measured."
    assert not assess_relation_requirements(COMPOSITION, [text])["missing"]


def test_supporting_fragment_can_follow_irrelevant_fragment():
    text = "Mixing temperature affects solvent uptake during heating and cooling."
    result = assess_relation_requirements(CYCLES, ["Unrelated discussion", text])
    assert not result["missing"]
    assert result["details"]["mixing_temperature_swelling_cycles"]["matching_evidence_indices"] == [1]


@pytest.mark.parametrize("query", ["List mixture compositions and conductivity values.", "What is diglyme conductivity?",
                                   "What is the PBI preparation protocol?"])
def test_out_of_scope_questions_unchanged(query):
    assert assess_relation_requirements(query, [""])["required"] == []


def test_missing_context_vetoes_even_complete_glossary_coverage():
    result = assess_evidence_adequacy(CYCLES, [SimpleNamespace(text="swelling")],
                                      concept_terms={"swelling": {"en": ["swelling"]}})
    assert not result.adequate
    assert result.reason == "missing_relation_context"


def test_context_match_does_not_override_required_substance_refusal():
    result = assess_evidence_adequacy(CYCLES + " in PBI?", [SimpleNamespace(
        text="Mixing temperature affects swelling during heating and cooling.")])
    assert not result.adequate
    assert result.reason == "missing_required_concepts"
