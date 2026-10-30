"""Constructed controls for sparse operation-duration comparison, no transport."""

import copy
import hashlib
import json

import pytest

from scripts.event_duration_evaluation import evaluate, validate_reference
from scripts.gigachat_event_proposal import catalog

TEXT = "Sample was washed for 2 hours and dried for 1 hour. It was stored for 2 days."


def reference(source=None):
    source = source or catalog(TEXT)
    text = source["exact_text"]
    operations = []
    for name in ("washed", "dried", "stored"):
        start = text.index(name)
        operations.append({"id": name, "anchor": {"start": start, "end": start + len(name), "text": name},
                           "duration_state": "present"})
    return {"exact_text_sha256": hashlib.sha256(text.encode()).hexdigest(), "target_operation_id": "washed",
            "operations": operations, "duration_owners": [{"atom_id": f"D{i}", "operation_id": name}
                for i, name in enumerate(("washed", "dried", "stored"), 1)], "unannotated_atom_ids": []}


def event(ids=None, status="present", contexts=None):
    missing = {"status": "not_found", "ids": []}
    return {"kind": "preparation", "context_ids": contexts or ["S1"],
            "duration": {"status": status, "ids": ["D1"] if ids is None else ids},
            **{field: copy.deepcopy(missing) for field in ("sample", "operation", "conditions", "completion_criterion")}}


def native(target=None, others=None, diagnostic="Constructed.", finish="stop"):
    content = {"target": event() if target is None else target, "other_events": others or [], "diagnostic": diagnostic}
    return json.dumps({"choices": [{"finish_reason": finish, "message": {"role": "assistant",
                      "content": json.dumps(content)}}]}).encode()


def run(raw):
    return evaluate(raw, catalog(TEXT), reference())


def test_same_statement_different_operations_remain_separate():
    result = run(native(event(["D1", "D2"])))
    row = result["events"][0]
    assert row["multiple_annotated_operations_in_one_event"]
    assert row["target_comparison"]["other_operation_atom_ids"] == ["D2"]
    assert row["target_comparison"]["state"] == "other_operation_duration_selected"
    assert result["original_parser"]["accepted"]  # Exact IDs do not establish scientific assignment.
    assert result["scientific_acceptance"] == "not_evaluated"


def test_rejected_reply_remains_rejected_despite_matching_raw_duration():
    result = run(native(diagnostic=""))
    assert not result["original_parser"]["accepted"]
    assert result["original_parser"]["error"] == "Too many events or missing diagnostic"
    assert result["events"][0]["target_comparison"]["state"] == "raw_duration_field_agrees_with_preliminary_reference"


def test_other_event_merge_and_repetition_are_not_target_accuracy():
    result = run(native(others=[event(), event(["D2", "D3"], contexts=["S1", "S2"])]))
    assert result["events"][2]["multiple_annotated_operations_in_one_event"]
    assert result["repeated_duration_selections"] == {"D1": ["target", "other_events[0]"]}
    assert result["events"][0]["target_comparison"]["state"] == "raw_duration_field_agrees_with_preliminary_reference"


def test_two_atoms_same_annotated_operation_do_not_imply_merge():
    ref = reference()
    ref["duration_owners"][1]["operation_id"] = "washed"
    ref["operations"][1]["duration_state"] = "unresolved"
    row = evaluate(native(event(["D1", "D2"])), catalog(TEXT), ref)["events"][0]
    assert not row["multiple_annotated_operations_in_one_event"]
    assert row["target_comparison"]["missing_atom_ids"] == []


@pytest.mark.parametrize("status,expected", [("not_found", "annotated_target_duration_missing"),
                                           ("uncertain", "annotated_target_duration_missing")])
def test_missing_annotated_duration_is_not_agreement(status, expected):
    assert run(native(event([], status)))["events"][0]["target_comparison"]["state"] == expected


@pytest.mark.parametrize("status,expected", [("not_found", "raw_duration_field_agrees_with_preliminary_reference"),
                                           ("uncertain", "missing_duration_status_disagrees")])
def test_absence_in_excerpt_is_distinct_from_model_uncertainty(status, expected):
    ref = reference()
    ref["operations"][0]["duration_state"] = "not_in_excerpt"
    ref["duration_owners"] = ref["duration_owners"][1:]
    ref["unannotated_atom_ids"] = ["D1"]
    result = evaluate(native(event([], status)), catalog(TEXT), ref)
    assert result["events"][0]["target_comparison"]["state"] == expected


def test_unannotated_atom_not_false_positive_or_match():
    ref = reference()
    ref["duration_owners"] = ref["duration_owners"][1:]
    ref["operations"][0]["duration_state"] = "unresolved"
    ref["unannotated_atom_ids"] = ["D1"]
    row = evaluate(native(), catalog(TEXT), ref)["events"][0]
    assert row["target_comparison"]["state"] == "unresolved_not_scored"
    assert row["target_comparison"]["other_operation_atom_ids"] == []


@pytest.mark.parametrize("change", ["unknown", "duplicate", "nonpresent", "empty_present", "outside", "order", "context_order"])
def test_invalid_duration_selection_never_gets_semantic_comparison(change):
    target = event()
    if change == "unknown":
        target["duration"]["ids"] = ["D99"]
    elif change == "duplicate":
        target["duration"]["ids"] = ["D1", "D1"]
    elif change == "nonpresent":
        target["duration"]["status"] = "not_found"
    elif change == "empty_present":
        target["duration"]["ids"] = []
    elif change == "outside":
        target["context_ids"] = ["S2"]
    elif change == "order":
        target["duration"]["ids"] = ["D2", "D1"]
    else:
        target["context_ids"] = ["S2", "S1"]
    row = run(native(target))["events"][0]
    assert row["target_comparison"]["state"] == "invalid_raw_duration_selection_not_scored"
    assert not row["multiple_annotated_operations_in_one_event"]


def test_unrelated_field_contradiction_visible_without_changing_raw_data():
    target = event()
    target["operation"]["ids"] = ["S1"]
    raw = native(target)
    source, ref = catalog(TEXT), reference()
    saved = copy.deepcopy((source, ref))
    result = evaluate(raw, source, ref)
    assert (source, ref) == saved
    assert result["events"][0]["formal_issues"] == ["operation:status_id_contradiction"]
    assert not result["original_parser"]["accepted"]


@pytest.mark.parametrize("change", ["hash", "anchor", "duplicate_op", "target", "owner", "duplicate_atom",
                                    "missing_atom", "state", "unknown_unannotated"])
def test_invalid_reference_fails_loudly(change):
    ref = reference()
    if change == "hash":
        ref["exact_text_sha256"] = "0" * 64
    elif change == "anchor":
        ref["operations"][0]["anchor"]["start"] += 1
    elif change == "duplicate_op":
        ref["operations"].append(copy.deepcopy(ref["operations"][0]))
    elif change == "target":
        ref["target_operation_id"] = "absent"
    elif change == "owner":
        ref["duration_owners"][0]["operation_id"] = "absent"
    elif change == "duplicate_atom":
        ref["unannotated_atom_ids"] = ["D1"]
    elif change == "missing_atom":
        ref["duration_owners"].pop()
    elif change == "state":
        ref["operations"][0]["duration_state"] = "not_in_excerpt"
    else:
        ref["unannotated_atom_ids"] = ["D99"]
    with pytest.raises(ValueError):
        validate_reference(catalog(TEXT), ref)


@pytest.mark.parametrize("finish", ["blacklist", "length", None])
def test_filtered_or_incomplete_output_not_scored(finish):
    with pytest.raises(ValueError, match="cannot be duration-scored"):
        run(native(finish=finish))


@pytest.mark.parametrize("raw", [b'{"choices":[],"choices":[]}', b'{', b'{"choices":[]}'])
def test_malformed_or_duplicate_json_not_repaired(raw):
    with pytest.raises(ValueError):
        run(raw)


def test_source_drift_fails_before_output_inspection():
    source = catalog(TEXT)
    source["duration_atoms"][0]["unit_text"] = "days"
    with pytest.raises(ValueError, match="drift"):
        evaluate(native(), source, reference())
