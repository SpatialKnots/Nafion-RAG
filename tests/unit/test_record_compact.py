"""Synthetic compact-wire counterexamples, never a scientific extraction benchmark."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.records import extraction
from app.records.compact import VERSION, CompactReply, build_compact_request, parse_compact_completion, resolve_compact_reply
from app.records.extraction import FIELDS, LINK_ROLES, run_extraction
from app.records.full_evaluation import FullRecordCase, FullRecordReference, evaluate_extractions
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash


def source():
    text = "Sample L ionic conductivity 1 × 10−4 S cm−1 at room temperature."
    page = "Hidden prefix. " + text + " Hidden suffix."
    start = page.index(text)
    data = dict(article_id=uuid4(), original_pdf_path="/synthetic/a.pdf", original_pdf_sha256="a" * 64,
                page_number=1, text_layer_id=uuid4(), text_layer="original", layer_pdf_path="/synthetic/a.pdf",
                layer_pdf_sha256="a" * 64, page_text=page, page_text_sha256=text_hash(page), start=start,
                end=start + len(text), quote=text, quote_sha256=text_hash(text), selection_basis="expert_oracle",
                selection_note="Synthetic selected clause only.")
    data["region_id"] = source_identity(data)
    return CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic", regions=(SourceRegion.model_validate(data),))


def reply():
    return CompactReply(sample_label="Sample L", property_name="ionic conductivity", value="1 × 10−4",
                        unit="S cm−1", temperature="room temperature")


def envelope(value, finish="stop"):
    return json.dumps({"choices": [{"finish_reason": finish, "message": {"content": value.model_dump_json()}}]}).encode()


def test_fixed_keys_and_exact_partial_candidate_without_inferred_linkage():
    bundle = source()
    output = resolve_compact_reply(bundle, reply())
    candidate = output.records[0]
    assert output.producer == VERSION
    assert candidate.value.raw_value.raw_text == "1 × 10−4"
    assert candidate.temperature.raw_text == "room temperature"
    assert candidate.value.representation == "unparsed"
    assert candidate.linkage == ()
    assert candidate.method.status == "unsupported"
    assert "Outside compact" in candidate.method.note
    assert candidate.review_state == "needs_review"
    assert candidate.li_ion_confirmation == "not_reviewed"
    assert CandidateBundle.model_validate_json(output.model_dump_json()) == output
    assert resolve_compact_reply(bundle, reply()).records == output.records


@pytest.mark.parametrize("key", ["sample_label", "property_name", "value", "unit", "temperature"])
def test_missing_key_is_not_silently_filled(key):
    data = reply().model_dump()
    data.pop(key)
    with pytest.raises(ValueError):
        CompactReply.model_validate(data)


@pytest.mark.parametrize("raw", ["0.0001", "invented", " "])
def test_no_normalization_or_invented_spans(raw):
    data = reply().model_dump()
    data["value"] = raw
    with pytest.raises(ValueError):
        resolve_compact_reply(source(), CompactReply.model_validate(data))


def test_null_is_abstention_without_fabricated_missingness_or_sample():
    data = reply().model_dump()
    data["sample_label"] = None
    candidate = resolve_compact_reply(source(), CompactReply.model_validate(data)).records[0]
    assert candidate.sample_label.status == "unsupported"
    assert candidate.sample_label.raw_text is None
    assert "abstention" in candidate.sample_label.note
    empty = CompactReply.model_validate(dict.fromkeys(data))
    assert resolve_compact_reply(source(), empty).records == ()


def test_prompt_contains_only_selected_clause_and_compact_schema():
    request = build_compact_request(source(), "Synthetic task", "synthetic", 256, 42)
    assert "Hidden prefix" not in request["messages"][1]["content"]
    assert "Hidden suffix" not in request["messages"][1]["content"]
    schema = request["response_format"]["schema"]
    assert set(schema["required"]) == set(reply().model_dump())
    assert len(schema["properties"]) == 5
    bundle = source()
    another = bundle.regions[0].model_dump()
    another.update(page_number=2)
    another["region_id"] = source_identity(another)
    combined = CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic",
                               regions=(bundle.regions[0], SourceRegion.model_validate(another)))
    with pytest.raises(ValueError, match="exactly one frozen"):
        build_compact_request(combined, "Synthetic task", "synthetic", 256, 42)


def test_truncation_and_extra_keys_are_failures():
    with pytest.raises(ValueError, match="Incomplete"):
        parse_compact_completion(envelope(reply(), "length"))
    with pytest.raises(ValueError):
        CompactReply.model_validate({**reply().model_dump(), "explanation": "Unrequested"})


def test_compact_run_and_full_evaluator_reparse_wire_and_keep_deferred_dimensions(tmp_path, monkeypatch):
    bundle = source()
    raw = bundle.model_dump_json(indent=2).encode()
    path, runtime = tmp_path / "input.json", tmp_path / "runtime.json"
    path.write_bytes(raw)
    runtime.write_text(json.dumps({"model_alias": "synthetic", "endpoint": "http://127.0.0.1:18088"}), encoding="utf-8")
    monkeypatch.setattr(extraction, "send_local_request", lambda *args: envelope(reply()))
    directory = tmp_path / "run"
    root = Path(__file__).resolve().parents[2]
    result = run_extraction(path, directory, task="Synthetic task", endpoint="http://127.0.0.1:18088", model="synthetic",
                            runtime_manifest=runtime, source_root=root, wire_format="compact", max_tokens=256, timeout_seconds=90)
    assert result["status"] == "integrity_valid"
    assert json.loads((directory / "manifest.json").read_bytes())["extraction_version"] == VERSION
    expected = resolve_compact_reply(bundle, reply()).records
    deferred = {name: "Synthetic out-of-scope dimension." for name in (*FIELDS, "representation", *LINK_ROLES)
                if name not in reply().model_dump()}
    case = FullRecordCase(case_id="synthetic", input_sha256=text_hash(raw.decode()), task="Synthetic task",
                          context=bundle, expected=expected, deferred=deferred, rationale="Synthetic reference only.")
    reference = FullRecordReference(reference_id=uuid4(), created_at=datetime.now(UTC), author="Synthetic",
                                    cases=(case,), limitations=("Synthetic; not independent gold.",))
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(reference.model_dump_json(), encoding="utf-8")
    report = evaluate_extractions(reference_path, {case.case_id: directory}, tmp_path / "evaluation", source_root=root)
    assert report["summary"]["dimension_outcomes"] == {"match": 5, "deferred": 15}
    assert report["summary"]["full_record_outcomes"] == {"deferred": 1}
    assert len(json.loads((directory / "reply.json").read_bytes())) == 5
