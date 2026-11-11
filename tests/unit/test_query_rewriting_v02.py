"""Independent field validity, title constraints and unchanged experiment isolation."""

import hashlib
import json
from unittest.mock import patch

import pytest

from scripts import query_rewriting_experiment as old
from scripts import query_rewriting_v02 as qr

TITLE = "Physical and Electrolytic Properties of Trifluorinated Linear Ethers"
CONTEXT = {"article_id": "a", "title": TITLE, "title_sha256": hashlib.sha256(TITLE.encode()).hexdigest(),
           "original_pdf_sha256": "a" * 64}
QUESTION = "Какие эфиры изучали?"
ENGLISH = "Which ethers were studied?"


@pytest.mark.parametrize("keywords", [None, "", {}, [], [""], [" ", "ethers", "ethers"], ["density", 3],
                                      ["x" * 301], ["value11.20"], ["esters"], ["k" + chr(97+i) for i in range(9)]])
def test_auxiliary_fault_does_not_destroy_valid_translation(keywords):
    plan = qr.normalize({"english_question": ENGLISH, "keywords": keywords}, QUESTION, CONTEXT)
    assert plan["english_question"] == ENGLISH
    assert len(plan["keywords"]) <= 6
    assert qr.validate(plan, QUESTION) is plan
    assert plan["requirements"] == []


def test_optional_keywords_may_be_absent():
    plan = qr.normalize({"english_question": ENGLISH}, QUESTION, CONTEXT)
    assert plan["keywords"] == [] and not plan["normalization_diagnostics"]


@pytest.mark.parametrize("english", ["", "Какие эфиры?", "Which esters were studied?", "Which diesters were studied?",
                                     "Which ethers were studied at25 degrees?"])
def test_invalid_question_is_not_silently_repaired(english):
    with pytest.raises(ValueError):
        qr.normalize({"english_question": english}, QUESTION, CONTEXT)


def test_post_charge_hold_is_not_soaking():
    question = "Почему выдержка48часов после заряда до5В?"
    with pytest.raises(ValueError, match="soaking"):
        qr.normalize({"english_question": "Why soak for48hours after charging to5V?"}, question, CONTEXT)
    assert qr.normalize({"english_question": "Why hold for48hours after charging to5V?"}, question, CONTEXT)


def test_lost_identifier_or_condition_still_blocks_translation():
    question = "Плотность EME при25°C?"
    for english in ("What is density at25°C?", "What is EME density at30°C?"):
        with pytest.raises(ValueError):
            qr.normalize({"english_question": english}, question, CONTEXT)


def test_verified_title_hash_and_article_scope_must_match():
    with pytest.raises(ValueError, match="title"):
        qr.context_valid({**CONTEXT, "title": "different"})
    with pytest.raises(ValueError, match="identity"):
        qr.request({"article_id": "different", "original_pdf_sha256": "a" * 64, "question_original": QUESTION},
                   "GigaChat-2-Max", CONTEXT)


def test_wire_request_contains_no_abstract_reference_or_previous_answer():
    case = {"article_id": "a", "original_pdf_sha256": "a" * 64, "question_original": QUESTION}
    native = json.loads(qr.request(case, "GigaChat-2-Max", CONTEXT))
    user = json.loads(native["messages"][1]["content"])
    assert set(user) == {"question", "verified_article", "locked_identifiers"}
    assert user["verified_article"]["title"] == TITLE
    assert native["response_format"]["schema"]["required"] == ["english_question"]


def test_unknown_or_duplicate_wire_keys_are_not_ignored():
    with pytest.raises(ValueError, match="schema"):
        qr.normalize({"english_question": ENGLISH, "answer": "finding"}, QUESTION, CONTEXT)
    envelope = {"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
        "content": '{"english_question":"Which ethers?","english_question":"Which esters?"}'}}]}
    with pytest.raises(ValueError, match="Duplicate"):
        qr.parse_response(json.dumps(envelope).encode(), QUESTION, CONTEXT)


def test_legacy_requirements_are_archived_without_changing_question():
    value = {"english_question": ENGLISH, "keywords": [""], "requirements": ["unrequested extra"]}
    plan = qr.normalize(value, QUESTION, CONTEXT, legacy=True)
    assert plan["requirements"] == []
    assert any(d["reason"] == "legacy_requirements_archived_not_executed" for d in plan["normalization_diagnostics"])


def test_v02_adapter_restores_old_validator_and_functions():
    from app.generation import service
    from app.retrieval import search

    question = "По статье Author (2020): " + QUESTION
    plan = qr.normalize({"english_question": ENGLISH}, QUESTION, CONTEXT)
    rank, assess, validator = search.rank_context, service.assess_evidence_adequacy, old.validate
    with qr.activate(question, plan):
        assert old.validate is qr.validate
        assert search.rank_context is not rank
    assert search.rank_context is rank and service.assess_evidence_adequacy is assess and old.validate is validator


def test_canonical_keyword_mutation_cannot_hide_as_normalization():
    plan = qr.normalize({"english_question": ENGLISH}, QUESTION, CONTEXT)
    with pytest.raises(ValueError, match="normalization"):
        qr.validate({**plan, "keywords": [""]}, QUESTION)


def test_v02_uses_original_required_concept_veto():
    from dataclasses import replace
    from types import SimpleNamespace

    from app.generation import service
    from app.generation.evidence_adequacy import assess_evidence_adequacy

    original = "По статье Author (2020): " + QUESTION
    evidence = [SimpleNamespace(text="Which ethers were studied")]
    baseline = assess_evidence_adequacy(original, evidence)
    veto = replace(baseline, required_concepts=replace(baseline.required_concepts, missing=["identity"]))
    plan = qr.normalize({"english_question": ENGLISH}, QUESTION, CONTEXT)
    with patch.object(service, "assess_evidence_adequacy", side_effect=[veto, replace(baseline, adequate=True)]):
        with qr.activate(original, plan):
            assert not service.assess_evidence_adequacy(original, evidence).adequate
