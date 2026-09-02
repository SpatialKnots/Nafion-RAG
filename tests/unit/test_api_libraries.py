from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import main
from app.db.models import Collection, LibrarySource, LibrarySourceFile
from app.library.schemas import LibrarySourceCreateRequest, LibrarySourceUpdateRequest


class FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self) -> None:
        self.collection = Collection(id=uuid.uuid4(), name="literature", description=None)
        self.source = LibrarySource(
            id=uuid.uuid4(),
            name="Library",
            path="D:\\Research\\Papers",
            collection_id=self.collection.id,
            enabled=True,
            watch_enabled=True,
            recursive=True,
            status="active",
        )
        self.file = LibrarySourceFile(
            id=uuid.uuid4(),
            library_source_id=self.source.id,
            external_path="D:\\Research\\Papers\\paper.pdf",
            relative_path="paper.pdf",
            filename="paper.pdf",
            content_hash_sha256="a" * 64,
            file_size_bytes=10,
            mtime_ns=1,
            status="queued",
        )
        self.sources = [self.source]
        self.files = [self.file]
        self.commits = 0

    def scalar(self, statement: object) -> object | None:
        text = str(statement)
        params = dict(statement.compile().params)  # type: ignore[attr-defined]
        if "FROM collections" in text:
            return self.collection
        if "FROM library_sources" in text:
            collection_id = _first_param(params, "collection_id")
            path = _first_param(params, "path")
            if collection_id == self.source.collection_id and path == self.source.path:
                return self.source
        if "FROM library_source_files" in text:
            job_id = _first_param(params, "ingestion_job_id")
            if job_id is not None:
                return None
        return None

    def scalars(self, statement: object) -> FakeScalarResult:
        text = str(statement)
        if "FROM library_source_files" in text:
            return FakeScalarResult(self.files)
        if "FROM library_sources" in text:
            return FakeScalarResult(self.sources)
        return FakeScalarResult([])

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        if model is LibrarySource and row_id == self.source.id:
            return self.source
        return None

    def add(self, value: object) -> None:
        if isinstance(value, LibrarySource):
            self.sources.append(value)

    def delete(self, value: object) -> None:
        if value is self.source:
            self.sources.remove(self.source)
            self.files.clear()

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1


def test_libraries_api_lists_sources() -> None:
    payload = main.libraries(FakeSession())  # type: ignore[arg-type]

    assert payload["items"][0]["id"]
    assert payload["items"][0]["name"] == "Library"
    assert payload["items"][0]["status"] == "active"


def test_create_library_api_persists_source(monkeypatch, tmp_path) -> None:
    session = FakeSession()
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace())

    payload = main.create_library(
        session,  # type: ignore[arg-type]
        LibrarySourceCreateRequest(name="New library", path=str(tmp_path), collection="literature", recursive=False),
    )

    assert payload["name"] == "New library"
    assert payload["path"] == str(tmp_path.resolve())
    assert payload["recursive"] is False
    assert session.commits == 1


def test_create_library_api_rejects_missing_folder(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace())

    with pytest.raises(HTTPException) as exc_info:
        main.create_library(  # type: ignore[arg-type]
            FakeSession(),
            LibrarySourceCreateRequest(name="Missing", path=str(tmp_path / "missing"), collection="literature"),
        )

    assert exc_info.value.status_code == 400
    assert "unavailable" in str(exc_info.value.detail)


def test_create_library_api_rejects_duplicate_source(monkeypatch, tmp_path) -> None:
    session = FakeSession()
    session.source.path = str(tmp_path.resolve())
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace())

    with pytest.raises(HTTPException) as exc_info:
        main.create_library(  # type: ignore[arg-type]
            session,
            LibrarySourceCreateRequest(name="Duplicate", path=session.source.path, collection="literature"),
        )

    assert exc_info.value.status_code == 400
    assert "already exists" in str(exc_info.value.detail)


def test_update_library_api_can_disable_source(monkeypatch, tmp_path) -> None:
    session = FakeSession()
    session.source.path = str(tmp_path)
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace())

    payload = main.update_library(  # type: ignore[arg-type]
        session,
        session.source.id,
        LibrarySourceUpdateRequest(enabled=False, watch_enabled=False, recursive=False),
    )

    assert payload["enabled"] is False
    assert payload["watch_enabled"] is False
    assert payload["recursive"] is False
    assert payload["status"] == "disabled"
    assert session.commits == 1


def test_library_files_api_lists_discovered_files() -> None:
    session = FakeSession()

    payload = main.library_files(session, session.source.id)  # type: ignore[arg-type]

    assert payload["items"][0]["filename"] == "paper.pdf"
    assert payload["items"][0]["status"] == "queued"


def test_library_files_api_accepts_status_filter() -> None:
    session = FakeSession()
    session.file.status = "failed"

    payload = main.library_files(session, session.source.id, status="failed")  # type: ignore[arg-type]

    assert payload["items"][0]["filename"] == "paper.pdf"


def test_delete_library_api_removes_source_and_files() -> None:
    session = FakeSession()
    session.file.status = "duplicate"

    payload = main.delete_library(session, session.source.id)  # type: ignore[arg-type]

    assert payload == {"id": str(session.source.id), "deleted_files": 1}
    assert session.sources == []
    assert session.files == []
    assert session.commits == 1


def test_delete_library_api_rejects_active_file() -> None:
    session = FakeSession()

    with pytest.raises(HTTPException) as exc_info:
        main.delete_library(session, session.source.id)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 400
    assert "queued or ingesting" in str(exc_info.value.detail)


def test_library_scan_api_commits_scan(monkeypatch) -> None:
    session = FakeSession()
    library_id = session.source.id
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        main,
        "scan_and_queue_library_source",
        lambda active_session, settings, active_library_id: SimpleNamespace(
            library_source_id=str(active_library_id),
            discovered=1,
            unchanged=0,
            duplicates=0,
            missing=0,
            queued=1,
            status="active",
            error=None,
        ),
    )

    payload = main.library_scan(session, library_id)  # type: ignore[arg-type]

    assert payload["library_source_id"] == str(library_id)
    assert payload["queued"] == 1
    assert session.commits == 1


def test_unknown_library_returns_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        main.library_detail(FakeSession(), uuid.uuid4())  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404


def _first_param(params: dict[str, object], fragment: str) -> object | None:
    for key, value in params.items():
        if fragment in key:
            return value
    return None
