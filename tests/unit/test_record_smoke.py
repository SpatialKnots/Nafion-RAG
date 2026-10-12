"""Synthetic local-provider and evidence failure cases; no model/scientific gold."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.records import smoke
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash


def context(raw: str = "Li-Naﬁon 1 × 10−3 S cm−1 at room temperature.") -> CandidateBundle:
    data = {
        "article_id": str(uuid4()), "original_pdf_path": "/data/pdf/synthetic.pdf", "original_pdf_sha256": "a" * 64,
        "page_number": 1, "text_layer_id": str(uuid4()), "text_layer": "original",
        "layer_pdf_path": "/data/pdf/synthetic.pdf", "layer_pdf_sha256": "a" * 64,
        "page_text": raw, "page_text_sha256": text_hash(raw), "start": 0, "end": len(raw),
        "quote": raw, "quote_sha256": text_hash(raw), "selection_basis": "manual_development",
        "selection_note": "Synthetic test fixture, not scientific gold.",
    }
    data["region_id"] = source_identity(data)
    return CandidateBundle(
        run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic-test", regions=(SourceRegion.model_validate(data),),
    )


def output_with_quote(quote: str, alias: str = "R1") -> smoke.WireExtraction:
    observations = [
        {"field": field, "status": "not_found_in_context", "raw_text": None, "evidence": [], "note": "Synthetic missing field."}
        for field in sorted(smoke.REQUIRED_FIELDS) if field != "value"
    ]
    observations.append({
        "field": "value", "status": "present", "raw_text": quote,
        "evidence": [{"region": alias, "quote": quote}], "note": "Synthetic raw quote.",
    })
    return smoke.WireExtraction.model_validate({"schema_version": "records_smoke_fields_v0.1", "observations": observations})


@pytest.mark.parametrize("endpoint", [
    "https://127.0.0.1:8080", "http://example.com:8080", "http://127.0.0.1", "http://localhost:8080",
    "http://127.0.0.1:8080/path", "http://u:p@127.0.0.1:8080", "http://127.0.0.1:8080?x=1",
])
def test_only_explicit_loopback_origins_allowed(endpoint: str) -> None:
    with pytest.raises(ValueError):
        smoke.check_local_endpoint(endpoint)


def test_exact_quote_resolves_unicode_codepoint_span() -> None:
    bundle = context()
    observations = smoke.resolve_observations(bundle, output_with_quote("1 × 10−3"))
    value = observations["value"]
    assert value.raw_text == "1 × 10−3"
    span = value.evidence[0]
    assert bundle.regions[0].quote[span.start:span.end] == span.quote
    assert span.region_id == bundle.regions[0].region_id


@pytest.mark.parametrize("text,quote,alias", [
    ("Li-Naﬁon", "Li-Nafion", "R1"),
    ("value value", "value", "R1"),
    ("aaa", "aa", "R1"),
    ("value", "value", "unknown"),
])
def test_missing_normalized_ambiguous_or_unknown_evidence_fails(text: str, quote: str, alias: str) -> None:
    with pytest.raises(ValueError):
        smoke.resolve_observations(context(text), output_with_quote(quote, alias))


def test_nonempty_output_cannot_omit_required_missingness() -> None:
    with pytest.raises(ValidationError, match="all ten"):
        smoke.WireExtraction.model_validate({
            "schema_version": "records_smoke_fields_v0.1",
            "observations": [{"field": "value", "status": "ambiguous", "raw_text": None, "evidence": [], "note": "Unclear."}],
        })


def test_request_sends_source_without_manual_answers_or_selection_notes() -> None:
    bundle = context()
    request = json.dumps(smoke.build_request(bundle, "test", "local", 10, 42), ensure_ascii=False)
    assert "Li-Naﬁon" in request
    assert "Synthetic test fixture, not scientific gold." not in request
    assert "records" not in request.split('"context"')[-1].split('"response_format"')[0]
    assert "OpenAI" not in request


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "input.json"
    source.write_text(context().model_dump_json(), encoding="utf-8")
    runtime = tmp_path / "identity.json"
    runtime.write_text(json.dumps({"model_alias": "local", "endpoint": "http://127.0.0.1:18086"}), encoding="utf-8")
    code = tmp_path / "app" / "records" / "schema.py"
    code.parent.mkdir(parents=True)
    code.write_text("# synthetic source fixture\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("# synthetic fixture\n", encoding="utf-8")
    return source, runtime, tmp_path


@pytest.mark.parametrize("failure", ["invalid_json", "length", "transport", "unknown_evidence"])
def test_smoke_preserves_failure_artifacts(inputs, monkeypatch, failure: str) -> None:
    source, runtime, root = inputs

    def fake_send(endpoint: str, payload: bytes, timeout: int) -> bytes:
        if failure == "transport":
            raise URLError("Synthetic connection failure")
        content = "not JSON" if failure == "invalid_json" else output_with_quote("invented").model_dump_json()
        return json.dumps({
            "choices": [{"message": {"content": content}, "finish_reason": "length" if failure == "length" else "stop"}],
        }).encode()

    monkeypatch.setattr(smoke, "send_local_request", fake_send)
    destination = root / "run"
    result = smoke.run_smoke(
        source, destination, task="Synthetic task", endpoint="http://127.0.0.1:18086", model="local",
        runtime_manifest=runtime, source_root=root,
    )
    assert result["status"] == "failed"
    assert result["scientific_admission"] == "not_evaluated"
    assert (destination / "input.json").read_bytes() == source.read_bytes()
    assert (destination / "request.json").is_file()
    assert json.loads((destination / "result.json").read_bytes())["error_type"]
    assert not (destination / "observations.json").exists()


def test_empty_output_integrity_does_not_claim_scientific_success(inputs, monkeypatch) -> None:
    source, runtime, root = inputs
    body = json.dumps({"schema_version": "records_smoke_fields_v0.1", "observations": []})
    monkeypatch.setattr(smoke, "send_local_request", lambda *args: json.dumps({
        "choices": [{"message": {"content": body}, "finish_reason": "stop"}],
    }).encode())
    result = smoke.run_smoke(
        source, root / "run", task="Synthetic task", endpoint="http://127.0.0.1:18086", model="local",
        runtime_manifest=runtime, source_root=root,
    )
    assert result["empty_output"] is True
    assert result["scientific_admission"] == "not_evaluated"
    with pytest.raises(FileExistsError):
        smoke.run_smoke(
            source, root / "run", task="test", endpoint="http://127.0.0.1:18086", model="local",
            runtime_manifest=runtime, source_root=root,
        )


def single_reply(**changes) -> smoke.SingleFieldReply:
    data = {"status": "present", "raw_text": "1 × 10−3", "region": "R1", "quote": "1 × 10−3", "note": ""}
    data.update(changes)
    return smoke.SingleFieldReply.model_validate(data)


def test_single_field_preserves_unicode_span_without_full_record_claim() -> None:
    bundle = context()
    value = smoke.resolve_single_field(bundle, single_reply(), "value")["value"]
    assert value.raw_text == "1 × 10−3"
    span = value.evidence[0]
    assert bundle.regions[0].quote[span.start:span.end] == span.quote


@pytest.mark.parametrize("changes", [
    {"quote": "1 x 10-3"},
    {"region": "R2"},
    {"raw_text": "1 × 10−4"},
    {"region": None, "quote": None},
    {"status": "not_found_in_context", "note": "Missing."},
])
def test_single_field_rejects_broken_evidence_or_asserted_missing_value(changes) -> None:
    with pytest.raises(ValueError):
        smoke.resolve_single_field(context(), single_reply(**changes), "value")


@pytest.mark.parametrize("changes", [
    {"region": None}, {"quote": None}, {"quote": "a" * 241}, {"field": "value"},
])
def test_single_field_rejects_unpaired_long_or_extra_output(changes) -> None:
    with pytest.raises(ValidationError):
        single_reply(**changes)


def test_single_field_missingness_requires_diagnostic_and_null_value() -> None:
    output = single_reply(status="not_found_in_context", raw_text=None, region=None, quote=None, note="No measurement.")
    observation = smoke.resolve_single_field(context(), output, "value")["value"]
    assert observation.status == "not_found_in_context"
    assert observation.evidence == ()
    with pytest.raises(ValidationError):
        smoke.resolve_single_field(context(), output.model_copy(update={"note": ""}), "value")


def test_single_field_request_uses_identical_source_context_and_explicit_field_meaning() -> None:
    bundle = context()
    old = smoke.build_request(bundle, "test", "local", 384, 42)
    new = smoke.build_single_field_request(bundle, "test", "composition_basis", "local", 384, 42)
    old_content = json.loads(old["messages"][1]["content"])
    new_content = json.loads(new["messages"][1]["content"])
    assert new_content["context"] == old_content["context"]
    assert new_content["task"] == old_content["task"]
    assert new_content["field"] == "composition_basis"
    assert "mass/mole/volume" in new_content["field_meaning"]
    assert "Synthetic test fixture" not in json.dumps(new)
    assert set(new["response_format"]["schema"]["properties"]) == {"status", "raw_text", "region", "quote", "note"}


@pytest.mark.parametrize("content,finish_reason,stage", [
    (single_reply().model_dump_json(), "stop", None),
    (single_reply(quote="invented").model_dump_json(), "stop", "evidence_integrity"),
    ("{", "length", "response_envelope"),
    ('{"observations": []}', "stop", "output_contract"),
])
def test_single_field_pipeline_records_exact_outcome(inputs, monkeypatch, content, finish_reason, stage) -> None:
    source, runtime, root = inputs
    monkeypatch.setattr(smoke, "send_local_request", lambda *args: json.dumps({
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
    }).encode())
    destination = root / "single"
    result = smoke.run_smoke(
        source, destination, task="Synthetic task", endpoint="http://127.0.0.1:18086", model="local",
        runtime_manifest=runtime, source_root=root, field="value", max_tokens=384,
    )
    assert (destination / "model_output.txt").read_text(encoding="utf-8") == content
    assert result["scientific_admission"] == "not_evaluated"
    assert (destination / "observations.json").exists() is (stage is None)
    if stage is not None:
        assert result["status"] == "failed"
        assert result["stage"] == stage
    else:
        assert result["status"] == "integrity_valid"
        assert set(json.loads((destination / "observations.json").read_bytes())) == {"value"}
    manifest = json.loads((destination / "manifest.json").read_bytes())
    assert manifest["output_contract"] == "records_smoke_single_field_v0.2"
    assert manifest["requested_field"] == "value"


def test_repeated_source_has_distinct_model_run_identity(inputs, monkeypatch) -> None:
    source, runtime, root = inputs
    monkeypatch.setattr(smoke, "send_local_request", lambda *args: json.dumps({
        "choices": [{"message": {"content": single_reply().model_dump_json()}, "finish_reason": "stop"}],
    }).encode())
    manifests = []
    for name in ("first", "second"):
        smoke.run_smoke(source, root / name, task="test", endpoint="http://127.0.0.1:18086", model="local",
                        runtime_manifest=runtime, source_root=root, field="value")
        manifests.append(json.loads((root / name / "manifest.json").read_bytes()))
    assert manifests[0]["run_id"] == manifests[1]["run_id"]
    assert manifests[0]["smoke_run_id"] != manifests[1]["smoke_run_id"]


@pytest.mark.parametrize("data", [
    {"region": None, "text": "value"}, {"region": "R1", "text": None},
    {"region": "R1", "text": ""}, {"region": "R1", "text": "a" * 241},
    {"region": None, "text": None, "status": "present"},
])
def test_span_contract_rejects_inconsistent_or_extra_data(data) -> None:
    with pytest.raises(ValidationError):
        smoke.SpanFieldReply.model_validate(data)


@pytest.mark.parametrize("text,region", [("1 x 10-3", "R1"), ("1 × 10−3", "R2")])
def test_span_contract_still_rejects_normalization_and_wrong_region(text, region) -> None:
    with pytest.raises(ValueError):
        smoke.resolve_span_field(context(), smoke.SpanFieldReply(region=region, text=text), "value")


def test_span_null_means_model_abstention_with_explicit_diagnostic() -> None:
    output = smoke.resolve_span_field(context(), smoke.SpanFieldReply(region=None, text=None), "value")["value"]
    assert output.status == "not_found_in_context"
    assert output.raw_text is None
    assert "not been independently verified" in output.note


def test_span_request_preserves_context_and_places_field_meaning_before_source() -> None:
    bundle = context()
    request = smoke.build_span_field_request(bundle, "test", "method", "local", 192, 42)
    content = json.loads(request["messages"][1]["content"])
    old = json.loads(smoke.build_request(bundle, "test", "local", 192, 42)["messages"][1]["content"])
    assert content["context"] == old["context"]
    assert "Requested field: method" in request["messages"][0]["content"]
    assert set(request["response_format"]["schema"]["properties"]) == {"region", "text"}
    assert request["response_format"]["schema"]["properties"]["region"]["enum"] == ["R1", None]


@pytest.mark.parametrize("text", ["1 × 10−3", None])
def test_span_pipeline_preserves_literal_value_or_model_abstention(inputs, monkeypatch, text) -> None:
    source, runtime, root = inputs
    body = json.dumps({"region": "R1" if text is not None else None, "text": text}, ensure_ascii=False)
    monkeypatch.setattr(smoke, "send_local_request", lambda *args: json.dumps({
        "choices": [{"message": {"content": body}, "finish_reason": "stop"}],
    }).encode())
    result = smoke.run_smoke(source, root / "span", task="test", endpoint="http://127.0.0.1:18086", model="local",
                             runtime_manifest=runtime, source_root=root, field="value", field_format="span")
    assert result["status"] == "integrity_valid"
    assert result["scientific_admission"] == "not_evaluated"
    observations = json.loads((root / "span" / "observations.json").read_bytes())
    assert observations["value"]["raw_text"] == text
    manifest = json.loads((root / "span" / "manifest.json").read_bytes())
    assert manifest["output_contract"] == "records_smoke_span_field_v0.3"
    with pytest.raises(ValueError, match="requires a requested field"):
        smoke.run_smoke(source, root / "invalid", task="test", endpoint="http://127.0.0.1:18086", model="local",
                        runtime_manifest=runtime, source_root=root, field_format="span")
    assert not (root / "invalid").exists()
