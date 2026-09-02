from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.ingestion.queue import claim_next_job, enqueue_upload, job_to_response, process_claimed_job, recover_stale_jobs
from app.ingestion.service import IngestionResult
from app.ingestion.upload import StagedUpload


class FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self) -> None:
        self.collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
        self.duplicate = None
        self.active = None
        self.queued: list[object] = []
        self.added: list[object] = []

    def scalar(self, statement: object) -> object | None:
        text = str(statement)
        if "FROM collections" in text:
            return self.collection
        if "FROM articles" in text:
            return self.duplicate
        if "IN (__[POSTCOMPILE_status_1])" in text:
            return self.active
        if "ingestion_jobs.status = :status_1" in text:
            return self.queued[0] if self.queued else None
        return None

    def scalars(self, statement: object) -> FakeScalarResult:
        if "FROM library_source_files" in str(statement):
            return FakeScalarResult([])
        return FakeScalarResult(self.queued)

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None


def test_enqueue_valid_upload_creates_queued_job_and_moves_file(tmp_path) -> None:
    staged_path = tmp_path / "incoming.part"
    staged_path.write_bytes(b"%PDF-1.4\n")
    staged = StagedUpload(path=staged_path, original_filename="paper.pdf", checksum_sha256="a" * 64, file_size_bytes=9)
    settings = SimpleNamespace(data_root=tmp_path / "data")
    session = FakeSession()

    job = enqueue_upload(session, settings, staged, "literature")  # type: ignore[arg-type]

    assert job.status == "queued"
    assert Path(job.input_path).is_file()
    assert not staged_path.exists()
    assert job.original_filename == "paper.pdf"


def test_enqueue_duplicate_returns_terminal_job_and_deletes_staged(tmp_path) -> None:
    staged_path = tmp_path / "incoming.part"
    staged_path.write_bytes(b"%PDF-1.4\n")
    article_id = uuid.uuid4()
    staged = StagedUpload(path=staged_path, original_filename="paper.pdf", checksum_sha256="a" * 64, file_size_bytes=9)
    session = FakeSession()
    session.duplicate = SimpleNamespace(id=article_id)

    job = enqueue_upload(session, SimpleNamespace(data_root=tmp_path / "data"), staged, "literature")  # type: ignore[arg-type]

    assert job.status == "duplicate"
    assert job.article_id == article_id
    assert not staged_path.exists()
    assert job_to_response(job)["article_url"] == f"/ui/articles/{article_id}"


def test_job_response_sanitizes_internal_error_paths() -> None:
    job = SimpleNamespace(
        id=uuid.uuid4(),
        status="failed",
        collection_id=uuid.uuid4(),
        article_id=None,
        original_filename="bad.pdf",
        checksum_sha256="a" * 64,
        file_size_bytes=10,
        force_ocr=False,
        attempt_count=1,
        worker_id="worker",
        error_type="RuntimeError",
        error_message="OCR completed but output still lacks a usable text layer: data\\processed\\ocr\\bad.pdf",
        created_at=None,
        updated_at=None,
        started_at=None,
        finished_at=None,
    )

    payload = job_to_response(job)

    assert payload["error_message"] == "Ingestion failed during PDF processing. See local logs for details."


def test_claim_next_job_sets_processing_and_attempt() -> None:
    session = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        status="queued",
        worker_id=None,
        attempt_count=0,
        started_at=None,
        heartbeat_at=None,
        updated_at=None,
        created_at=datetime.now(UTC),
    )
    session.queued = [job]

    claimed = claim_next_job(session, SimpleNamespace(ingestion_lease_seconds=1200, ingestion_max_attempts=3), "worker-1")  # type: ignore[arg-type]

    assert claimed is job
    assert job.status == "processing"
    assert job.worker_id == "worker-1"
    assert job.attempt_count == 1
    assert job.heartbeat_at is not None


def test_recover_stale_job_requeues_before_max_attempts() -> None:
    old = datetime.now(UTC) - timedelta(seconds=2000)
    job = SimpleNamespace(
        status="processing",
        heartbeat_at=old,
        attempt_count=1,
        worker_id="old-worker",
        updated_at=None,
        finished_at=None,
        error_type=None,
        error_message=None,
        created_at=old,
    )
    session = FakeSession()
    session.queued = [job]

    recovered = recover_stale_jobs(session, SimpleNamespace(ingestion_lease_seconds=1200, ingestion_max_attempts=3))  # type: ignore[arg-type]

    assert recovered == 1
    assert job.status == "queued"
    assert job.worker_id is None


def test_process_claimed_library_job_preserves_external_pdf(monkeypatch, tmp_path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\none")
    collection_id = uuid.uuid4()
    article_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        input_path=str(pdf_path),
        collection_id=collection_id,
        article_id=None,
        checksum_sha256=None,
        file_size_bytes=None,
        force_ocr=False,
        status="processing",
        error_type=None,
        error_message=None,
        finished_at=None,
        updated_at=None,
    )
    library_file = SimpleNamespace(
        ingestion_job_id=job.id,
        status="ingesting",
        article_id=None,
        content_hash_sha256=None,
        file_size_bytes=None,
        last_error=None,
        last_ingested_at=None,
        updated_at=None,
    )

    class LibrarySession:
        def scalar(self, statement: object) -> object | None:
            if "FROM library_source_files" in str(statement):
                return library_file
            return None

        def scalars(self, statement: object) -> FakeScalarResult:
            if "FROM library_source_files" in str(statement):
                return FakeScalarResult([library_file])
            return FakeScalarResult([])

        def get(self, model: object, row_id: object) -> object | None:
            if row_id == collection_id:
                return SimpleNamespace(id=collection_id, name="literature")
            if row_id == job.id:
                return job
            return None

        def flush(self) -> None:
            return None

    monkeypatch.setattr(
        "app.ingestion.queue.process_pdf",
        lambda *args, **kwargs: IngestionResult(
            article_id=str(article_id),
            status="indexed",
            checksum_sha256="a" * 64,
            page_count=1,
            chunk_count=1,
            ocr_required=False,
        ),
    )

    process_claimed_job(LibrarySession(), SimpleNamespace(), job)  # type: ignore[arg-type]

    assert pdf_path.exists()
    assert job.status == "indexed"
    assert library_file.status == "text_ready"
    assert library_file.article_id == article_id
