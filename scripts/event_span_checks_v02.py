"""Sparse exact-anchor development checks, not semantic extraction or accuracy."""

from __future__ import annotations

from typing import Any, Literal

from scripts.event_spans_v02 import validate_catalog
from scripts.gigachat_event_proposal import StrictModel

VERSION = "event_span_checks_v0.2_offline"


class Anchor(StrictModel):
    start: int
    end: int
    text: str


class Operation(StrictModel):
    id: str
    anchor: Anchor


class Check(StrictModel):
    id: str
    mode: Literal["require", "forbid"]
    operation_id: str
    field: Literal["sample", "method", "duration", "conditions", "completion_criterion", "result", "exclusion"]
    status: Literal["present", "not_found", "uncertain"]
    value: Anchor | None
    duration_relation: Literal["exact", "range", "at_least", "at_most", "approximate", "unresolved", "not_established"] | None


class Reference(StrictModel):
    operations: list[Operation]
    checks: list[Check]


def compare(source: dict[str, Any], reference: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    validate_catalog(source)
    ref = Reference.model_validate(reference)
    operations = {op.id: op.anchor for op in ref.operations}
    if len(operations) != len(ref.operations) or not all(operations):
        raise ValueError("Invalid reference operation IDs")
    if len({c.id for c in ref.checks}) != len(ref.checks) or any(not c.id for c in ref.checks):
        raise ValueError("Duplicate or empty reference check IDs")
    for anchor in [*operations.values(), *(c.value for c in ref.checks if c.value is not None)]:
        if not 0 <= anchor.start < anchor.end <= len(source["exact_text"]) or (
                source["exact_text"][anchor.start:anchor.end] != anchor.text):
            raise ValueError("Reference anchor differs from exact text")
    # Revalidate the original selection rather than trusting caller-supplied restored spans.
    from scripts.event_spans_v02 import validate_reply
    if validate_reply(restored["raw_selection"], source) != restored:
        raise ValueError("Restored proposal drift")
    aligned = {op_id: [event for event in restored["events"] if event["operation"]["start"] <= a.start
                       and a.end <= event["operation"]["end"]] for op_id, a in operations.items()}
    compound = {event["id"]: [op_id for op_id, events in aligned.items() if event in events] for event in restored["events"]}
    rows = []
    for check in ref.checks:
        if check.operation_id not in operations:
            raise ValueError("Unknown reference operation")
        if (check.status == "present") != (check.value is not None) or (check.mode == "forbid" and check.status != "present"):
            raise ValueError("Reference check status/value contradiction")
        if check.duration_relation is not None and check.field != "duration":
            raise ValueError("Duration relation supplied for another field")
        if check.duration_relation is not None and ((check.status == "present") == (check.duration_relation == "not_established")):
            raise ValueError("Reference duration status/relation contradiction")
        candidates = aligned[check.operation_id]
        matched = False
        if len(candidates) != 1:
            state = "operation_unaligned_or_ambiguous_not_scored"
        elif len(compound[candidates[0]["id"]]) > 1:
            state = "compound_operation_by_reference_not_scored"
        else:
            selection = candidates[0]["fields"][check.field]
            matched = selection["status"] == check.status
            if check.value is not None:
                matched = matched and any(s["start"] <= check.value.start and check.value.end <= s["end"] for s in selection["spans"])
            if check.duration_relation is not None:
                matched = matched and selection.get("relation") == check.duration_relation
            state = ("required_binding_matched" if matched else "required_binding_missed") if check.mode == "require" else (
                "forbidden_binding_proposed" if matched else "forbidden_binding_not_proposed_in_aligned_event")
        rows.append({"check_id": check.id, "mode": check.mode, "state": state,
                     "aligned_event_ids": [event["id"] for event in candidates]})
    return {"version": VERSION, "checks": rows, "compound_operation_event_ids": [eid for eid, ops in compound.items() if len(ops) > 1],
            "unannotated_operations": [eid for eid, ops in compound.items() if not ops],
            "scientific_acceptance": "not_evaluated", "independent_accuracy": None}
