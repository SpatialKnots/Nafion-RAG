"""Synthetic OpenAI transport/Responses counterexamples; no live API calls."""

from __future__ import annotations

import io
import json
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import ProxyHandler
from uuid import uuid4

import pytest

from app.records import openai_backend as api
from app.records.compact import COMPACT_FIELDS, CompactReply, resolve_compact_reply
from app.records.extraction import FIELDS, LINK_ROLES, build_record_request
from app.records.full_evaluation import FullRecordCase, FullRecordReference, evaluate_extractions, inspect_extraction
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash

ROOT = Path(__file__).resolve().parents[2]
KEY = "synthetic-credential-never-a-real-key"


def context():
    quote = "Sample L ionic conductivity 1 × 10−4 S cm−1 at room temperature."
    page = "Hidden full-page text. " + quote
    start = page.index(quote)
    data = dict(article_id=uuid4(), original_pdf_path="/synthetic/a.pdf", original_pdf_sha256="a" * 64,
                page_number=1, text_layer_id=uuid4(), text_layer="original", layer_pdf_path="/synthetic/a.pdf",
                layer_pdf_sha256="a" * 64, page_text=page, page_text_sha256=text_hash(page), start=start,
                end=len(page), quote=quote, quote_sha256=text_hash(quote), selection_basis="expert_oracle", selection_note="Synthetic.")
    data["region_id"] = source_identity(data)
    return CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic", regions=(SourceRegion.model_validate(data),))


def reply():
    return CompactReply(sample_label="Sample L", property_name="ionic conductivity", value="1 × 10−4",
                        unit="S cm−1", temperature="room temperature")


def response(content=None):
    return {"id": "synthetic-response", "model": "synthetic-returned-model", "status": "completed", "error": None,
            "output": [{"type": "reasoning", "summary": []},
                       {"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": content if content is not None else reply().model_dump_json()}]}],
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}


def fixture_run(tmp_path, monkeypatch, payload=None, error=None, wire_format="compact"):
    source = context()
    path = tmp_path / "input.json"
    path.write_bytes(source.model_dump_json(indent=2).encode())

    def send(*args):
        if error is not None:
            raise error
        return json.dumps(payload if payload is not None else response()).encode(), "synthetic-request-id"

    monkeypatch.setattr(api, "send_openai_request", send)
    directory = tmp_path / "run"
    result = api.run_openai_extraction(path, directory, task="Synthetic task", model="synthetic", api_key=KEY,
                                       source_root=ROOT, wire_format=wire_format, max_output_tokens=2048)
    return source, directory, result


@pytest.mark.parametrize("wire_format", ["full", "compact"])
def test_request_keeps_source_messages_and_uses_native_strict_schema(wire_format):
    source = context()
    request = api.build_openai_request(source, "Synthetic task", "synthetic", 2048, wire_format, "medium")
    if wire_format == "full":
        assert request["input"] == build_record_request(source, "Synthetic task", "synthetic", 2048, 42)["messages"]
    else:
        assert json.loads(request["input"][1]["content"])["source"] == source.regions[0].quote
    serialized = json.dumps(request)
    assert "Hidden full-page" not in serialized
    assert "/synthetic/a.pdf" not in serialized
    assert request["store"] is False and request["truncation"] == "disabled"
    assert request["text"]["format"]["strict"] is True
    assert request["reasoning"] == {"effort": "medium"}
    assert not ({"seed", "temperature", "tools", "api_key", "Authorization"} & request.keys())


@pytest.mark.parametrize("mutation", ["incomplete", "failed", "error", "refusal", "two_blocks", "two_messages", "tool", "no_text"])
def test_native_response_failure_is_not_abstention(mutation):
    data = response()
    if mutation in {"incomplete", "failed"}:
        data["status"] = mutation
    elif mutation == "error":
        data["error"] = {"code": "synthetic"}
    elif mutation == "refusal":
        data["output"][1]["content"] = [{"type": "refusal", "refusal": "Synthetic refusal"}]
    elif mutation == "two_blocks":
        data["output"][1]["content"] *= 2
    elif mutation == "two_messages":
        data["output"].append(data["output"][1])
    elif mutation == "tool":
        data["output"].append({"type": "function_call"})
    else:
        data["output"] = []
    with pytest.raises(ValueError):
        api.responses_content(json.dumps(data).encode())


def test_fixed_https_transport_never_redirects_or_forwards_proxy_env(monkeypatch):
    observed = {}

    def opener(*handlers):
        assert any(isinstance(handler, ProxyHandler) and handler.proxies == {} for handler in handlers)

        def send(request, timeout):
            observed.update(url=request.full_url, authorization=request.get_header("Authorization"), data=request.data, timeout=timeout)
            return nullcontext(SimpleNamespace(read=lambda: b"synthetic", headers={"x-request-id": "synthetic-id"}))

        return SimpleNamespace(open=send)

    monkeypatch.setattr(api, "build_opener", opener)
    assert api.send_openai_request(b"source bytes", KEY, 30) == (b"synthetic", "synthetic-id")
    assert observed == {"url": api.ENDPOINT, "authorization": "Bearer " + KEY, "data": b"source bytes", "timeout": 30}
    with pytest.raises(HTTPError):
        api._NoRedirect().redirect_request(SimpleNamespace(full_url=api.ENDPOINT), None, 302, "redirect", None, "https://elsewhere.test")


@pytest.mark.parametrize("kind", ["timeout", "http", "literal", "incomplete"])
def test_run_preserves_failures_usage_and_redacts_credential(tmp_path, monkeypatch, kind):
    data, error = response(), None
    if kind == "timeout":
        error = TimeoutError("Synthetic timeout")
    elif kind == "http":
        error = HTTPError(api.ENDPOINT, 401, "Synthetic authentication failure", {}, io.BytesIO(KEY.encode()))
    elif kind == "literal":
        bad = reply().model_dump()
        bad["value"] = "invented"
        data = response(json.dumps(bad))
    else:
        data["status"] = "incomplete"
    _, directory, result = fixture_run(tmp_path, monkeypatch, data, error)
    assert result["status"] == "failed"
    assert not (directory / "candidates.json").exists()
    for path in directory.iterdir():
        assert KEY.encode() not in path.read_bytes()
    if kind in {"literal", "incomplete"}:
        assert result["usage"] == data["usage"]
        assert json.loads((directory / "response.json").read_bytes()) == data
    if kind == "literal":
        assert (directory / "reply.json").is_file()
    if kind == "http":
        assert (directory / "http_error_body_redacted.bin").read_bytes() == b"<redacted>"


def test_openai_compact_reparses_in_full_evaluator_and_keeps_unknown_dimensions(tmp_path, monkeypatch):
    source, directory, result = fixture_run(tmp_path, monkeypatch)
    assert result["status"] == "integrity_valid"
    assert result["returned_model"] == "synthetic-returned-model"
    assert result["usage"]["output_tokens"] == 50
    assert result["request_id"] == "synthetic-request-id"
    expected = resolve_compact_reply(source, reply()).records
    deferred = {name: "Synthetic deferred dimension." for name in (*FIELDS, "representation", *LINK_ROLES) if name not in COMPACT_FIELDS}
    case = FullRecordCase(case_id="synthetic", input_sha256=text_hash(source.model_dump_json(indent=2)), task="Synthetic task",
                          context=source, expected=expected, deferred=deferred, rationale="Synthetic development reference.")
    reference = FullRecordReference(reference_id=uuid4(), created_at=datetime.now(UTC), author="Synthetic",
                                    cases=(case,), limitations=("Synthetic, not independent gold.",))
    path = tmp_path / "reference.json"
    path.write_text(reference.model_dump_json(), encoding="utf-8")
    report = evaluate_extractions(path, {case.case_id: directory}, tmp_path / "evaluation", source_root=ROOT)
    assert report["summary"]["dimension_outcomes"] == {"match": 5, "deferred": 15}
    assert report["summary"]["full_record_outcomes"] == {"deferred": 1}
    request_path = directory / "request.json"
    request = json.loads(request_path.read_bytes())
    request["store"] = True
    request_path.write_bytes(json.dumps(request).encode())
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["request_sha256"] = text_hash(request_path.read_text())
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="fixed bounded"):
        inspect_extraction(case, directory)


def test_openai_full_empty_output_is_explicit_model_abstention(tmp_path, monkeypatch):
    payload = response(json.dumps({
        "schema_version": "records_bounded_reply_v0.1", "measurements": [], "diagnostic": "Synthetic abstention.",
    }))
    _, _, result = fixture_run(tmp_path, monkeypatch, payload, wire_format="full")
    assert result["status"] == "integrity_valid" and result["abstention"] is True
