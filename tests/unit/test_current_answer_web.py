"""Offline HTTP pipeline, archived-contract parity, failure and concurrency controls."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.generation import current_answer, current_answer_routes, query_rewriting, rewrite_context, service
from app.generation.gigachat import GigaChatAnswerProvider
from app.generation.providers import GeneratedClaim, GenerationUnavailableError, ProviderResult
from app.main import app
from app.retrieval import search as search_module
from app.retrieval.search import SearchResponse, SearchResult
from scripts import query_rewriting_v02 as archived

QUESTION = "Какова плотность жидкости?"
ENGLISH = "What is the density of the liquid?"
BODY = "The measured density of the liquid is1.2 g cm−3 at25 C. Liquid density is measured experimentally."
ARTICLE = "00000000-0000-0000-0000-000000000001"
LIBRARY = "00000000-0000-0000-0000-000000000009"


def envelope(value, *, finish="stop"):
    return json.dumps({"model": "offline-GigaChat", "choices": [{"finish_reason": finish,
        "message": {"role": "assistant", "content": json.dumps(value, ensure_ascii=False)}}]}, ensure_ascii=False).encode()


class Session:
    def __init__(self):
        self.statements, self.rollbacks = [], 0

    def execute(self, statement):
        self.statements.append(str(statement))

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def runtime(monkeypatch):
    state = {"session": Session(), "posts": [], "searches": [], "english": ENGLISH, "body": BODY,
             "rewrite_error": None, "answer_error": None, "finish": "stop",
             "claim": "Плотность жидкости составляет1.2 г/см³ при25 C.", "answerable": True}
    settings = Settings(_env_file=None, gigachat_credentials="offline-placeholder")

    def transport(self, url, body, authorization, *, oauth=False):
        # OAuth/authorization values must never appear in returned diagnostics.
        state["posts"].append((url, body))
        if oauth:
            return b'{"access_token":"offline-private-token"}'
        payload = json.loads(body)
        if "english_question" in payload["response_format"]["schema"].get("properties", {}):
            if state["rewrite_error"]:
                raise state["rewrite_error"]
            return envelope({"english_question": state["english"], "keywords": []}, finish=state["finish"])
        if state["answer_error"]:
            raise state["answer_error"]
        return envelope({"answerable": state["answerable"], "claims":
            [{"text": state["claim"], "citation_ids": ["E1"]}] if state["answerable"] else []})

    def search(*args, **kwargs):
        state["searches"].append((args, kwargs))
        row = SearchResult(article_id=ARTICLE, chunk_id="00000000-0000-0000-0000-000000000002", title="Constructed liquid",
            doi=None, page_start=2, page_end=3, source_type="main_text", snippet=state["body"], full_text=state["body"],
            score=1, retrieval_method="offline")
        return SearchResponse(query=args[1], results=[row])

    monkeypatch.setattr(GigaChatAnswerProvider, "_post", transport)
    monkeypatch.setattr(current_answer, "resolve_context", lambda *args: (None, {"status": "unavailable"}))
    monkeypatch.setattr(service, "search_chunks", search)
    monkeypatch.setattr(service, "complete_context", lambda session, question, collection, filters, rows: (rows, None))
    monkeypatch.setattr(current_answer_routes, "get_settings", lambda: settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = lambda: state["session"]
    try:
        with TestClient(app) as client:
            yield client, state
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(get_session, None)


def test_http_runs_rewriting_source_pipeline_answer_and_guard(runtime):
    client, state = runtime
    response = client.post("/answer/current", json={"question": QUESTION, "library_source_id": LIBRARY})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "answered" and data["stage"] == "complete"
    assert data["rewriting"]["plan"]["english_question"] == ENGLISH
    assert data["rewriting"]["meaning_review"] == "not_performed"
    assert data["review"]["scientific_support"] == "not_evaluated"
    assert data["review"]["native_result"]["claims"][0]["text"] == state["claim"]
    assert data["attempts"] == {"rewriting": {"oauth": 1, "model": 1}, "answer": {"oauth": 1, "model": 1}}
    assert len(state["posts"]) == 4
    args, kwargs = state["searches"][0]
    assert args[1] == QUESTION and args[3] == 5
    assert kwargs["ranking_question"] == ENGLISH + " "
    assert str(kwargs["filters"].library_source_id) == LIBRARY
    assert not kwargs["settings"].vector_index_cache_enabled
    native_request = data["transport"]["answer"][0]["request"]
    assert "Question:\n" + QUESTION in native_request["messages"][1]["content"]
    assert "offline-private-token" not in response.text and "offline-placeholder" not in response.text
    assert state["session"].statements == ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"]
    assert state["session"].rollbacks == 1


@pytest.mark.parametrize("kind", ["identifier", "number", "length", "filtered", "network"])
def test_failed_rewriting_never_reaches_answer_or_fallback(runtime, kind):
    client, state = runtime
    question = QUESTION
    if kind == "identifier":
        question += " Li"
    elif kind == "number":
        state["english"] += " at 300 K"
    elif kind == "length":
        state["english"] = "Short"
    elif kind == "filtered":
        state["finish"] = "blacklist"
    else:
        state["rewrite_error"] = GenerationUnavailableError("offline failure")
    response = client.post("/answer/current", json={"question": question})
    assert response.status_code in {502, 503}
    data = response.json()
    assert data["stage"] == "rewriting" and data["answer"] is None
    assert not state["searches"] and len(state["posts"]) == 2
    assert data["attempts"]["answer"] == {"model": 0, "oauth": 0}
    assert not data["retry_performed"] and not data["fallback_performed"]
    assert state["session"].rollbacks == 1


def test_answer_transport_failure_preserves_rewrite_and_preparation(runtime):
    client, state = runtime
    state["answer_error"] = GenerationUnavailableError("offline answer failure")
    response = client.post("/answer/current", json={"question": QUESTION})
    assert response.status_code == 503
    data = response.json()
    assert data["rewriting"]["plan"]["english_question"] == ENGLISH
    assert data["preparation"]["evidence_count"] == 1
    assert data["transport"]["answer"][0]["request"]
    assert data["transport"]["answer"][0]["raw_response"] is None
    assert len(state["posts"]) == 4


def test_provider_abstention_is_separate_from_missing_source_gate(runtime):
    client, state = runtime
    state["answerable"] = False
    data = client.post("/answer/current", json={"question": QUESTION}).json()
    assert data["delivery_status"] == "provider_abstained" and data["answer"]["status"] == "insufficient_evidence"
    assert len(state["posts"]) == 4


def test_gate_refusal_does_not_spend_answer_call(runtime):
    client, state = runtime
    state["body"] = "An unrelated publication about magnetic susceptibility of crystals."
    data = client.post("/answer/current", json={"question": QUESTION}).json()
    assert data["delivery_status"] == "baseline_preprovider_refusal"
    assert data["attempts"]["answer"] == {"model": 0, "oauth": 0}
    assert len(state["posts"]) == 2


def test_guard_withholds_but_keeps_native_result(runtime):
    client, state = runtime
    state.update(english="What is the energy density?", claim="Energy density731Wh/kg.",
        body="Energy density of731 Wh kg−1 based on the total cathode/anode masses is achieved.")
    data = client.post("/answer/current", json={"question": "Какова удельная энергия?"}).json()
    assert data["delivery_status"] == "insufficient_confirmation"
    assert data["answer"]["claims"] == [] and data["review"]["withheld"]
    assert data["review"]["native_result"]["claims"][0]["text"] == state["claim"]


@pytest.mark.parametrize("route", ["/ui/answer/current", "/ui/answer/current/result"])
def test_ui_posts_use_same_pipeline_and_show_pdf_source_links(runtime, route):
    client, state = runtime
    response = client.post(route, data={"question": QUESTION, "library_source_id": LIBRARY})
    assert response.status_code == 200, response.text
    assert ENGLISH in response.text and "/articles/" + ARTICLE + "/pdf" in response.text
    assert "Constructed liquid" in response.text
    assert "Исходный результат модели" in response.text
    assert len(state["posts"]) == 4


def test_page_load_uses_no_model_and_preserves_library_cookie(runtime):
    client, state = runtime
    client.cookies.set("ariadne_library_id", LIBRARY)
    response = client.get("/ui/answer/current")
    assert response.status_code == 200 and not state["posts"]
    assert LIBRARY in response.text and 'data-async-result="/ui/answer/current/result"' in response.text
    assert "до двух" in response.text and "ручная проверка" in response.text


@pytest.mark.parametrize("options", [{"method": "exact"}, {"top_k": 0}, {"question": "x" * 4001}, {"gold": "forbidden"}])
def test_invalid_inputs_are_rejected_before_model(runtime, options):
    client, state = runtime
    response = client.post("/answer/current", json={"question": QUESTION, **options})
    assert response.status_code == 422 and not state["posts"]


CONTEXT = {"article_id": ARTICLE, "title": "Ethers for batteries", "original_pdf_sha256": "a" * 64,
           "title_sha256": hashlib.sha256(b"Ethers for batteries").hexdigest()}


@pytest.mark.parametrize("value", [
    {"english_question": ENGLISH}, {"english_question": ENGLISH, "keywords": []},
    {"english_question": ENGLISH, "keywords": ["density", "density", "", 3, "at 300 K"]},
    {"english_question": ENGLISH, "keywords": "density"},
    {"english_question": "What is the Li liquid density?"},
])
def test_v02_parser_and_request_contract_parity(value):
    case = {"question_original": QUESTION, **CONTEXT}
    assert query_rewriting.request(case, "GigaChat-2-Max", CONTEXT) == archived.request(case, "GigaChat-2-Max", CONTEXT)
    assert query_rewriting.parse_response(envelope(value), QUESTION, CONTEXT) == archived.parse_response(
        envelope(value), QUESTION, CONTEXT)


@pytest.mark.parametrize("question,english", [
    ("Плотность Li?", "What is the liquid density?"),
    (QUESTION, "What is the density at300 K?"),
    ("Какие эфиры?", "What are the esters?"),
    ("Выдержка после зарядки?", "What is the soaking after charging?"),
])
def test_v02_rejections_match_archived_validator(question, english):
    for module in [archived, query_rewriting]:
        with pytest.raises(ValueError):
            module.parse_response(envelope({"english_question": english}), question, CONTEXT)


def test_archived_thirty_rewrites_parse_identically_without_model():
    root = Path("output/fan_doi_besenhard_rewriting_20261113")
    if not root.exists():
        pytest.skip("Optional local archived experiment is unavailable")
    plans = json.loads((root / "plans_freeze_v01/plans.json").read_text(encoding="utf-8"))["cases"]
    assert sum(row["accepted"] for row in plans) == 26
    for row in plans:
        if not row["accepted"]:
            continue
        plan = row["plan"]
        # The raw original question is stored in the prepared API request.
        request = json.loads((root / "prepared_v01" / row["id"] / "api_request.json").read_text(encoding="utf-8"))
        question = query_rewriting.question_body(request["question"])
        assert query_rewriting.validate(deepcopy(plan), question) == archived.validate(deepcopy(plan), question)


def test_request_local_rewriting_isolated_across_parallel_answers(monkeypatch):
    seen = []

    def search(session, question, *args, **kwargs):
        seen.append((question, kwargs.get("ranking_question")))
        return SearchResponse(query=question, results=[])

    monkeypatch.setattr(service, "search_chunks", search)
    monkeypatch.setattr(service, "complete_context", lambda s, q, c, f, rows: (rows, None))
    baseline_rank = search_module.rank_context
    settings = Settings(_env_file=None)

    def call(index):
        question = QUESTION + " " + str(index)
        plan = query_rewriting.normalize({"english_question": ENGLISH + " " + str(index)}, question, None)
        service.answer_question(Session(), settings, question, rewrite_plan=plan)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(call, range(12)))
    assert len(seen) == 12
    for question, ranking in seen:
        assert ranking == ENGLISH + " " + question.rsplit(" ", 1)[1] + " "
    assert search_module.rank_context is baseline_rank
    assert service.assess_evidence_adequacy.__module__ == "app.generation.evidence_adequacy"


def test_baseline_service_does_not_receive_rewrite_options(runtime, monkeypatch):
    _, state = runtime

    class Provider:
        def generate(self, *args, **kwargs):
            return ProviderResult(True, [GeneratedClaim(state["claim"], ["E1"])], "offline", "offline")

    service.answer_question(Session(), Settings(_env_file=None), ENGLISH, provider=Provider())
    assert "ranking_question" not in state["searches"][0][1]
    assert not state["posts"]


def test_request_local_selection_and_adequacy_match_archived_adapter(runtime):
    _, state = runtime
    question = "По статье Author (2020): " + QUESTION
    plan = query_rewriting.normalize({"english_question": ENGLISH, "keywords": ["density"]}, QUESTION, CONTEXT)

    class Provider:
        def generate(self, *args, **kwargs):
            return ProviderResult(True, [GeneratedClaim(state["claim"], ["E1"])], "offline", "offline")

    settings = Settings(_env_file=None)
    with archived.activate(question, plan):
        old = service.answer_question(Session(), settings, question, provider=Provider())
    new = service.answer_question(Session(), settings, question, provider=Provider(), rewrite_plan=plan)
    assert old == new


def test_source_title_is_bound_to_original_pdf_span_and_library(tmp_path, monkeypatch):
    import fitz

    from scripts import tac_experiment

    pdf = tmp_path / "source.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((50, 70), "Ethers for batteries", fontsize=22)
        page.insert_text((50, 120), "Author and coauthors. Original experimental evidence.")
        document.save(pdf)
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    article = SimpleNamespace(id=ARTICLE, checksum_sha256=checksum, title="Untrusted filename label")
    seen = []

    def inventory(session, collection, filters):
        seen.append((collection, str(filters.library_source_id)))
        return {ARTICLE: {"title": "Author 2020", "authors": None, "year": 2020}}

    def title(page):
        quote = "Ethers for batteries"
        start = page["text"].index(quote)
        return tac_experiment.TACSpan("T", page["page"], start, start + len(quote), quote,
            "constructed_test_layout", "original", checksum, page["text_sha256"]), []

    monkeypatch.setattr(rewrite_context, "_source_reference_inventory", inventory)
    monkeypatch.setattr(rewrite_context, "resolve_article_pdf", lambda *a: SimpleNamespace(path=pdf))
    monkeypatch.setattr(tac_experiment, "title_from_layout", title)
    session = SimpleNamespace(get=lambda *a: article)
    context, proof = rewrite_context.resolve_context(session, Settings(_env_file=None),
        "По статье Author (2020): " + QUESTION, "subset", LIBRARY)
    assert context["title"] == "Ethers for batteries" and context["original_pdf_sha256"] == checksum
    assert proof["source"]["quote"] == context["title"]
    assert seen == [("subset", LIBRARY)]
    article.checksum_sha256 = "0" * 64
    with pytest.raises(rewrite_context.PdfStorageIntegrityError, match="checksum"):
        rewrite_context.resolve_context(session, Settings(_env_file=None), "Author (2020)", "subset", LIBRARY)
