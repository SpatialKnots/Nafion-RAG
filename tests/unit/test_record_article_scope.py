"""Constructed source/coverage counterexamples, not scientific eligibility labels."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.records.article_scope import Screening, export_article_scope, validate_screening
from app.records.pilot import source_content, write_pilot_packet
from app.records.schema import EvidenceSpan, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_pilot import document, profile

ROOT = Path(__file__).resolve().parents[2]


def setup_packet(tmp_path):
    docs = []
    for index in range(3):
        directory = tmp_path / str(index)
        directory.mkdir()
        docs.append(document(directory, f'Synthetic document {index}: Li-Naﬁon </script><script>alert("x")</script>'))
    # The third document deliberately lacks selected text for one stored page and
    # has another missing original page; neither gap may disappear from task scope.
    docs[2] = replace(docs[2], pdf_page_count=3, stored_page_numbers=(1, 2),
                      diagnostics=("empty_selected_page:2", "missing_stored_page:3"))
    content = source_content(tuple(docs))
    fingerprint = text_hash(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    prof = profile(docs[0])
    prof["articles"] = [profile(doc)["articles"][0] for doc in docs]
    prof_path = tmp_path / "profile.json"
    prof_path.write_text(json.dumps(prof), encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"source_fingerprint": "a" * 64}), encoding="utf-8")
    protocol = tmp_path / "protocol.md"
    protocol.write_text("Synthetic packet only. No scientific data.", encoding="utf-8")
    packet = tmp_path / "packet"
    write_pilot_packet(tuple(docs), prof_path, packet, protocol_path=protocol,
                       baseline_manifest_path=baseline, source_root=ROOT)
    entries = []
    for index, doc in enumerate(docs):
        region = doc.bundle.regions[0]
        span = EvidenceSpan(region_id=region.region_id, start=0, end=len(region.quote), quote=region.quote)
        entries.append({"article_id": str(doc.article_id), "status": "proposed_supplement" if index == 1 else "proposed_primary",
                        "rationale": "Constructed proposal, not scientific eligibility.",
                        "inspected_pages": [1], "evidence": [span.model_dump(mode="json")]})
    data = {"source_fingerprint": fingerprint, "author": "Synthetic assistant fixture",
            "scope": "Li-Nafion conductivity; preserve author property wording", "documents": entries,
            "relations": [{"kind": "proposed_supplement_of", "subject": entries[1]["article_id"],
                           "target": entries[0]["article_id"], "rationale": "Synthetic relationship only.",
                           "subject_evidence": entries[1]["evidence"], "target_evidence": entries[0]["evidence"]}]}
    path = tmp_path / "screening.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return packet, path, data, content, {str(d.article_id): d.bundle for d in docs}


def test_export_retains_all_documents_full_scope_and_byte_identical_bundles(tmp_path):
    packet, path, data, _, _ = setup_packet(tmp_path)
    result = export_article_scope(packet, path, tmp_path / "out", source_root=ROOT)
    assert len(result["documents"]) == 3
    assert result["summary"]["article_tasks"] == 2
    assert result["summary"]["task_pdf_pages"] == 5
    assert result["summary"]["task_selected_text_pages"] == 3
    assert result["summary"]["scientifically_eligible_independent_publications"] is None
    assert result["summary"]["scientific_recall"] is None
    assert result["summary"]["human_time_savings"] is None
    assert result["summary"]["new_model_calls"] == 0
    assert result["identity_diagnostics"]["same_original_pdf"]  # Identical synthetic PDF bytes; no work equivalence.
    third = next(t for t in result["tasks"] if t["primary_article_id"] == data["documents"][2]["article_id"])
    pages = third["documents"][0]["pages"]
    assert [p["text_state"] for p in pages] == ["selected_text", "empty_selected_text", "missing_stored_page"]
    assert all(p["non_text_completeness"] == "not_established" for p in pages)
    for task in result["tasks"]:
        for source in task["documents"]:
            assert (tmp_path / "out" / source["bundle"]).read_bytes() == (
                packet / "sources" / f'{source["article_id"]}.json').read_bytes()
    rendered = (tmp_path / "out" / "review.html").read_text(encoding="utf-8")
    assert rendered.count('class="document"') == 3
    assert '<script>alert("x")</script>' not in rendered
    assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in rendered
    assert (tmp_path / "out" / "screening.json").read_bytes() == path.read_bytes()


def test_repeated_exports_are_byte_identical_and_refuse_overwrite(tmp_path):
    packet, path, _, _, _ = setup_packet(tmp_path)
    outputs = [tmp_path / "a", tmp_path / "b"]
    for output in outputs:
        export_article_scope(packet, path, output, source_root=ROOT)
    a, b = [{p.relative_to(output).as_posix(): file_hash(p) for p in output.rglob("*") if p.is_file()} for output in outputs]
    assert a == b
    with pytest.raises(FileExistsError, match="already exists"):
        export_article_scope(packet, path, outputs[0], source_root=ROOT)


@pytest.mark.parametrize("mutation,error", [
    ("missing_document", "each packet document"), ("duplicate_document", "each packet document"),
    ("fingerprint", "fingerprint"), ("wrong_quote", "exact source span"),
    ("wrong_document", "different document"), ("out_of_range", "outside original PDF"),
    ("uninspected_evidence", "declared inspected pages"), ("missing_parent", "one source-supported"),
    ("duplicate_parent", "multiple or duplicate"), ("self_link", "distinct registered"),
    ("unknown_parent", "distinct registered"), ("wrong_parent_role", "primary target"),
    ("swapped_link_evidence", "different document"), ("missing_identity_evidence", "identity or screening excerpt"),
])
def test_bad_screening_and_relations_fail_without_silent_repairs(tmp_path, mutation, error):
    _, _, data, inventory, bundles = setup_packet(tmp_path)
    if mutation == "missing_document":
        data["documents"].pop()
    elif mutation == "duplicate_document":
        data["documents"].append(data["documents"][0])
    elif mutation == "fingerprint":
        data["source_fingerprint"] = "0" * 64
    elif mutation == "wrong_quote":
        data["documents"][0]["evidence"][0]["quote"] = "invented"
    elif mutation == "wrong_document":
        data["documents"][0]["evidence"] = data["documents"][1]["evidence"]
    elif mutation == "out_of_range":
        data["documents"][0]["inspected_pages"] = [100]
    elif mutation == "uninspected_evidence":
        data["documents"][2]["inspected_pages"] = [2]
    elif mutation == "missing_parent":
        data["relations"] = []
    elif mutation == "duplicate_parent":
        data["relations"].append(data["relations"][0])
    elif mutation == "self_link":
        data["relations"][0]["target"] = data["relations"][0]["subject"]
    elif mutation == "unknown_parent":
        data["relations"][0]["target"] = str(uuid4())
    elif mutation == "wrong_parent_role":
        data["documents"][0]["status"] = "unresolved"
    elif mutation == "swapped_link_evidence":
        data["relations"][0]["subject_evidence"] = data["relations"][0]["target_evidence"]
    elif mutation == "missing_identity_evidence":
        data["documents"][0].update(status="unresolved", evidence=[])
    with pytest.raises(ValueError, match=error):
        validate_screening(Screening.model_validate(data), inventory, bundles, inventory_fingerprint(inventory))


def inventory_fingerprint(inventory):
    return text_hash(json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


@pytest.mark.parametrize("mutation", ["author", "version", "extra", "no_evidence", "duplicate_page"])
def test_schema_rejects_independence_claims_unknown_versions_and_unsupported_inputs(tmp_path, mutation):
    _, _, data, _, _ = setup_packet(tmp_path)
    if mutation == "author":
        data["author_kind"] = "human"
    elif mutation == "version":
        data["version"] = "unknown"
    elif mutation == "extra":
        data["confirmed_eligible"] = True
    elif mutation == "no_evidence":
        data["documents"][0]["evidence"] = []
    else:
        data["documents"][0]["inspected_pages"] = [1, 1]
    with pytest.raises(ValidationError):
        Screening.model_validate(data)


@pytest.mark.parametrize("changed", ["pdf", "source", "inventory"])
def test_export_rejects_changed_packet_or_pdf(tmp_path, changed):
    packet, path, _, inventory, _ = setup_packet(tmp_path)
    if changed == "pdf":
        target = Path(inventory[0]["original_pdf_path"])
    elif changed == "source":
        target = packet / "sources" / f'{inventory[0]["article_id"]}.json'
    else:
        target = packet / "source_inventory.json"
    target.write_bytes(target.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="[Cc]hanged source|[Cc]hecksum|[Cc]hanged source packet|Source/input changed"):
        export_article_scope(packet, path, tmp_path / "out", source_root=ROOT)


def test_all_empty_unresolved_document_remains_in_declared_scope():
    identifier = str(uuid4())
    row = {"article_id": identifier, "pdf_page_count": 1}
    screening = Screening(source_fingerprint="a" * 64, author="Constructed assistant fixture",
                          scope="Li-Nafion conductivity; preserve author property wording",
                          documents=({"article_id": identifier, "status": "unresolved",
                                      "rationale": "All text unavailable; not a negative scientific label."},))
    validate_screening(screening, [row], {identifier: None}, "a" * 64)
