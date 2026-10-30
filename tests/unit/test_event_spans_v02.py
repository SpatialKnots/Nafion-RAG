"""Contract and exact-source controls; constructed fixtures are not LLM results."""

import copy
import json
from pathlib import Path

import pytest

from scripts.event_span_checks_v02 import compare
from scripts.event_spans_v02 import Span, build_request, catalog, parse_proposal, restore, select_exact, validate_reply

ROOT = Path(__file__).resolve().parents[2]
TEXT = "Sample A was dried at 60°C for at least 1 hour and stored for 2 weeks."


def proposal():
    events = []
    for eid, operation, duration in (("E1", "dried", "at least 1 hour"), ("E2", "stored", "2 weeks")):
        missing = {"status": "not_found", "spans": []}
        events.append({"id": eid, "kind": "drying" if eid == "E1" else "storage", "operation": select_exact(TEXT, operation),
                       "duration": {"status": "present", "spans": [select_exact(TEXT, duration)],
                                    "relation": "at_least" if eid == "E1" else "exact"},
                       **{key: copy.deepcopy(missing) for key in (
                           "sample", "method", "conditions", "completion_criterion", "result", "exclusion")}})
    return {"events": events, "target": {"status": "present", "event_ids": ["E1"]}, "relations": [], "diagnostic": "Constructed."}


def native(value, finish="stop"):
    return json.dumps({"choices": [{"finish_reason": finish, "message": {"role": "assistant",
                       "content": json.dumps(value, ensure_ascii=False)}}]}, ensure_ascii=False).encode()


def test_distinct_operations_and_bounds_inside_one_sentence_restore_exactly():
    result = parse_proposal(native(proposal()), catalog(TEXT))
    a, b = result["events"]
    assert a["operation"]["text"] == "dried" and b["operation"]["text"] == "stored"
    assert a["fields"]["duration"]["spans"][0]["text"] == "at least 1 hour"
    assert a["fields"]["duration"]["relation"] == "at_least"
    assert b["fields"]["duration"]["spans"][0]["text"] == "2 weeks"
    assert result["scientific_acceptance"] == "not_evaluated"


def test_raw_hyphenation_soft_hyphen_nbsp_unicode_and_offsets_preserved():
    text = "Суши\xad\nли 40\u00a0минут при 60оС; неиз-\nменность спектров."
    source = catalog(text)
    for fragment in ("Суши\xad\nли", "40\u00a0минут", "60оС", "неиз-\nменность"):
        value = restore(Span.model_validate(select_exact(text, fragment)), source)
        assert text[value["start"]:value["end"]] == fragment == value["text"]


@pytest.mark.parametrize("diagnostic", ["", " ", "\n\t", None, 12])
def test_nonblank_diagnostic_is_part_of_local_schema(diagnostic):
    value = proposal()
    value["diagnostic"] = diagnostic
    with pytest.raises(ValueError):
        validate_reply(value, catalog(TEXT))


@pytest.mark.parametrize("field", ["sample", "method", "duration", "conditions", "completion_criterion", "result", "exclusion"])
@pytest.mark.parametrize("change", ["present_empty", "missing_nonempty", "uncertain_nonempty"])
def test_status_and_spans_cannot_contradict_for_any_field(field, change):
    value = proposal()
    selected = {"status": "present" if change == "present_empty" else "not_found" if change == "missing_nonempty" else "uncertain",
                "spans": [] if change == "present_empty" else [select_exact(TEXT, "dried")]}
    if field == "duration":
        selected["relation"] = "exact" if change == "present_empty" else "not_established"
    value["events"][0][field] = selected
    with pytest.raises(ValueError):
        validate_reply(value, catalog(TEXT))


@pytest.mark.parametrize("change", ["unknown_target", "duplicate_target", "duplicate_event", "reverse_span", "outside_span",
                                    "float_span", "bool_span", "duplicate_field_span", "overlap", "unordered",
                                    "missing_relation", "present_not_established", "empty_target_present", "missing_target_ids", "extra"])
def test_source_and_structural_integrity_fail_without_repairs(change):
    value = proposal()
    first = value["events"][0]
    if change == "unknown_target":
        value["target"]["event_ids"] = ["E99"]
    elif change == "duplicate_target":
        value["target"]["event_ids"] = ["E1", "E1"]
    elif change == "duplicate_event":
        value["events"][1]["id"] = "E1"
    elif change == "reverse_span":
        first["operation"] = {"first": 8, "last": 1}
    elif change == "outside_span":
        first["operation"]["last"] = 999
    elif change == "float_span":
        first["operation"]["first"] = 1.0
    elif change == "bool_span":
        first["operation"]["first"] = True
    elif change == "duplicate_field_span":
        first["duration"]["spans"] *= 2
    elif change == "overlap":
        first["duration"]["spans"].append(select_exact(TEXT, "1 hour"))
    elif change == "unordered":
        first["duration"]["spans"] = [select_exact(TEXT, "2 weeks"), select_exact(TEXT, "1 hour")]
    elif change == "missing_relation":
        del first["duration"]["relation"]
    elif change == "present_not_established":
        first["duration"]["relation"] = "not_established"
    elif change == "empty_target_present":
        value["target"]["event_ids"] = []
    elif change == "missing_target_ids":
        value["target"]["status"] = "not_found"
    else:
        first["invented"] = "repair"
    saved = copy.deepcopy(value)
    with pytest.raises(ValueError):
        validate_reply(value, catalog(TEXT))
    assert value == saved


@pytest.mark.parametrize("change", ["unknown", "self", "duplicate", "reversed_evidence"])
def test_invalid_relations_rejected(change):
    value = proposal()
    rel = {"from_event": "E1", "to_event": "E2", "kind": "precedes", "status": "proposed",
           "evidence": [select_exact(TEXT, "and")]}
    value["relations"] = [rel]
    if change == "unknown":
        rel["to_event"] = "E99"
    elif change == "self":
        rel["to_event"] = "E1"
    elif change == "duplicate":
        value["relations"].append(copy.deepcopy(rel))
    else:
        rel["evidence"] = [select_exact(TEXT, "stored"), select_exact(TEXT, "dried")]
    with pytest.raises(ValueError):
        validate_reply(value, catalog(TEXT))


def test_duration_reuse_is_diagnostic_without_invented_scientific_rejection():
    value = proposal()
    value["events"][1]["duration"] = copy.deepcopy(value["events"][0]["duration"])
    result = validate_reply(value, catalog(TEXT))
    assert result["warnings"][0]["event_ids"] == ["E1", "E2"]
    assert result["atomicity"] == "not_semantically_validated"


@pytest.mark.parametrize("finish", ["blacklist", "length", None])
def test_filtered_or_truncated_native_outputs_never_become_abstentions(finish):
    with pytest.raises(ValueError, match="incomplete or filtered"):
        parse_proposal(native(proposal(), finish), catalog(TEXT))


@pytest.mark.parametrize("raw", [b'{"choices":[],"choices":[]}', b'{', b'{"choices":[]}'])
def test_malformed_native_json_is_not_repaired(raw):
    with pytest.raises(ValueError):
        parse_proposal(raw, catalog(TEXT))


def test_catalog_drift_and_partial_token_annotations_fail():
    source = catalog(TEXT)
    source["tokens"][0]["text"] = "Invented"
    with pytest.raises(ValueError, match="drift"):
        validate_reply(proposal(), source)
    with pytest.raises(ValueError, match="boundaries"):
        select_exact(TEXT, "ampl")


def test_requests_only_contain_question_and_neutral_catalog_and_do_not_mutate_source():
    source = catalog(TEXT)
    frozen = copy.deepcopy(source)
    request = build_request("How long?", source, model="GigaChat-2-Max", max_tokens=1200)
    assert source == frozen
    assert json.loads(request["messages"][1]["content"]) == {"question": "How long?", "source": source}
    prop = request["response_format"]["schema"]["$defs"]["Span"]["properties"]
    assert prop["first"]["maximum"] == len(source["tokens"]) - 1
    assert request["response_format"]["schema"]["properties"]["diagnostic"]["pattern"] == r"\S"
    other = build_request("Why?", catalog("One."), model="GigaChat-2-Max", max_tokens=1200)
    assert other["response_format"]["schema"]["$defs"]["Span"]["properties"]["first"]["maximum"] == 1
    assert prop["first"]["maximum"] == len(source["tokens"]) - 1


DATA = json.loads((ROOT / "docs/records/event_span_fixtures_v0.2.json").read_bytes())
CASES = {c["id"]: c for c in json.loads((ROOT / "docs/records/real_experiment_cases_v0.1.json").read_bytes())["cases"]}


@pytest.mark.parametrize("fixture", DATA["cases"], ids=lambda r: r["case_id"])
def test_twelve_constructed_real_source_controls(fixture):
    source = catalog(CASES[fixture["case_id"]]["exact_text"])
    frozen = copy.deepcopy(fixture)
    restored = parse_proposal(native(fixture["contract_fixture"]), source)
    result = compare(source, fixture["reference"], restored)
    assert fixture == frozen
    assert not result["compound_operation_event_ids"]
    assert all(c["state"] in {"required_binding_matched", "forbidden_binding_not_proposed_in_aligned_event"} for c in result["checks"])
    assert result["independent_accuracy"] is None


def test_wrong_stage_span_stays_formally_valid_but_annotated_boundary_fails():
    fixture = next(r for r in DATA["cases"] if r["case_id"] == "protonation_missing_time")
    value = copy.deepcopy(fixture["contract_fixture"])
    drying = next(e for e in value["events"] if e["kind"] == "drying")
    storage = next(e for e in value["events"] if e["kind"] == "storage")
    drying["duration"]["spans"] += storage["duration"]["spans"]
    source = catalog(CASES[fixture["case_id"]]["exact_text"])
    restored = validate_reply(value, source)
    result = compare(source, fixture["reference"], restored)
    assert any(c["state"] == "forbidden_binding_proposed" for c in result["checks"])
    assert restored["scientific_acceptance"] == "not_evaluated"


def test_compound_operation_or_unknown_operation_is_not_a_pass():
    fixture = next(r for r in DATA["cases"] if r["case_id"] == "protonation_missing_time")
    value = copy.deepcopy(fixture["contract_fixture"])
    source = catalog(CASES[fixture["case_id"]]["exact_text"])
    value["events"] = value["events"][:1]
    value["target"]["event_ids"] = ["E1"]
    value["events"][0]["operation"] = {"first": 0, "last": len(source["tokens"]) - 1}
    result = compare(source, fixture["reference"], validate_reply(value, source))
    assert result["compound_operation_event_ids"] == ["E1"]
    assert all(c["state"] == "compound_operation_by_reference_not_scored" for c in result["checks"])
    value["events"][0]["operation"] = select_exact(source["exact_text"], "P2O5")
    result = compare(source, fixture["reference"], validate_reply(value, source))
    assert result["unannotated_operations"] == ["E1"]
    assert all(c["state"] == "operation_unaligned_or_ambiguous_not_scored" for c in result["checks"])


def test_reference_or_restored_drift_fails_loudly():
    fixture = DATA["cases"][0]
    source = catalog(CASES[fixture["case_id"]]["exact_text"])
    restored = validate_reply(fixture["contract_fixture"], source)
    bad = copy.deepcopy(fixture["reference"])
    bad["operations"][0]["anchor"]["text"] = "invented"
    with pytest.raises(ValueError, match="anchor"):
        compare(source, bad, restored)
    restored["events"][0]["operation"]["text"] = "invented"
    with pytest.raises(ValueError, match="drift"):
        compare(source, fixture["reference"], restored)
