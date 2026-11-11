"""Actual service/ASGI integration with synthetic transport and no DB/model execution."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.generation.answer_support import AuditedAnswerProvider
from app.generation.providers import GeneratedClaim, ProviderResult
from app.retrieval.search import SearchResponse, SearchResult

CASES = {
    "status": ("organofluorine compounds identified", "The organofluorine compounds have not been identified.",
               "The organofluorine compounds were identified.", "insufficient_evidence"),
    "role": ("SEI CFx POxFy composition", "SEI morphology was measured. The CEI contains CFx and POxFy.",
             "SEI contains CFx and POxFy.", "insufficient_evidence"),
    "energy": ("energy density", "Energy density of731 Wh kg−1 based on the total cathode/anode masses is achieved.",
               "Energy density731Wh/kg.", "insufficient_evidence"),
    "mixture": ("cycling efficiency ABC DEF", "The cycling efficiency of the EC−ABC and EC−DEF systems maintained about73%.",
                "Cycling efficiency of ABC and DEF is73%.", "insufficient_evidence"),
    "retained": ("CEI CFx POxFy composition", "The CEI contains CFx and POxFy.",
                 "CEI contains CFx and POxFy.", "answered"),
}


class NativeProvider:
    def __init__(self, text):
        self.calls = 0
        self.native = ProviderResult(True, [GeneratedClaim(text, ["E1"])], "synthetic", "offline-frozen")

    def generate(self, *args, **kwargs):
        self.calls += 1
        return self.native


@pytest.mark.parametrize("mode", CASES)
def test_actual_service_and_asgi_use_same_opt_in_whole_answer_decision(monkeypatch, mode):
    import app.main as main
    from app.db.session import get_session
    from app.generation import service

    question, body, text, expected = CASES[mode]
    native, reports = NativeProvider(text), []
    settings = Settings(_env_file=None, gigachat_credentials="offline-placeholder")
    result = SearchResult(article_id="00000000-0000-0000-0000-000000000001",
        chunk_id="00000000-0000-0000-0000-000000000002", title="Constructed evidence", doi=None,
        page_start=2, page_end=3, source_type="main_text", snippet=body, full_text=body,
        score=1.0, retrieval_method="frozen_synthetic")
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: SearchResponse(query=question, results=[result]))
    monkeypatch.setattr(service, "build_answer_provider", lambda s: AuditedAnswerProvider(native, reports.append))
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    direct = service.answer_question(object(), settings, question, answer_language="en")
    assert direct.status == expected
    assert native.calls == 1 and native.native.answerable is True and native.native.claims[0].text == text

    def session():
        yield object()

    main.app.dependency_overrides[get_session] = session
    try:
        with TestClient(main.app) as client:
            response = client.post("/answer", json={"question": question, "answer_language": "en"})
    finally:
        main.app.dependency_overrides.pop(get_session, None)
    assert response.status_code == 200 and response.json() == service.answer_response_to_dict(direct)
    assert native.calls == 2  # one synthetic result per separately executed direct/ASGI request
    assert len(reports) == 2 and reports[0] == reports[1]
    if expected == "answered":
        assert response.json()["claims"][0]["text"] == text
    else:
        assert response.json()["answer"] is None and response.json()["claims"] == []
