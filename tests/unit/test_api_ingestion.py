from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import main
from app.ingestion.upload import UploadValidationError


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.job = SimpleNamespace(id=uuid.uuid4(), status="queued")

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def scalar(self, statement: object) -> object | None:
        if "WHERE ingestion_jobs.id" in str(statement):
            return self.job
        return None

    def scalars(self, statement: object) -> list[object]:
        return [self.job]


class FakeRequest:
    headers: dict[str, str] = {}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_upload_pdfs_returns_queued_job(monkeypatch) -> None:
    session = FakeSession()
    job_id = uuid.uuid4()
    staged = SimpleNamespace(path="staged.part")
    upload = SimpleNamespace(filename="paper.pdf")
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(upload_max_files_per_request=10, upload_max_file_size_mb=100))

    async def stage(upload_arg: object, settings: object) -> object:
        return staged

    monkeypatch.setattr(main, "stage_upload_file", stage)
    monkeypatch.setattr(
        main,
        "enqueue_upload",
        lambda session_arg, settings, staged_arg, collection: SimpleNamespace(id=job_id, status="queued"),
    )
    monkeypatch.setattr(
        main,
        "job_to_response",
        lambda job: {
            "job_id": str(job.id),
            "status": job.status,
            "collection_id": str(uuid.uuid4()),
            "article_id": None,
            "original_filename": "paper.pdf",
            "checksum_sha256": "a" * 64,
            "file_size_bytes": 10,
            "force_ocr": False,
            "attempt_count": 0,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
    )

    payload = await main.upload_pdfs(FakeRequest(), session, [upload])  # type: ignore[arg-type]

    assert payload["items"][0]["status"] == "active"
    assert payload["items"][0]["job"]["job_id"] == str(job_id)
    assert session.commits == 1


@pytest.mark.anyio
async def test_upload_pdfs_isolates_validation_failure(monkeypatch) -> None:
    session = FakeSession()
    upload = SimpleNamespace(filename="bad.txt")
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(upload_max_files_per_request=10, upload_max_file_size_mb=100))

    async def fail_upload(upload_arg: object, settings: object) -> object:
        raise UploadValidationError("invalid_extension", "Only .pdf files are accepted")

    monkeypatch.setattr(main, "stage_upload_file", fail_upload)

    payload = await main.upload_pdfs(FakeRequest(), session, [upload])  # type: ignore[arg-type]

    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][0]["error_code"] == "invalid_extension"
    assert session.rollbacks == 1


def test_ingestion_job_returns_404_for_unknown_job() -> None:
    class MissingSession(FakeSession):
        def scalar(self, statement: object) -> object | None:
            return None

    with pytest.raises(HTTPException) as exc_info:
        main.ingestion_job(MissingSession(), uuid.uuid4())  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404
