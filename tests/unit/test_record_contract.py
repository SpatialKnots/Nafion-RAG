"""Synthetic integrity counterexamples; these are not scientific gold records."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.records.schema import CandidateBundle, EvidenceSpan, SourceRegion, TextObservation, source_identity, text_hash


def region_data(text: str = "Li-Naﬁon ionic conductivity 1 × 10−3 S cm−1 at room temperature.") -> dict[str, object]:
    data: dict[str, object] = {
        "article_id": str(uuid4()), "original_pdf_path": "/data/pdf/a.pdf", "original_pdf_sha256": "a" * 64,
        "page_number": 1, "text_layer_id": str(uuid4()), "text_layer": "original",
        "layer_pdf_path": "/data/pdf/a.pdf", "layer_pdf_sha256": "a" * 64,
        "page_text": text, "page_text_sha256": text_hash(text), "start": 0, "end": len(text),
        "quote": text, "quote_sha256": text_hash(text), "selection_basis": "manual_development",
        "selection_note": "Synthetic unit test only.",
    }
    data["region_id"] = source_identity(data)
    return data


def present(region: SourceRegion, raw: str) -> dict[str, object]:
    start = region.quote.index(raw)
    return {
        "status": "present", "raw_text": raw,
        "evidence": [{"region_id": region.region_id, "start": start, "end": start + len(raw), "quote": raw}],
    }


def bundle_data() -> dict[str, object]:
    region = SourceRegion.model_validate(region_data())
    missing = {"status": "not_found_in_context", "note": "Only synthetic first-page context inspected."}
    record = {
        "record_id": str(uuid4()), "article_id": str(region.article_id),
        "sample_label": present(region, "Li-Naﬁon"), "material_form": missing, "preparation": missing,
        "property_name": present(region, "ionic conductivity"),
        "value": {
            "raw_value": present(region, "1 × 10−3"), "raw_unit": present(region, "S cm−1"),
            "representation": "scalar", "approximation": missing, "uncertainty": missing,
        },
        "temperature": present(region, "room temperature"), "medium": missing, "medium_composition": missing,
        "composition_basis": missing,
        "conditioning": missing, "method": missing, "data_origin": missing, "li_ion_author_claim": missing,
    }
    return {
        "run_id": str(uuid4()), "created_at": datetime.now(UTC).isoformat(), "producer": "synthetic-test",
        "regions": [region.model_dump(mode="json")], "records": [record],
    }


def test_roundtrip_preserves_raw_units_ligature_exponents_and_temperature() -> None:
    bundle = CandidateBundle.model_validate(bundle_data())
    restored = CandidateBundle.model_validate_json(bundle.model_dump_json())
    assert restored == bundle
    record = restored.records[0]
    assert record.sample_label.raw_text == "Li-Naﬁon"
    assert record.value.raw_value.raw_text == "1 × 10−3"
    assert record.value.raw_unit.raw_text == "S cm−1"
    assert record.temperature.raw_text == "room temperature"
    assert record.review_state == "needs_review"
    assert record.li_ion_confirmation == "not_reviewed"


@pytest.mark.parametrize("field,value,error", [
    ("start", -1, "greater than or equal"),
    ("end", 10000, "outside page"),
    ("quote", "invented quote", "exact page span"),
    ("page_text_sha256", "b" * 64, "Text checksum"),
    ("quote_sha256", "b" * 64, "Text checksum"),
    ("region_id", "b" * 64, "identity checksum"),
    ("layer_pdf_sha256", "b" * 64, "original PDF"),
])
def test_source_tampering_is_rejected(field: str, value: object, error: str) -> None:
    data = region_data()
    data[field] = value
    with pytest.raises(ValidationError, match=error):
        SourceRegion.model_validate(data)


def test_repeated_quote_occurrences_have_different_identity() -> None:
    data = region_data("Li-Naﬁon; Li-Naﬁon")
    first = {**data, "start": 0, "end": 8, "quote": "Li-Naﬁon", "quote_sha256": text_hash("Li-Naﬁon")}
    second = {**first, "start": 10, "end": 18}
    first["region_id"] = source_identity(first)
    second["region_id"] = source_identity(second)
    assert SourceRegion.model_validate(first).region_id != SourceRegion.model_validate(second).region_id


@pytest.mark.parametrize("observation", [
    {"status": "present", "raw_text": "1", "evidence": []},
    {"status": "not_found_in_context", "raw_text": "25 °C", "note": "Assumed."},
    {"status": "ambiguous"},
    {"status": "not_reported", "note": "Not an article-wide review."},
])
def test_missingness_cannot_hide_asserted_values(observation: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TextObservation.model_validate(observation)


def test_raw_text_must_be_in_evidence() -> None:
    evidence = EvidenceSpan(region_id="a" * 64, start=0, end=8, quote="Li-Naﬁon")
    with pytest.raises(ValidationError, match="verbatim"):
        TextObservation(status="present", raw_text="H-Nafion", evidence=(evidence,))


@pytest.mark.parametrize("mutation,error", [
    ("unknown_region", "unknown region"),
    ("wrong_span", "exact region span"),
    ("wrong_article", "different article"),
    ("duplicate_region", "Duplicate source"),
    ("duplicate_record", "Duplicate record"),
    ("confirmed", "not_reviewed"),
    ("accepted", "needs_review"),
    ("extra_field", "Extra inputs"),
])
def test_bundle_rejects_invalid_evidence_or_admission(mutation: str, error: str) -> None:
    # JSON gives mutable plain structures for independent corruption cases.
    data = json.loads(json.dumps(bundle_data()))
    record = data["records"][0]
    span = record["sample_label"]["evidence"][0]
    if mutation == "unknown_region":
        span["region_id"] = "f" * 64
    elif mutation == "wrong_span":
        span["start"] = 1
        span["end"] += 1
    elif mutation == "wrong_article":
        other = region_data()
        data["regions"].append(other)
        record["article_id"] = other["article_id"]
    elif mutation == "duplicate_region":
        data["regions"].append(data["regions"][0])
    elif mutation == "duplicate_record":
        data["records"].append(record)
    elif mutation == "confirmed":
        record["li_ion_confirmation"] = "confirmed"
    elif mutation == "accepted":
        record["review_state"] = "accepted"
    else:
        record["normalized_temperature"] = 25
    with pytest.raises(ValidationError, match=error):
        CandidateBundle.model_validate(data)


def test_context_bundle_has_no_measurement_claim() -> None:
    data = bundle_data()
    data["records"] = []
    bundle = CandidateBundle.model_validate(data)
    assert bundle.records == ()


def test_naive_run_timestamp_is_rejected() -> None:
    data = bundle_data()
    data["created_at"] = "2026-10-09T12:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        CandidateBundle.model_validate(data)


def test_readiness_lists_missing_conditions_and_linkage_without_admission() -> None:
    from app.records.readiness import assess_readiness

    record = CandidateBundle.model_validate(bundle_data()).records[0]
    report = assess_readiness(record)
    assert "sample_label" not in report.missing_fields
    assert "temperature" not in report.missing_fields
    assert {"material_form", "medium", "medium_composition", "composition_basis", "method"} <= set(report.missing_fields)
    assert set(report.missing_linkage_roles) == {"sample_value", "property_value", "conditions_measurement"}
    assert report.to_dict()["scientific_admission"] == "not_evaluated"


def test_complete_observations_and_linkage_still_require_scientific_review() -> None:
    from app.records.readiness import assess_readiness

    data = json.loads(json.dumps(bundle_data()))
    record = data["records"][0]
    # Structurally supported claims can still be scientifically wrong.
    for name in ("material_form", "medium", "medium_composition", "composition_basis", "method"):
        record[name] = record["sample_label"]
    record["linkage"] = [
        {"role": role, "evidence": record["sample_label"]["evidence"], "note": "Synthetic structural test; no semantic claim."}
        for role in ("sample_value", "property_value", "conditions_measurement")
    ]
    report = assess_readiness(CandidateBundle.model_validate(data).records[0])
    assert not report.missing_fields
    assert not report.missing_linkage_roles
    assert report.to_dict()["review_state"] == "needs_review"
    assert report.to_dict()["scientific_admission"] == "not_evaluated"


def test_manifest_binds_artifact_and_code_bytes(tmp_path: Path) -> None:
    from app.records.runs import build_manifest

    artifact = tmp_path / "candidate.json"
    artifact.write_text(json.dumps(bundle_data(), ensure_ascii=False), encoding="utf-8")
    code = tmp_path / "app" / "records" / "schema.py"
    code.parent.mkdir(parents=True)
    code.write_text("# Synthetic source fingerprint fixture\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("# synthetic fixture\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=must-not-enter-manifest", encoding="utf-8")
    first = build_manifest(artifact, operation="manual_candidate", source_root=tmp_path)
    code.write_text("# changed source\n", encoding="utf-8")
    second = build_manifest(artifact, operation="manual_candidate", source_root=tmp_path)
    assert first["artifact"] == second["artifact"]
    assert first["code_fingerprint_sha256"] != second["code_fingerprint_sha256"]
    assert "SECRET" not in json.dumps(second)
    artifact.write_text('{"invalid": true}', encoding="utf-8")
    with pytest.raises(ValidationError):
        build_manifest(artifact, operation="manual_candidate", source_root=tmp_path)


def test_review_packet_keeps_exact_evidence_and_blank_decisions() -> None:
    from app.records.review import render_review_packet

    bundle = CandidateBundle.model_validate(bundle_data())
    rendered = render_review_packet(bundle)
    assert "room temperature" in rendered
    assert "1 × 10−3" in rendered
    assert "S cm−1" in rendered
    assert "page span [" in rendered
    assert "Reviewer: ______" in rendered
    assert "не gold" in rendered
    assert "needs_review" in rendered
    assert render_review_packet(bundle) == rendered


def test_review_packet_escapes_markdown_but_preserves_source_quote() -> None:
    from app.records.review import render_review_packet

    raw = "Li-Naﬁon | <tag> ``` quoted"
    region = SourceRegion.model_validate(region_data(raw))
    data = json.loads(json.dumps(bundle_data()))
    data["regions"].append(region.model_dump(mode="json"))
    # An ambiguous field can cite a diagnostic fragment without claiming a value.
    data["records"][0]["preparation"] = {
        "status": "ambiguous", "note": "a | b <tag>",
        "evidence": [{"region_id": region.region_id, "start": 0, "end": len(raw), "quote": raw}],
    }
    data["records"][0]["article_id"] = str(region.article_id)
    # Keep all observations within one article while testing arbitrary source markup.
    first = data["regions"][0]
    old_id = first["region_id"]
    first["article_id"] = str(region.article_id)
    first["region_id"] = source_identity(first)
    for obs in data["records"][0].values():
        if isinstance(obs, dict):
            for part in [obs, *obs.values()]:
                if isinstance(part, dict):
                    for span in part.get("evidence", []):
                        if span["region_id"] == old_id:
                            span["region_id"] = first["region_id"]
    rendered = render_review_packet(CandidateBundle.model_validate(data))
    assert "a &#124; b &lt;tag&gt;" in rendered
    assert f"````text\n{raw}\n````" in rendered


def test_empty_review_context_is_not_an_automatic_negative() -> None:
    from app.records.review import render_review_packet

    data = bundle_data()
    data["records"] = []
    rendered = render_review_packet(CandidateBundle.model_validate(data))
    assert "сам по себе не является отрицательной gold-разметкой" in rendered
