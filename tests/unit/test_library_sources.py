from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

from app.db.models import Article, Collection, IngestionJob, LibrarySource, LibrarySourceFile, VectorIndexState
from app.ingestion.checksum import sha256_file
from app.library.service import (
    create_library_source,
    delete_library_source,
    list_library_sources,
    reconcile_library_source_file_statuses,
    reconcile_library_source_vector_readiness,
    scan_and_queue_library_source,
    scan_library_source,
    update_library_source,
)


class FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self) -> None:
        self.collection = Collection(id=uuid.uuid4(), name="literature", description=None)
        self.sources: list[LibrarySource] = []
        self.files: list[LibrarySourceFile] = []
        self.articles: list[Article] = []
        self.jobs: list[IngestionJob] = []
        self.vector_states: list[VectorIndexState] = []
        self.flushed = 0

    def scalar(self, statement: object) -> object | None:
        text = str(statement)
        params = _statement_params(statement)
        if "FROM collections" in text:
            name = _first_param(params, "name")
            return self.collection if name in {None, self.collection.name} else None
        if "FROM articles" in text:
            checksum = _first_param(params, "checksum_sha256")
            return next((article for article in self.articles if article.checksum_sha256 == checksum), None)
        if "FROM library_source_files" in text:
            ingestion_job_id = _first_param(params, "ingestion_job_id")
            if ingestion_job_id is not None:
                return next((row for row in self.files if row.ingestion_job_id == ingestion_job_id), None)
            external_path = _first_param(params, "external_path")
            source_id = _first_param(params, "library_source_id")
            return next(
                (
                    row
                    for row in self.files
                    if (source_id is None or row.library_source_id == source_id) and row.external_path == external_path
                ),
                None,
            )
        if "FROM library_sources" in text:
            collection_id = _first_param(params, "collection_id")
            path = _first_param(params, "path")
            return next(
                (
                    source
                    for source in self.sources
                    if (collection_id is None or source.collection_id == collection_id) and (path is None or source.path == path)
                ),
                None,
            )
        if "FROM ingestion_jobs" in text:
            checksum = _first_param(params, "checksum_sha256")
            return next((job for job in self.jobs if job.checksum_sha256 == checksum and job.status in {"queued", "processing"}), None)
        if "FROM vector_index_states" in text:
            collection_id = _first_param(params, "collection_id")
            embedding_model = _first_param(params, "embedding_model")
            return next(
                (
                    state
                    for state in self.vector_states
                    if state.collection_id == collection_id and state.embedding_model == embedding_model
                ),
                None,
            )
        return None

    def scalars(self, statement: object) -> FakeScalarResult:
        text = str(statement)
        params = _statement_params(statement)
        if "FROM library_source_files" in text:
            source_id = _first_param(params, "library_source_id")
            ingestion_job_id = _first_param(params, "ingestion_job_id")
            return FakeScalarResult(
                [
                    row
                    for row in self.files
                    if (source_id is None or row.library_source_id == source_id)
                    and (ingestion_job_id is None or row.ingestion_job_id == ingestion_job_id)
                ]
            )
        if "FROM library_sources" in text:
            return FakeScalarResult(self.sources)
        return FakeScalarResult([])

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        if model is LibrarySource:
            return next((source for source in self.sources if source.id == row_id), None)
        if model is IngestionJob:
            return next((job for job in self.jobs if job.id == row_id), None)
        return None

    def add(self, value: object) -> None:
        if isinstance(value, LibrarySource):
            self.sources.append(value)
        if isinstance(value, LibrarySourceFile):
            self.files.append(value)
        if isinstance(value, IngestionJob):
            self.jobs.append(value)

    def delete(self, value: object) -> None:
        if isinstance(value, LibrarySource):
            self.sources = [source for source in self.sources if source.id != value.id]
            self.files = [row for row in self.files if row.library_source_id != value.id]

    def flush(self) -> None:
        self.flushed += 1


def test_create_library_source_persists_normalized_folder(tmp_path) -> None:
    session = FakeSession()

    source = create_library_source(
        session,  # type: ignore[arg-type]
        SimpleNamespace(),
        name="Nafion papers",
        path=tmp_path,
        collection_name="literature",
    )

    assert source in session.sources
    assert source.collection_id == session.collection.id
    assert source.path == str(tmp_path.resolve())
    assert source.status == "active"
    assert source.recursive is True


def test_list_library_sources_returns_registered_sources(tmp_path) -> None:
    session = FakeSession()
    source = create_library_source(
        session,  # type: ignore[arg-type]
        SimpleNamespace(),
        name="Nafion papers",
        path=tmp_path,
        collection_name="literature",
    )

    assert list_library_sources(session)[0] is source  # type: ignore[arg-type]


def test_create_library_source_rejects_duplicate_collection_path(tmp_path) -> None:
    session = FakeSession()
    create_library_source(
        session,  # type: ignore[arg-type]
        SimpleNamespace(),
        name="Nafion papers",
        path=tmp_path,
        collection_name="literature",
    )

    try:
        create_library_source(  # type: ignore[arg-type]
            session,
            SimpleNamespace(),
            name="Same folder",
            path=tmp_path,
            collection_name="literature",
        )
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected duplicate library source creation to fail")


def test_scan_discovers_pdf_and_ignores_non_pdf(tmp_path) -> None:
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4\none")
    (tmp_path / "notes.txt").write_text("not a pdf")
    session = _session_with_source(tmp_path)

    result = scan_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]

    assert result.discovered == 1
    assert len(session.files) == 1
    assert session.files[0].filename == "paper.pdf"


def test_scan_access_error_preserves_existing_file_status(tmp_path, monkeypatch) -> None:
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4 fixture")
    session = _session_with_source(tmp_path)
    scan_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]
    previous_status = session.files[0].status

    def denied_walk(root, *, onerror):
        onerror(PermissionError("denied test directory"))
        return iter(())

    monkeypatch.setattr("app.library.service.os.walk", denied_walk)
    result = scan_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]
    assert result.status == "error"
    assert result.missing == 0
    assert "PermissionError" in result.error
    assert session.files[0].status == previous_status
    assert session.files[0].relative_path == "paper.pdf"
    assert session.files[0].status == "discovered"
    assert session.files[0].content_hash_sha256 is not None


def test_update_library_source_changes_flags_and_validates_path(tmp_path) -> None:
    session = _session_with_source(tmp_path)

    source = update_library_source(  # type: ignore[arg-type]
        session,
        SimpleNamespace(),
        session.sources[0].id,
        name="Renamed",
        path=tmp_path,
        collection_name="literature",
        enabled=False,
        watch_enabled=False,
        recursive=False,
    )

    assert source.name == "Renamed"
    assert source.path == str(tmp_path.resolve())
    assert source.enabled is False
    assert source.watch_enabled is False
    assert source.recursive is False
    assert source.status == "disabled"


def test_delete_library_source_removes_source_files_without_articles(tmp_path) -> None:
    session = _session_with_source(tmp_path)
    source_id = session.sources[0].id
    article = Article(
        id=uuid.uuid4(),
        collection_id=session.collection.id,
        title="paper",
        authors=None,
        year=None,
        journal=None,
        doi=None,
        abstract=None,
        language=None,
        publication_type=None,
        pdf_original_path=str(tmp_path / "paper.pdf"),
        pdf_ocr_path=None,
        source_url=None,
        access_source="manual",
        license=None,
        checksum_sha256="a" * 64,
        zotero_key=None,
        status="indexed",
    )
    session.articles.append(article)
    session.files.append(
        LibrarySourceFile(
            id=uuid.uuid4(),
            library_source_id=session.sources[0].id,
            external_path=str((tmp_path / "paper.pdf").resolve()),
            relative_path="paper.pdf",
            filename="paper.pdf",
            article_id=article.id,
            status="duplicate",
        )
    )

    payload = delete_library_source(session, source_id)  # type: ignore[arg-type]

    assert payload == {"id": str(source_id), "deleted_files": 1}
    assert session.sources == []
    assert session.files == []
    assert session.articles == [article]


def test_delete_library_source_rejects_queued_files(tmp_path) -> None:
    session = _session_with_source(tmp_path)
    session.files.append(
        LibrarySourceFile(
            id=uuid.uuid4(),
            library_source_id=session.sources[0].id,
            external_path=str((tmp_path / "paper.pdf").resolve()),
            relative_path="paper.pdf",
            filename="paper.pdf",
            status="queued",
        )
    )

    try:
        delete_library_source(session, session.sources[0].id)  # type: ignore[arg-type]
    except ValueError as exc:
        assert "queued or ingesting" in str(exc)
    else:
        raise AssertionError("Expected active library file deletion to fail")


def test_scan_missing_folder_sets_source_status(tmp_path) -> None:
    source_path = tmp_path / "missing"
    session = _session_with_source(source_path, create_folder=False)

    result = scan_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]

    assert result.status == "missing"
    assert session.sources[0].status == "missing"
    assert "unavailable" in (session.sources[0].last_error or "")


def test_scan_same_folder_twice_does_not_add_second_file(tmp_path) -> None:
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4\none")
    session = _session_with_source(tmp_path)

    first = scan_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]
    second = scan_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]

    assert first.discovered == 1
    assert second.discovered == 0
    assert second.unchanged == 1
    assert len(session.files) == 1


def test_scan_same_hash_as_existing_article_marks_duplicate(tmp_path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\none")
    session = _session_with_source(tmp_path)
    session.articles.append(
        Article(
            id=uuid.uuid4(),
            collection_id=session.collection.id,
            title="paper",
            authors=None,
            year=None,
            journal=None,
            doi=None,
            abstract=None,
            language=None,
            publication_type=None,
            pdf_original_path=str(pdf_path),
            pdf_ocr_path=None,
            source_url=None,
            access_source="manual",
            license=None,
            checksum_sha256=sha256_file(pdf_path),
            zotero_key=None,
            status="indexed",
        )
    )

    result = scan_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]

    assert result.duplicates == 1
    assert session.files[0].status == "duplicate"
    assert session.files[0].article_id == session.articles[0].id


def test_scan_and_queue_new_pdf_creates_ingestion_job(tmp_path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\none")
    session = _session_with_source(tmp_path)

    result = scan_and_queue_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]

    assert result.discovered == 1
    assert result.queued == 1
    assert len(session.jobs) == 1
    assert session.jobs[0].input_path == str(pdf_path.resolve())
    assert session.jobs[0].status == "queued"
    assert session.files[0].status == "queued"
    assert session.files[0].ingestion_job_id == session.jobs[0].id


def test_scan_and_queue_same_folder_twice_does_not_create_second_job(tmp_path) -> None:
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4\none")
    session = _session_with_source(tmp_path)

    first = scan_and_queue_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]
    second = scan_and_queue_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]

    assert first.queued == 1
    assert second.queued == 0
    assert len(session.jobs) == 1
    assert session.files[0].status == "queued"


def test_scan_and_queue_same_hash_different_name_reuses_active_job(tmp_path) -> None:
    payload = b"%PDF-1.4\nsame content"
    (tmp_path / "paper-a.pdf").write_bytes(payload)
    (tmp_path / "paper-b.pdf").write_bytes(payload)
    session = _session_with_source(tmp_path)

    result = scan_and_queue_library_source(session, SimpleNamespace(), session.sources[0].id)  # type: ignore[arg-type]

    assert result.discovered == 2
    assert result.queued == 1
    assert len(session.jobs) == 1
    assert {row.status for row in session.files} == {"queued"}
    assert {row.ingestion_job_id for row in session.files} == {session.jobs[0].id}


def test_scan_and_queue_respects_queue_limit(tmp_path) -> None:
    (tmp_path / "paper-a.pdf").write_bytes(b"%PDF-1.4\na")
    (tmp_path / "paper-b.pdf").write_bytes(b"%PDF-1.4\nb")
    session = _session_with_source(tmp_path)

    result = scan_and_queue_library_source(  # type: ignore[arg-type]
        session,
        SimpleNamespace(),
        session.sources[0].id,
        queue_limit=1,
    )

    assert result.discovered == 2
    assert result.queued == 1
    assert len(session.jobs) == 1
    assert [row.status for row in session.files].count("queued") == 1
    assert [row.status for row in session.files].count("discovered") == 1


def test_reconcile_library_source_file_status_from_ingestion_job(tmp_path) -> None:
    session = _session_with_source(tmp_path)
    article_id = uuid.uuid4()
    job_id = uuid.uuid4()
    session.jobs.append(
        IngestionJob(
            id=job_id,
            input_path=str(tmp_path / "paper.pdf"),
            collection_id=session.collection.id,
            article_id=article_id,
            original_filename="paper.pdf",
            checksum_sha256="a" * 64,
            file_size_bytes=10,
            force_ocr=False,
            status="indexed",
        )
    )
    session.files.append(
        LibrarySourceFile(
            id=uuid.uuid4(),
            library_source_id=session.sources[0].id,
            external_path=str((tmp_path / "paper.pdf").resolve()),
            relative_path="paper.pdf",
            filename="paper.pdf",
            content_hash_sha256="a" * 64,
            file_size_bytes=10,
            mtime_ns=1,
            ingestion_job_id=job_id,
            status="ingesting",
        )
    )

    updated = reconcile_library_source_file_statuses(session, job_id)  # type: ignore[arg-type]

    assert updated == 1
    assert session.files[0].status == "text_ready"
    assert session.files[0].article_id == article_id
    assert session.files[0].last_ingested_at is not None


def test_reconcile_marks_indexed_library_file_ready_when_vector_index_ready(tmp_path) -> None:
    session = _session_with_source(tmp_path)
    article_id = uuid.uuid4()
    job_id = uuid.uuid4()
    session.jobs.append(
        IngestionJob(
            id=job_id,
            input_path=str(tmp_path / "paper.pdf"),
            collection_id=session.collection.id,
            article_id=article_id,
            original_filename="paper.pdf",
            checksum_sha256="a" * 64,
            file_size_bytes=10,
            force_ocr=False,
            status="indexed",
        )
    )
    session.vector_states.append(
        VectorIndexState(
            id=uuid.uuid4(),
            collection_id=session.collection.id,
            embedding_model="test/model",
            status="ready",
            desired_revision=1,
            active_revision=1,
            active_generation_id="generation-1",
        )
    )
    session.files.append(
        LibrarySourceFile(
            id=uuid.uuid4(),
            library_source_id=session.sources[0].id,
            external_path=str((tmp_path / "paper.pdf").resolve()),
            relative_path="paper.pdf",
            filename="paper.pdf",
            ingestion_job_id=job_id,
            status="ingesting",
        )
    )

    updated = reconcile_library_source_file_statuses(  # type: ignore[arg-type]
        session,
        job_id,
        settings=SimpleNamespace(embedding_model="test/model"),
    )

    assert updated == 1
    assert session.files[0].status == "ready"


def test_reconcile_vector_readiness_demotes_ready_when_index_is_stale(tmp_path) -> None:
    session = _session_with_source(tmp_path)
    session.vector_states.append(
        VectorIndexState(
            id=uuid.uuid4(),
            collection_id=session.collection.id,
            embedding_model="test/model",
            status="stale",
            desired_revision=2,
            active_revision=1,
            active_generation_id="generation-1",
        )
    )
    session.files.append(
        LibrarySourceFile(
            id=uuid.uuid4(),
            library_source_id=session.sources[0].id,
            external_path=str((tmp_path / "paper.pdf").resolve()),
            relative_path="paper.pdf",
            filename="paper.pdf",
            article_id=uuid.uuid4(),
            status="ready",
        )
    )

    updated = reconcile_library_source_vector_readiness(  # type: ignore[arg-type]
        session,
        SimpleNamespace(embedding_model="test/model"),
    )

    assert updated == 1
    assert session.files[0].status == "text_ready"


def _session_with_source(path: Path, *, create_folder: bool = True) -> FakeSession:
    if create_folder:
        path.mkdir(exist_ok=True)
    session = FakeSession()
    session.sources.append(
        LibrarySource(
            id=uuid.uuid4(),
            name="Nafion papers",
            path=str(path.resolve()),
            collection_id=session.collection.id,
            enabled=True,
            watch_enabled=True,
            recursive=True,
            status="active",
        )
    )
    return session


def _statement_params(statement: object) -> dict[str, object]:
    return dict(statement.compile().params)  # type: ignore[attr-defined]


def _first_param(params: dict[str, object], fragment: str) -> object | None:
    for key, value in params.items():
        if fragment in key:
            return value
    return None
