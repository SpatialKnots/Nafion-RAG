"""Token-coordinate counterexamples; no live model calls or scientific gold claims."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.records import openai_backend as api
from app.records.extraction import FIELDS, LINK_ROLES
from app.records.full_evaluation import FullRecordCase, FullRecordReference, evaluate_extractions, inspect_extraction
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash
from app.records.spans import (
    VERSION,
    SpanCompactReply,
    SpanFullReply,
    SpanMeasurement,
    SpanObservation,
    TokenSpan,
    build_span_messages,
    resolve_span_reply,
    resolve_token_span,
    token_offsets,
)

ROOT = Path(__file__).resolve().parents[2]


def source():
    quote = "Sample L ionic conductivity 1 × 10 −4 S cm −1 at -40 to + 80 °C.\r\nSample L reused. Naﬁon."
    page = "Hidden prefix. " + quote + " Hidden suffix."
    start = page.index(quote)
    data = dict(article_id=uuid4(), original_pdf_path="/synthetic/a.pdf", original_pdf_sha256="a" * 64,
                page_number=1, text_layer_id=uuid4(), text_layer="original", layer_pdf_path="/synthetic/a.pdf",
                layer_pdf_sha256="a" * 64, page_text=page, page_text_sha256=text_hash(page), start=start,
                end=start + len(quote), quote=quote, quote_sha256=text_hash(quote), selection_basis="expert_oracle",
                selection_note="Synthetic token source.")
    data["region_id"] = source_identity(data)
    return CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic", regions=(SourceRegion.model_validate(data),))


def select(bundle, quote, start=0):
    text = bundle.regions[0].quote
    position = text.index(quote, start)
    offsets = token_offsets(text)
    first = next(i for i, pair in enumerate(offsets) if pair[0] == position)
    last = next(i for i, pair in enumerate(offsets) if pair[1] == position + len(quote))
    return TokenSpan(region="R1", start_token=first, end_token=last)


def compact(bundle):
    return SpanCompactReply(**{name: select(bundle, quote) for name, quote in {
        "sample_label": "Sample L", "property_name": "ionic conductivity", "value": "1 × 10 −4",
        "unit": "S cm −1", "temperature": "-40 to + 80 °C",
    }.items()})


def full(bundle):
    selected = compact(bundle)
    fields = selected.model_dump()
    return SpanFullReply(schema_version="records_span_reply_v0.1", diagnostic="Synthetic selection.", measurements=(SpanMeasurement(
        observations=tuple(SpanObservation(field=name, status="present" if name in fields else "unsupported",
            raw_span=getattr(selected, name, None), evidence=(getattr(selected, name),) if name in fields else (), note="Synthetic.")
            for name in FIELDS), representation="unparsed", linkage=()),))


def test_unicode_whitespace_crlf_and_repeated_text_are_sliced_by_position():
    bundle = source()
    first = resolve_token_span(bundle, select(bundle, "Sample L"))
    second = resolve_token_span(bundle, select(bundle, "Sample L", start=1))
    assert first.quote == second.quote and first.start != second.start
    assert resolve_token_span(bundle, select(bundle, "°C.\r\nSample L")).quote == "°C.\r\nSample L"
    assert resolve_token_span(bundle, select(bundle, "Naﬁon")).quote == "Naﬁon"
    result = resolve_span_reply(bundle, compact(bundle))
    assert result.records[0].value.raw_value.raw_text == "1 × 10 −4"
    assert result.records[0].temperature.raw_text == "-40 to + 80 °C"
    assert result.records[0].sample_label.evidence == (first,)
    assert result.records[0].linkage == () and result.records[0].review_state == "needs_review"
    assert result.records[0].li_ion_confirmation == "not_reviewed"
    assert result.records[0].method.status == "unsupported"
    assert "Outside compact" in result.records[0].method.note
    assert resolve_span_reply(bundle, compact(bundle)).records == result.records
    assert CandidateBundle.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("change", [{"start_token": -1}, {"start_token": 1, "end_token": 0},
                                   {"end_token": True}, {"end_token": 1.0}, {"end_token": "1"}])
def test_invalid_coordinate_types_and_order_are_rejected(change):
    with pytest.raises(ValueError):
        TokenSpan.model_validate({"region": "R1", "start_token": 0, "end_token": 0, **change})


@pytest.mark.parametrize("change", [{"region": "R0"}, {"region": "R999"}, {"end_token": 100000}])
def test_unknown_and_out_of_bounds_coordinates_are_not_clipped(change):
    with pytest.raises(ValueError):
        resolve_token_span(source(), TokenSpan.model_validate({"region": "R1", "start_token": 0, "end_token": 0, **change}))


def test_raw_span_must_be_inside_evidence_at_same_occurrence():
    bundle = source()
    reply = full(bundle).model_dump()
    reply["measurements"][0]["observations"][0]["evidence"] = [select(bundle, "Sample L", start=1).model_dump()]
    with pytest.raises(ValueError, match="coordinates"):
        resolve_span_reply(bundle, SpanFullReply.model_validate(reply))


@pytest.mark.parametrize("change", [{"status": "unsupported"}, {"raw_span": None}, {"evidence": []}])
def test_present_and_nonpresent_field_semantics_remain_strict(change):
    bundle = source()
    data = full(bundle).model_dump()
    data["measurements"][0]["observations"][0].update(change)
    with pytest.raises(ValueError):
        resolve_span_reply(bundle, SpanFullReply.model_validate(data))


def test_missing_keys_extra_text_and_duplicate_field_roles_are_rejected():
    bundle = source()
    data = compact(bundle).model_dump()
    data.pop("sample_label")
    with pytest.raises(ValueError):
        SpanCompactReply.model_validate(data)
    data = full(bundle).model_dump()
    data["measurements"][0]["observations"][1]["field"] = "sample_label"
    with pytest.raises(ValueError, match="sixteen"):
        SpanFullReply.model_validate(data)
    with pytest.raises(ValueError):
        TokenSpan.model_validate({**select(bundle, "Naﬁon").model_dump(), "quote": "invented"})
    data = full(bundle).model_dump()
    link = {"role": "sample_value", "evidence": [select(bundle, "Sample L").model_dump()], "note": "Synthetic."}
    data["measurements"][0]["linkage"] = [link, link]
    with pytest.raises(ValueError, match="Duplicate"):
        SpanFullReply.model_validate(data)


def test_nulls_and_empty_measurement_array_are_explicit_abstentions():
    bundle = source()
    assert resolve_span_reply(bundle, SpanCompactReply(**dict.fromkeys(compact(bundle).model_dump()))).records == ()
    assert resolve_span_reply(bundle, SpanFullReply(schema_version="records_span_reply_v0.1", measurements=(),
                                                  diagnostic="Synthetic empty result.")).records == ()


def test_token_request_never_includes_full_page_or_source_paths():
    bundle = source()
    for wire in ("span_full", "span_compact"):
        request = api.build_openai_request(bundle, "Synthetic task", "synthetic", 2048, wire, "medium")
        user = json.loads(request["input"][1]["content"])
        assert user["context"][0]["source"] == bundle.regions[0].quote
        assert user["tokenizer"] == VERSION
        assert user["context"][0]["tokens"][0] == [0, "Sample"]
        assert "Hidden" not in json.dumps(request) and "/synthetic/a.pdf" not in json.dumps(request)
        assert request["store"] is False
    data = bundle.regions[0].model_dump()
    data["page_number"] = 2
    data["region_id"] = source_identity(data)
    combined = CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic",
                               regions=(bundle.regions[0], SourceRegion.model_validate(data)))
    with pytest.raises(ValueError, match="exactly one"):
        build_span_messages(combined, "Synthetic task", compact=True)
    with pytest.raises(ValueError, match="source-only"):
        build_span_messages(resolve_span_reply(bundle, compact(bundle)), "Synthetic task", compact=False)


@pytest.mark.parametrize("wire", ["span_full", "span_compact"])
def test_native_run_and_evaluator_preserve_coordinates_and_deferred_dimensions(tmp_path, monkeypatch, wire):
    bundle = source()
    reply = compact(bundle) if wire == "span_compact" else full(bundle)
    raw = bundle.model_dump_json(indent=2)
    input_path = tmp_path / "input.json"
    input_path.write_bytes(raw.encode("utf-8"))
    envelope = {"status": "completed", "model": "synthetic", "usage": {"output_tokens": 123}, "output": [
        {"type": "message", "role": "assistant", "status": "completed", "content": [
            {"type": "output_text", "text": reply.model_dump_json()}]}]}
    monkeypatch.setattr(api, "send_openai_request", lambda *a: (json.dumps(envelope).encode(), "synthetic-request-id"))
    directory = tmp_path / "run"
    result = api.run_openai_extraction(input_path, directory, task="Synthetic task", model="synthetic", api_key="synthetic-key",
                                       source_root=ROOT, wire_format=wire)
    assert result["status"] == "integrity_valid"
    expected = resolve_span_reply(bundle, reply).records
    deferred = {name: "Synthetic deferred field." for name in (*FIELDS, "representation", *LINK_ROLES)
                if name not in compact(bundle).model_dump()}
    case = FullRecordCase(case_id="synthetic", input_sha256=text_hash(raw), task="Synthetic task", context=bundle,
                          expected=expected, deferred=deferred, rationale="Synthetic reference.")
    reference = FullRecordReference(reference_id=uuid4(), created_at=datetime.now(UTC), author="Synthetic", cases=(case,),
                                    limitations=("Synthetic, not independent gold.",))
    path = tmp_path / "reference.json"
    path.write_text(reference.model_dump_json(), encoding="utf-8")
    report = evaluate_extractions(path, {"synthetic": directory}, tmp_path / "evaluation", source_root=ROOT)
    assert report["summary"]["dimension_outcomes"] == {"match": 5, "deferred": 15}
    assert report["summary"]["full_record_outcomes"] == {"deferred": 1}
    request_path = directory / "request.json"
    request = json.loads(request_path.read_bytes())
    user = json.loads(request["input"][1]["content"])
    user["context"][0]["tokens"][0][1] = "Tampered"
    request["input"][1]["content"] = json.dumps(user)
    request_path.write_text(json.dumps(request), encoding="utf-8")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["request_sha256"] = text_hash(request_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="fixed bounded"):
        inspect_extraction(case, directory)
