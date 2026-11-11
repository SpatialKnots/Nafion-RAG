"""No real network or database; scientific rewrite boundaries and experimental isolation."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import query_rewriting_experiment as qr

QUESTION = "Какие энергии активации для TFEME и TFEMEE?"
PLAN = {"english_question": "What are activation energies for TFEME and TFEMEE?",
        "keywords": ["activation energy", "TFEME", "TFEMEE"], "requirements": ["Reported activation energies for both ethers"]}


def test_strict_translation_and_literal_entities():
    assert qr.validate(PLAN, QUESTION) == PLAN
    assert qr.identifiers("LiCoPO₄ при25°C") == ["LiCoPO₄", "C"]


@pytest.mark.parametrize("change", ["extra", "missing_entity", "new_number", "lost_number", "russian", "oversized", "duplicates"])
def test_invalid_rewrites_are_never_repaired(change):
    plan = {**PLAN, "keywords": list(PLAN["keywords"])}
    question = QUESTION
    if change == "extra":
        plan["answer"] = "pretend answer"
    elif change == "missing_entity":
        plan["english_question"] = "What is activation energy for TFEME?"
    elif change == "new_number":
        plan["requirements"] = ["Value should be11.20"]
    elif change == "lost_number":
        question += " при25°C"
    elif change == "russian":
        plan["english_question"] += " энергия"
    elif change == "oversized":
        plan["keywords"] = ["x" * 501]
    else:
        plan["keywords"] *= 2
    with pytest.raises(ValueError):
        qr.validate(plan, question)


def test_request_has_only_original_question_context_and_locked_identifiers():
    from app.generation.gigachat import _json

    request = _json(qr.request({"id": "Satoh_08", "question_original": QUESTION}, "GigaChat-2-Max"))
    user = _json(request["messages"][1]["content"])
    assert set(user) == {"question", "article_context", "locked_identifiers"}
    assert user["question"] == QUESTION
    assert request["max_tokens"] == 1200
    assert "reference" not in user and "evidence" not in user


def test_adapter_restores_functions_and_enforces_original_required_concepts():
    from app.generation import service
    from app.generation.evidence_adequacy import assess_evidence_adequacy
    from app.retrieval import search

    original = "По статье Satoh (2013): " + QUESTION
    original_rank = search.rank_context
    original_assess = service.assess_evidence_adequacy
    evidence = [SimpleNamespace(text="Activation energies TFEME TFEMEE")]
    baseline = assess_evidence_adequacy(original, evidence)
    veto = replace(baseline, required_concepts=replace(baseline.required_concepts, missing=["required_identity"]))
    translated = replace(baseline, adequate=True)
    with patch.object(service, "assess_evidence_adequacy", side_effect=[veto, translated]):
        with qr.activate(original, PLAN):
            result = service.assess_evidence_adequacy(original, evidence)
            assert not result.adequate and result.reason == "missing_required_concepts"
            with pytest.raises(ValueError, match="different"):
                service.assess_evidence_adequacy("unrelated", evidence)
    assert service.assess_evidence_adequacy is original_assess
    assert search.rank_context is original_rank


def test_rewrite_rank_uses_english_but_preserves_objects_and_bound_top_k():
    from app.retrieval import search

    rows = [SimpleNamespace(full_text="Title", snippet="Title"),
            SimpleNamespace(full_text="Unrelated methods", snippet=""),
            SimpleNamespace(full_text="TFEME TFEMEE activation energy", snippet="")]
    with qr.activate("По статье Satoh (2013): " + QUESTION, PLAN):
        selected, metadata = search.rank_context("По статье Satoh (2013): " + QUESTION, rows, top_k=2)
    assert selected == [rows[0], rows[2]]
    assert selected[0] is rows[0] and metadata["query_rewritten"]
