"""Constructed status/role/coverage controls, never independent scientific evaluation."""

from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from app.generation.answer_support import AuditedAnswerProvider, audit
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError, ProviderResult

NEGATIVE = "The organofluorine compounds have not been identified. The possible compounds are lithium alkoxides."
ASSERTION = "Авторы идентифицировали возможные органофторсодержащие соединения как литиевые алкоксиды."
GRAPH = ("SEI morphology was measured. XPS confirmed the high F contents in the CEI on the cathode. "
         "These fluorine-containing species (CFx and POxFy species) are resistant to oxidation.")
ENERGY = "A high energy density of >\u200b731 Wh kg−1 based on the total cathode/anode masses is achieved."
MIXTURE = "The cycling efficiency of the EC−ABC and the EC−DEF systems maintained about 73% even at the 41st cycle."


def source(text, cid="E1", article="work", kind="main_text"):
    return Evidence(cid, article, "chunk-" + cid, "Title", None, 2, 3, kind, text, 1.0, "frozen", {}, {})


def check(text, body=NEGATIVE, question="Что установлено?", more=None, cites=None):
    return audit(question, [GeneratedClaim(text, cites or ["E1"])], [source(body), *(more or [])])


@pytest.mark.parametrize("text", [ASSERTION, "Organofluorine compounds were identified.",
                                "Авторы идентифицировали органофторсодержащие соединения."])
def test_affirmative_identification_conflicts_with_explicit_negative(text):
    report = check(text)
    assert report["decision"] == "withhold_conflict"
    assert report["claims"][0]["findings"][0]["code"] == "identification_status_conflict"


@pytest.mark.parametrize("text", ["Органофторсодержащие соединения не были идентифицированы.",
    "Authors suggested organofluorine compounds could be identified.",
    "Если органофторсодержащие соединения идентифицированы, нужны дополнительные данные.",
    "Возможно органофторсодержащие соединения идентифицированы.",
    "Авторы предположили состав, но не идентифицировали органофторсодержащие соединения.",
    "LiF identified; organofluorine compounds were not identified.",
    "LiF identified and organofluorine compounds were not identified.",
    "LiF identified, although the organofluorine compounds remain unknown."])
def test_negation_conditional_or_other_subject_does_not_become_status_conflict(text):
    assert check(text)["decision"] == "not_blocked_by_finite_checks"


@pytest.mark.parametrize("body", ["Previous work: " + NEGATIVE, "Hypothetical: " + NEGATIVE,
    "The reduction products have not been identified.", "The organofluorine compounds were identified."])
def test_noncurrent_different_or_positive_source_is_not_negative_identification(body):
    assert check(ASSERTION, body)["decision"] == "not_blocked_by_finite_checks"


def test_conflicting_current_source_status_remains_unresolved():
    positive = source("The organofluorine compounds were identified.", "E2")
    report = check(ASSERTION, more=[positive], cites=["E1", "E2"])
    assert report["decision"] == "not_blocked_by_finite_checks"
    assert {o["kind"] for o in report["claims"][0]["source_status_observations"]} == {"identified", "not_identified"}


def test_only_cited_raw_sources_supply_observations():
    positive = "The organofluorine compounds were identified."
    assert check(ASSERTION, positive, more=[source(NEGATIVE, "E2")])["decision"] == "not_blocked_by_finite_checks"
    report = audit("Question", [GeneratedClaim(ASSERTION, ["E1"])], [source(NEGATIVE, kind="source_fact_derived")])
    assert report["decision"] == "not_blocked_by_finite_checks"


def test_cross_work_sources_are_not_silently_joined():
    report = check(ASSERTION, more=[source(NEGATIVE, "E2", "different-work")], cites=["E1", "E2"])
    assert report["claims"][0]["semantic_support"] == "cross_work_binding_not_evaluated"
    assert report["decision"] == "not_blocked_by_finite_checks"


@pytest.mark.parametrize("body,text", [
    ("The CEI contains CFx and POxFy.", "SEI содержит CFx и POxFy."),
    ("The SEI consists of LiF and Li2O.", "CEI contains LiF and Li2O."),
    (GRAPH, "Состав SEI обогащён соединениями CFx и POxFy."),
    ("The CEI contains LiF, CFx and POxFy.", "SEI contains CFx and POxFy."),
])
def test_linked_composition_fingerprint_cannot_change_interphase_owner(body, text):
    report = check(text, body)
    assert report["decision"] == "withhold_conflict"
    assert report["claims"][0]["findings"][0]["code"] == "interphase_role_conflict"


@pytest.mark.parametrize("text", ["CEI contains CFx and POxFy.", "SEI may contain CFx and POxFy.",
    "SEI possibly contains CFx and POxFy.",
    "SEI does not contain CFx and POxFy.", "SEI and CEI contain different amounts of CFx and POxFy.",
    "SEI contains LiF and Li2O."])
def test_correct_negated_hedged_multi_role_or_different_fingerprint_is_not_role_conflict(text):
    assert check(text, GRAPH)["decision"] == "not_blocked_by_finite_checks"


@pytest.mark.parametrize("body", [
    "The CEI is dense. Various compounds (CFx and POxFy) were analyzed.",
    "The CEI may contain CFx and POxFy.",
    "The CEI can contain CFx and POxFy.",
    "The possible CEI contains CFx and POxFy.",
    "XPS confirmed the CEI composition. These species in SEI (CFx and POxFy) are stable.",
])
def test_role_membership_alone_or_unresolved_anaphor_is_insufficient(body):
    assert check("SEI contains CFx and POxFy.", body)["decision"] == "not_blocked_by_finite_checks"


def test_same_fingerprint_in_both_source_roles_is_not_a_unique_owner():
    report = check("SEI contains CFx and POxFy.", "The CEI contains CFx and POxFy.",
                   more=[source("The SEI contains CFx and POxFy.", "E2")], cites=["E1", "E2"])
    assert report["decision"] == "not_blocked_by_finite_checks"


@pytest.mark.parametrize("text", ["Удельная энергия превышает731Вт·ч/кг.",
                                 "Energy density is731 Wh/kg, not based on the total cathode/anode masses."])
def test_source_bound_energy_requires_mass_denominator(text):
    report = check(text, ENERGY, "Какую удельную энергию получили?")
    assert report["decision"] == "withhold_incomplete"
    assert report["completeness_findings"][0]["code"] == "missing_energy_mass_basis"


@pytest.mark.parametrize("text", ["Удельная энергия731Вт·ч/кг на суммарную массу анода и катода.",
    "Energy density is731Wh/kg based on total cathode/anode masses.",
    "Это не энергия полной ячейки:731Вт·ч/кг отнесено к суммарной массе анода и катода.",
    "Температура составляет731°C.", "Energy density0.731kWh/kg was reported."])
def test_explicit_mass_basis_or_unbound_other_quantity_does_not_trigger_gap(text):
    assert check(text, ENERGY, "Какую удельную энергию получили?")["decision"] == "not_blocked_by_finite_checks"


@pytest.mark.parametrize("prefix", ["Prior literature: ", "Hypothetical "])
def test_noncurrent_energy_is_not_a_current_contract(prefix):
    assert check("Energy density731Wh/kg.", prefix + ENERGY, "Specific energy?")["decision"] == "not_blocked_by_finite_checks"


def test_conflicting_energy_mass_bases_are_not_forced_to_one_contract():
    alternative = source("Energy density of731 Wh kg−1 based on the full cell mass was reported.", "E2")
    report = check("Energy density731Wh/kg.", ENERGY, "Specific energy?", [alternative], ["E1", "E2"])
    assert report["decision"] == "not_blocked_by_finite_checks"
    assert any(i["status"] == "ambiguous_source_bases_not_evaluated" for i in report["completeness_inspection"])


def test_named_mixture_performance_keeps_co_component_condition():
    report = check("Cycling efficiency of ABC and DEF is73%.", MIXTURE, "Cycling efficiency of ABC and DEF?")
    assert report["decision"] == "withhold_incomplete"
    assert report["completeness_findings"][0]["required_prefix"] == "EC"


def test_pdf_spacing_between_approximation_and_percentage_does_not_erase_condition():
    report = check("Cycling efficiency of ABC is73%.", MIXTURE.replace("about 73", "about73"),
                   "Cycling efficiency of ABC?")
    assert report["decision"] == "withhold_incomplete"


@pytest.mark.parametrize("text", ["EC–ABC and EC–DEF cycling efficiency is73%.",
    "В смеси с этиленкарбонатом эффективность циклирования ABC и DEF составляет73%.",
    "With ethylene carbonate, ABC and DEF cycling efficiency is73.0%."])
def test_explicit_mixture_or_recognized_co_component_alias_is_retained(text):
    assert check(text, MIXTURE, "Cycling efficiency of ABC and DEF?")["decision"] == "not_blocked_by_finite_checks"


@pytest.mark.parametrize("question,text,body", [
    ("Conductivity of ABC?", "Efficiency73%.", MIXTURE),
    ("Cycling efficiency of XYZ?", "Cycling efficiency73%.", MIXTURE),
    ("Cycling efficiency of ABC?", "Cycling efficiency74%.", MIXTURE),
    ("Cycling efficiency of ABC?", "Cycling efficiency73%.", "Future: " + MIXTURE),
])
def test_unbound_mixture_question_value_or_source_is_not_a_gap(question, text, body):
    assert check(text, body, question)["decision"] == "not_blocked_by_finite_checks"


def test_duplicate_overlapping_mixture_sources_do_not_count_as_independent_gaps():
    report = check("Cycling efficiency of ABC is73%.", MIXTURE, "Cycling efficiency of ABC?",
                   [source(MIXTURE, "E2")], ["E1", "E2"])
    assert len(report["completeness_findings"]) == 1


def test_every_finding_anchor_matches_unchanged_raw_source():
    evidence = [source(NEGATIVE)]
    claims = [GeneratedClaim(ASSERTION, ["E1"])]
    frozen = deepcopy([asdict(evidence[0]), asdict(claims[0])])
    report = audit("Question", claims, evidence)
    for finding in report["claims"][0]["findings"]:
        for observation in finding["source_observations"]:
            a = observation["anchor"]
            assert evidence[0].text[a["start"]:a["end"]] == a["text"]
    assert [asdict(evidence[0]), asdict(claims[0])] == frozen
    assert report["not_evaluated"] and not report["repair_performed"]


class FrozenProvider:
    def __init__(self, result):
        self.result, self.calls, self.arguments = result, 0, None

    def generate(self, question, evidence, *, answer_style="claims", answer_language="auto"):
        self.calls += 1
        self.arguments = question, evidence, answer_style, answer_language
        return self.result


def test_opt_in_wrapper_abstains_without_retry_repair_or_partial_selection():
    native = ProviderResult(True, [GeneratedClaim(ASSERTION, ["E1"])], "synthetic", "frozen")
    provider, reports, evidence = FrozenProvider(native), [], [source(NEGATIVE)]
    result = AuditedAnswerProvider(provider, reports.append).generate("Question", evidence, answer_language="ru")
    assert not result.answerable and result.claims == [] and native.claims[0].text == ASSERTION
    assert provider.calls == 1 and provider.arguments[1] is evidence
    assert reports[0]["wrapper_decision"] == {"origin": "deterministic_finite_source_audit", "native_answerable": True,
                                            "guarded_answerable": False, "second_provider_call": False}


def test_callback_cannot_mutate_the_decision_already_computed():
    provider = FrozenProvider(ProviderResult(True, [GeneratedClaim(ASSERTION, ["E1"])], "synthetic", None))
    guarded = AuditedAnswerProvider(provider, lambda r: r.update(decision="not_blocked_by_finite_checks"))
    assert not guarded.generate("Question", [source(NEGATIVE)]).answerable and provider.calls == 1


def test_good_or_original_abstention_is_preserved_as_same_result():
    for native in (ProviderResult(True, [GeneratedClaim("CEI contains CFx and POxFy.", ["E1"])], "synthetic", None),
                   ProviderResult(False, [], "synthetic", None)):
        provider = FrozenProvider(native)
        assert AuditedAnswerProvider(provider).generate("Question", [source(GRAPH)]) is native
        assert provider.calls == 1


def test_inconsistent_provider_contract_and_unbound_citations_fail_loudly():
    provider = FrozenProvider(ProviderResult(False, [GeneratedClaim(ASSERTION, ["E1"])], "synthetic", None))
    with pytest.raises(GenerationOutputError):
        AuditedAnswerProvider(provider).generate("Question", [source(NEGATIVE)])
    for citations in (["unknown"], ["E1", "E1"], []):
        with pytest.raises(ValueError):
            audit("Question", [GeneratedClaim(ASSERTION, citations)], [source(NEGATIVE)])
    with pytest.raises(ValueError):
        audit("Question", [GeneratedClaim(ASSERTION, ["E1"])], [source(NEGATIVE), source(NEGATIVE)])


def test_transport_budgets_and_nonfinite_metadata_are_not_accepted():
    with pytest.raises(ValueError, match="budget"):
        audit("Q", [GeneratedClaim("x", ["E1"])] * 65, [source(NEGATIVE)])
    with pytest.raises(ValueError, match="budget"):
        check("x", "x" * 300000)
    with pytest.raises(ValueError):
        audit("Q", [GeneratedClaim("x", ["E1"])], [replace(source(NEGATIVE), score=float("nan"))])
