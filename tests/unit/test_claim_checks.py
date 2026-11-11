"""Adverse assertions must not turn a matching number or quote into scientific support."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.generation.answer_evidence_packet import build_packet, serialize_packet
from app.generation.answer_requirements import build_requirements
from app.generation.claim_checks import build_checks, fact_assertion, load_checks, save_checks, validate_checks

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "output/answer_requirements_20261109/controls_v01.json").read_bytes())


def inputs(case_id="complete"):
    p = copy.deepcopy(next(c["parent"] for c in CASES if c["id"] == case_id))
    parent = {"version": "answer_requirements_preparation_v0.1", "preparation": p, "requirements": build_requirements(p),
              "generation_performed": False, "external_request_constructed": False, "network_ready": False}
    packet = build_packet(parent)
    return parent, packet


def fact_claim(packet, property="capacity_retention"):
    fact = next(f for f in packet["content"]["facts"] if f["fact"]["property"] == property)
    return {"id": "fact", "kind": "fact", "fact_ref": fact["id"], "assertion": fact_assertion(fact["fact"])}


def sum_claim(packet):
    row = packet["content"]["transformations"][0]
    return {"id": "sum", "kind": "arithmetic", "transformation_ref": row["id"],
            "assertion": {k: copy.deepcopy(row["arithmetic"][k]) for k in ("operands", "result", "unit")}}


def quote_claim(packet):
    anchor = packet["content"]["anchors"][0]
    return {"id": "quote", "kind": "quotation", "anchor_ref": anchor["id"], "text": anchor["anchor"]["text"]}


def check(packet, parent, claims):
    return build_checks(packet, parent, claims, expected_packet_id=packet["packet_id"])


def test_exact_quote_and_fact_keep_three_distinct_levels_and_unchanged_blockers():
    parent, packet = inputs()
    before = serialize_packet(packet)
    report = check(packet, parent, [quote_claim(packet), fact_claim(packet), sum_claim(packet)])
    quote, fact, arithmetic = report["results"]
    assert quote["literal_presence"]["status"] == "exact_match"
    assert quote["semantic_support"]["status"] == "not_evaluated"
    assert fact["semantic_support"]["status"] == "matches_finite_source_contract"
    assert fact["semantic_support"]["scientific_ownership_verified"] is False
    assert arithmetic["literal_presence"]["status"] == "not_applicable_system_arithmetic"
    assert arithmetic["semantic_support"]["status"] == "not_evaluated"
    assert arithmetic["arithmetic"]["status"] == "matches_bound_sum"
    assert all(r["scientific_validity"] == {"status": "not_evaluated"} for r in report["results"])
    assert report["stop"]["baseline"] == packet["content"]["stop"]
    assert report["stop"]["admission_changed"] is False
    assert serialize_packet(packet) == before


@pytest.mark.parametrize("field", ["sample", "unit", "operation", "property", "current", "cycles", "status", "numeric"])
def test_same_number_with_wrong_cell_unit_conditions_or_status_is_not_supported(field):
    parent, packet = inputs()
    claim = fact_claim(packet)
    assertion = claim["assertion"]
    original_number = assertion["value"]["text"]
    if field in {"sample", "unit"}:
        assertion[field]["text"] = "other"
    elif field in {"operation", "property"}:
        assertion[field] = "other"
    elif field in {"current", "cycles"}:
        assertion["conditions"][field]["text"] = "999"
    elif field == "status":
        assertion["epistemic_status"] = "source_reported"
    else:
        assertion["value"]["numeric_value"] = "999"
    result = check(packet, parent, [claim])["results"][0]
    assert assertion["value"]["text"] == original_number
    assert result["semantic_support"]["status"] == "differs_from_bound_fact"
    assert result["semantic_support"]["differences"]
    assert result["scientific_validity"]["status"] == "not_evaluated"


def test_unreported_temperature_and_dropped_unknowns_are_not_silently_accepted():
    parent, packet = inputs("exposed_real_full_packet")
    row = next(f for f in packet["content"]["facts"] if f["fact"]["property"] == "coulombic_efficiency"
               and f["fact"]["unknown_fields"])
    claim = {"id": "unknowns", "kind": "fact", "fact_ref": row["id"], "assertion": fact_assertion(row["fact"])}
    assert claim["assertion"]["unknown_fields"]
    claim["assertion"]["conditions"]["temperature"] = {
        "text": "25", "normalization": "nfkc_dehyphenation_whitespace_only", "numeric_value": "25",
        "numeric_interpretation": "literal_decimal"}
    claim["assertion"]["unknown_fields"] = []
    row = check(packet, parent, [claim])["results"][0]
    assert row["semantic_support"]["status"] == "differs_from_bound_fact"
    assert row["semantic_support"]["bound_unknown_fields"]
    assert any(f["status"] == "no_bound_field_anchor" for f in row["literal_presence"]["fields"])


def test_matching_one_fact_does_not_discharge_conflicting_source_values():
    parent, packet = inputs("conflicting_value")
    claim = fact_claim(packet, "coulombic_efficiency")
    result = check(packet, parent, [claim])["results"][0]
    assert result["semantic_support"]["tuple_matches"] is True
    assert result["semantic_support"]["status"] == "ambiguous_source_candidates"
    assert len(result["semantic_support"]["requirement"]["fact_refs"]) > 1


def test_matching_fact_does_not_discharge_another_uninspected_selected_source():
    parent, packet = inputs()
    ce = next(f for f in packet["content"]["facts"] if f["fact"]["property"] == "coulombic_efficiency")
    chunk_id = ce["fact"]["support"]["chunk_id"]
    del parent["preparation"]["sources"]["chunks"][chunk_id]
    parent["requirements"] = build_requirements(parent["preparation"])
    packet = build_packet(parent)
    result = check(packet, parent, [fact_claim(packet)])["results"][0]
    assert result["semantic_support"]["tuple_matches"] is True
    assert result["semantic_support"]["status"] == "uninspected_selected_sources"


def test_matching_fact_preserves_unresolved_cross_role_identity():
    parent, packet = inputs("missing_identity")
    row = check(packet, parent, [fact_claim(packet)])["results"][0]
    assert row["semantic_support"]["tuple_matches"] is True
    assert row["semantic_support"]["role_identity"]["state"] == "identity_unresolved"


@pytest.mark.parametrize("replacement", ["prefix", "whitespace", "unicode"])
def test_quote_mismatch_is_local_and_is_never_automatically_repaired(replacement):
    parent, packet = inputs()
    claim = quote_claim(packet)
    claim["text"] = {"prefix": "x" + claim["text"], "whitespace": claim["text"] + " ", "unicode": "Δ" + claim["text"]}[replacement]
    row = check(packet, parent, [claim])["results"][0]
    assert row["literal_presence"]["status"] == "mismatch_at_bound_anchor"
    assert row["semantic_support"]["status"] == "not_evaluated"


def test_normalized_field_surface_is_distinguished_from_exact_raw_copy():
    parent, packet = inputs("exposed_real_full_packet")
    claim = fact_claim(packet, "base_salt_concentration")
    row = check(packet, parent, [claim])["results"][0]
    assert row["semantic_support"]["tuple_matches"] is True
    assert row["literal_presence"]["status"] == "raw_surface_differences"
    assert any(f["status"] == "not_exact_raw_surface" for f in row["literal_presence"]["fields"])


@pytest.mark.parametrize("field", ["operands", "result", "unit"])
def test_wrong_sum_bindings_remain_failures_even_if_algebra_is_correct(field):
    parent, packet = inputs()
    claim = sum_claim(packet)
    if field == "operands":
        claim["assertion"].update(operands=["1", "1"], result="2")
    else:
        claim["assertion"][field] = "999" if field == "result" else "mM"
    row = check(packet, parent, [claim])["results"][0]
    assert row["arithmetic"]["status"] == "sum_or_binding_mismatch"
    assert row["semantic_support"]["status"] == "not_evaluated"


def test_sum_accepts_exact_result_with_trailing_zeros_but_preserves_spelling():
    from decimal import localcontext

    parent, packet = inputs()
    claim = sum_claim(packet)
    claim["assertion"]["result"] += "0" if "." in claim["assertion"]["result"] else ".0"
    with localcontext() as context:
        context.prec = 1
        # Existing packet recipes use Decimal; construct the comparison before
        # context reduction and exercise the independent arithmetic function only.
        from app.generation.claim_checks import ArithmeticClaim, _arithmetic_check
        row = _arithmetic_check(ArithmeticClaim.model_validate(claim), packet["content"])
    assert row["arithmetic"]["status"] == "matches_bound_sum"
    assert row["arithmetic"]["asserted"]["result"] == claim["assertion"]["result"]


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "1e1000000", "1/2", "1,35", "+1", "01", "1" * 81])
def test_decimal_input_does_not_accept_exponents_special_values_or_unbounded_digits(bad):
    parent, packet = inputs()
    claim = sum_claim(packet)
    claim["assertion"]["result"] = bad
    with pytest.raises(ValueError):
        check(packet, parent, [claim])


@pytest.mark.parametrize("change", ["free_prose", "extra", "incomplete_tuple", "foreign_fact", "foreign_anchor", "duplicate_id",
                                    "too_many", "too_large", "long_quote", "coercion"])
def test_invalid_or_unbounded_claim_inputs_fail_visibly(change):
    parent, packet = inputs()
    claims = [fact_claim(packet)]
    if change == "free_prose":
        claims = [{"id": "x", "kind": "prose", "text": "Scientifically correct"}]
    elif change == "extra":
        claims[0]["scientific_validity"] = "approved"
    elif change == "incomplete_tuple":
        del claims[0]["assertion"]["epistemic_status"]
    elif change == "foreign_fact":
        claims[0]["fact_ref"] = "F:foreign"
    elif change == "foreign_anchor":
        claims = [quote_claim(packet)]
        claims[0]["anchor_ref"] = "A:foreign"
    elif change == "duplicate_id":
        claims += copy.deepcopy(claims)
    elif change == "too_many":
        claims *= 65
    elif change == "too_large":
        claims = [{**quote_claim(packet), "id": str(i), "text": "a" * 8000} for i in range(33)]
    elif change == "long_quote":
        claims = [{**quote_claim(packet), "text": "a" * 8001}]
    else:
        claims[0]["assertion"]["value"]["text"] = 98
    with pytest.raises(ValueError):
        check(packet, parent, claims)


@pytest.mark.parametrize("change", ["packet", "parent", "packet_pin", "report_pin", "result", "scientific", "blockers",
                                    "claims", "order", "event", "report_extra", "code"])
def test_trusted_reconstruction_rejects_tampering_stale_inputs_and_false_approval(change):
    from app.generation import claim_checks as module

    parent, packet = inputs()
    claims = [quote_claim(packet), fact_claim(packet)]
    report = check(packet, parent, claims)
    packet_id, report_id = packet["packet_id"], report["report_id"]
    if change == "packet":
        packet["content"]["facts"][0]["fact"]["value"]["text"] = "999"
    elif change == "parent":
        parent["preparation"]["blocking_reasons"].append("new_blocker")
    elif change == "packet_pin":
        packet_id = "0" * 64
    elif change == "report_pin":
        report_id = "0" * 64
    elif change == "result":
        report["results"][0]["literal_presence"]["status"] = "approved"
    elif change == "scientific":
        report["scientific_validity"] = "approved"
    elif change == "blockers":
        report["stop"]["baseline"]["baseline_blocking_reasons"] = []
    elif change == "claims":
        claims[0]["text"] += " changed"
    elif change == "order":
        report["journal"]["events"].reverse()
    elif change == "event":
        report["journal"]["events"][0]["previous_hash"] = "0" * 64
    elif change == "report_extra":
        report["approved"] = True
    else:
        with patch.object(module, "code_bindings", return_value={"changed": "0" * 64}), pytest.raises(ValueError):
            validate_checks(report, packet, parent, claims, expected_packet_id=packet_id, expected_report_id=report_id)
        return
    with pytest.raises(ValueError):
        validate_checks(report, packet, parent, claims, expected_packet_id=packet_id, expected_report_id=report_id)


def test_canonical_roundtrip_refuses_overwrite_and_reformatted_json(tmp_path):
    parent, packet = inputs()
    claims = [fact_claim(packet)]
    report = check(packet, parent, claims)
    path = tmp_path / "checks.json"
    kwargs = {"expected_packet_id": packet["packet_id"], "expected_report_id": report["report_id"]}
    save_checks(path, report, packet, parent, claims, **kwargs)
    original = path.read_bytes()
    assert load_checks(path, packet, parent, claims, **kwargs) == report
    with pytest.raises(FileExistsError):
        save_checks(path, report, packet, parent, claims, **kwargs)
    assert path.read_bytes() == original
    other = tmp_path / "noncanonical.json"
    other.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        load_checks(other, packet, parent, claims, **kwargs)


def test_empty_claims_never_become_vacuous_approval_or_call_tools():
    parent, packet = inputs()
    with patch("app.generation.service.search_chunks", side_effect=AssertionError("No retrieval")), \
         patch("app.generation.service.build_answer_provider", side_effect=AssertionError("No provider")):
        report = check(packet, parent, [])
    assert report["stop"]["reason"] == "no_claims"
    assert report["results"] == []
    assert report["scientific_validity"] == "not_evaluated"
    assert len(report["journal"]["events"]) == 1


def test_cli_uses_explicit_parent_claims_packet_pin_and_exclusive_output(tmp_path, monkeypatch, capsys):
    from scripts.check_answer_claims import main

    parent, packet = inputs()
    claims = [fact_claim(packet)]
    for name, data in (("packet", packet), ("parent", parent), ("claims", claims)):
        (tmp_path / (name + ".json")).write_bytes(serialize_packet(data))
    output = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", ["check_answer_claims", "--packet", str(tmp_path / "packet.json"),
        "--parent", str(tmp_path / "parent.json"), "--claims", str(tmp_path / "claims.json"),
        "--packet-id", packet["packet_id"], "--output", str(output)])
    main()
    summary = json.loads(capsys.readouterr().out)
    assert summary["claims_checked"] == 1 and summary["scientific_validity"] == "not_evaluated"
    assert load_checks(output, packet, parent, claims, expected_packet_id=packet["packet_id"],
                       expected_report_id=summary["report_id"])["claims"] == claims
    with pytest.raises(FileExistsError):
        main()


def test_dictionary_key_order_cannot_change_report_identity():
    parent, packet = inputs()
    claims = [fact_claim(packet)]
    report = check(packet, parent, claims)
    restored = check(json.loads(serialize_packet(packet)), json.loads(serialize_packet(parent)),
                     json.loads(serialize_packet(claims)))
    assert serialize_packet(restored) == serialize_packet(report)


def test_claim_count_boundary_is_allowed_without_automatic_approval():
    parent, packet = inputs()
    claims = [{**quote_claim(packet), "id": str(i)} for i in range(64)]
    report = check(packet, parent, claims)
    assert report["stop"]["claims_checked"] == 64
    assert report["scientific_validity"] == "not_evaluated"


def test_diagnostic_context_capsule_is_not_accepted_as_a_source_packet():
    parent, packet = inputs()
    capsule = {"version": "bounded_coulombic_context_action_v0.2", "input_packet": packet}
    with pytest.raises(ValueError):
        build_checks(capsule, parent, [], expected_packet_id=packet["packet_id"])
