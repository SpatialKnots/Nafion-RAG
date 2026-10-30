"""Constructed runtime GigaChat transport tests; live model calls are forbidden."""

from __future__ import annotations

import io
import json
import socket
import ssl
import traceback
from dataclasses import replace
from email.message import Message
from http.client import IncompleteRead
from typing import Any
from urllib.error import HTTPError, URLError
from uuid import UUID

import pytest

from app.core.config import Settings
from app.generation import gigachat as giga
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError, GenerationUnavailableError
from app.generation.service import answer_question, build_answer_provider
from app.retrieval.search import SearchResponse, SearchResult

KEY = "constructed-authorization-key"
TOKEN = "constructed-access-token"
ANSWER = {"answerable": True, "claims": [{"text": "Conductivity was measured.", "citation_ids": ["E1"]}]}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Real networking forbidden in GigaChat runtime tests")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


def provider(**kwargs):
    return giga.GigaChatAnswerProvider(**{
        "credentials": KEY, "scope": "GIGACHAT_API_PERS", "model": "GigaChat-2-Max",
        "timeout_seconds": 17, "max_tokens": 1200, **kwargs,
    })


def evidence():
    return Evidence(citation_id="E1", article_id="article", chunk_id="chunk", title="Scientific source", doi=None,
                    page_start=2, page_end=2, source_type="method", text="Conductivity was measured by\nimpedance spectroscopy.",
                    score=1.0, retrieval_method="exact_ilike", method_scores={}, method_ranks={})


def envelope(answer=None, **kwargs):
    return {"model": "GigaChat-2-Max:constructed", "choices": [
        {"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(ANSWER if answer is None else answer)}}
    ], **kwargs}


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self.body


class Transport:
    def __init__(self, monkeypatch, replies):
        self.replies = list(replies)
        self.requests: list[Any] = []
        self.handlers: list[Any] = []
        monkeypatch.setattr(giga, "build_opener", self.build)

    def build(self, *handlers):
        self.handlers.extend(handlers)
        return self

    def open(self, request, *, timeout):
        assert timeout == 17
        self.requests.append(request)
        value = self.replies.pop(0)
        if isinstance(value, Exception):
            raise value
        return Response(value if isinstance(value, bytes) else json.dumps(value).encode())


def test_runtime_oauth_native_schema_and_result(monkeypatch):
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope()])
    result = provider().generate("How was conductivity measured?", [evidence()], answer_language="ru")
    assert result.provider == "gigachat"
    assert result.model == "GigaChat-2-Max"
    assert result.claims == [GeneratedClaim(text="Conductivity was measured.", citation_ids=["E1"])]
    auth, chat = transport.requests
    assert [r.full_url for r in transport.requests] == [giga.AUTH_URL, giga.CHAT_URL]
    assert auth.get_header("Authorization") == "Basic " + KEY
    assert UUID(auth.get_header("Rquid")).version == 4
    assert auth.data == b"scope=GIGACHAT_API_PERS"
    assert auth.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert chat.get_header("Authorization") == "Bearer " + TOKEN
    body = json.loads(chat.data)
    assert body["model"] == "GigaChat-2-Max"
    assert body["max_tokens"] == 1200
    assert body["stream"] is False
    assert set(body["response_format"]) == {"type", "schema", "strict"}
    assert body["response_format"]["schema"]["required"] == ["answerable", "claims"]
    assert body["response_format"]["strict"] is True
    assert "Answer language: Russian." in body["messages"][1]["content"]
    assert "Conductivity was measured by impedance spectroscopy." in body["messages"][1]["content"]
    assert KEY not in json.dumps(body) and TOKEN not in json.dumps(body)
    assert "temperature" not in body and "reasoning" not in body
    tls = [h._context for h in transport.handlers if isinstance(h, giga.HTTPSHandler)]
    assert all(c.verify_mode == ssl.CERT_REQUIRED and c.check_hostname for c in tls)
    assert all(h.proxies == {} for h in transport.handlers if isinstance(h, giga.ProxyHandler))


@pytest.mark.parametrize("scope", sorted(giga.SCOPES))
def test_scope_is_explicit_not_changed_by_adapter(monkeypatch, scope):
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope({"answerable": False, "claims": []})])
    assert provider(scope=scope).generate("question", [evidence()]).answerable is False
    assert transport.requests[0].data == ("scope=" + scope).encode()


def test_empty_evidence_performs_no_oauth_or_generation(monkeypatch):
    transport = Transport(monkeypatch, [])
    assert provider().generate("question", []).answerable is False
    assert not transport.requests


def test_mini_review_and_language_are_preserved(monkeypatch):
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope()])
    provider().generate("question", [evidence()], answer_style="mini_review", answer_language="en")
    prompt = json.loads(transport.requests[1].data)["messages"][1]["content"]
    assert "Answer style: mini_review" in prompt and "Answer language: English." in prompt
    assert "Article 1: title='Scientific source'" in prompt


@pytest.mark.parametrize("answer_style", ["claims", "mini_review"])
def test_request_constrains_citations_to_exact_supplied_ids_in_both_styles(monkeypatch, answer_style):
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope()])
    first = replace(evidence(), citation_id="E2", text="Untrusted text mentions E999 and [E999].")
    second = evidence()
    sources = [first, second, first]
    original_texts = [item.text for item in sources]
    provider().generate("question", sources, answer_style=answer_style)
    request = json.loads(transport.requests[1].data)
    schema = request["response_format"]["schema"]
    assert schema["$defs"]["_Claim"]["properties"]["citation_ids"]["items"] == {
        "type": "string", "enum": ["E2", "E1"]}
    assert request["response_format"]["strict"] is True
    prompt = request["messages"][1]["content"]
    assert 'Allowed citation_ids values (exact strings): ["E2", "E1"]' in prompt
    assert "Square brackets delimiting evidence headings are not part of the IDs." in prompt
    assert "Do not add brackets, whitespace, or other characters to an ID." in prompt
    assert "Untrusted text mentions E999 and [E999]." in prompt
    assert [item.text for item in sources] == original_texts


def test_citation_enum_is_request_local_and_does_not_leak_between_generations(monkeypatch):
    second_answer = {"answerable": True, "claims": [{"text": "Second source.", "citation_ids": ["E9"]}]}
    transport = Transport(monkeypatch, [
        {"access_token": TOKEN}, envelope(), {"access_token": TOKEN}, envelope(second_answer)])
    active = provider()
    active.generate("first question", [evidence()])
    result = active.generate("second question", [replace(evidence(), citation_id="E9")])
    bodies = [json.loads(r.data) for r in transport.requests if r.full_url == giga.CHAT_URL]
    enums = [b["response_format"]["schema"]["$defs"]["_Claim"]["properties"]["citation_ids"]["items"]["enum"] for b in bodies]
    assert enums == [["E1"], ["E9"]]
    assert 'Allowed citation_ids values (exact strings): ["E9"]' in bodies[1]["messages"][1]["content"]
    assert result.claims[0].citation_ids == ["E9"]
    assert "enum" not in giga._Answer.model_json_schema()["$defs"]["_Claim"]["properties"]["citation_ids"]["items"]


@pytest.mark.parametrize("answer_style", ["claims", "mini_review"])
def test_both_styles_explicitly_request_empty_claims_for_insufficient_evidence(monkeypatch, answer_style):
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope({"answerable": False, "claims": []})])
    result = provider().generate("question", [evidence()], answer_style=answer_style)
    body = json.loads(transport.requests[1].data)
    prompt = body["messages"][1]["content"]
    assert 'return exactly {"answerable": false, "claims": []}' in prompt
    assert "do not put explanations or missing-information statements in claims" in prompt
    assert "When answerable=true, claims must contain at least one supported scientific statement with citation_ids." in prompt
    assert result.answerable is False and result.claims == []
    expected_schema = giga._Answer.model_json_schema()
    expected_schema["$defs"]["_Claim"]["properties"]["citation_ids"]["items"]["enum"] = ["E1"]
    assert body["response_format"] == {"type": "json_schema", "schema": expected_schema, "strict": True}
    assert len(transport.requests) == 2


@pytest.mark.parametrize("answer", [
    {"answerable": False, "claims": []},
    {"answerable": False, "claims": [{"text": "No exact dwell time is supplied.", "citation_ids": ["E1"]}]},
    {"answerable": False, "claims": [{"text": "No information about this material.", "citation_ids": []}]},
    {"answerable": True, "claims": []},
])
def test_answer_service_accepts_only_consistent_abstention_and_never_repairs_explanatory_claims(monkeypatch, answer):
    settings = Settings(_env_file=None, gigachat_credentials=KEY, rag_timeout_seconds=17)
    source = evidence()
    result = SearchResult(article_id=source.article_id, chunk_id=source.chunk_id, title=source.title, doi=source.doi,
        page_start=2, page_end=2, source_type="method", snippet=source.text, score=1.0,
        retrieval_method="exact_ilike", method_scores={}, method_ranks={})
    monkeypatch.setattr("app.generation.service.search_chunks",
                        lambda *a, **k: SearchResponse(query="conductivity measured", results=[result]))
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope(answer)])
    if answer == {"answerable": False, "claims": []}:
        response = answer_question(object(), settings, "conductivity measured")
        assert response.status == "insufficient_evidence"
        assert response.answer is None and response.claims == [] and response.citations == []
        assert response.generation_provider == "gigachat"
    else:
        with pytest.raises(GenerationOutputError, match="answerable and claims are inconsistent"):
            answer_question(object(), settings, "conductivity measured")
    assert len(transport.requests) == 2


@pytest.mark.parametrize("answer_style", ["claims", "mini_review"])
@pytest.mark.parametrize("question,source_text,claim_text", [
    ("What exact hold duration was reported?",
     "Measurement started when the impedance spectra stopped changing.", None),
    ("What criterion was used before measurement?",
     "Measurement started when the impedance spectra stopped changing.", "The criterion was unchanged impedance spectra."),
    ("What was the dwell time at each measurement temperature?",
     "The casting solution was stirred for 45 minutes. Conductivity was measured after spectra stabilized.", None),
    ("How long was the casting solution stirred?",
     "The casting solution was stirred for 45 minutes. Conductivity was measured after spectra stabilized.",
     "The casting solution was stirred for 45 minutes."),
    ("What conductivity was reported for specimen B at 30 C?",
     "At 30 C specimen A had conductivity 2 mS/cm. Conductivity of specimen B was not reported.", None),
    ("What conductivity was reported for specimen A at 30 C?",
     "At 30 C specimen A had conductivity 2 mS/cm. Conductivity of specimen B was not reported.",
     "Specimen A had conductivity 2 mS/cm at 30 C."),
])
def test_generic_requested_information_guidance_preserves_inputs_and_constructed_reply_status(
    monkeypatch, answer_style, question, source_text, claim_text,
):
    # Entirely constructed transport fixtures. These test request/adapter behavior,
    # not whether a real model can decide answerability or scientific entailment.
    claims = [] if claim_text is None else [{"text": claim_text, "citation_ids": ["E1"]}]
    reply = {"answerable": claim_text is not None, "claims": claims}
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope(reply)])
    item = replace(evidence(), text=source_text)
    result = provider().generate(question, [item], answer_style=answer_style)
    request = json.loads(transport.requests[1].data)
    prompt = request["messages"][1]["content"]
    assert "A citation supporting a related fact is not sufficient." in prompt
    assert "do not substitute a completion criterion, an unspecified waiting time" in prompt
    assert "Do not borrow a value from another sample, work, or experimental stage" in prompt
    assert "When the question asks for a method or criterion itself, a directly supported qualitative answer is allowed." in prompt
    assert f"Question:\n{question}\n" in prompt and source_text in prompt
    assert item.text == source_text
    assert result.answerable is reply["answerable"]
    assert result.claims == [GeneratedClaim(text=c["text"], citation_ids=c["citation_ids"]) for c in claims]
    assert len(transport.requests) == 2


@pytest.mark.parametrize("values, error", [
    ({"credentials": ""}, "GIGACHAT_CREDENTIALS"),
    ({"credentials": "key\r\ninjected"}, "GIGACHAT_CREDENTIALS"),
    ({"scope": "unknown"}, "GIGACHAT_SCOPE"),
    ({"model": "gpt-4.1-mini"}, "RAG_MODEL"),
    ({"model": ""}, "RAG_MODEL"),
])
def test_configuration_errors_are_local(values, error):
    with pytest.raises(GenerationUnavailableError, match=error):
        provider(**values)


@pytest.mark.parametrize("values", [{"timeout_seconds": 0}, {"max_tokens": 0}])
def test_invalid_request_limits(values):
    with pytest.raises(ValueError, match="positive"):
        provider(**values)


@pytest.mark.parametrize("reply", [b"not json", b'{"access_token":"x","access_token":"y"}',
                                    [], {}, {"access_token": "bad\ntoken"}, {"access_token": ""}])
def test_bad_oauth_stops_before_generation(monkeypatch, reply):
    transport = Transport(monkeypatch, [reply])
    with pytest.raises(GenerationUnavailableError, match="OAuth"):
        provider().generate("question", [evidence()])
    assert len(transport.requests) == 1


@pytest.mark.parametrize("stage", ["OAuth", "generation"])
@pytest.mark.parametrize("failure", ["http", "url", "timeout", "tls", "incomplete"])
def test_transport_errors_do_not_retry_fallback_or_expose_secrets(monkeypatch, stage, failure):
    failures = {
        "http": HTTPError(giga.CHAT_URL, 401, KEY, {}, io.BytesIO(TOKEN.encode())),
        "url": URLError(KEY + TOKEN), "timeout": TimeoutError(KEY),
        "tls": ssl.SSLCertVerificationError(KEY), "incomplete": IncompleteRead(TOKEN.encode()),
    }
    replies = ([{"access_token": TOKEN}] if stage == "generation" else []) + [failures[failure]]
    transport = Transport(monkeypatch, replies)
    with pytest.raises(GenerationUnavailableError, match=stage) as caught:
        provider().generate("question", [evidence()])
    assert len(transport.requests) == (1 if stage == "OAuth" else 2)
    rendered = "".join(traceback.format_exception(caught.value))
    assert KEY not in rendered and TOKEN not in rendered


def test_redirect_is_explicitly_rejected():
    with pytest.raises(HTTPError, match="redirects are forbidden"):
        giga._NoRedirect().redirect_request(giga.Request(giga.AUTH_URL), None, 307, "redirect", Message(), "https://foreign.test")


def test_additional_ca_keeps_system_verification(monkeypatch):
    class Context:
        def load_verify_locations(self, *, cafile):
            assert cafile == "additional-ca.pem"
    monkeypatch.setattr(giga.ssl, "create_default_context", lambda: Context())
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope()])
    provider(ca_bundle_file="additional-ca.pem").generate("question", [evidence()])
    assert len(transport.requests) == 2


def test_bad_ca_file_is_explicit_and_no_transport(monkeypatch, tmp_path):
    transport = Transport(monkeypatch, [])
    with pytest.raises(GenerationUnavailableError, match="TLS trust configuration failed"):
        provider(ca_bundle_file=str(tmp_path / "absent.pem")).generate("question", [evidence()])
    assert not transport.requests


@pytest.mark.parametrize("reason", ["length", "blacklist", "function_call", "error", None])
def test_incomplete_filtered_or_function_reply_is_not_abstention(reason):
    reply = envelope()
    reply["choices"][0]["finish_reason"] = reason
    with pytest.raises(GenerationOutputError, match="incomplete or filtered"):
        provider()._parse_response(reply)


@pytest.mark.parametrize("message", [None, {"role": "user"}, {"role": "assistant", "content": ""},
    {"role": "assistant", "refusal": "refused"}, {"role": "assistant", "function_call": {"name": "test"}},
    {"role": "assistant", "tool_calls": [{"id": "test"}]}])
def test_invalid_message_is_not_scientific_absence(message):
    reply = envelope()
    reply["choices"][0]["message"] = message
    with pytest.raises(GenerationOutputError):
        provider()._parse_response(reply)


@pytest.mark.parametrize("reply", [[], {}, {"choices": []}, {"choices": [None]}, {"choices": [{}, {}]}])
def test_invalid_envelope(reply):
    with pytest.raises(GenerationOutputError):
        provider()._parse_response(reply)


@pytest.mark.parametrize("content", [
    "not json", '{"answerable":false,"answerable":true,"claims":[]}',
    '{"answerable":NaN,"claims":[]}', '{"answerable":true,"claims":[],"other":1}',
    '{"answerable":"false","claims":[]}', '{"answerable":false,"claims":[{"text":"x","citation_ids":[]}] }',
    '{"answerable":true,"claims":[]}', '{"answerable":true,"claims":[{"text":" ","citation_ids":["E1"]}]}',
    '{"answerable":true,"claims":[{"text":"x","citation_ids":[1]}]}',
    '{"answerable":true,"claims":[{"text":"x","citation_ids":["E1"],"other":1}]}',
])
def test_malformed_or_inconsistent_content_is_not_repaired(content):
    reply = envelope()
    reply["choices"][0]["message"]["content"] = content
    with pytest.raises(GenerationOutputError):
        provider()._parse_response(reply)


def test_invalid_wire_json_is_rejected(monkeypatch):
    Transport(monkeypatch, [{"access_token": TOKEN}, b'{"choices":NaN}'])
    with pytest.raises(GenerationOutputError, match="not valid JSON"):
        provider().generate("question", [evidence()])


def test_defaults_and_local_credentials_do_not_call_network():
    settings = Settings(_env_file=None, gigachat_credentials=KEY)
    assert settings.rag_provider == "gigachat"
    assert settings.rag_model == "GigaChat-2-Max"
    assert settings.rag_gigachat_max_tokens == 1200
    assert KEY not in repr(settings)
    assert isinstance(build_answer_provider(settings), giga.GigaChatAnswerProvider)


@pytest.mark.parametrize("citation", ["E1", "foreign", "[E1]", " E1", "E1 "])
def test_answer_service_uses_gigachat_and_keeps_citation_validation(monkeypatch, citation):
    settings = Settings(_env_file=None, gigachat_credentials=KEY)
    source = evidence()
    result = SearchResult(article_id=source.article_id, chunk_id=source.chunk_id, title=source.title, doi=source.doi,
        page_start=2, page_end=2, source_type="method", snippet=source.text, score=1.0,
        retrieval_method="exact_ilike", method_scores={}, method_ranks={})
    monkeypatch.setattr("app.generation.service.search_chunks",
                        lambda *a, **k: SearchResponse(query="conductivity measured", results=[result]))
    answer = {"answerable": True, "claims": [{"text": "Conductivity was measured.", "citation_ids": [citation]}]}
    transport = Transport(monkeypatch, [{"access_token": TOKEN}, envelope(answer)])
    settings.rag_timeout_seconds = 17
    if citation != "E1":
        with pytest.raises(GenerationOutputError, match="unknown citations"):
            answer_question(object(), settings, "conductivity measured")
    else:
        response = answer_question(object(), settings, "conductivity measured")
        assert response.status == "answered"
        assert response.generation_provider == "gigachat"
        assert response.generation_model == "GigaChat-2-Max"
        assert response.citations[0].page_start == 2
    assert len(transport.requests) == 2
