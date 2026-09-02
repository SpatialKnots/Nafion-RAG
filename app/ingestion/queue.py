from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Collection, IngestionJob
from app.documents.service import build_pdf_url
from app.ingestion.service import get_collection, process_pdf
from app.ingestion.upload import StagedUpload, move_to_queued, remove_staged_file
from app.library.service import is_library_ingestion_job, reconcile_library_source_file_statuses

LOGGER = logging.getLogger(__name__)
TERMINAL_STATUSES = {"indexed", "duplicate", "failed"}
ACTIVE_STATUSES = {"queued", "processing"}
SAFE_ERROR_MESSAGES = {
    "LeaseExpired": "Worker lease expired and max attempts were exhausted",
    "MissingStagedFile": "Queued upload file is unavailable",
    "UnknownCollection": "Job collection is unavailable",
}


def job_to_response(job: IngestionJob) -> dict[str, object]:
    article_id = str(job.article_id) if job.article_id else None
    error_type = job.error_type
    return {
        "job_id": str(job.id),
        "status": job.status,
        "collection_id": str(job.collection_id),
        "article_id": article_id,
        "original_filename": job.original_filename,
        "checksum_sha256": job.checksum_sha256,
        "file_size_bytes": job.file_size_bytes,
        "force_ocr": job.force_ocr,
        "attempt_count": job.attempt_count,
        "worker_id": job.worker_id,
        "error_type": error_type,
        "error_message": _public_error_message(error_type, job.error_message),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "article_url": f"/ui/articles/{article_id}" if article_id else None,
        "pdf_url": build_pdf_url(article_id, "original") if article_id else None,
    }


def _public_error_message(error_type: str | None, error_message: str | None) -> str | None:
    if error_message is None:
        return None
    if error_type in SAFE_ERROR_MESSAGES:
        return SAFE_ERROR_MESSAGES[error_type]
    if _looks_like_internal_diagnostic(error_message):
        return "Ingestion failed during PDF processing. See local logs for details."
    return error_message[:300]


def _looks_like_internal_diagnostic(message: str) -> bool:
    lowered = message.lower()
    return "\\" in message or "/" in message or "traceback" in lowered or "data\\processed" in lowered or "data/processed" in lowered


def enqueue_upload(
    session: Session,
    settings: Settings,
    staged: StagedUpload,
    collection_name: str,
    *,
    force_ocr: bool = False,
) -> IngestionJob:
    collection = get_collection(session, collection_name)
    now = datetime.now(UTC)
    duplicate = session.scalar(select(Article).where(Article.checksum_sha256 == staged.checksum_sha256))
    if duplicate is not None and not force_ocr:
        remove_staged_file(staged.path)
        job = IngestionJob(
            input_path="duplicate",
            collection_id=collection.id,
            article_id=duplicate.id,
            original_filename=staged.original_filename,
            checksum_sha256=staged.checksum_sha256,
            file_size_bytes=staged.file_size_bytes,
            force_ocr=False,
            status="duplicate",
            finished_at=now,
            updated_at=now,
        )
        session.add(job)
        session.flush()
        return job

    active = session.scalar(
        select(IngestionJob)
        .where(IngestionJob.checksum_sha256 == staged.checksum_sha256)
        .where(IngestionJob.status.in_(ACTIVE_STATUSES))
        .where(IngestionJob.force_ocr.is_(force_ocr))
        .order_by(IngestionJob.created_at)
        .limit(1)
    )
    if active is not None:
        remove_staged_file(staged.path)
        return active

    job_id = uuid.uuid4()
    queued_path = move_to_queued(staged, settings, job_id)
    job = IngestionJob(
        id=job_id,
        input_path=str(queued_path),
        collection_id=collection.id,
        original_filename=staged.original_filename,
        checksum_sha256=staged.checksum_sha256,
        file_size_bytes=staged.file_size_bytes,
        force_ocr=force_ocr,
        status="queued",
        updated_at=now,
    )
    session.add(job)
    session.flush()
    return job


def recover_stale_jobs(session: Session, settings: Settings) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.ingestion_lease_seconds)
    jobs = list(
        session.scalars(
            select(IngestionJob)
            .where(IngestionJob.status == "processing")
            .where(IngestionJob.heartbeat_at < cutoff)
            .order_by(IngestionJob.created_at)
        )
    )
    recovered = 0
    now = datetime.now(UTC)
    for job in jobs:
        if job.attempt_count >= settings.ingestion_max_attempts:
            job.status = "failed"
            job.error_type = "LeaseExpired"
            job.error_message = "Worker lease expired and max attempts were exhausted"
            job.finished_at = now
        else:
            job.status = "queued"
            job.worker_id = None
            job.heartbeat_at = None
        job.updated_at = now
        recovered += 1
    return recovered


def claim_next_job(session: Session, settings: Settings, worker_id: str) -> IngestionJob | None:
    recover_stale_jobs(session, settings)
    statement = (
        select(IngestionJob)
        .where(IngestionJob.status == "queued")
        .order_by(IngestionJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = session.scalar(statement)
    if job is None:
        return None
    now = datetime.now(UTC)
    job.status = "processing"
    job.worker_id = worker_id
    job.attempt_count += 1
    job.started_at = job.started_at or now
    job.heartbeat_at = now
    job.updated_at = now
    reconcile_library_source_file_statuses(session, job.id)
    return job


def process_claimed_job(session: Session, settings: Settings, job: IngestionJob) -> None:
    staged_path = Path(job.input_path)
    now = datetime.now(UTC)
    is_library_job = is_library_ingestion_job(session, job.id)
    if not staged_path.is_file():
        job.status = "failed"
        job.error_type = "MissingStagedFile"
        job.error_message = "Queued upload file is unavailable"
        job.finished_at = now
        job.updated_at = now
        reconcile_library_source_file_statuses(session, job.id)
        return
    collection = session.get(Collection, job.collection_id)
    if collection is None:
        job.status = "failed"
        job.error_type = "UnknownCollection"
        job.error_message = "Job collection is unavailable"
        job.finished_at = now
        job.updated_at = now
        reconcile_library_source_file_statuses(session, job.id)
        return
    try:
        result = process_pdf(session, settings, staged_path, collection, force_ocr=job.force_ocr)
    except Exception as exc:
        LOGGER.exception("ingestion job failed", extra={"job_id": str(job.id)})
        job.status = "failed"
        job.error_type = type(exc).__name__
        job.error_message = str(exc)[:1000]
        job.finished_at = datetime.now(UTC)
        job.updated_at = datetime.now(UTC)
        reconcile_library_source_file_statuses(session, job.id)
        return

    job.article_id = uuid.UUID(result.article_id)
    job.checksum_sha256 = result.checksum_sha256
    job.status = result.status
    job.error_type = None
    job.error_message = None
    job.finished_at = datetime.now(UTC)
    job.updated_at = datetime.now(UTC)
    reconcile_library_source_file_statuses(session, job.id)
    if result.status in {"indexed", "duplicate"} and not is_library_job:
        remove_staged_file(staged_path)


def process_one_job(session: Session, settings: Settings, worker_id: str) -> IngestionJob | None:
    job = claim_next_job(session, settings, worker_id)
    if job is None:
        session.commit()
        return None
    session.commit()
    job = session.get(IngestionJob, job.id)
    if job is None:
        return None
    process_claimed_job(session, settings, job)
    session.commit()
    return job
