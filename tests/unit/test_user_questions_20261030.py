"""Verbatim question and offline-boundary controls; no real DB/provider calls."""

import json
from types import SimpleNamespace

import pytest

from scripts import gigachat_answer_smoke as smoke
from scripts import user_questions_20261030 as questions


def test_questions_preserve_verbatim_spelling_and_have_no_invented_gold():
    cases = questions.load_cases()
    assert len(cases) == 3 and "пре переходе" in cases[0]["question"]
    assert [(c["id"], c["question"]) for c in cases] == list(questions.EXPECTED)


def test_scope_restores_helper_provenance_after_failure():
    before = smoke.QUESTION, smoke.VERSION, smoke.PROTOCOL
    with pytest.raises(RuntimeError, match="constructed"):
        with questions.case_scope(questions.load_cases()[0]):
            assert smoke.QUESTION == questions.EXPECTED[0][1] and smoke.VERSION == questions.VERSION
            raise RuntimeError("constructed")
    assert (smoke.QUESTION, smoke.VERSION, smoke.PROTOCOL) == before


@pytest.mark.parametrize("generation_reached,size", [(True, 80), (True, 100001), (False, 0)])
def test_preparation_never_authorizes_or_reserves_live_calls(tmp_path, monkeypatch, generation_reached, size):
    settings = SimpleNamespace(default_collection="literature", rag_retrieval_method="hybrid_cross_lingual", rag_top_k=5,
        rag_model="GigaChat-2-Max", rag_gigachat_max_tokens=1200, rag_timeout_seconds=120, gigachat_scope="GIGACHAT_API_PERS")
    monkeypatch.setattr(smoke, "configure", lambda: settings)
    monkeypatch.setattr(smoke, "source_inputs", lambda *a: {})
    monkeypatch.setattr(smoke, "reserve", lambda *a, **k: pytest.fail("No live reservation during preparation"))
    monkeypatch.setattr(smoke, "Observation", lambda *a: SimpleNamespace(trace={"captured": True}, sources={"diagnostics": []},
        body=b"x" * size if size else None, result={}))

    def route(*args):
        if generation_reached:
            raise smoke.PreparedBoundary()
        return SimpleNamespace(status_code=200, json=lambda: {"status": "insufficient_evidence"})

    monkeypatch.setattr(smoke, "run_route", route)
    case = questions.load_cases()[0]
    result = questions.prepare(tmp_path, case, smoke.NetworkPolicy())
    contract = json.loads((tmp_path / case["id"] / "prepared/contract.json").read_bytes())
    assert contract["maximum_model_attempts"] == contract["maximum_oauth_attempts"] == contract["new_slot_reservations"] == 0
    assert contract["new_model_calls"] == contract["new_oauth_calls"] == 0
    assert (result["preparation_status"] == "ready_for_explicit_scope_authorization") == (generation_reached and size <= 100000)
