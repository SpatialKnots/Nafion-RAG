import json
from pathlib import Path

import pytest

from scripts.freeze_baseline import ROOT_FILES, digest, safe_path, selected_paths, verify


@pytest.mark.parametrize("name", ["../.env", "/outside", "C:/outside", "app/../../.env", "app\\..\\.env"])
def test_snapshot_rejects_escaping_paths(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError):
        safe_path(tmp_path, name)


def test_snapshot_accepts_nested_relative_path(tmp_path: Path) -> None:
    assert safe_path(tmp_path, "app/facts/review_store.py") == tmp_path / "app" / "facts" / "review_store.py"


def minimal_snapshot(root: Path) -> Path:
    source = root / "source"
    source.mkdir()
    raw = b"synthetic snapshot test fixture"
    (source / "fixture.py").write_bytes(raw)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "files": [{"path": "fixture.py", "size": len(raw), "sha256": digest(raw)}],
                "artifacts": {},
                "source_fingerprint": "synthetic",
            }
        ),
        encoding="utf-8",
    )
    return source


def test_snapshot_detects_modified_source(tmp_path: Path) -> None:
    source = minimal_snapshot(tmp_path)
    (source / "fixture.py").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify(tmp_path)


def test_snapshot_detects_unlisted_secret_file(tmp_path: Path) -> None:
    source = minimal_snapshot(tmp_path)
    (source / ".env").write_text("SYNTHETIC_SECRET=fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory mismatch"):
        verify(tmp_path)


def test_snapshot_includes_runtime_assets_without_private_data_or_caches(tmp_path: Path) -> None:
    for name in ROOT_FILES:
        (tmp_path / name).write_text("fixture", encoding="utf-8")
    assets = [
        "app/terms/taxonomy_v04.json", "app/static/terms_review.js",
        "scripts/terms_graph/template.html", "scripts/terms_graph/graph.js", "scripts/terms_graph/graph.css",
    ]
    excluded = [".env", "data/private.json", "output/diagram.html", "app/__pycache__/fixture.py"]
    for name in assets + excluded:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    names = set(selected_paths(tmp_path))
    assert set(assets).issubset(names)
    assert not set(excluded) & names
