"""Constructed matching/cohort counterexamples, not scientific reference annotations."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.records.full_evaluation import observations
from app.records.pilot import write_pilot_packet
from app.records.pilot_audit import audit_packet
from app.records.pilot_evaluation import (
    ExpectedRecord,
    PilotReference,
    PilotReferenceCase,
    compare_case,
    evaluate_pilot,
    maximum_matching,
    summarize,
)
from app.records.schema import EvidenceSpan, RecordCandidate
from app.records.sources import file_hash
from tests.unit.test_record_checks_export import ROOT, make_bundle, save_bundle
from tests.unit.test_record_pilot import document, profile


def reference_case(tmp_path):
    bundle = make_bundle(tmp_path)
    data = bundle.records[0].model_dump(mode="json")
    # Synthetic text explicitly defines absence; no uncertain field is promoted on real data.
    for item in [data[name] for name in data if isinstance(data[name], dict) and "status" in data[name]] + [
            data["value"][name] for name in ("raw_value", "raw_unit", "approximation", "uncertainty")]:
        if item["status"] == "unsupported":
            item["status"] = "not_found_in_context"
    record = RecordCandidate.model_validate(data)
    bundle = bundle.model_copy(update={"records": (record,)})
    context = bundle.model_copy(update={"records": ()})
    path = save_bundle(tmp_path / "context.json", context)
    case = PilotReferenceCase(case_id="synthetic", context_path=str(path), context_sha256=file_hash(path), context=context,
                              scope_note="Constructed complete annotation of this synthetic source region only.",
                              exhaustive_scope=True, annotation_state="annotated", expected=(ExpectedRecord(record=record),))
    return case, bundle


def dataset(case):
    return PilotReference(author="Synthetic fixture", author_kind="assistant", reference_kind="development_reference",
                          annotated_before_predictions=False, provenance_note="Constructed data; no human measurement.", cases=(case,))


@pytest.mark.parametrize("edges,cardinality", [([], 0), ([[]], 0), ([[0, 1], [0]], 2),
                                            ([[0], [0], [0]], 1), ([[0, 1], [1, 2], [0]], 3), ([[4], [3], []], 2)])
def test_maximum_matching_uses_augmenting_paths_and_never_reuses_reference(edges, cardinality):
    matching = maximum_matching(edges)
    assert len(matching) == len(set(matching.values())) == cardinality
    assert all(reference in edges[prediction] for prediction, reference in matching.items())
    assert matching == maximum_matching(edges)


def test_duplicate_predictions_are_false_positives_not_extra_recall(tmp_path):
    case, bundle = reference_case(tmp_path)
    duplicate = bundle.records[0].model_copy(update={"record_id": uuid4()})
    prediction = bundle.model_copy(update={"records": (bundle.records[0], duplicate)})
    row = compare_case(case, prediction)
    assert (row["known_tp"], row["known_fp"], row["known_fn"]) == (1, 1, 0)
    summary = summarize(dataset(case), [row])
    assert summary["precision_exact_reference"] == 0.5 and summary["recall_exact_reference"] == 1.0
    assert summary["scientific_admission"] == "not_evaluated"


def test_multiple_reference_records_match_reversed_prediction_order(tmp_path):
    case, bundle = reference_case(tmp_path)
    data = bundle.records[0].model_dump(mode="json")
    data["record_id"] = str(uuid4())
    data["value"]["raw_value"] = data["medium_composition"]
    second = RecordCandidate.model_validate(data)
    case = PilotReferenceCase.model_validate(case.model_dump() | {"expected": (*case.expected, ExpectedRecord(record=second))})
    prediction = bundle.model_copy(update={"records": (second, bundle.records[0])})
    row = compare_case(case, prediction)
    assert row["known_tp"] == 2 and row["known_fp"] == row["known_fn"] == 0
    assert row["exact_assignments"] == [{"prediction_index": 0, "reference_index": 1}, {"prediction_index": 1, "reference_index": 0}]


def test_deferred_matching_reassigns_exact_tie_without_creating_false_errors(tmp_path):
    case, bundle = reference_case(tmp_path)
    region = bundle.regions[0]
    broad = EvidenceSpan(region_id=region.region_id, start=0, end=len(region.quote), quote=region.quote)
    broad_record = bundle.records[0].model_copy(update={
        "sample_label": bundle.records[0].sample_label.model_copy(update={"evidence": (broad,)})})
    other = broad_record.model_copy(update={"record_id": uuid4()})
    second = ExpectedRecord(record=other, deferred={"sample_value": "Synthetic unresolved linkage."})
    case = PilotReferenceCase.model_validate(case.model_dump() | {"expected": (*case.expected, second)})
    prediction = bundle.model_copy(update={"records": (broad_record, bundle.records[0].model_copy(update={"record_id": uuid4()}))})
    row = compare_case(case, prediction)
    assert row["known_tp"] == row["unresolved_pairs"] == 1
    assert row["known_fp"] == row["known_fn"] == 0
    assert row["exact_assignments"] == [{"prediction_index": 1, "reference_index": 0}]


def test_wrong_value_is_both_nonmatching_prediction_and_missing_reference(tmp_path):
    case, bundle = reference_case(tmp_path)
    record = bundle.records[0].model_dump(mode="json")
    record["value"]["raw_value"] = record["medium_composition"]
    wrong = bundle.model_copy(update={"records": (RecordCandidate.model_validate(record),)})
    row = compare_case(case, wrong)
    assert (row["known_tp"], row["known_fp"], row["known_fn"]) == (0, 1, 1)
    assert row["pair_comparisons"][0][0]["dimensions"]["value"]["outcome"] == "mismatch"


def test_deferred_fields_remain_in_denominator_with_null_rates(tmp_path):
    case, bundle = reference_case(tmp_path)
    expected = case.expected[0].model_copy(update={"deferred": {"sample_value": "Synthetic unresolved linkage."}})
    case = case.model_copy(update={"expected": (expected,)})
    row = compare_case(case, bundle)
    assert row["known_tp"] == 0 and row["unresolved_pairs"] == 1
    summary = summarize(dataset(case), [row])
    assert summary["expected_records"] == 1 and summary["deferred_dimensions"] == 1
    assert summary["precision_exact_reference"] is None and summary["recall_exact_reference"] is None


def test_incomplete_scope_suppresses_recall_without_inventing_source_absence(tmp_path):
    case, bundle = reference_case(tmp_path)
    case = case.model_copy(update={"exhaustive_scope": False})
    summary = summarize(dataset(case), [compare_case(case, bundle)])
    assert summary["precision_exact_reference"] == 1.0 and summary["recall_exact_reference"] is None


def test_unannotated_empty_reference_is_not_correct_negative(tmp_path):
    case, bundle = reference_case(tmp_path)
    case = PilotReferenceCase.model_validate(case.model_dump() | {"annotation_state": "unannotated", "expected": ()})
    row = compare_case(case, bundle.model_copy(update={"records": ()}))
    assert row["status"] == "unannotated"
    summary = summarize(dataset(case), [row])
    assert summary["precision_exact_reference"] is summary["recall_exact_reference"] is None


def test_duplicate_role_proposals_are_not_hidden_by_dict_conversion(tmp_path):
    case, bundle = reference_case(tmp_path)
    record = bundle.records[0].model_copy(update={"linkage": bundle.records[0].linkage + (bundle.records[0].linkage[0],)})
    row = compare_case(case, bundle.model_copy(update={"records": (record,)}))
    assert row["known_tp"] == 0 and row["known_fp"] == row["known_fn"] == 1
    assert row["pair_comparisons"][0][0]["duplicate_linkage_roles"] == ["sample_value"]


def test_duplicate_reference_records_and_unresolved_expectations_are_rejected(tmp_path):
    case, bundle = reference_case(tmp_path)
    duplicate = ExpectedRecord(record=case.expected[0].record.model_copy(update={"record_id": uuid4()}))
    with pytest.raises(ValueError, match="Duplicate exact reference"):
        PilotReferenceCase.model_validate(case.model_dump() | {"expected": (*case.expected, duplicate)})
    record = make_bundle(tmp_path).records[0]
    with pytest.raises(ValueError, match="deferred"):
        ExpectedRecord(record=record)
    deferred = {name: "Constructed unresolved expectation." for name, obs in observations(record).items() if obs.status == "unsupported"}
    assert ExpectedRecord(record=record, deferred=deferred).deferred == deferred


@pytest.mark.parametrize("kind,before", [("assistant", True), ("human", False)])
def test_independence_declarations_cannot_promote_agent_labels(tmp_path, kind, before):
    case, _ = reference_case(tmp_path)
    data = dataset(case).model_dump() | {"reference_kind": "independent_annotation_declared", "author_kind": kind,
                                        "annotated_before_predictions": before}
    with pytest.raises(ValueError, match="declared human"):
        PilotReference.model_validate(data)


def test_declared_human_independence_still_is_not_authenticated(tmp_path):
    case, bundle = reference_case(tmp_path)
    reference = PilotReference.model_validate(dataset(case).model_dump() | {"reference_kind": "independent_annotation_declared",
                                                                          "author_kind": "human", "annotated_before_predictions": True})
    summary = summarize(reference, [compare_case(case, bundle)])
    assert summary["independence"] == "Caller-declared, not authenticated"
    assert summary["scientific_admission"] == "not_evaluated"


@pytest.mark.parametrize("mode", ["available", "missing", "invalid"])
def test_offline_artifacts_preserve_scope_failures_and_inputs(tmp_path, mode):
    case, bundle = reference_case(tmp_path)
    ref_path = tmp_path / "reference.json"
    ref_path.write_text(dataset(case).model_dump_json(indent=2), encoding="utf-8")
    candidate_path = tmp_path / "prediction.json"
    mapping = {}
    if mode != "missing":
        candidate_path.write_text(bundle.model_dump_json() if mode == "available" else '{"bad":true}', encoding="utf-8")
        mapping = {case.case_id: candidate_path}
    before = ref_path.read_bytes()
    report = evaluate_pilot(ref_path, mapping, tmp_path / "out", source_root=ROOT)
    assert report["summary"]["expected_records"] == 1
    if mode == "available":
        assert report["summary"]["known_tp"] == 1
    else:
        assert report["summary"]["unavailable_expected_records"] == 1
        assert report["summary"]["precision_exact_reference"] is None
        assert report["cases"][0]["proposed_records"] is None
    manifest = json.loads((tmp_path / "out/manifest.json").read_bytes())
    assert all(file_hash(tmp_path / "out" / name) == checksum for name, checksum in manifest["outputs"].items())
    assert ref_path.read_bytes() == before
    assert (tmp_path / "out/review.html").is_file()
    with pytest.raises(FileExistsError):
        evaluate_pilot(ref_path, mapping, tmp_path / "out", source_root=ROOT)


@pytest.mark.parametrize("failure", ["context_bytes", "prediction_sources", "pdf", "unknown_case"])
def test_identity_failures_stop_before_success_output(tmp_path, failure):
    case, bundle = reference_case(tmp_path)
    ref_path = tmp_path / "reference.json"
    ref_path.write_text(dataset(case).model_dump_json(), encoding="utf-8")
    path = save_bundle(tmp_path / "prediction.json", bundle)
    mapping = {case.case_id: path}
    if failure == "context_bytes":
        Path(case.context_path).write_bytes(b"tampered")
    elif failure == "prediction_sources":
        save_bundle(path, make_bundle(tmp_path))
    elif failure == "pdf":
        Path(bundle.regions[0].original_pdf_path).write_bytes(b"tampered")
    else:
        mapping = {"unknown": path}
    with pytest.raises(ValueError):
        evaluate_pilot(ref_path, mapping, tmp_path / "out", source_root=ROOT)
    assert not (tmp_path / "out").exists()


def packet_fixture(tmp_path):
    doc = document(tmp_path)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile(doc, "li_nafion_mention")), encoding="utf-8")
    protocol = tmp_path / "protocol.md"
    protocol.write_text("Constructed source-only packet.", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"source_fingerprint": "b" * 64}), encoding="utf-8")
    packet = tmp_path / "packet"
    write_pilot_packet((doc,), profile_path, packet, protocol_path=protocol, baseline_manifest_path=baseline, source_root=ROOT)
    return packet, doc


def test_source_audit_keeps_eligibility_exposure_and_human_time_unknown(tmp_path):
    packet, doc = packet_fixture(tmp_path)
    report = audit_packet(packet, tmp_path / "audit", annotator_availability="unavailable", source_root=ROOT)
    assert report["summary"]["documents"] == report["summary"]["lexical_candidate_count"] == 1
    assert report["summary"]["scientifically_eligible_publications"] is None
    assert report["summary"]["independent_annotator_availability"] == "unavailable"
    assert report["summary"]["scientific_precision"] is report["summary"]["human_time_savings"] is None
    assert report["documents"][0]["exposure"] == "development_exposed"
    page = (tmp_path / "audit/review.html").read_text(encoding="utf-8")
    assert "Synthetic &lt;/h2&gt; title" in page and "Synthetic </h2> title" not in page
    assert Path(doc.original_pdf_path).as_uri() in page
    repeated = audit_packet(packet, tmp_path / "repeat", annotator_availability="unavailable", source_root=ROOT)
    assert repeated == report


@pytest.mark.parametrize("failure", ["artifact", "pdf", "fingerprint", "summary", "gold", "path_escape"])
def test_source_audit_does_not_repair_changed_packets(tmp_path, failure):
    packet, doc = packet_fixture(tmp_path)
    manifest_path = packet / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if failure == "artifact":
        (packet / "source_inventory.json").write_bytes(b"tampered")
    elif failure == "pdf":
        Path(doc.original_pdf_path).write_bytes(b"tampered")
    else:
        if failure == "fingerprint":
            manifest["source_fingerprint"] = "f" * 64
        elif failure == "summary":
            manifest["documents"] = 999
        elif failure == "gold":
            manifest["independent_gold"] = True
        else:
            manifest["artifacts_sha256"]["../escape.json"] = "f" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        audit_packet(packet, tmp_path / "audit", source_root=ROOT)
    assert not (tmp_path / "audit").exists()
