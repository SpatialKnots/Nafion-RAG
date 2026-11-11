"""Explicit offline assertions against reconstructed evidence; never answer admission."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

from app.generation.answer_evidence_packet import serialize_packet, validate_packet
from app.records.schema import text_hash
from app.records.sources import file_hash

VERSION = "offline_claim_checks_v0.1"
CODE_FILES = ("app/generation/claim_checks.py",)
MAX_CLAIMS = 64
MAX_INPUT_BYTES = 256000
Text = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
DecimalText = Annotated[str, StringConstraints(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$", max_length=80)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AssertedValue(StrictModel):
    text: Text
    normalization: Literal["nfkc_dehyphenation_whitespace_only"]
    numeric_value: Text | None
    numeric_interpretation: Text | None


class AssertedFact(StrictModel):
    property: Text
    sample: AssertedValue | None
    value: AssertedValue | None
    unit: AssertedValue | None
    operation: Text
    method: AssertedValue | None
    conditions: Annotated[dict[Text, AssertedValue], Field(max_length=32)]
    epistemic_status: Text
    unknown_fields: Annotated[list[Text], Field(max_length=32)]


class QuotationClaim(StrictModel):
    id: Text
    kind: Literal["quotation"]
    anchor_ref: Text
    text: Annotated[str, StringConstraints(min_length=1, max_length=8000)]


class FactClaim(StrictModel):
    id: Text
    kind: Literal["fact"]
    fact_ref: Text
    assertion: AssertedFact


class AssertedSum(StrictModel):
    operands: Annotated[list[DecimalText], Field(min_length=2, max_length=16)]
    result: DecimalText
    unit: Text


class ArithmeticClaim(StrictModel):
    id: Text
    kind: Literal["arithmetic"]
    transformation_ref: Text
    assertion: AssertedSum


Claim = Annotated[QuotationClaim | FactClaim | ArithmeticClaim, Field(discriminator="kind")]
CLAIMS = TypeAdapter(list[Claim])


def _hash(value: dict[str, Any]) -> str:
    return text_hash(serialize_packet(value).decode("utf-8"))


def code_bindings() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    return {name: file_hash(root / name) for name in CODE_FILES}


def fact_assertion(fact: dict[str, Any]) -> dict[str, Any]:
    """Project a source recipe tuple; this helper does not establish its truth."""
    def value(item: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if item is None else {k: deepcopy(v) for k, v in item.items() if k != "source"}

    return {"property": fact["property"], "sample": value(fact["sample"]), "value": value(fact["value"]),
        "unit": value(fact["unit"]), "operation": fact["operation"], "method": value(fact["method"]),
        "conditions": {k: value(v) for k, v in fact["conditions"].items()},
        "epistemic_status": fact["epistemic_status"], "unknown_fields": list(fact["unknown_fields"])}


def _differences(asserted: Any, bound: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(asserted, dict) and isinstance(bound, dict):
        return [d for k in sorted(asserted.keys() | bound.keys())
                for d in _differences(asserted.get(k), bound.get(k), (path + "." if path else "") + k)]
    if asserted == bound:
        return []
    return [{"field": path, "asserted": deepcopy(asserted), "bound": deepcopy(bound)}]


def _get(rows: list[dict[str, Any]], ref: str) -> dict[str, Any]:
    found = [r for r in rows if r["id"] == ref]
    if len(found) != 1:
        raise ValueError("Claim reference is not unique in the current packet: " + ref)
    return found[0]


def _literal_fact(assertion: dict[str, Any], fact: dict[str, Any]) -> dict[str, Any]:
    fields = []
    for key in ("sample", "value", "unit", "method"):
        if assertion[key] is not None:
            fields.append((key, assertion[key], fact[key]))
    for key in sorted(assertion["conditions"]):
        fields.append(("conditions." + key, assertion["conditions"][key], fact["conditions"].get(key)))
    checks = []
    for path, asserted, bound in fields:
        anchor = bound["source"] if bound is not None else None
        checks.append({"field": path, "asserted_text": asserted["text"], "raw_anchor": deepcopy(anchor),
            "status": "exact_match" if anchor and asserted["text"] == anchor["text"] else
                      "not_exact_raw_surface" if anchor else "no_bound_field_anchor",
            "recipe_normalization": bound["normalization"] if bound else None})
    return {"status": "exact_bound_surfaces" if checks and all(c["status"] == "exact_match" for c in checks)
            else "raw_surface_differences" if checks else "no_textual_values_asserted", "fields": checks,
            "scope": "asserted_value_text_at_its_bound_field_only_not_article_wide_search",
            "meaning": "normalization_or_surface_difference_is_not_scientific_contradiction"}


def _fact_check(claim: FactClaim, content: dict[str, Any]) -> dict[str, Any]:
    row = _get(content["facts"], claim.fact_ref)
    requirement = _get(content["requirements"], row["requirement_ref"])
    assertion, bound = claim.assertion.model_dump(), fact_assertion(row["fact"])
    differences = _differences(assertion, bound)
    state = requirement["state"]
    uninspected = bool(content["inspection"]["uninspected"])
    status = ("differs_from_bound_fact" if differences else "ambiguous_source_candidates" if state == "ambiguous_source_candidates"
              else "uninspected_selected_sources" if uninspected else "matches_finite_source_contract")
    return {"literal_presence": _literal_fact(assertion, row["fact"]),
        "semantic_support": {"status": status, "tuple_matches": not differences, "differences": differences,
            "scope": "complete_existing_recipe_tuple_not_general_entailment_or_cross_role_ownership",
            "requirement_ref": requirement["id"], "requirement_state": state, "requirement": deepcopy(requirement),
            "role_identity": deepcopy(next((r for r in content["requirements"] if r["id"] == "role_identity"), None)),
            "uninspected_sources": deepcopy(content["inspection"]["uninspected"]),
            "scientific_ownership_verified": False, "bound_unknown_fields": bound["unknown_fields"]},
        "arithmetic": {"status": "not_requested"}, "fact_refs": [row["id"]], "anchor_refs": [row["support_ref"]]}


def _arithmetic_check(claim: ArithmeticClaim, content: dict[str, Any]) -> dict[str, Any]:
    row = _get(content["transformations"], claim.transformation_ref)
    bound = row["arithmetic"]
    if (bound.get("operation") != "sum" or bound.get("origin") != "system_arithmetic"
            or bound.get("unit_conversion") is not False):
        raise ValueError("Only unchanged-unit source recipe sums are supported")
    # Fraction parses decimal strings exactly, independently of the Decimal context.
    operands, result = claim.assertion.operands, claim.assertion.result
    total = sum((Fraction(v) for v in operands), Fraction(0))
    bound_total = sum((Fraction(v) for v in bound["operands"]), Fraction(0))
    if bound_total != Fraction(bound["result"]):
        raise ValueError("Reconstructed source recipe sum is inconsistent")
    bindings_match = operands == bound["operands"] and claim.assertion.unit == bound["unit"]
    correct = total == Fraction(result)
    result_matches = Fraction(result) == Fraction(bound["result"])
    return {"literal_presence": {"status": "not_applicable_system_arithmetic"},
        "semantic_support": {"status": "not_evaluated", "scope": "arithmetic_does_not_establish_scientific_support"},
        "arithmetic": {"status": "matches_bound_sum" if bindings_match and correct and result_matches else "sum_or_binding_mismatch",
            "origin": "system_arithmetic", "operation": "sum", "operands_and_unit_match": bindings_match,
            "asserted_sum_correct": correct, "result_matches_bound_numeric_value": result_matches,
            "exact_fraction": str(total), "asserted": claim.assertion.model_dump(), "bound": deepcopy(bound),
            "comparison": "exact_ordered_operand_spelling_and_unit_exact_rational_result", "unit_conversion": False},
        "fact_refs": deepcopy(row["input_fact_refs"]), "anchor_refs": sorted({_get(content["facts"], f)["support_ref"]
             for f in row["input_fact_refs"]})}


def _check(claim: QuotationClaim | FactClaim | ArithmeticClaim, content: dict[str, Any]) -> dict[str, Any]:
    if isinstance(claim, FactClaim):
        result = _fact_check(claim, content)
    elif isinstance(claim, ArithmeticClaim):
        result = _arithmetic_check(claim, content)
    else:
        anchor = _get(content["anchors"], claim.anchor_ref)
        result = {"literal_presence": {"status": "exact_match" if claim.text == anchor["anchor"]["text"] else "mismatch_at_bound_anchor",
                     "asserted_text": claim.text, "bound_text": anchor["anchor"]["text"],
                     "scope": "complete_bound_raw_anchor_only_no_normalization_or_article_wide_absence_claim"},
            "semantic_support": {"status": "not_evaluated", "scope": "literal_copy_is_not_semantic_support"},
            "arithmetic": {"status": "not_requested"}, "fact_refs": [], "anchor_refs": [anchor["id"]]}
    anchors = [_get(content["anchors"], ref) for ref in result["anchor_refs"]]
    source_refs = sorted({a["source_ref"] for a in anchors})
    return {"claim_id": claim.id, "kind": claim.kind, **result, "scientific_validity": {"status": "not_evaluated"},
        "sources": [deepcopy(_get(content["sources"], s)) for s in source_refs], "anchors": deepcopy(anchors),
        "admission_changed": False, "meaning": "diagnostic_comparison_not_scientific_acceptance"}


def build_checks(packet: dict[str, Any], current_parent: dict[str, Any], claims: list[dict[str, Any]], *,
                 expected_packet_id: str) -> dict[str, Any]:
    validate_packet(packet, current_parent, expected_packet_id=expected_packet_id)
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("Claim input must be a list of at most 64 explicit assertions")
    if len(serialize_packet({"claims": claims})) > MAX_INPUT_BYTES:
        raise ValueError("Claim input exceeds canonical byte budget")
    parsed = CLAIMS.validate_python(claims)
    if len({c.id for c in parsed}) != len(parsed):
        raise ValueError("Claim IDs must be unique")
    bindings = code_bindings()
    content = packet["content"]
    results = [_check(c, content) for c in parsed]
    base_stop = content["stop"]
    stop = {"reason": "explicit_claim_checks_complete" if parsed else "no_claims", "claims_checked": len(parsed),
        "model_calls_executed": 0, "new_source_actions_executed": 0, "generation_performed": False,
        "admission_changed": False, "scientific_validity": "not_evaluated", "baseline": deepcopy(base_stop)}
    events: list[dict[str, Any]] = []
    for kind, input_hash, output, reason in [
        ("claim_checked", _hash(c.model_dump()), r, "explicit_assertion_compared") for c, r in zip(parsed, results, strict=True)
    ] + [("claim_checks_stopped", expected_packet_id, stop, stop["reason"])]:
        event = {"sequence": len(events) + 1, "kind": kind, "actor_kind": "deterministic_system",
            "previous_hash": events[-1]["event_hash"] if events else packet["journal"]["root_hash"],
            "input_hash": input_hash, "output_hash": _hash(output), "reason": reason,
            "scientific_validity": "not_evaluated"}
        events.append({**event, "event_hash": _hash(event)})
    core = {"version": VERSION, "packet_id": expected_packet_id, "parent_hash": content["parent_hash"],
        "claim_origin": "caller_supplied_diagnostic_assertions_not_generated_answer_or_human_review",
        "code_bindings": bindings, "code_scope": "checker_only_plus_validated_packet_declared_dependencies",
        "claims": deepcopy(claims), "results": results, "stop": stop,
        "journal": {"parent_root_hash": packet["journal"]["root_hash"], "events": events,
                    "root_hash": events[-1]["event_hash"], "human_reviews": []},
        "scientific_validity": "not_evaluated", "generation_performed": False, "network_ready": False}
    if bindings != code_bindings():
        raise ValueError("Claim checker code changed during construction")
    return {**core, "report_id": _hash(core)}


def validate_checks(report: dict[str, Any], packet: dict[str, Any], current_parent: dict[str, Any],
                    claims: list[dict[str, Any]], *, expected_packet_id: str, expected_report_id: str) -> None:
    if report.get("report_id") != expected_report_id:
        raise ValueError("Claim check report differs from pinned identity")
    if serialize_packet(report) != serialize_packet(build_checks(packet, current_parent, claims, expected_packet_id=expected_packet_id)):
        raise ValueError("Claim checks differ from trusted input/code/journal reconstruction")


def save_checks(path: Path, report: dict[str, Any], packet: dict[str, Any], current_parent: dict[str, Any],
                claims: list[dict[str, Any]], *, expected_packet_id: str, expected_report_id: str) -> None:
    validate_checks(report, packet, current_parent, claims, expected_packet_id=expected_packet_id, expected_report_id=expected_report_id)
    with path.open("xb") as stream:
        stream.write(serialize_packet(report))
        stream.flush()
        os.fsync(stream.fileno())


def load_checks(path: Path, packet: dict[str, Any], current_parent: dict[str, Any], claims: list[dict[str, Any]], *,
                expected_packet_id: str, expected_report_id: str) -> dict[str, Any]:
    raw = path.read_bytes()
    report = json.loads(raw)
    if not isinstance(report, dict) or serialize_packet(report) != raw:
        raise ValueError("Claim check export is not canonical UTF-8 JSON")
    validate_checks(report, packet, current_parent, claims, expected_packet_id=expected_packet_id, expected_report_id=expected_report_id)
    return report
