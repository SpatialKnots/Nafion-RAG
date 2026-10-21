"""Verified same-machine backups of the independent full-record revision store.

Original PDF paths and historical source/code identities are never rewritten.
This is not a PostgreSQL, whole-corpus or cross-machine recovery mechanism.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from app.records.revision_store import DB_NAME, canonical, connection, digest, load_state
from app.records.sources import file_hash

VERSION = "records_backup_v0.1"
POLICY = "same_machine_original_pdf_paths_required"


def _safe(root: Path, name: str) -> Path:
    parts = PurePosixPath(name).parts
    if (not parts or str(PurePosixPath(name)) != name or PurePosixPath(name).is_absolute()
            or ".." in parts or any("\\" in p or ":" in p for p in parts)):
        raise ValueError(f"Unsafe backup path: {name}")
    path = root.joinpath(*parts)
    if any(p.is_symlink() or (p.exists() and getattr(p.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
           for p in (path, *path.parents)):
        raise ValueError(f"Linked backup path: {name}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Backup path escapes root: {name}")
    return path


def _inventory(root: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in root.rglob("*"):
        name = path.relative_to(root).as_posix()
        _safe(root, name)
        if path.is_file():
            result[name] = {"sha256": file_hash(path), "bytes": path.stat().st_size}
    return result


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental replacement of any prior artifact.
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)


def create_backup(root: Path, destination: Path) -> dict[str, Any]:
    """Capture a consistent SQLite snapshot, frozen context and registered PDFs."""
    if destination.exists():
        raise FileExistsError(f"Backup destination already exists: {destination}")
    if destination.resolve().is_relative_to(root.resolve()):
        raise ValueError("Backup destination must be outside the review store")
    _safe(destination, "store")
    # Verify live context first, then verify the captured DB against copied context.
    load_state(root)
    source_files = {"snapshot.json": file_hash(_safe(root, "snapshot.json"))}
    source_files.update({f"baseline/{name}": row["sha256"] for name, row in _inventory(root / "baseline").items()})
    destination.mkdir(parents=True, exist_ok=False)
    store = destination / "store"
    store.mkdir()
    with connection(root) as source:
        target_db = sqlite3.connect(store / DB_NAME)
        try:
            source.backup(target_db)
            if target_db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite backup integrity check failed")
            target_db.execute("PRAGMA journal_mode=DELETE")
        finally:
            target_db.close()
    for name, expected in source_files.items():
        _copy(_safe(root, name), _safe(store, name))
        if file_hash(store / name) != expected or file_hash(root / name) != expected:
            raise ValueError(f"Review context changed during backup: {name}")
    state = load_state(store)
    pdfs = json.loads((store / "baseline/manifest.json").read_bytes())["pdfs"]
    registry = []
    for pdf in pdfs:
        original = Path(pdf["path"])
        name = f"pdfs/{pdf['sha256']}.pdf"
        target = _safe(destination, name)
        if not target.exists():
            _copy(original, target)
        if file_hash(target) != pdf["sha256"] or file_hash(original) != pdf["sha256"]:
            raise ValueError(f"Source PDF changed during backup: {original}")
        registry.append({"original_path": str(original), "copy": name, "sha256": pdf["sha256"]})
    manifest = {"version": VERSION, "created_at": datetime.now(UTC).isoformat(), "restore_policy": POLICY,
                "snapshot_id": state["snapshot_id"], "state_sha256": digest(canonical(state)),
                "records": len(state["records"]), "events": sum(len(r["history"]) for r in state["records"]),
                "pdfs": registry, "files": _inventory(destination)}
    raw = canonical(manifest)
    with (destination / "manifest.json").open("xb") as stream:
        stream.write(raw)
    checksum = digest(raw)
    verify_backup(destination, checksum)
    return {"destination": str(destination), "manifest_sha256": checksum,
            "snapshot_id": manifest["snapshot_id"], "records": manifest["records"], "events": manifest["events"],
            "pdf_paths": len(registry), "restore_policy": POLICY}


def verify_backup(root: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    """Verify bytes offline; the manifest digest must be kept separately."""
    raw = _safe(root, "manifest.json").read_bytes()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) or digest(raw) != expected_manifest_sha256:
        raise ValueError("Backup manifest checksum mismatch")
    manifest: dict[str, Any] = json.loads(raw)
    if manifest["version"] != VERSION or manifest["restore_policy"] != POLICY:
        raise ValueError("Unsupported backup version or restore policy")
    for name in manifest["files"]:
        _safe(root, name)
        if name not in {f"store/{DB_NAME}", "store/snapshot.json"} and not name.startswith(("store/baseline/", "pdfs/")):
            raise ValueError(f"Unexpected backup member: {name}")
    actual = _inventory(root)
    actual.pop("manifest.json")
    if actual != manifest["files"]:
        raise ValueError("Backup file inventory/checksum mismatch")
    # Cross-check the PDF registry against the immutable baseline, not merely itself.
    baseline = json.loads(_safe(root, "store/baseline/manifest.json").read_bytes())
    expected = [{"original_path": p["path"], "copy": f"pdfs/{p['sha256']}.pdf", "sha256": p["sha256"]}
                for p in baseline["pdfs"]]
    if manifest["pdfs"] != expected:
        raise ValueError("Backup PDF registry differs from baseline")
    for pdf in expected:
        if file_hash(_safe(root, pdf["copy"])) != pdf["sha256"]:
            raise ValueError("Backup PDF checksum mismatch")
    return manifest


def restore_backup(backup: Path, destination: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    """Restore into a fresh directory; never replace original PDFs or a live DB."""
    if destination.exists():
        raise FileExistsError(f"Restore destination already exists: {destination}")
    if destination.resolve().is_relative_to(backup.resolve()):
        raise ValueError("Restore destination must be outside the backup")
    _safe(destination, DB_NAME)
    manifest = verify_backup(backup, expected_manifest_sha256)
    for pdf in manifest["pdfs"]:
        path = Path(pdf["original_path"])
        if not path.is_file() or file_hash(path) != pdf["sha256"]:
            raise ValueError(f"Original PDF missing/changed at registered path; automatic PDF replacement is disabled: {path}")
    # Only create the destination after the package and source paths are verified.
    destination.mkdir(parents=True, exist_ok=False)
    for name in manifest["files"]:
        if name.startswith("store/"):
            _copy(_safe(backup, name), _safe(destination, name.removeprefix("store/")))
    state = load_state(destination)
    if state["snapshot_id"] != manifest["snapshot_id"] or digest(canonical(state)) != manifest["state_sha256"]:
        raise ValueError("Restored revision state differs from captured state (including code context)")
    # Detect a package change while it was being copied as well.
    verify_backup(backup, expected_manifest_sha256)
    return {"destination": str(destination), "snapshot_id": state["snapshot_id"], "records": len(state["records"]),
            "events": sum(len(r["history"]) for r in state["records"]), "state_sha256": manifest["state_sha256"],
            "stale_code": state["stale_code"], "restore_policy": POLICY}
