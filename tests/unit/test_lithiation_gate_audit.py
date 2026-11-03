"""Counterexamples prevent promoting a lexical workaround as a scientific fix."""

import pytest

from app.generation import evidence_adequacy as gate
from scripts import lithiation_gate_audit as audit


def test_noun_alias_changes_affirmative_and_nonperformance_together():
    controls = {row["id"]: row for row in audit.constructed_controls()}
    for name in ("affirmative_other_form", "negated_other_form", "heading_only", "future_only", "different_material"):
        variants = controls[name]["variants"]
        assert not variants["baseline"]["adequate"]
        assert variants["noun_alias_only"]["adequate"]
        assert variants["noun_alias_only"]["top_coverage"] == 0.5


def test_dropping_method_words_alone_admits_material_mention():
    text = ["Nafion membrane conductivity was measured."]
    assert not audit.probe(audit.QUESTION, text, "baseline")["adequate"]
    changed = audit.probe(audit.QUESTION, text, "drop_question_words_only")
    assert changed["adequate"] and changed["matched_terms"] == ["nafion"]


@pytest.mark.parametrize("variant", audit.VARIANTS)
def test_existing_identity_veto_survives_candidate(variant):
    question = audit.QUESTION + " Используется DMF?"
    result = audit.probe(question, ["Nafion. Проводили литирование ионным обменом в воде."], variant)
    assert not result["adequate"]
    assert result["reason"] == "missing_required_concepts"
    assert result["required_concepts"]["missing"] == ["dimethylformamide"]


@pytest.mark.parametrize("variant", audit.VARIANTS)
def test_no_evidence_still_rejected(variant):
    assert audit.probe(audit.QUESTION, [], variant)["reason"] == "no_evidence"


def test_original_exact_surface_already_admits_nonperformance():
    result = audit.probe(audit.QUESTION, ["Nafion. Литирования не проводили."], "baseline")
    assert result["adequate"]


def test_variant_restores_runtime_dictionaries_on_failure():
    common, synonyms = gate.COMMON_QUERY_TERMS, gate.DOMAIN_TERM_SYNONYMS
    with pytest.raises(RuntimeError, match="constructed"):
        with audit.variant_scope("alias_and_drop"):
            assert "литирования" in gate.DOMAIN_TERM_SYNONYMS
            raise RuntimeError("constructed")
    assert gate.COMMON_QUERY_TERMS is common
    assert gate.DOMAIN_TERM_SYNONYMS is synonyms


def test_unknown_variant_rejected():
    with pytest.raises(ValueError, match="Unknown offline gate variant"):
        audit.probe(audit.QUESTION, ["Nafion"], "runtime_override")


def test_source_offsets_preserve_exact_case_and_unicode():
    text = "α = 0. ЛИТИРОВАНИЕ\nмембраны; литирования."
    occurrences = audit.source_occurrences(text)
    assert len(occurrences) == 2
    for row in occurrences:
        assert text[row["start"]:row["end"]] == row["exact_text"]
    assert audit.source_occurrences("делитирование") == []
