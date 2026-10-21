"""Synthetic recovery checks; no scientific confirmations or production writes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.records.backup import create_backup, restore_backup, verify_backup
from app.records.revision_store import DB_NAME, canonical, digest, initialize_store, load_state, save_revision
from tests.unit.test_record_checks_export import ROOT, make_bundle, save_bundle
from tests.unit.test_record_revisions import request_for


@pytest.fixture
def prepared(tmp_path):
    bundle = make_bundle(tmp_path, ocr=True)
    root = tmp_path / "review"
    initialize_store([save_bundle(tmp_path / "input.json", bundle)], root, source_root=ROOT)
    save_revision(root, request_for(root))
    save_revision(root, request_for(root, action="restore", restore_revision=0))
    return root, bundle


def test_roundtrip_preserves_history_exact_sources_and_unreviewed_status(prepared, tmp_path):
    root, bundle = prepared
    before = load_state(root)
    backup = tmp_path / "backup"
    receipt = create_backup(root, backup)
    manifest = verify_backup(backup, receipt["manifest_sha256"])
    assert receipt["events"] == 2
    assert manifest["state_sha256"] == digest(canonical(before))
    for entry in manifest["pdfs"]:
        assert (backup / entry["copy"]).read_bytes() == Path(entry["original_path"]).read_bytes()
    restored = tmp_path / "restored"
    result = restore_backup(backup, restored, receipt["manifest_sha256"])
    assert load_state(restored) == before == load_state(root)
    assert result["events"] == 2 and not result["stale_code"]
    assert load_state(restored)["records"][0]["declared_review_status"] == "unreviewed"
    # Captured baseline input copies are sufficient; the external input JSON can disappear.
    (tmp_path / "input.json").unlink()
    assert load_state(restored) == before
    assert Path(bundle.regions[0].original_pdf_path).is_file()


def test_online_backup_contains_committed_wal_and_excludes_later_events(prepared, tmp_path):
    root, _ = prepared
    writer = sqlite3.connect(root / DB_NAME)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        save_revision(root, request_for(root, action="decide", decision="needs_changes"))
        receipt = create_backup(root, tmp_path / "backup")
        save_revision(root, request_for(root, action="decide", decision="unreviewed"))
        restored = tmp_path / "restored"
        restore_backup(tmp_path / "backup", restored, receipt["manifest_sha256"])
        assert len(load_state(root)["records"][0]["history"]) == 4
        assert len(load_state(restored)["records"][0]["history"]) == 3
        assert load_state(restored)["records"][0]["declared_review_status"] == "needs_changes"
        assert not list((tmp_path / "backup").rglob("*-wal"))
    finally:
        writer.close()


@pytest.mark.parametrize("member", ["store/record_revisions.sqlite3", "store/snapshot.json", "store/baseline/table.json", "pdf"])
def test_changed_backup_bytes_fail_before_restore(prepared, tmp_path, member):
    root, _ = prepared
    backup = tmp_path / "backup"
    receipt = create_backup(root, backup)
    manifest = verify_backup(backup, receipt["manifest_sha256"])
    path = backup / (manifest["pdfs"][0]["copy"] if member == "pdf" else member)
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="inventory/checksum"):
        restore_backup(backup, tmp_path / "restored", receipt["manifest_sha256"])
    assert not (tmp_path / "restored").exists()


def test_rewritten_manifest_requires_separate_original_digest(prepared, tmp_path):
    root, _ = prepared
    receipt = create_backup(root, tmp_path / "backup")
    path = tmp_path / "backup/manifest.json"
    data = json.loads(path.read_bytes())
    data["events"] = 0
    path.write_bytes(canonical(data))
    with pytest.raises(ValueError, match="manifest checksum"):
        verify_backup(path.parent, receipt["manifest_sha256"])


@pytest.mark.parametrize("member", ["../escape", "/absolute", "C:/drive", "store\\wrong", "store/../wrong", "store//wrong"])
def test_unsafe_member_rejected_even_with_matching_manifest_digest(prepared, tmp_path, member):
    root, _ = prepared
    create_backup(root, tmp_path / "backup")
    path = tmp_path / "backup/manifest.json"
    data = json.loads(path.read_bytes())
    data["files"][member] = {"sha256": "0" * 64, "bytes": 0}
    raw = canonical(data)
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="Unsafe backup path"):
        verify_backup(path.parent, digest(raw))


def test_missing_original_pdf_fails_without_automatic_replacement(prepared, tmp_path):
    root, bundle = prepared
    backup = tmp_path / "backup"
    receipt = create_backup(root, backup)
    original = Path(bundle.regions[0].original_pdf_path)
    original.unlink()  # Only a generated synthetic fixture, never a corpus PDF.
    # Package verification is independent of external source paths.
    verify_backup(backup, receipt["manifest_sha256"])
    with pytest.raises(ValueError, match="Original PDF missing/changed"):
        restore_backup(backup, tmp_path / "restored", receipt["manifest_sha256"])
    assert not original.exists() and not (tmp_path / "restored").exists()


def test_changed_pdf_rejected_and_existing_directories_never_overwritten(prepared, tmp_path):
    root, bundle = prepared
    backup = tmp_path / "backup"
    receipt = create_backup(root, backup)
    with pytest.raises(FileExistsError):
        create_backup(root, backup)
    with pytest.raises(FileExistsError):
        restore_backup(backup, root, receipt["manifest_sha256"])
    with pytest.raises(ValueError, match="outside"):
        create_backup(root, root / "nested")
    with pytest.raises(ValueError, match="outside"):
        restore_backup(backup, backup / "nested", receipt["manifest_sha256"])
    Path(bundle.regions[0].layer_pdf_path).write_bytes(b"changed synthetic PDF")
    with pytest.raises(ValueError, match="Original PDF missing/changed"):
        restore_backup(backup, tmp_path / "restored", receipt["manifest_sha256"])


def test_unlisted_file_and_missing_manifest_are_not_valid_backups(prepared, tmp_path):
    root, _ = prepared
    backup = tmp_path / "backup"
    receipt = create_backup(root, backup)
    (backup / "extra").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="inventory/checksum"):
        verify_backup(backup, receipt["manifest_sha256"])
    (backup / "manifest.json").unlink()
    with pytest.raises(FileNotFoundError):
        verify_backup(backup, receipt["manifest_sha256"])
