"""Synthetic source-packet invariants; no scientific accuracy or gold fixtures."""

from __future__ import annotations

import html
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.records.pilot import PilotDocument, render_source_html, selection_audit, source_content, write_pilot_packet
from app.records.schema import CandidateBundle, RecordCandidate, SourceRegion, source_identity, text_hash
from app.records.sources import file_hash


def document(tmp_path: Path, raw: str = "Synthetic raw: Li-Naﬁon 1 × 10−3 S cm−1") -> PilotDocument:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF synthetic immutable source; not a scientific PDF")
    checksum = file_hash(pdf)
    data = {
        "article_id": str(uuid4()), "original_pdf_path": str(pdf), "original_pdf_sha256": checksum,
        "page_number": 1, "text_layer_id": str(uuid4()), "text_layer": "original",
        "layer_pdf_path": str(pdf), "layer_pdf_sha256": checksum,
        "page_text": raw, "page_text_sha256": text_hash(raw), "start": 0, "end": len(raw),
        "quote": raw, "quote_sha256": text_hash(raw), "selection_basis": "fixed_page",
        "selection_note": "Synthetic full selected-page test.",
    }
    data["region_id"] = source_identity(data)
    region = SourceRegion.model_validate(data)
    bundle = CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="synthetic", regions=(region,))
    return PilotDocument(region.article_id, "Synthetic </h2> title", None, str(pdf), checksum, 1, (1,), bundle)


def profile(doc: PilotDocument, priority: str = "no_anchor") -> dict[str, object]:
    return {"schema_version": 1, "articles": [{
        "article_id": str(doc.article_id), "pdf_sha256": doc.original_pdf_sha256, "candidate_priority": priority,
    }]}


def test_full_raw_source_survives_packet_and_html_escaping(tmp_path: Path) -> None:
    doc = document(tmp_path, 'Li-Naﬁon 1 × 10−3 S cm−1 </script><script>alert("fixture")</script>')
    doc.validate()
    assert doc.bundle is not None
    raw = doc.bundle.regions[0].quote
    rendered = render_source_html((doc,), "a" * 64)
    assert html.escape(raw) in rendered
    assert '<script>alert("fixture")</script>' not in rendered
    assert doc.original_pdf_sha256 in rendered
    assert Path(doc.original_pdf_path).as_uri() in rendered
    assert "candidate_priority" not in rendered


def test_source_fingerprint_payload_ignores_run_identity(tmp_path: Path) -> None:
    doc = document(tmp_path)
    assert doc.bundle is not None
    changed = replace(doc, bundle=doc.bundle.model_copy(update={"run_id": uuid4(), "created_at": datetime.now(UTC)}))
    assert source_content((doc,)) == source_content((changed,))


def test_partial_page_cannot_be_source_only_full_scope(tmp_path: Path) -> None:
    doc = document(tmp_path)
    assert doc.bundle is not None
    data = doc.bundle.regions[0].model_dump()
    data.update(start=10, quote=data["page_text"][10:], quote_sha256=text_hash(data["page_text"][10:]))
    data["region_id"] = source_identity(data)
    region = SourceRegion.model_validate(data)
    changed = replace(doc, bundle=doc.bundle.model_copy(update={"regions": (region,)}))
    with pytest.raises(ValueError, match="complete stored pages"):
        changed.validate()


def test_source_packet_rejects_candidate_filled_bundle(tmp_path: Path) -> None:
    doc = document(tmp_path)
    assert doc.bundle is not None
    missing = {"status": "not_found_in_context", "note": "Synthetic context only."}
    fields = {key: missing for key in (
        "sample_label", "material_form", "preparation", "property_name", "temperature", "medium",
        "medium_composition", "composition_basis", "conditioning", "method", "data_origin", "li_ion_author_claim",
    )}
    record = RecordCandidate.model_validate({
        "record_id": uuid4(), "article_id": doc.article_id, **fields,
        "value": {key: missing for key in ("raw_value", "raw_unit", "approximation", "uncertainty")},
    })
    changed = replace(doc, bundle=doc.bundle.model_copy(update={"records": (record,)}))
    with pytest.raises(ValueError, match="must not contain candidate records"):
        changed.validate()


@pytest.mark.parametrize("change,error", [
    ({"bundle": None}, "Unexported stored page"),
    ({"pdf_page_count": 2}, "Missing original-PDF page"),
    ({"stored_page_numbers": (1, 1)}, "Duplicate stored page"),
    ({"original_pdf_sha256": "f" * 64}, "different article/PDF"),
])
def test_undocumented_losses_or_source_drift_fail(tmp_path: Path, change: dict[str, object], error: str) -> None:
    with pytest.raises(ValueError, match=error):
        replace(document(tmp_path), **change).validate()


def test_empty_and_missing_pages_are_explicit_not_negative_gold(tmp_path: Path) -> None:
    doc = replace(document(tmp_path), bundle=None, pdf_page_count=2,
                  diagnostics=("empty_selected_page:1", "missing_stored_page:2"))
    doc.validate()
    audit = selection_audit(profile(doc), (doc,))
    assert audit["scientifically_eligible_publications"] is None
    assert audit["annotation_status"] == "not_annotated"
    assert audit["documents_without_lexical_hit"] == [str(doc.article_id)]
    assert audit["split"] == "development_only_no_untouched_evaluation"


@pytest.mark.parametrize("mutation", ["missing_document", "duplicate_document", "pdf_drift", "unknown_priority"])
def test_selection_audit_cannot_drop_documents_or_accept_changed_pdf(tmp_path: Path, mutation: str) -> None:
    doc = document(tmp_path)
    data = profile(doc)
    rows = data["articles"]
    if mutation == "missing_document":
        rows.clear()
    elif mutation == "duplicate_document":
        rows.append(rows[0].copy())
    elif mutation == "pdf_drift":
        rows[0]["pdf_sha256"] = "f" * 64
    else:
        rows[0]["candidate_priority"] = "scientifically_confirmed"
    with pytest.raises(ValueError):
        selection_audit(data, (doc,))


def test_packet_is_exclusive_source_only_and_fingerprints_every_output(tmp_path: Path) -> None:
    doc = document(tmp_path)
    original_bytes = Path(doc.original_pdf_path).read_bytes()
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile(doc, "li_nafion_mention")), encoding="utf-8")
    protocol = tmp_path / "protocol.md"
    protocol.write_text("Synthetic protocol; no scientific annotation.", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"source_fingerprint": "b" * 64}), encoding="utf-8")
    output = tmp_path / "packet"
    manifest = write_pilot_packet(
        (doc,), profile_path, output, protocol_path=protocol, baseline_manifest_path=baseline,
        source_root=Path(__file__).resolve().parents[2],
    )
    assert manifest["candidate_records"] == manifest["annotations"] == 0
    assert manifest["independent_gold"] is False
    assert manifest["scientific_admission"] == "not_evaluated"
    assert manifest["lexical_candidate_count"] == 1
    for name, checksum in manifest["artifacts_sha256"].items():
        assert file_hash(output / name) == checksum
    assert Path(doc.original_pdf_path).read_bytes() == original_bytes
    assert doc.bundle is not None
    assert CandidateBundle.model_validate_json((output / "sources" / f"{doc.article_id}.json").read_bytes()) == doc.bundle
    with pytest.raises(FileExistsError):
        write_pilot_packet(
            (doc,), profile_path, output, protocol_path=protocol, baseline_manifest_path=baseline,
            source_root=Path(__file__).resolve().parents[2],
        )
