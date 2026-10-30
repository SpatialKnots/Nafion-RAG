"""Offline comparison with explicit, preliminary operation-duration annotations.

This evaluator consumes annotations; it does not extract semantic relations.
Inspection of rejected raw selections never promotes them to accepted events.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Literal

from app.generation.gigachat import _json
from scripts.gigachat_event_proposal import EventReply, StrictModel, catalog, parse_proposal

VERSION = "event_duration_evaluation_v0.1"


class Anchor(StrictModel):
    start: int
    end: int
    text: str


class OperationReference(StrictModel):
    id: str
    anchor: Anchor
    duration_state: Literal["present", "not_in_excerpt", "unresolved"]


class DurationOwner(StrictModel):
    atom_id: str
    operation_id: str


class Reference(StrictModel):
    exact_text_sha256: str
    target_operation_id: str
    operations: list[OperationReference]
    duration_owners: list[DurationOwner]
    unannotated_atom_ids: list[str]


def validate_reference(source: dict[str, Any], value: dict[str, Any]) -> Reference:
    """Reject drift or contradictory labels, without silently repairing either."""
    if source != catalog(source["exact_text"]):
        raise ValueError("Source catalog drift")
    ref = Reference.model_validate(value)
    text = source["exact_text"]
    if hashlib.sha256(text.encode()).hexdigest() != ref.exact_text_sha256:
        raise ValueError("Reference text hash differs")
    operations = {op.id: op for op in ref.operations}
    if len(operations) != len(ref.operations) or not all(operations) or ref.target_operation_id not in operations:
        raise ValueError("Duplicate, empty or missing reference operation")
    for op in ref.operations:
        a = op.anchor
        if not 0 <= a.start < a.end <= len(text) or text[a.start:a.end] != a.text:
            raise ValueError("Reference operation anchor differs from exact input")
    atoms = {a["id"] for a in source["duration_atoms"]}
    assigned = [row.atom_id for row in ref.duration_owners]
    inventory = assigned + ref.unannotated_atom_ids
    if len(inventory) != len(set(inventory)) or set(inventory) != atoms:
        raise ValueError("Duration annotations must partition the exact atom inventory")
    if any(row.operation_id not in operations for row in ref.duration_owners):
        raise ValueError("Unknown duration owner")
    counts = Counter(row.operation_id for row in ref.duration_owners)
    for op in ref.operations:
        if (op.duration_state == "present") != bool(counts[op.id]):
            raise ValueError("Duration state contradicts annotated owners")
    return ref


def evaluate(raw: bytes, source: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """Compare raw duration selections only; preserve the original parser verdict.

    Distinct annotated owners in one atomic event are reported even when both
    values occur in a single statement. Unknown/unannotated atoms are not negatives.
    Invalid native envelopes/content raise rather than yield semantic results.
    """
    ref = validate_reference(source, reference)
    native = _json(raw)
    if not isinstance(native, dict) or not isinstance(native.get("choices"), list) or len(native["choices"]) != 1:
        raise ValueError("Expected one native choice for raw inspection")
    choice = native["choices"][0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
        raise ValueError("Filtered or incomplete reply cannot be duration-scored")
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant" or not isinstance(message.get("content"), str) or any(
            message.get(key) for key in ("refusal", "function_call", "tool_calls")):
        raise ValueError("Expected plain assistant content for raw inspection")
    reply = EventReply.model_validate(_json(message["content"]))
    try:
        parse_proposal(raw, source)
    except ValueError as exc:
        original = {"accepted": False, "error_type": type(exc).__name__, "error": str(exc)}
    else:
        original = {"accepted": True, "error_type": None, "error": None}
    statements = {s["id"]: s for s in source["statements"]}
    atoms = {a["id"]: a for a in source["duration_atoms"]}
    owners = {row.atom_id: row.operation_id for row in ref.duration_owners}
    target_ref = next(op for op in ref.operations if op.id == ref.target_operation_id)
    expected = {a for a, owner in owners.items() if owner == target_ref.id}
    rows = []
    occurrences: dict[str, list[str]] = {}
    for index, event in enumerate([reply.target, *reply.other_events]):
        path = "target" if index == 0 else f"other_events[{index - 1}]"
        issues = []
        context = event.context_ids
        if not context or len(context) != len(set(context)) or any(s not in statements for s in context):
            issues.append("invalid_context_ids")
        elif context != sorted(context, key=lambda s: statements[s]["start"]):
            issues.append("context_ids_out_of_source_order")
        for field in ("sample", "operation", "duration", "conditions", "completion_criterion"):
            selection = getattr(event, field)
            registry = atoms if field == "duration" else statements
            if (selection.status == "present") != bool(selection.ids):
                issues.append(field + ":status_id_contradiction")
            if len(selection.ids) != len(set(selection.ids)) or any(s not in registry for s in selection.ids):
                issues.append(field + ":invalid_ids")
                continue
            if selection.ids != sorted(selection.ids, key=lambda s: registry[s]["start"]):
                issues.append(field + ":ids_out_of_source_order")
            if any((registry[s]["statement_id"] if field == "duration" else s) not in context for s in selection.ids):
                issues.append(field + ":outside_context")
        duration_valid = not any(i.startswith(("duration:", "invalid_context", "context_ids_")) for i in issues)
        selected = event.duration.ids
        owner_ids = sorted({owners[a] for a in selected if a in owners}) if duration_valid else []
        comparison: dict[str, Any] = {"state": "not_target"}
        if index == 0:
            if not duration_valid:
                comparison = {"state": "invalid_raw_duration_selection_not_scored"}
            else:
                wrong = [a for a in selected if a in owners and owners[a] != target_ref.id]
                missing = sorted(expected - set(selected))
                unknown = [a for a in selected if a not in owners]
                if wrong:
                    state = "other_operation_duration_selected"
                elif target_ref.duration_state == "unresolved" or unknown:
                    state = "unresolved_not_scored"
                elif missing or (expected and event.duration.status != "present"):
                    state = "annotated_target_duration_missing"
                elif target_ref.duration_state == "not_in_excerpt" and event.duration.status != "not_found":
                    state = "missing_duration_status_disagrees"
                else:
                    state = "raw_duration_field_agrees_with_preliminary_reference"
                comparison = {"state": state, "expected_atom_ids": sorted(expected), "missing_atom_ids": missing,
                              "other_operation_atom_ids": wrong, "unannotated_atom_ids": unknown}
        if duration_valid:
            for atom in selected:
                occurrences.setdefault(atom, []).append(path)
        rows.append({"path": path, "kind": event.kind, "formal_issues": issues,
                     "raw_duration_status": event.duration.status, "raw_duration_ids": selected,
                     "duration_selection_inspectable": duration_valid, "annotated_owner_ids": owner_ids,
                     "multiple_annotated_operations_in_one_event": len(owner_ids) > 1,
                     "unannotated_selected_atom_ids": [a for a in selected if a not in owners] if duration_valid else [],
                     "target_comparison": comparison})
    return {"version": VERSION, "original_parser": original, "events": rows,
            "repeated_duration_selections": {a: paths for a, paths in occurrences.items() if len(paths) > 1},
            "scope": "raw_duration_fields_against_explicit_preliminary_annotation",
            "annotation_is_semantic_extractor": False, "scientific_acceptance": "not_evaluated",
            "runtime_action": "none_offline_only"}
