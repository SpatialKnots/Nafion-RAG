"""Finite ownership diagnostics: controls and exposed raw selections, no transport."""

import copy
import json
from pathlib import Path

import pytest

from scripts.event_spans_v02 import catalog, select_exact, validate_reply
from scripts.event_value_ownership_audit import audit, recognition_view, source_regions

ROOT = Path(__file__).resolve().parents[2]


def proposal(text, operation, duration=None, conditions=None, relation="exact", kind="other"):
    event = {"id": "E1", "kind": kind, "operation": select_exact(text, operation)}
    for field in ("sample", "method", "duration", "conditions", "completion_criterion", "result", "exclusion"):
        phrase = duration if field == "duration" else conditions if field == "conditions" else None
        event[field] = {"status": "present" if phrase is not None else "not_found",
                        "spans": [select_exact(text, phrase)] if phrase is not None else []}
        if field == "duration":
            event[field]["relation"] = relation if phrase is not None else "not_established"
    return {"events": [event], "target": {"status": "present", "event_ids": ["E1"]}, "relations": [], "diagnostic": "Constructed."}


def run(text, operation, duration=None, conditions=None, **kwargs):
    source = catalog(text)
    return audit(source, validate_reply(proposal(text, operation, duration, conditions, **kwargs), source))


def selected(result, field="duration"):
    return next(row for row in result["selections"] if row["field"] == field)


@pytest.mark.parametrize("text,operation,value", [
    ("Sample was cleaned for 2 hours. It was protonated in HCl.", "protonated", "2 hours"),
    ("Мембрану очищали 2 ч. Протонирование проводили в HCl.", "Протонирование", "2 ч"),
    ("Sample was dried for 1 hour. Another sample was dried for 2 hours.", "dried for 2 hours", "1 hour"),
])
def test_different_explicit_source_regions_diagnosed_without_model_kind_or_reference(text, operation, value):
    result = run(text, operation, value)
    row = selected(result)
    assert row["state"] == "different_explicit_operation_regions"
    assert row["operation_region_ids"] != row["value_region_ids"]
    assert not row["owner_established"]
    assert result["scientific_acceptance"] == "not_evaluated"
    assert not result["uses_reference_annotations"]


def test_same_sentence_individual_drying_and_storage_durations_stay_separate():
    text = "Samples were dried for 1 hour and stored for 2 weeks."
    result = run(text, "dried", "2 weeks")
    assert selected(result)["state"] == "different_explicit_operation_regions"
    assert len(result["regions"]) == 2
    assert selected(run(text, "dried", "1 hour"))["state"] == "same_local_region_unverified"
    assert selected(run(text, "stored", "2 weeks"))["state"] == "same_local_region_unverified"


def test_same_number_in_different_regions_does_not_merge_operation_identity():
    text = "Samples were cleaned for 2 hours. Samples were dried for 2 hours."
    result = run(text, "dried", "2 hours")  # First occurrence deliberately selected.
    assert selected(result)["state"] == "different_explicit_operation_regions"


@pytest.mark.parametrize("text", [
    "Samples were dried and stored for 2 hours.",
    "Samples were dried at 60°C and stored for 2 hours.",
    "Samples were dried, stored for 2 hours.",
])
def test_shared_tail_or_undelimited_multiple_operations_never_get_nearest_owner(text):
    row = selected(run(text, "dried", "2 hours"))
    assert row["state"] == "selected_operation_or_scope_unresolved"


@pytest.mark.parametrize("tail", [
    "It was protonated under the same conditions.", "Both samples were protonated.",
    "It was protonated similarly.", "Если образец протонировали, условия уточняли.",
    "It was not protonated.",
])
def test_shared_referential_negated_or_conditional_scope_remains_unresolved(tail):
    text = "Sample was cleaned for 2 hours. " + tail
    operation = "протонировали" if "протонировали" in tail else "protonated"
    row = selected(run(text, operation, "2 hours"))
    assert row["state"] != "different_explicit_operation_regions"
    assert "unresolved" in row["state"]


def test_reference_between_regions_blocks_an_ownership_claim():
    text = "Sample was cleaned for 2 hours. The same conditions applied. Sample was protonated."
    row = selected(run(text, "protonated", "2 hours"))
    assert row["state"] == "cross_region_reference_unresolved"


def test_unknown_operation_or_selected_nonoperation_is_not_silently_accepted():
    text = "Samples underwent frobnication for 2 hours."
    assert selected(run(text, "frobnication", "2 hours"))["state"] == "selected_operation_or_scope_unresolved"
    text = "Samples were dried at 60°C for 2 hours."
    assert selected(run(text, "Samples", "2 hours"))["state"] == "selected_operation_or_scope_unresolved"


def test_broad_operation_span_crossing_steps_is_unresolved():
    text = "Samples were dried for 1 hour. Samples were stored for 2 weeks."
    row = selected(run(text, "dried for 1 hour. Samples were stored", "2 weeks"))
    assert row["state"] == "selected_operation_or_scope_unresolved"


def test_explicit_temporal_sequence_does_not_need_two_duration_values():
    text = "Sample was protonated in HCl, then rinsed for 2 minutes."
    assert selected(run(text, "protonated", "2 minutes"))["state"] == "different_explicit_operation_regions"


def test_russian_following_rinse_boundary_and_hyphenated_operation_are_mapped_exactly():
    text = "Очищали 2 ч. Про-\nтонирование в HCl с последующей про-\nмывкой. Сушили 1 ч и оставляли на 2 недели."
    result = run(text, "Про-\nтонирование", "2 ч")
    assert selected(result)["state"] == "different_explicit_operation_regions"
    raw_anchor = next(a for r in result["regions"] for a in r["operation_anchors"] if a["kind"] == "protonation")
    assert raw_anchor["text"] == "Про-\nтонирование" == text[raw_anchor["start"]:raw_anchor["end"]]


@pytest.mark.parametrize("text", ["Протонирование очищенной мембраны проводили в HCl.",
                                "Cleaned membranes were protonated in HCl."])
def test_cleaned_material_modifier_is_not_a_new_cleaning_operation(text):
    kinds = [a["kind"] for r in source_regions(text) for a in r["operation_anchors"]]
    assert kinds == ["protonation"]


@pytest.mark.parametrize("text,operation,duration", [
    ("Sample was cleaned in 5 wt. % peroxide for 2 hours while mixing.", "cleaned", "2 hours"),
    ("Очистка образца в 5 мас. % растворе длилась 40 минут при перемешивании.", "Очистка", "40 минут"),
])
def test_abbreviation_split_does_not_become_a_false_operation_conflict(text, operation, duration):
    result = run(text, operation, duration)
    assert selected(result)["state"] == "selected_operation_or_scope_unresolved"
    assert any("abbreviation_statement_boundary_unresolved" in r["diagnostics"] for r in result["regions"])


def test_recognition_view_preserves_raw_mapping_and_numeric_range_hyphens():
    text = "вы\xad\nсушивали 40\u00a0минут при 60–80°C"
    view = recognition_view(text)
    assert view.text == "высушивали 40\u00a0минут при 60–80°C"
    assert view.anchor(0, len("высушивали"))["text"] == "вы\xad\nсушивали"
    assert view.raw == text


@pytest.mark.parametrize("phrase,relation,expected", [
    ("2 hours", "at_least", "declared_relation_cue_not_found_in_finite_scope"),
    ("at least 2 hours", "exact", "declared_relation_differs_from_explicit_cue"),
    ("at least 2 hours", "at_least", "no_lexical_relation_conflict_unverified"),
    ("не менее 24 ч", "at_least", "no_lexical_relation_conflict_unverified"),
    ("не более 24 ч", "at_most", "no_lexical_relation_conflict_unverified"),
    ("about 2 hours", "approximate", "no_lexical_relation_conflict_unverified"),
    ("1–2 hours", "exact", "declared_relation_differs_from_explicit_cue"),
    ("1–2 hours", "range", "no_lexical_relation_conflict_unverified"),
    ("more than 2 hours", "at_least", "strict_bound_unmodeled_unresolved"),
    ("2 hours", "unresolved", "declared_unresolved"),
])
def test_duration_bound_reading_keeps_cues_and_uncertainty(phrase, relation, expected):
    result = run("Samples were held for " + phrase + ".", "held", phrase, relation=relation)
    assert selected(result)["duration_relation"]["state"] == expected


def test_bound_outside_model_selection_stays_visible_with_exact_raw_quote():
    text = "Samples were held for at least 2 hours."
    row = selected(run(text, "held", "2 hours", relation="exact"))
    assert row["duration_relation"]["state"] == "declared_relation_differs_from_explicit_cue"
    assert row["duration_relation"]["diagnostics"] == ["explicit_cue_outside_selected_span"]
    cue = row["duration_relation"]["cue"]
    assert cue["text"] == text[cue["start"]:cue["end"]] == "at least "
    assert row["state"] == "same_local_region_unverified"


def test_missing_field_is_not_a_proven_absence_or_accepted_event():
    row = selected(run("Sample was dried until constant mass.", "dried"))
    assert row["state"] == "no_selected_value_not_evaluated" and not row["owner_established"]


def test_input_immutability_and_independence_from_model_kind():
    text = "Sample was cleaned for 2 hours. It was protonated."
    source = catalog(text)
    value = proposal(text, "protonated", "2 hours", kind="protonation")
    restored = validate_reply(value, source)
    before = copy.deepcopy((source, restored))
    result = audit(source, restored)
    assert (source, restored) == before
    value["events"][0]["kind"] = "storage"
    assert audit(source, validate_reply(value, source)) == result


@pytest.mark.parametrize("change", ["catalog", "restored"])
def test_drift_is_rejected_without_repair(change):
    text = "Sample was dried for 2 hours."
    source = catalog(text)
    restored = validate_reply(proposal(text, "dried", "2 hours"), source)
    if change == "catalog":
        source["tokens"][0]["text"] = "Invented"
    else:
        restored["events"][0]["operation"]["text"] = "Invented"
    with pytest.raises(ValueError, match="drift"):
        audit(source, restored)


def test_multiple_duration_atoms_and_unrecognized_criterion_are_unresolved():
    text = "Sample was dried for 1 hour or 2 hours."
    row = selected(run(text, "dried", "1 hour or 2 hours"))
    assert row["duration_relation"]["state"] == "duration_expression_unresolved"
    assert len(row["duration_relation"]["source_atoms"]) == 2
    text = "Sample was dried until constant mass."
    row = selected(run(text, "dried", "until constant mass"))
    assert row["duration_relation"]["state"] == "duration_expression_unresolved"


def test_exposed_live_wrong_stage_selections_flagged_without_reference_labels():
    report = json.loads((ROOT / "output/event_span_live_pilot_20261029_v02/review_v02/report.json").read_bytes())
    case = next(r for r in report["cases"] if r["id"] == "protonation_missing_time")
    result = audit(case["input"]["source"], case["restored"])
    conflicts = [r for r in result["selections"] if r["state"] == "different_explicit_operation_regions"]
    assert {(r["event_id"], r["field"]) for r in conflicts} == {("E1", "duration"), ("E2", "duration"), ("E2", "conditions")}
    assert sum(r["duration_relation"] is not None and r["duration_relation"]["state"] ==
               "declared_relation_cue_not_found_in_finite_scope" for r in result["selections"]) == 2
