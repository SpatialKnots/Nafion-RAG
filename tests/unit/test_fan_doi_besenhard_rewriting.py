"""Synthetic API controls for the connected profile; no real model or corpus DB."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.generation import required_fields_guard_routes as routes
from app.generation import service
from app.generation.providers import GeneratedClaim, ProviderResult
from app.main import app
from app.retrieval.search import SearchResponse, SearchResult
from scripts import fan_doi_besenhard_rewriting_20261113 as connected
from scripts import query_rewriting_v02 as qr

QUESTION = "Каковы ограничения карбонатных электролитов?"
ENGLISH = "What are the limitations of carbonate electrolytes?"
ORIGINAL = "По статье Author (2020): " + QUESTION
TITLE = "Limitations of carbonate electrolytes"
ARTICLE = "00000000-0000-0000-0000-000000000001"
CONTEXT = {"article_id": ARTICLE, "title": TITLE, "title_sha256": connected.f.sha(TITLE.encode()),
           "original_pdf_sha256": "a" * 64}
CASE = {"id": "Synthetic", "question_original": QUESTION, "question": ORIGINAL,
        "article_id": ARTICLE, "original_pdf_sha256": "a" * 64}
BODY = "Limitations of carbonate electrolytes include oxidation and reactivity with metal."


@pytest.fixture
def runtime(monkeypatch):
    class Session:
        def __init__(self):
            self.statements, self.rollbacks = [], 0

        def execute(self, statement):
            self.statements.append(str(statement))

        def rollback(self):
            self.rollbacks += 1

    class Provider:
        def __init__(self):
            self.inputs = []

        def generate(self, question, evidence, **kwargs):
            self.inputs.append((question, evidence))
            return ProviderResult(True, [GeneratedClaim(BODY, ["E1"])], "synthetic", "offline")

    session, provider = Session(), Provider()
    result = SearchResult(article_id=ARTICLE, chunk_id="00000000-0000-0000-0000-000000000002",
        title="Author 2020", doi=None, page_start=1, page_end=1, source_type="main_text",
        snippet=BODY, full_text=BODY, score=1, retrieval_method="synthetic")
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: SearchResponse(query=ORIGINAL, results=[result]))
    monkeypatch.setattr(routes, "make_provider", lambda s: provider)
    settings = Settings(_env_file=None, gigachat_credentials="offline-placeholder")

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client, session, provider
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)


def test_connected_actual_api_uses_translation_for_admission_and_original_for_answer(runtime):
    client, session, provider = runtime
    before = client.post("/answer/experimental/required-fields", json={"question": ORIGINAL}).json()
    assert before["answer"]["status"] == "insufficient_evidence" and not provider.inputs
    plan = qr.normalize({"english_question": ENGLISH}, QUESTION, CONTEXT)
    original_assess = service.assess_evidence_adequacy
    with connected.activate(CASE, plan):
        after = client.post("/answer/experimental/required-fields", json={"question": ORIGINAL}).json()
    assert after["answer"]["status"] == "answered"
    assert len(provider.inputs) == 1 and provider.inputs[0][0] == ORIGINAL
    assert provider.inputs[0][1][0].text == BODY
    diagnostic = after["answer"]["metadata"]["evidence_adequacy"]["concept_coverage"]["rewriting_experiment"]
    assert diagnostic["version"] == qr.VERSION and not diagnostic["original_assessment"]["adequate"]
    assert service.assess_evidence_adequacy is original_assess
    again = client.post("/answer/experimental/required-fields", json={"question": ORIGINAL}).json()
    assert again["answer"]["status"] == "insufficient_evidence" and len(provider.inputs) == 1
    assert session.rollbacks == 3
    assert all(s == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY" for s in session.statements)


def test_connected_api_does_not_remove_original_material_veto(runtime):
    client, _, provider = runtime
    question = "Каковы ограничения PBI карбонатных электролитов?"
    case = {**CASE, "question_original": question, "question": "По статье Author (2020): " + question}
    plan = qr.normalize({"english_question": "What are the limitations of PBI carbonate electrolytes?"}, question, CONTEXT)
    with connected.activate(case, plan):
        data = client.post("/answer/experimental/required-fields", json={"question": case["question"]}).json()
    assert data["answer"]["status"] == "insufficient_evidence" and not provider.inputs
    assert "polybenzimidazole" in data["answer"]["metadata"]["evidence_adequacy"]["required_concepts"]["missing"]


def test_original_relation_veto_is_preserved(monkeypatch):
    assessment = service.assess_evidence_adequacy
    calls = []

    def assess(question, evidence, **kwargs):
        result = assessment(question, evidence, **kwargs)
        calls.append(question)
        if question == ORIGINAL:
            return replace(result, relation_requirements={**result.relation_requirements, "missing": ["condition"]})
        return replace(result, adequate=True)

    monkeypatch.setattr(service, "assess_evidence_adequacy", assess)
    plan = qr.normalize({"english_question": ENGLISH}, QUESTION, CONTEXT)
    with connected.activate(CASE, plan):
        result = service.assess_evidence_adequacy(ORIGINAL, [])
    assert not result.adequate and result.reason == "missing_relation_context"
    assert calls == [ORIGINAL, ENGLISH]


@pytest.mark.parametrize("key,value", [("article_id", "other"), ("original_pdf_sha256", "b" * 64)])
def test_plan_bound_to_different_article_is_rejected(key, value):
    plan = qr.normalize({"english_question": ENGLISH}, QUESTION, CONTEXT)
    with pytest.raises(ValueError, match="article drift"):
        with connected.activate({**CASE, key: value}, plan):
            pytest.fail("Mismatched plan activated")


def test_profile_guard_rejects_reference_and_assessment_files():
    guard = connected.ReferenceGuard()
    for path in (connected.baseline.USER_FILE, connected.baseline.PRIVATE / "supplied_original.md",
                 connected.BASE / "assessment_v01/report.json"):
        with pytest.raises(PermissionError):
            guard("open", (str(path), "r", 0))
    assert len(guard.denied) == 3


def test_profile_guard_allows_only_question_plan_and_baseline_inputs():
    guard = connected.ReferenceGuard()
    for path in (connected.FREEZE / "questions.json", connected.BASE / "plans_freeze_v01/plans.json",
                 connected.baseline.FREEZE / "questions.json", connected.baseline.INVENTORY):
        guard("open", (str(path), "r", 0))
    assert not guard.denied


def test_missing_live_authorization_cannot_enter_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(connected, "BASE", tmp_path)
    monkeypatch.setattr(connected, "cases", lambda: [])
    with pytest.raises(FileNotFoundError):
        with connected.rewrite_environment():
            pytest.fail("Live scope opened without authorization")
