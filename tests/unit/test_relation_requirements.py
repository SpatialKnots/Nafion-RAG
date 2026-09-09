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


@pytest.mark.parametrize("text", [
    "Mixing temperature effects on swelling during heating and cooling were not investigated.",
    "We did not measure swelling during heating and cooling at different mixing temperatures.",
    "We hypothesize that mixing temperature affects swelling during heating and cooling.",
    "Влияние температуры смешения на набухание при нагреве и охлаждении не исследовали.",
    "Выдвигаем гипотезу о влиянии температуры смешения на набухание при нагреве и охлаждении.",
])
def test_explicit_non_observations_cannot_supply_relation_context(text):
    result = assess_evidence_adequacy(CYCLES, [SimpleNamespace(text=text)],
                                      concept_terms={"swelling": {"en": ["swelling"], "ru": ["набухание"]}})
    assert not result.adequate
    assert result.reason == "missing_relation_context"
    detail = result.relation_requirements["details"]["mixing_temperature_swelling_cycles"]["fragments"][0]
    assert detail["raw_matched"]
    assert detail["excluded_statements"]
    assert detail["matched"] == []


@pytest.mark.parametrize("text", [
    "Measurements show mixing temperature did not affect swelling during heating and cooling.",
    "No effect of mixing temperature on swelling during heating and cooling was observed.",
    "Измерения показали: температура смешения не влияет на набухание при нагреве и охлаждении.",
])
def test_measured_null_effect_is_not_an_unperformed_experiment(text):
    result = assess_relation_requirements(CYCLES, [text])
    assert not result["missing"]
    detail = result["details"]["mixing_temperature_swelling_cycles"]["fragments"][0]
    assert detail["excluded_statements"] == []


def test_disqualified_sentence_cannot_lend_missing_cues_to_observation():
    text = "Mixing temperature affects swelling. Swelling during heating and cooling was not measured."
    result = assess_relation_requirements(CYCLES, [text])
    assert result["missing"] == ["mixing_temperature_swelling_cycles"]
    fragment = result["details"]["mixing_temperature_swelling_cycles"]["fragments"][0]
    assert fragment["missing"] == ["heating", "cooling"]


@pytest.mark.parametrize("separate_fragment", [False, True])
def test_observation_survives_separate_hypothesis(separate_fragment):
    hypothesis = "We hypothesize that mixing temperature affects swelling during heating and cooling."
    observation = "We measured swelling during heating and cooling: mixing temperature had no effect."
    texts = [hypothesis, observation] if separate_fragment else [hypothesis + " " + observation]
    result = assess_evidence_adequacy(CYCLES, [SimpleNamespace(text=text) for text in texts])
    assert result.adequate
    assert not result.relation_requirements["missing"]


def test_unrelated_unperformed_measurement_does_not_veto_observed_relation():
    text = ("Mechanical strength was not measured. "
            "Mixing temperature affected swelling during heating and cooling in our measurements.")
    assert assess_evidence_adequacy(CYCLES, [SimpleNamespace(text=text)]).adequate


def test_statement_filter_does_not_expand_question_scope():
    result = assess_relation_requirements("Was the mechanical strength test performed?", ["Tests were not performed."])
    assert result["required"] == []
    assert result["missing"] == []


@pytest.mark.parametrize("text", [
    "Mixing temperature was recorded for sample A. Swelling was measured in sample B. "
    "Heating and cooling calibrated the instrument.",
    "Heating and cooling were applied to sample A. Mixing temperature affected swelling in sample B.",
    "Температура смешения зарегистрирована для образца А. Набухание измерено для образца Б. "
    "Нагрев и охлаждение использовали для калибровки прибора.",
])
def test_fragment_cue_inventory_does_not_supply_local_links(text):
    result = assess_evidence_adequacy(CYCLES, [SimpleNamespace(text=text)],
                                      concept_terms={"swelling": {"en": ["swelling"], "ru": ["набухание"]}})
    detail = result.relation_requirements["details"]["mixing_temperature_swelling_cycles"]
    assert detail["local_link_candidate_indices"] == []
    assert result.relation_requirements["local_links_policy"] == "diagnostic_only_not_adequacy_veto"
    fragment = detail["fragments"][0]
    assert fragment["missing"] == []
    assert fragment["missing_local_links"]


def test_local_links_can_describe_heating_and_cooling_in_separate_sentences():
    text = ("Mixing temperature affected swelling. Swelling increased during heating. "
            "Swelling was unchanged during cooling.")
    result = assess_evidence_adequacy(CYCLES, [SimpleNamespace(text=text)])
    assert result.adequate
    fragment = result.relation_requirements["details"]["mixing_temperature_swelling_cycles"]["fragments"][0]
    assert fragment["missing_local_links"] == []
    assert fragment["local_links"]["swelling_cooling"]["matching_statement_indices"] == [2]


def test_hypothesis_cannot_supply_missing_local_link():
    text = ("We hypothesize that mixing temperature affects swelling. Mixing temperature was recorded. "
            "Swelling was measured during heating and cooling.")
    result = assess_relation_requirements(CYCLES, [text])
    fragment = result["details"]["mixing_temperature_swelling_cycles"]["fragments"][0]
    assert fragment["missing"] == []
    assert fragment["missing_local_links"] == ["temperature_swelling"]
    assert fragment["local_links"]["swelling_cooling"]["matching_statement_indices"] == [2]
    assert not result["missing"]  # Local links are diagnostics, not a production veto.
    assert result["details"]["mixing_temperature_swelling_cycles"]["local_link_candidate_indices"] == []


def test_local_links_cannot_be_combined_across_fragments():
    texts = ["Mixing temperature affected swelling.", "Swelling increased during heating and cooling."]
    assert assess_relation_requirements(CYCLES, texts)["missing"]


def test_composition_context_does_not_require_cycle_links():
    text = "Conductivity was measured in a mixture with varying compositions."
    result = assess_relation_requirements(COMPOSITION, [text])
    assert not result["missing"]
    fragment = result["details"]["mixture_composition_conductivity"]["fragments"][0]
    assert fragment["local_links"] == {}


def test_pronoun_reference_keeps_production_adequacy_despite_missing_local_links():
    text = ("Mixing temperature affected swelling of the membrane. This response was measured during heating and cooling: "
            "it increased during heating and remained constant during cooling.")
    result = assess_evidence_adequacy(CYCLES, [SimpleNamespace(text=text)])
    assert result.adequate
    detail = result.relation_requirements["details"]["mixing_temperature_swelling_cycles"]
    assert detail["matching_evidence_indices"] == [0]
    assert detail["local_link_candidate_indices"] == []
