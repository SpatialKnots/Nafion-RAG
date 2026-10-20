"""Synthetic persistence, stale-source, concurrency, restore and HTTP review safety tests."""
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.terms.review_bundle import automatic_graph_view, backup, graph_view, render_table, restore
from app.terms.review_projection import project_review, review_queue
from app.terms.review_store import (
    SCHEMA,
    Decision,
    ReviewConflict,
    code_hashes,
    connection,
    history,
    latest,
    load_snapshot,
    register_snapshot,
    save_decision,
    sha,
    snapshot_diff,
)
from scripts.tac_review_html import render_table as make_table
from scripts.tac_term_classification import DEFAULT_TAXONOMY, build_classification
from scripts.tac_terms_graph import ASSETS, attach_classification, project_graph
from scripts.terms_review_server import create_app
from tests.unit.test_term_contexts import inputs, sidecar


def prepared(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    snapshot, profiles, metadata, terms = inputs(source_root)
    contexts = sidecar(snapshot, profiles, terms)
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_bytes())
    classes = build_classification(contexts, taxonomy, "d" * 64, "b" * 64)
    classes["taxonomy_content_sha256"] = sha(json.dumps(taxonomy, sort_keys=True, ensure_ascii=False).encode())
    graph = project_graph(snapshot, profiles, contexts, source_root)
    attach_classification(graph, contexts, classes, "d" * 64)
    graph["provenance"] = {"input_sha256": {"fixture": "a" * 64}}
    table = make_table(snapshot, profiles, metadata, source_root, terms["profiles_sha256"], terms=terms,
                       terms_sha256="e" * 64, term_contexts=contexts, term_contexts_sha256="d" * 64,
                       classification=classes)
    paths = {s[key] for a in graph["articles"] for m in a["mentions"] for s in [m["source"]]
             for key in ("original_pdf_path", "layer_pdf_path")}
    data = {"schema": SCHEMA, "graph": graph, "source_root": str(source_root), "table_html": table,
            "input_sha256": graph["provenance"]["input_sha256"], "policy_code_sha256": code_hashes(),
            "assets": {sha(name.encode()): {"path": name, "sha256": sha((source_root / name).read_bytes())} for name in paths},
            "viewer_assets": {name: (ASSETS / name).read_text(encoding="utf-8") for name in ("graph.js", "graph.css", "template.html")}}
    root = tmp_path / "review"
    sid = register_snapshot(root, data)
    target = next(a for a in graph["articles"][0]["assignments"] if a["axis"] == "type" and a["proposals"])
    return root, sid, data, target


def request(sid, target, **fields):
    defaults = dict(snapshot_id=sid, target_kind="classification", target_id=target["assignment_id"], expected_revision=0,
                    action="confirm", categories=[target["proposals"][0]["category"]], reason="Synthetic source review",
                    reviewer="fixture", reviewer_kind="assistant")
    return Decision(**(defaults | fields))


def test_decisions_survive_restart_correct_restore_and_replay_cutoff(tmp_path):
    root, sid, data, target = prepared(tmp_path)
    initial = deepcopy(data)
    first = save_decision(root, request(sid, target))
    save_decision(root, request(sid, target, action="correct", categories=["process"], expected_revision=1))
    assert latest(Path(str(root)), sid)[f'classification:{target["assignment_id"]}']["categories"] == ["process"]
    saved = save_decision(root, request(sid, target, action="restore", categories=[], expected_revision=2, restore_revision=1))
    assert saved["revision"] == 3 and saved["categories"] == first["categories"]
    assert len(history(root, sid)) == 3
    expected = project_review(data["graph"], latest(root, sid, first["event_id"]), sid, first["event_id"])
    assert graph_view(root, sid, cutoff=first["event_id"])[1] == expected
    assert data == initial
    assert load_snapshot(root, sid)[1] == initial
    with connection(root) as conn, pytest.raises(sqlite3.IntegrityError, match="Immutable"):
        conn.execute("DELETE FROM events")


def test_real_concurrent_writes_prevent_lost_updates(tmp_path):
    root, sid, _, target = prepared(tmp_path)
    def write():
        try:
            return save_decision(root, request(sid, target))["revision"]
        except ReviewConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write(), range(2)))
    assert sorted(map(str, results)) == ["1", "conflict"]
    assert len(history(root, sid)) == 1


@pytest.mark.parametrize("mutation", ["snapshot", "source", "code", "new_current"])
def test_changed_sources_code_and_snapshot_never_accept_decision(tmp_path, monkeypatch, mutation):
    root, sid, data, target = prepared(tmp_path)
    if mutation == "snapshot":
        (root / "snapshots" / f"{sid}.json").write_text("{}")
    elif mutation == "source":
        asset = next(iter(data["assets"].values()))
        (Path(data["source_root"]) / asset["path"]).write_bytes(b"changed fixture PDF")
    elif mutation == "code":
        monkeypatch.setattr("app.terms.review_store.code_hashes", lambda: {"changed": "f" * 64})
    else:
        changed = deepcopy(data)
        changed["input_sha256"]["fixture"] = "b" * 64
        register_snapshot(root, changed)
        delta = snapshot_diff(root, sid, data)
        assert delta["changed_inputs"]["fixture"]["current"] == "b" * 64
        assert delta["automatic_decision_reuse"] is False
    with pytest.raises(ReviewConflict):
        save_decision(root, request(sid, target))
    assert history(root, sid) == []


@pytest.mark.parametrize("fields", [{"target_id": "f" * 64}, {"categories": ["unknown_category"]},
                                     {"action": "reject"}, {"reason": " "}, {"reviewer": " "},
                                     {"action": "restore", "restore_revision": 99, "categories": []}])
def test_invalid_targets_and_decisions_are_rejected(tmp_path, fields):
    root, sid, _, target = prepared(tmp_path)
    with pytest.raises(ValueError):
        save_decision(root, request(sid, target, **fields))
    assert history(root, sid) == []


def test_axes_and_relevance_are_independent_and_rejected_candidates_remain_visible(tmp_path):
    root, sid, data, target = prepared(tmp_path)
    save_decision(root, request(sid, target, action="correct", categories=["process"]))
    graph = graph_view(root, sid)[1]
    term = next(t for t in graph["articles"][0]["terms"] if t["term_id"] == target["term_id"])
    assert "process" in term["memberships"]["type"] and "unclassified" in term["memberships"]["role"]
    save_decision(root, request(sid, target, target_kind="relevance", target_id=term["term_id"], action="reject", categories=[]))
    effective = graph_view(root, sid)[1]
    rejected = next(t for t in effective["articles"][0]["terms"] if t["term_id"] == term["term_id"])
    assert rejected["memberships"]["type"] == ["term_rejected"]
    raw = graph_view(root, sid, "proposals")[1]
    assert len(raw["articles"][0]["terms"]) == len(data["graph"]["articles"][0]["terms"])
    assert "term_rejected" not in next(t for t in raw["articles"][0]["terms"] if t["term_id"] == term["term_id"])["memberships"]["type"]


def test_backup_restore_preserves_history_views_and_refuses_overwrite(tmp_path):
    root, sid, _, target = prepared(tmp_path)
    save_decision(root, request(sid, target))
    archive = tmp_path / "backup.zip"
    backup(root, archive)
    restored = tmp_path / "restored"
    restore(archive, restored)
    assert history(root) == history(restored)
    assert graph_view(root, sid)[1] == graph_view(restored, sid)[1]
    with pytest.raises(FileExistsError):
        restore(archive, restored)


def test_tampered_backup_is_rejected_before_writing(tmp_path):
    root, _, _, _ = prepared(tmp_path)
    archive = tmp_path / "backup.zip"
    backup(root, archive)
    damaged = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(damaged, "w") as target:
        for name in source.namelist():
            raw = source.read(name)
            target.writestr(name, raw + b"damaged" if name.endswith(".sqlite3") else raw)
    destination = tmp_path / "bad_restore"
    with pytest.raises(ValueError, match="checksum"):
        restore(damaged, destination)
    assert not destination.exists()


def test_http_manual_decisions_disabled_and_archive_does_not_change_automatic_subsets(tmp_path):
    root, sid, data, target = prepared(tmp_path)
    client = TestClient(create_app(root), base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
    response = client.get("/ui/terms-review")
    assert response.status_code == 200
    assert client.cookies.get("terms_review_csrf") is None
    assert 'id: "terms-auto-bar"' in response.text
    assert 'id:"review-save"' not in response.text
    body = request(sid, target, reason='<script>alert("unsafe")</script>').model_dump(mode="json")
    for action in ("confirm", "correct", "reject", "uncertain", "restore"):
        assert client.post("/ui/terms-review/decision", json=body | {"action": action}).status_code == 410
    assert history(root, sid) == []
    # Existing archival fixtures remain readable, but never drive the live subsets.
    saved = save_decision(root, request(sid, target, action="correct", categories=["process"], reason=body["reason"]))
    prior_history = history(root, sid)
    remote = TestClient(create_app(root), base_url="http://127.0.0.1", client=("192.0.2.1", 50000))
    assert remote.post("/ui/terms-review/decision", json=body).status_code == 410
    assert client.post("/ui/terms-review/decision", content=b"invalid JSON").status_code == 410
    state = client.get(f"/ui/terms-review/state?snapshot={sid}").json()
    assert state["workflow_mode"] == "automatic" and state["manual_decisions_enabled"] is False
    assert state["decisions"] == {} and state["events"] == [] and state["revision_cutoff"] == 0
    automatic = automatic_graph_view(root, sid)[1]
    changed = next(a for a in automatic["articles"][0]["assignments"] if a["assignment_id"] == target["assignment_id"])
    assert changed["review_decision"] is None
    term = next(t for t in automatic["articles"][0]["terms"] if t["term_id"] == target["term_id"])
    assert "process" not in term["memberships"]["type"]
    exported = client.get(f"/ui/terms-review/export?snapshot={sid}").json()
    assert exported["events"][0]["reviewer_kind"] == "assistant" and exported["independent_acceptance"] is False
    table = client.get(f"/ui/terms-review/table?snapshot={sid}")
    assert table.status_code == 200 and table.text.count("<th>") == 8
    assert 'class="review-event"' not in table.text
    assert '<script>alert("unsafe")</script>' not in table.text
    assert client.get(f"/ui/terms-review/table?snapshot={sid}&cutoff={saved['event_id']}").status_code == 422
    asset = next(iter(data["assets"]))
    assert client.get(f"/ui/terms-review/asset?snapshot={sid}&asset={asset}").status_code == 200
    assert client.get(f"/ui/terms-review/asset?snapshot={sid}&asset=../../secret").status_code == 409
    assert render_table(data, sid, latest(root, sid), 1).count('<p class="review-event">') == 1
    assert "&lt;script&gt;" in render_table(data, sid, latest(root, sid), 1)
    assert history(root, sid) == prior_history
    assert review_queue(data["graph"], latest(root, sid), state="all")
