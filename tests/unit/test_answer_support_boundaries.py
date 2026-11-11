"""Adverse scientific-boundary probes, separate from the already frozen v0.1 measurement."""

import pytest

from app.generation.answer_support import audit
from app.generation.providers import Evidence, GeneratedClaim


def run(text, bodies, question="What was identified?"):
    sources = [Evidence(f"E{i}", "work", f"chunk{i}", None, None, 1, 1, "main_text", body,
                        1.0, "constructed", {}, {}) for i, body in enumerate(bodies, 1)]
    claims = [GeneratedClaim(text, [e.citation_id for e in sources])]
    return audit(question, claims, sources)


@pytest.mark.parametrize("source,claim", [
    ("The organofluorine compounds have not been characterized.", "Organofluorine compounds were identified."),
    ("The organofluorine compounds have not been established.", "Organofluorine compounds were identified."),
    ("The organofluorine compounds have not been identified.", "Organofluorine compounds were characterized."),
    ("The organofluorine compounds have not been identified.", "Авторы установили проводимость органофторных соединений."),
])
def test_identification_characterization_and_establishment_are_distinct_predicates(source, claim):
    assert run(claim, [source])["decision"] == "not_blocked_by_finite_checks"


def test_characterization_does_not_cancel_explicit_negative_identification():
    report = run("Organofluorine compounds were identified.", [
        "The organofluorine compounds have not been identified.", "The organofluorine compounds were characterized."])
    assert report["decision"] == "withhold_conflict"


@pytest.mark.parametrize("prefix,expected", [("RUN", "not_blocked_by_finite_checks"), ("EC", "withhold_incomplete")])
def test_arbitrary_hyphenated_sample_code_does_not_prove_a_co_solvent(prefix, expected):
    body = f"The cycling efficiency of the {prefix}−ABC systems maintained about73%."
    assert run("Cycling efficiency of ABC is73%.", [body], "Cycling efficiency of ABC?")["decision"] == expected


@pytest.mark.parametrize("claim,source", [
    ("Источник ошибочно сообщает, что SEI содержит CFx и POxFy.", "The CEI contains CFx and POxFy."),
    ("It is incorrectly claimed that organofluorine compounds were identified.",
     "The organofluorine compounds have not been identified."),
])
def test_explicit_error_reporting_is_not_treated_as_unqualified_endorsement(claim, source):
    assert run(claim, [source])["decision"] == "not_blocked_by_finite_checks"
