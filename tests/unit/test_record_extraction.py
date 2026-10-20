"""Synthetic bounded-record counterexamples; no model inference or scientific gold."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.records import extraction
from app.records.extraction import FIELDS, FullRecordReply, build_record_request, parse_completion, resolve_reply, run_extraction
from app.records.full_evaluation import (
    FullRecordCase,
    FullRecordReference,
    compare_record,
    evaluate_extractions,
    inspect_extraction,
)
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash

ROOT = Path(__file__).resolve().parents[2]
TASK = "Synthetic measurement task, not scientific evidence."


def context(text="Sample L conductivity 1 × 10−4 S cm−1 at 20 °C. Other header 25 °C."):
    data = {
        "article_id": str(uuid4()), "original_pdf_path": "/synthetic/source.pdf", "original_pdf_sha256": "a" * 64,
        "page_number": 1, "text_layer_id": str(uuid4()), "text_layer": "original",
        "layer_pdf_path": "/synthetic/source.pdf", "layer_pdf_sha256": "a" * 64,
        "page_text": text, "page_text_sha256": text_hash(text), "start": 0, "end": len(text),
        "quote": text, "quote_sha256": text_hash(text), "selection_basis": "manual_development",
        "selection_note": "Synthetic fixture; not a real source.",
    }
    data["region_id"] = source_identity(data)
    return CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic", regions=(SourceRegion.model_validate(data),))


def wire(empty=False):
    supplied = {"sample_label": "Sample L", "property_name": "conductivity", "value": "1 × 10−4",
                "unit": "S cm−1", "temperature": "20 °C"}
    fields = [{"field": name, "status": "present" if name in supplied else "not_found_in_context",
               "raw_text": supplied.get(name), "evidence": [{"region": "R1", "quote": supplied[name]}] if name in supplied else [],
               "note": "Synthetic observation only."} for name in FIELDS]
    return {"schema_version": "records_bounded_reply_v0.1", "measurements": [] if empty else [
        {"observations": fields, "representation": "scalar", "linkage": []}], "diagnostic": "Synthetic reply only."}


def envelope(reply, finish="stop"):
    return json.dumps({"choices": [{"finish_reason": finish, "message": {"content": json.dumps(reply, ensure_ascii=False)}}]}).encode()


def reference_case(bundle, expected=None, deferred=None):
    if expected is None:
        expected = resolve_reply(bundle, FullRecordReply.model_validate(wire())).records
    return FullRecordCase(case_id="synthetic", input_sha256=text_hash(bundle.model_dump_json(indent=2)), task=TASK,
                          context=bundle, expected=expected, deferred=deferred or {}, rationale="Synthetic expected proposal.")


def fixture_run(tmp_path, monkeypatch, reply=None, response=None, transport_error=False):
    bundle = context()
    source = tmp_path / "source.json"
    source.write_text(bundle.model_dump_json(indent=2), encoding="utf-8", newline="\n")
    identity = tmp_path / "runtime.json"
    identity.write_text(json.dumps({"model_alias": "synthetic", "endpoint": "http://127.0.0.1:18086"}), encoding="utf-8")

    def send(*args):
        if transport_error:
            raise URLError("Synthetic connection failure")
        return response if response is not None else envelope(reply if reply is not None else wire())

    monkeypatch.setattr(extraction, "send_local_request", send)
    directory = tmp_path / "run"
    result = run_extraction(source, directory, task=TASK, endpoint="http://127.0.0.1:18086", model="synthetic",
                            runtime_manifest=identity, source_root=ROOT)
    return bundle, directory, result


def test_resolved_record_preserves_raw_evidence_and_stable_identity():
    bundle = context()
    reply = FullRecordReply.model_validate(wire())
    first, second = resolve_reply(bundle, reply), resolve_reply(bundle, reply)
    assert first.records[0] == second.records[0]
    assert first.records[0].value.raw_value.raw_text == "1 × 10−4"
    assert first.records[0].review_state == "needs_review"
    assert first.records[0].li_ion_confirmation == "not_reviewed"
    assert CandidateBundle.model_validate_json(first.model_dump_json()) == first
    reordered = wire()
    reordered["measurements"][0]["observations"].reverse()
    assert resolve_reply(bundle, FullRecordReply.model_validate(reordered)).records == first.records


@pytest.mark.parametrize("mutation", ["duplicate_field", "missing_field", "duplicate_link", "two_records", "unknown_field", "empty_note"])
def test_wire_rejects_ambiguous_or_incomplete_record_structure(mutation):
    data = wire()
    measurement = data["measurements"][0]
    if mutation == "duplicate_field":
        measurement["observations"][-1] = measurement["observations"][0]
    elif mutation == "missing_field":
        measurement["observations"].pop()
    elif mutation == "duplicate_link":
        link = {"role": "sample_value", "evidence": [{"region": "R1", "quote": "Sample L"}], "note": "Synthetic"}
        measurement["linkage"] = [link, link]
    elif mutation == "two_records":
        data["measurements"].append(measurement)
    elif mutation == "unknown_field":
        measurement["observations"][0]["field"] = "normalized_temperature"
    else:
        data["diagnostic"] = ""
    with pytest.raises(ValidationError):
        FullRecordReply.model_validate(data)


@pytest.mark.parametrize("mutation", ["invented_quote", "unknown_region", "raw_not_in_quote", "asserted_missing"])
def test_literal_integrity_failures_remain_failures(mutation):
    data = wire()
    obs = data["measurements"][0]["observations"][0]
    if mutation == "invented_quote":
        obs["evidence"][0]["quote"] = "Invented sample"
    elif mutation == "unknown_region":
        obs["evidence"][0]["region"] = "R99"
    elif mutation == "raw_not_in_quote":
        obs["raw_text"] = "Li-Nafion"
    else:
        obs["status"] = "not_found_in_context"
    with pytest.raises(ValueError):
        resolve_reply(context(), FullRecordReply.model_validate(data))


def test_repeated_unit_requires_unique_context_and_correct_reference_anchor():
    bundle = context("Sample L conductivity 1 × 10−4 S cm−1 at 20 °C. Electronic unit S cm−1.")
    data = wire()
    with pytest.raises(ValueError, match="exactly one"):
        resolve_reply(bundle, FullRecordReply.model_validate(data))
    unit = next(o for o in data["measurements"][0]["observations"] if o["field"] == "unit")
    unit["evidence"][0]["quote"] = "1 × 10−4 S cm−1"
    correct = resolve_reply(bundle, FullRecordReply.model_validate(data)).records[0]
    case = reference_case(bundle, (correct,))
    unit["evidence"][0]["quote"] = "Electronic unit S cm−1"
    wrong = resolve_reply(bundle, FullRecordReply.model_validate(data)).records[0]
    dimensions = compare_record(case, wrong)["dimensions"]
    assert dimensions["unit"]["raw_agreement"] is True
    assert dimensions["unit"]["anchor_agreement"] is False


def test_candidate_answers_and_cross_article_context_cannot_enter_model_prompt():
    bundle = context()
    filled = resolve_reply(bundle, FullRecordReply.model_validate(wire()))
    with pytest.raises(ValueError, match="source-only"):
        build_record_request(filled, TASK, "synthetic", 100, 42)
    other = context()
    combined = CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic", regions=bundle.regions + other.regions)
    with pytest.raises(ValueError, match="exactly one article"):
        build_record_request(combined, TASK, "synthetic", 100, 42)


@pytest.mark.parametrize("finish", ["length", "content_filter", None])
def test_incomplete_response_is_not_abstention(finish):
    with pytest.raises(ValueError, match="Incomplete"):
        parse_completion(envelope(wire(True), finish))


def test_wrong_footnote_temperature_and_prior_method_fail_even_when_literal():
    bundle = context()
    case = reference_case(bundle)
    data = wire()
    fields = {o["field"]: o for o in data["measurements"][0]["observations"]}
    fields["temperature"].update(raw_text="25 °C", evidence=[{"region": "R1", "quote": "25 °C"}])
    fields["method"].update(status="present", raw_text="Other header", evidence=[{"region": "R1", "quote": "Other header"}])
    record = resolve_reply(bundle, FullRecordReply.model_validate(data)).records[0]
    report = compare_record(case, record)
    assert report["dimensions"]["temperature"]["outcome"] == "mismatch"
    assert report["dimensions"]["method"]["outcome"] == "mismatch"
    assert report["full_record_agreement"] == "mismatch"


def test_deferred_linkage_prevents_full_record_match():
    bundle = context()
    case = reference_case(bundle, deferred={"conditions_measurement": "Synthetic unresolved linkage."})
    result = compare_record(case, case.expected[0])
    assert result["dimension_outcomes"] == {"match": 19, "deferred": 1}
    assert result["full_record_agreement"] == "deferred"


@pytest.mark.parametrize("failure", ["transport", "truncated", "invented"])
def test_execution_preserves_failure_artifacts_and_evaluation_denominators(tmp_path, monkeypatch, failure):
    data = wire()
    if failure == "invented":
        data["measurements"][0]["observations"][0]["evidence"][0]["quote"] = "Invented"
    response = envelope(data, "length" if failure == "truncated" else "stop")
    bundle, directory, result = fixture_run(tmp_path, monkeypatch, response=response, transport_error=failure == "transport")
    assert result["status"] == "failed"
    assert not (directory / "candidates.json").exists()
    row = inspect_extraction(reference_case(bundle), directory)
    assert row["status"] in {"invalid", "unavailable"}
    assert len(row["dimensions"]) == 20
    assert (directory / "request.json").exists()
    if failure != "transport":
        assert (directory / "response.json").read_bytes() == response


@pytest.mark.parametrize("empty_reference,empty_prediction,expected", [(True, True, "correct"), (True, False, "false_assertion"),
                                                                       (False, True, "missed_record")])
def test_abstention_and_omission_are_distinct(tmp_path, monkeypatch, empty_reference, empty_prediction, expected):
    bundle, directory, _ = fixture_run(tmp_path, monkeypatch, reply=wire(empty_prediction))
    case = reference_case(bundle, expected=() if empty_reference else None)
    assert inspect_extraction(case, directory)["abstention"] == expected


def test_evaluator_reparses_raw_response_ignores_success_flag_and_saves_sources(tmp_path, monkeypatch):
    bundle, directory, _ = fixture_run(tmp_path, monkeypatch)
    (directory / "result.json").write_text('{"status":"failed"}', encoding="utf-8")
    case = reference_case(bundle)
    reference = FullRecordReference(reference_id=uuid4(), created_at=datetime.now(UTC), author="Synthetic fixture",
                                    cases=(case,), limitations=("Synthetic; not independent gold.",))
    path = tmp_path / "reference.json"
    path.write_text(reference.model_dump_json(), encoding="utf-8")
    report = evaluate_extractions(path, {case.case_id: directory}, tmp_path / "evaluation", source_root=ROOT)
    assert report["summary"]["full_record_outcomes"] == {"match": 1}
    assert report["summary"]["dimension_outcomes"] == {"match": 20}
    assert (tmp_path / "evaluation/runs/0/response.json").is_file()
    assert (tmp_path / "evaluation/review.html").is_file()
    with pytest.raises(FileExistsError):
        evaluate_extractions(path, {}, tmp_path / "evaluation", source_root=ROOT)
    missing = evaluate_extractions(path, {}, tmp_path / "missing", source_root=ROOT)
    assert missing["summary"]["expected_record_dimensions"] == 20
    assert missing["summary"]["dimension_outcomes"] == {"unavailable": 20}


@pytest.mark.parametrize("artifact", ["request.json", "input.json", "runtime_identity.json", "manifest.json"])
def test_tampered_experiment_binding_stops_evaluation(tmp_path, monkeypatch, artifact):
    bundle, directory, _ = fixture_run(tmp_path, monkeypatch)
    path = directory / artifact
    data = json.loads(path.read_bytes())
    if artifact == "request.json":
        data["messages"][1]["content"] = "Changed task"
    elif artifact == "input.json":
        data["producer"] = "changed"
    elif artifact == "runtime_identity.json":
        data["model_alias"] = "changed"
    else:
        data["task"] = "Changed task"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        inspect_extraction(reference_case(bundle), directory)


def test_linkage_and_range_representation_are_evaluated_separately():
    bundle = context()
    data = wire()
    link = {"role": "conditions_measurement", "evidence": [{"region": "R1", "quote": bundle.regions[0].quote}],
            "note": "Synthetic explicit condition link."}
    data["measurements"][0]["linkage"] = [link]
    expected = resolve_reply(bundle, FullRecordReply.model_validate(data)).records
    case = reference_case(bundle, expected)
    data["measurements"][0].update(linkage=[], representation="range")
    actual = resolve_reply(bundle, FullRecordReply.model_validate(data)).records[0]
    compared = compare_record(case, actual)
    assert compared["dimensions"]["conditions_measurement"]["outcome"] == "mismatch"
    assert compared["dimensions"]["representation"]["outcome"] == "mismatch"
    assert compared["dimensions"]["value"]["outcome"] == "match"


def test_runtime_model_mismatch_rejected_even_with_recomputed_checksum(tmp_path, monkeypatch):
    bundle, directory, _ = fixture_run(tmp_path, monkeypatch)
    path = directory / "runtime_identity.json"
    data = json.loads(path.read_bytes())
    data["model_alias"] = "Other model"
    raw = json.dumps(data).encode()
    path.write_bytes(raw)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["runtime_identity_sha256"] = text_hash(raw.decode())
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="model differs"):
        inspect_extraction(reference_case(bundle), directory)


def test_reference_rejects_unknown_dimensions_unresolved_grading_and_duplicate_cases():
    bundle = context()
    case = reference_case(bundle)
    with pytest.raises(ValueError, match="Unknown deferred"):
        FullRecordCase.model_validate({**case.model_dump(), "deferred": {"unknown": "Synthetic"}})
    record = case.expected[0].model_dump()
    record["method"] = {"status": "ambiguous", "note": "Synthetic unresolved attribution."}
    with pytest.raises(ValueError, match="must be deferred"):
        FullRecordCase.model_validate({**case.model_dump(), "expected": [record]})
    with pytest.raises(ValueError, match="Duplicate reference"):
        FullRecordReference(reference_id=uuid4(), created_at=datetime.now(UTC), author="Synthetic",
                            cases=(case, case), limitations=("Synthetic",))


@pytest.mark.parametrize("name", ["input.json", "manifest.json", "request.json", "runtime_identity.json"])
def test_missing_run_metadata_remains_in_denominator(tmp_path, monkeypatch, name):
    bundle, directory, _ = fixture_run(tmp_path, monkeypatch)
    (directory / name).rename(directory / (name + '.unavailable'))
    row = inspect_extraction(reference_case(bundle), directory)
    assert row["status"] == "unavailable"
    assert name in row["diagnostic"]
    assert len(row["dimensions"]) == 20
