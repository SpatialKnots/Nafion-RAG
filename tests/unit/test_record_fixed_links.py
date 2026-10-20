"""Fixed-link wire counterexamples and unchanged evidence/evaluation semantics."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.records import openai_backend as api
from app.records.extraction import FIELDS, LINK_ROLES
from app.records.fixed_links import FixedSpanReply, build_fixed_messages, parse_fixed_reply, resolve_fixed_reply
from app.records.full_evaluation import FullRecordCase, FullRecordReference, evaluate_extractions
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash
from app.records.spans import SpanFullReply, token_offsets

ROOT = Path(__file__).resolve().parents[2]


def source():
    quote = "Sample L conductivity 1 S/cm at 20 °C.\nMethod EIS."
    page = "Hidden page text. " + quote
    data = dict(article_id=uuid4(), original_pdf_path="/synthetic/a.pdf", original_pdf_sha256="a" * 64,
                page_number=1, text_layer_id=uuid4(), text_layer="original", layer_pdf_path="/synthetic/a.pdf",
                layer_pdf_sha256="a" * 64, page_text=page, page_text_sha256=text_hash(page), start=page.index(quote),
                end=len(page), quote=quote, quote_sha256=text_hash(quote), selection_basis="expert_oracle", selection_note="Synthetic.")
    data["region_id"] = source_identity(data)
    return CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic", regions=(SourceRegion.model_validate(data),))


def selection(bundle, quote):
    text = bundle.regions[0].quote
    start = text.index(quote)
    offsets = token_offsets(text)
    return {"region": "R1", "start_token": next(i for i, pair in enumerate(offsets) if pair[0] == start),
            "end_token": next(i for i, pair in enumerate(offsets) if pair[1] == start + len(quote))}


def proposal(bundle):
    raw = {"sample_label": "Sample L", "property_name": "conductivity", "value": "1", "unit": "S/cm", "temperature": "20 °C"}
    observations = [{"field": name, "status": "present" if name in raw else "unsupported",
        "raw_span": selection(bundle, raw[name]) if name in raw else None,
        "evidence": [selection(bundle, raw[name])] if name in raw else [], "note": "Synthetic observation."} for name in FIELDS]
    return {"schema_version": "records_span_fixed_reply_v0.1", "diagnostic": "Synthetic selection.", "measurements": [{
        "observations": observations, "representation": "scalar", "linkage": {
            role: {"evidence": [selection(bundle, "Sample L conductivity 1 S/cm at 20 °C.")],
                   "note": "Synthetic link " + role} for role in LINK_ROLES}}]}


@pytest.mark.parametrize("null_roles", [(), ("sample_value",), ("property_value",), ("conditions_measurement",), LINK_ROLES])
def test_named_slots_preserve_roles_coordinates_notes_and_explicit_nulls(null_roles):
    bundle = source()
    data = proposal(bundle)
    for role in null_roles:
        data["measurements"][0]["linkage"][role] = None
    reply = parse_fixed_reply(json.dumps(data))
    candidate = resolve_fixed_reply(bundle, reply).records[0]
    assert {link.role for link in candidate.linkage} == set(LINK_ROLES) - set(null_roles)
    for link in candidate.linkage:
        assert link.note == "Synthetic link " + link.role
        assert link.evidence[0].quote == "Sample L conductivity 1 S/cm at 20 °C."
        assert link.evidence[0].start == 0 and link.evidence[0].end == len("Sample L conductivity 1 S/cm at 20 °C.")
    assert candidate.value.raw_value.raw_text == "1" and candidate.value.raw_unit.raw_text == "S/cm"
    assert candidate.review_state == "needs_review" and candidate.li_ion_confirmation == "not_reviewed"
    assert candidate.method.status == "unsupported" and candidate.method.raw_text is None
    assert reply.as_span_reply().measurements[0].observations == reply.measurements[0].observations
    assert resolve_fixed_reply(bundle, reply).records == (candidate,)
    assert CandidateBundle.model_validate_json(resolve_fixed_reply(bundle, reply).model_dump_json()).records == (candidate,)


@pytest.mark.parametrize("kind", ["missing", "extra", "array", "role_in_slot", "empty_evidence", "duplicate_observation"])
def test_missing_nulls_legacy_arrays_unexpected_roles_and_duplicate_observations_fail(kind):
    bundle = source()
    data = proposal(bundle)
    links = data["measurements"][0]["linkage"]
    if kind == "missing":
        links.pop("sample_value")
    elif kind == "extra":
        links["invented_role"] = None
    elif kind == "array":
        data["measurements"][0]["linkage"] = [{"role": "sample_value", **links["sample_value"]}] * 2
    elif kind == "role_in_slot":
        links["sample_value"]["role"] = "conditions_measurement"
    elif kind == "empty_evidence":
        links["sample_value"]["evidence"] = []
    else:
        data["measurements"][0]["observations"][1]["field"] = "sample_label"
    with pytest.raises(ValueError):
        parse_fixed_reply(json.dumps(data))


@pytest.mark.parametrize("content", ['{"sample_value": null, "sample_value": null}',
                                     '{"nested": {"start_token": 0, "start_token": 1}}'])
def test_duplicate_json_keys_are_not_silently_overwritten(content):
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        parse_fixed_reply(content)


def test_invalid_link_coordinates_fail_and_historical_duplicate_roles_still_fail():
    bundle = source()
    data = proposal(bundle)
    data["measurements"][0]["linkage"]["sample_value"]["evidence"][0]["end_token"] = 999
    with pytest.raises(ValueError, match="outside"):
        resolve_fixed_reply(bundle, parse_fixed_reply(json.dumps(data)))
    valid = parse_fixed_reply(json.dumps(proposal(bundle)))
    old = valid.as_span_reply().model_dump(mode="json")
    old["measurements"][0]["linkage"].append(old["measurements"][0]["linkage"][0])
    with pytest.raises(ValueError, match="Duplicate span linkage"):
        SpanFullReply.model_validate(old)


def test_schema_requires_all_three_nullable_slots_and_keeps_source_token_map():
    bundle = source()
    request = api.build_openai_request(bundle, "Synthetic task", "synthetic", 8192, "span_fixed", "medium")
    schema = request["text"]["format"]["schema"]
    slots = schema["$defs"]["LinkSlots"]
    assert set(slots["properties"]) == set(slots["required"]) == set(LINK_ROLES)
    assert slots["additionalProperties"] is False
    assert all({"type": "null"} in field["anyOf"] for field in slots["properties"].values())
    assert "role" not in schema["$defs"]["LinkSelection"]["properties"]
    user = json.loads(build_fixed_messages(bundle, "Synthetic task")[1]["content"])
    assert user["context"][0]["source"] == bundle.regions[0].quote
    assert "Hidden page" not in json.dumps(request) and "/synthetic/a.pdf" not in json.dumps(request)
    empty = FixedSpanReply(schema_version="records_span_fixed_reply_v0.1", measurements=(), diagnostic="Synthetic negative.")
    assert resolve_fixed_reply(bundle, empty).records == ()


@pytest.mark.parametrize("duplicate_key", [False, True])
def test_native_saved_raw_outputs_reparse_without_losing_links_or_accepting_duplicate_keys(tmp_path, monkeypatch, duplicate_key):
    bundle = source()
    raw = bundle.model_dump_json(indent=2).encode()
    path = tmp_path / "input.json"
    path.write_bytes(raw)
    content = json.dumps(proposal(bundle))
    if duplicate_key:
        content = content.replace('"linkage": {', '"linkage": {"sample_value": null,', 1)
    response = {"status": "completed", "output": [{"type": "message", "role": "assistant", "status": "completed",
        "content": [{"type": "output_text", "text": content}]}], "usage": {"output_tokens": 123}}
    monkeypatch.setattr(api, "send_openai_request", lambda *args: (json.dumps(response).encode(), "synthetic-request-id"))
    run = tmp_path / "run"
    result = api.run_openai_extraction(path, run, task="Synthetic task", model="synthetic", api_key="synthetic-key",
                                       source_root=ROOT, wire_format="span_fixed")
    if duplicate_key:
        assert result["status"] == "failed" and result["stage"] == "completion_contract"
        assert "Duplicate JSON key" in result["error"] and (run / "response.json").is_file()
        assert not (run / "candidates.json").exists()
        with pytest.raises(ValueError, match="Duplicate JSON key"):
            api.resolve_openai_response(bundle, (run / "response.json").read_bytes(), "span_fixed")
        return
    assert result["status"] == "integrity_valid"
    expected = resolve_fixed_reply(bundle, parse_fixed_reply(content)).records
    deferred = {name: "Synthetic unannotated field." for name in FIELDS if name not in {
        "sample_label", "property_name", "value", "unit", "temperature"}}
    case = FullRecordCase(case_id="synthetic", input_sha256=text_hash(raw.decode()), task="Synthetic task", context=bundle,
                          expected=expected, deferred=deferred, rationale="Synthetic, not scientific evaluation.")
    reference = FullRecordReference(reference_id=uuid4(), created_at=datetime.now(UTC), author="Synthetic", cases=(case,),
                                    limitations=("Synthetic; no independent gold.",))
    ref = tmp_path / "reference.json"
    ref.write_bytes(reference.model_dump_json().encode())
    report = evaluate_extractions(ref, {"synthetic": run}, tmp_path / "evaluation", source_root=ROOT)
    assert report["summary"]["dimension_outcomes"] == {"match": 9, "deferred": 11}
    row = report["cases"][0]
    assert all(row["dimensions"][role]["outcome"] == "match" for role in LINK_ROLES)
    assert row["full_record_agreement"] == "deferred"
