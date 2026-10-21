"""Synthetic full-record revision, concurrency and local HTTP counterexamples."""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.records import revision_store as store
from app.records.revision_ui import create_app
from app.records.schema import RecordCandidate
from tests.unit.test_record_checks_export import ROOT, make_bundle, save_bundle


@pytest.fixture
def prepared(tmp_path):
    bundle = make_bundle(tmp_path, ocr=True)
    path = save_bundle(tmp_path / "input.json", bundle)
    root = tmp_path / "review"
    sid = store.initialize_store([path], root, source_root=ROOT)
    return root, sid, bundle, path


def request_for(root, *, action="edit", **overrides):
    state = store.load_state(root)
    current = state["records"][0]
    payload = dict(snapshot_id=state["snapshot_id"], record_key=current["record_key"],
                   expected_revision=current["revision"], action=action, actor="Synthetic test actor", actor_kind="assistant",
                   reason="Constructed test only; no real scientific approval.")
    if action == "edit":
        data = json.loads(json.dumps(current["candidate"]))
        data["composition_basis"]["raw_text"] = "mass"
        payload["candidate"] = data
    payload.update(overrides)
    return store.RevisionRequest.model_validate(payload)


def test_edit_reopen_export_retains_original_sources_and_all_raw_values(prepared):
    root, sid, bundle, path = prepared
    inputs = {path: path.read_bytes(), Path(bundle.regions[0].original_pdf_path): Path(bundle.regions[0].original_pdf_path).read_bytes(),
              Path(bundle.regions[0].layer_pdf_path): Path(bundle.regions[0].layer_pdf_path).read_bytes()}
    event = store.save_revision(root, request_for(root))
    assert event["revision"] == 1 and event["declared_review_status"] == "unreviewed"
    state = store.load_state(root)
    current = state["records"][0]
    assert state["snapshot_id"] == sid and not state["stale_code"]
    assert current["original_candidate"] == bundle.records[0].model_dump(mode="json")
    assert current["candidate"]["composition_basis"]["raw_text"] == "mass"
    assert current["candidate"]["composition_basis"]["evidence"] == current["original_candidate"]["composition_basis"]["evidence"]
    assert current["candidate"]["value"] == current["original_candidate"]["value"]
    exported = store.export_review(root)
    row = next(csv.DictReader(io.StringIO(store.review_csv(exported))))
    assert row["revision"] == "1" and row["declared_review_status"] == "unreviewed"
    assert row["candidate_review_state"] == "needs_review" and row["scientific_admission"] == "not_evaluated"
    assert row["evidence_json_pointer"] == "review.json#/records/0"
    assert len(exported["records"][0]["history"]) == 1
    for file, raw in inputs.items():
        assert file.read_bytes() == raw


def test_human_decision_edit_and_restore_create_new_unreviewed_revisions(prepared):
    root, *_ = prepared
    confirmed = store.save_revision(
        root, request_for(root, action="decide", decision="confirmed", actor_kind="human", source_reviewed=True))
    assert confirmed["declared_review_status"] == "confirmed"
    edited = store.save_revision(root, request_for(root))
    assert edited["revision"] == 2 and edited["declared_review_status"] == "unreviewed"
    store.save_revision(root, request_for(root, action="decide", decision="confirmed", actor_kind="human", source_reviewed=True))
    restored = store.save_revision(root, request_for(root, action="restore", restore_revision=1))
    assert restored["revision"] == 4 and restored["declared_review_status"] == "unreviewed"
    state = store.load_state(root)["records"][0]
    assert state["candidate"] == state["original_candidate"]
    assert len(state["history"]) == 4 and state["history"][0]["declared_review_status"] == "confirmed"


@pytest.mark.parametrize("actor_kind,source_reviewed", [("assistant", True), ("human", False), ("assistant", False)])
def test_confirmation_requires_explicit_human_source_attestation(prepared, actor_kind, source_reviewed):
    root, *_ = prepared
    with pytest.raises(store.RevisionConflict, match="Confirmation requires"):
        store.save_revision(root, request_for(root, action="decide", decision="confirmed", actor_kind=actor_kind,
                                             source_reviewed=source_reviewed))
    assert store.load_state(root)["records"][0]["revision"] == 0


def test_incomplete_record_cannot_be_human_confirmed(prepared):
    root, *_ = prepared
    request = request_for(root)
    candidate = request.candidate.model_dump(mode="json")
    candidate["method"] = dict(status="not_found_in_context", note="Missing synthetic prerequisite.")
    store.save_revision(root, request.model_copy(update={"candidate": RecordCandidate.model_validate(candidate)}))
    with pytest.raises(store.RevisionConflict, match="Confirmation requires"):
        store.save_revision(root, request_for(root, action="decide", decision="confirmed", actor_kind="human", source_reviewed=True))


def test_concurrent_same_revision_has_one_winner_and_no_lost_update(prepared):
    root, *_ = prepared
    request = request_for(root)

    def save():
        try:
            store.save_revision(root, request)
            return "saved"
        except store.RevisionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: save(), range(2))) == ["conflict", "saved"]
    assert len(store.load_state(root)["records"][0]["history"]) == 1


@pytest.mark.parametrize("mutation", [
    "record_id", "article_id", "evidence", "unknown_record", "wrong_snapshot", "no_op", "unknown_restore"])
def test_invalid_edits_and_identifiers_do_not_append_events(prepared, mutation):
    root, *_ = prepared
    request = request_for(root)
    payload = request.model_dump(mode="json")
    if mutation in {"record_id", "article_id"}:
        payload["candidate"][mutation] = str(uuid4())
    elif mutation == "evidence":
        payload["candidate"]["composition_basis"]["evidence"][0]["quote"] = "invented"
    elif mutation == "unknown_record":
        payload["record_key"] = "unknown"
    elif mutation == "wrong_snapshot":
        payload["snapshot_id"] = "f" * 64
    elif mutation == "no_op":
        payload["candidate"] = store.load_state(root)["records"][0]["candidate"]
    else:
        payload.update(action="restore", candidate=None, restore_revision=999)
    with pytest.raises(ValueError):
        store.save_revision(root, store.RevisionRequest.model_validate(payload))
    assert store.load_state(root)["records"][0]["revision"] == 0


@pytest.mark.parametrize("failure", ["pdf", "ocr", "baseline", "input_copy", "snapshot", "code"])
def test_changed_source_baseline_and_code_block_saves(prepared, monkeypatch, failure):
    root, _, bundle, _ = prepared
    request = request_for(root)
    paths = {"pdf": Path(bundle.regions[0].original_pdf_path), "ocr": Path(bundle.regions[0].layer_pdf_path),
             "baseline": root / "baseline/table.json", "input_copy": root / "baseline/inputs/0001.json", "snapshot": root / "snapshot.json"}
    if failure == "code":
        hashes = store.code_hashes()
        monkeypatch.setattr(store, "code_hashes", lambda: hashes | {"schema.py": "f" * 64})
        assert store.load_state(root)["stale_code"]
        with pytest.raises(store.RevisionConflict):
            store.export_review(root)
    else:
        file = paths[failure]
        if failure == "snapshot":
            data = json.loads(file.read_bytes())
            data["extra"] = "tampered snapshot identity"
            file.write_text(json.dumps(data), encoding="utf-8")
        else:
            file.write_bytes(b"changed")
    with pytest.raises(ValueError):
        store.save_revision(root, request)
    with sqlite3.connect(root / store.DB_NAME) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_event_hash_chain_and_database_identifiers_are_checked(prepared):
    root, *_ = prepared
    store.save_revision(root, request_for(root))
    with sqlite3.connect(root / store.DB_NAME) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="Immutable"):
            conn.execute("DELETE FROM events")
        conn.execute("DROP TRIGGER immutable_update")
        conn.execute("UPDATE events SET payload='{}'")
    with pytest.raises(store.RevisionConflict, match="event hash"):
        store.load_state(root)
    with sqlite3.connect(root / store.DB_NAME) as conn:
        conn.execute("PRAGMA application_id=123")
    with pytest.raises(store.RevisionConflict, match="Unsupported"):
        store.load_state(root)


def test_missing_store_reads_do_not_initialize_database(tmp_path):
    root = tmp_path / "absent"
    with pytest.raises(sqlite3.OperationalError):
        store.load_state(root)
    assert not root.exists()


def test_exact_quote_occurrences_are_explicit_and_overlaps_supported(tmp_path):
    bundle = make_bundle(tmp_path, sample="aaaa")
    region = bundle.regions[0]
    span = store.locate_evidence(bundle, region.region_id, "aa", 2)
    assert span.start == region.quote.index("aaaa") + 1
    assert span.quote == "aa"
    for quote, occurrence, region_id in [("aa", 4, region.region_id), ("invented", 1, region.region_id),
                                          ("aa", 0, region.region_id), ("aa", 1, "unknown")]:
        with pytest.raises(ValueError):
            store.locate_evidence(bundle, region_id, quote, occurrence)


@pytest.mark.parametrize("payload", [dict(action="edit", candidate=None), dict(action="decide", decision=None),
                                    dict(action="restore", restore_revision=None), dict(actor="  "), dict(reason="\n")])
def test_action_shape_and_blank_identity_fail_before_save(prepared, payload):
    root, *_ = prepared
    data = request_for(root).model_dump(mode="json") | payload
    with pytest.raises(ValueError):
        store.RevisionRequest.model_validate(data)


def open_client(root):
    client = TestClient(create_app(root))
    state = client.get("/api/state").json()
    page = client.get("/record", params={"key": state["records"][0]["record_key"]})
    initial = json.loads(re.search(r'<script type="application/json" id="initial">(.*?)</script>', page.text, re.S).group(1))
    return client, initial


def test_http_editor_save_restart_history_exports_and_registered_pdf(prepared):
    root, _, bundle, _ = prepared
    client, initial = open_client(root)
    headers = {"X-Record-CSRF": initial["csrf"]}
    request = request_for(root)
    response = client.post("/api/revisions", json=request.model_dump(mode="json"), headers=headers)
    assert response.status_code == 200, response.text
    client.close()
    reopened, initial = open_client(root)
    assert initial["item"]["revision"] == 1
    assert len(initial["item"]["history"]) == 1
    assert reopened.get("/export/review.json").json()["records"][0]["revision"] == 1
    rows = list(csv.DictReader(io.StringIO(reopened.get("/export/review.csv").text)))
    assert rows[0]["composition_basis"] == "mass" and rows[0]["declared_review_status"] == "unreviewed"
    region = bundle.regions[0]
    pdf = reopened.get(f"/pdf/C1/{region.region_id}/original")
    assert pdf.status_code == 200 and pdf.content == Path(region.original_pdf_path).read_bytes()
    assert reopened.get("/pdf/C1/unknown/original").status_code == 404
    assert reopened.get(f"/pdf/C1/{region.region_id}/arbitrary").status_code == 404
    assert reopened.get("/record", params={"key": "unknown"}).status_code == 404
    reopened.close()


@pytest.mark.parametrize("failure", ["missing_token", "wrong_token", "foreign_origin", "missing_cookie"])
def test_http_write_protection_preserves_revision(prepared, failure):
    root, *_ = prepared
    client, initial = open_client(root)
    headers = {"X-Record-CSRF": initial["csrf"]}
    if failure == "missing_token":
        headers = {}
    elif failure == "wrong_token":
        headers["X-Record-CSRF"] = "bad"
    elif failure == "foreign_origin":
        headers["Origin"] = "https://unrelated.example"
    else:
        client.cookies.clear()
    response = client.post("/api/revisions", json=request_for(root).model_dump(mode="json"), headers=headers)
    assert response.status_code == 403
    assert store.load_state(root)["records"][0]["revision"] == 0
    client.close()


def test_http_stale_revision_conflict_and_evidence_resolution(prepared):
    root, _, bundle, _ = prepared
    client, initial = open_client(root)
    headers = {"X-Record-CSRF": initial["csrf"], "Origin": "http://testserver"}
    data = request_for(root).model_dump(mode="json")
    assert client.post("/api/revisions", json=data, headers=headers).status_code == 200
    assert client.post("/api/revisions", json=data, headers=headers).status_code == 409
    region = bundle.regions[0]
    payload = dict(case_id="C1", region_id=region.region_id, quote="mass", occurrence=1)
    response = client.post("/api/evidence", json=payload, headers=headers)
    assert response.status_code == 200 and response.json()["quote"] == "mass"
    payload["quote"] = "fabricated"
    assert client.post("/api/evidence", json=payload, headers=headers).status_code == 422
    assert client.get("/", headers={"Host": "foreign.example"}).status_code == 400
    client.close()


def test_html_escapes_untrusted_source_and_csv_keeps_exact_json(tmp_path):
    source = '</script><img src=x onerror="alert(1)">'
    bundle = make_bundle(tmp_path, sample=source)
    path = save_bundle(tmp_path / "input.json", bundle)
    root = tmp_path / "review"
    store.initialize_store([path], root, source_root=ROOT)
    client, initial = open_client(root)
    page = client.get("/record", params={"key": initial["item"]["record_key"]}).text
    assert source not in page and "&lt;/script&gt;&lt;img" in page
    assert "\\u003c/script>" in page and "innerHTML" not in page
    assert initial["item"]["candidate"]["sample_label"]["raw_text"] == source
    client.close()


def test_empty_bundles_remain_visible_and_initialization_refuses_existing_root(tmp_path):
    bundle = make_bundle(tmp_path).model_copy(update={"records": ()})
    path = save_bundle(tmp_path / "input.json", bundle)
    root = tmp_path / "review"
    store.initialize_store([path], root, source_root=ROOT)
    with pytest.raises(FileExistsError):
        store.initialize_store([path], root, source_root=ROOT)
    with TestClient(create_app(root)) as client:
        assert "Предложенных записей нет" in client.get("/").text
        assert client.get("/export/review.json").json()["records"] == []
        assert list(csv.DictReader(io.StringIO(client.get("/export/review.csv").text))) == []


def test_json_source_evidence_preserves_crlf_and_astral_unicode(tmp_path):
    sample = "Sample\r\n🧪 L"
    bundle = make_bundle(tmp_path, sample=sample)
    path = save_bundle(tmp_path / "input.json", bundle)
    root = tmp_path / "review"
    store.initialize_store([path], root, source_root=ROOT)
    client, initial = open_client(root)
    assert initial["item"]["candidate"]["sample_label"]["raw_text"] == sample
    region = bundle.regions[0]
    data = dict(case_id="C1", region_id=region.region_id, quote=sample, occurrence=1)
    response = client.post("/api/evidence", json=data, headers={"X-Record-CSRF": initial["csrf"]})
    assert response.status_code == 200 and response.json()["end"] - response.json()["start"] == len(sample)
    assert response.json()["quote"] == sample
    data["quote"] = sample.replace("\r\n", "\n")
    assert client.post("/api/evidence", json=data, headers={"X-Record-CSRF": initial["csrf"]}).status_code == 422
    client.close()
