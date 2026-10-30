"""Constructed schema/source integrity controls; no model transport."""

import copy
import json

import pytest

from scripts.gigachat_event_proposal import build_request, catalog, parse_proposal

TEXT = "Sample A was held for 2 часа. Spectra were unchanged."


def proposal():
    missing = {"status": "not_found", "ids": []}
    return {"target": {"kind": "measurement_wait", "context_ids": ["S1"],
                       "sample": {"status": "present", "ids": ["S1"]},
                       "operation": {"status": "present", "ids": ["S1"]},
                       "duration": {"status": "present", "ids": ["D1"]},
                       "conditions": missing, "completion_criterion": missing}, "other_events": [], "diagnostic": "Constructed."}


def native(value, finish="stop"):
    return json.dumps({"choices": [{"finish_reason": finish, "message": {
        "role": "assistant", "content": json.dumps(value, ensure_ascii=False)}}]}, ensure_ascii=False).encode()


def test_raw_source_atoms_and_restored_values_keep_units_offsets_and_line_breaks():
    source = catalog(TEXT)
    atom, = source["duration_atoms"]
    assert atom["value_text"] == "2" and atom["unit_text"] == "часа"
    assert TEXT[atom["start"]:atom["end"]] == atom["text"] == "2 часа"
    result = parse_proposal(native(proposal()), source)
    assert result["target"]["fields"]["duration"]["exact_source_selections"] == [atom]
    assert result["scientific_acceptance"] == "not_evaluated"


def test_criterion_has_no_duration_atom_and_schema_is_request_local():
    source = catalog("Неиз-\nменность спектров служила критерием.")
    a = build_request("Каков критерий?", source, model="GigaChat-2-Max", max_tokens=1200)
    b = build_request("How long?", catalog(TEXT), model="GigaChat-2-Max", max_tokens=1200)
    assert a["response_format"]["schema"]["$defs"]["DurationSelection"]["properties"]["ids"]["maxItems"] == 0
    assert b["response_format"]["schema"]["$defs"]["DurationSelection"]["properties"]["ids"]["items"]["enum"] == ["D1"]
    assert source["statements"][0]["text"] == source["exact_text"]


@pytest.mark.parametrize("change", ["unknown_id", "duplicate_id", "nonpresent_ids", "present_no_ids", "wrong_context", "extra_field"])
def test_invalid_selections_are_rejected_without_repair(change):
    value = proposal()
    if change == "unknown_id":
        value["target"]["duration"]["ids"] = ["D99"]
    elif change == "duplicate_id":
        value["target"]["context_ids"] = ["S1", "S1"]
    elif change == "nonpresent_ids":
        value["target"]["duration"]["status"] = "uncertain"
    elif change == "present_no_ids":
        value["target"]["duration"]["ids"] = []
    elif change == "wrong_context":
        value["target"]["context_ids"] = ["S2"]
    else:
        value["target"]["invented"] = "repair"
    with pytest.raises(ValueError):
        parse_proposal(native(value), catalog(TEXT))


@pytest.mark.parametrize("finish", ["length", "blacklist", None])
def test_incomplete_and_filtered_native_outputs_are_not_scientific_abstentions(finish):
    with pytest.raises(ValueError, match="incomplete or filtered"):
        parse_proposal(native(proposal(), finish), catalog(TEXT))


def test_duplicate_json_key_and_catalog_drift_fail():
    with pytest.raises(ValueError):
        parse_proposal(b'{"choices":[],"choices":[]}', catalog(TEXT))
    source = catalog(TEXT)
    source["duration_atoms"][0]["unit_text"] = "days"
    with pytest.raises(ValueError, match="drift"):
        parse_proposal(native(proposal()), source)


def test_formal_integrity_cannot_validate_wrong_event_assignment():
    source = catalog("Sample A was dried for 2 hours.")
    value = proposal()  # Wrong scientific kind deliberately remains an unverified proposal.
    saved = copy.deepcopy(value)
    result = parse_proposal(native(value), source)
    assert value == saved and result["target"]["kind"] == "measurement_wait"
    assert result["target"]["scientific_event_assignment"] == "unverified_model_proposal"
