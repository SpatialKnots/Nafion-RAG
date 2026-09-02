from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Collection, IngestionJob, LibrarySource, LibrarySourceFile, VectorIndexState
from app.ingestion.checksum import sha256_file
from app.library.schemas import LibraryScanResult
from app.retrieval.index_lifecycle import VECTOR_INDEX_READY

TEMPORARY_PDF_PREFIXES = ("~$", ".~")
ACTIVE_INGESTION_STATUSES = {"queued", "processing"}
ACTIVE_LIBRARY_FILE_STATUSES = {"queued", "ingesting"}


class DuplicateLibrarySourceError(ValueError):
    def __init__(self, source: LibrarySource) -> None:
        self.source = source
        collection = source.collection.name if source.collection is not None else source.collection_id
        super().__init__(f"Library source already exists for collection '{collection}' and path: {source.path}")


def create_library_source(
    session: Session,
    settings: Settings,
    *,
    name: str,
    path: str | Path,
    collection_name: str,
    recursive: bool = True,
) -> LibrarySource:
    del settings
    collection = _get_collection(session, collection_name)
    normalized_path = _validate_existing_directory(path)
    existing = _get_source_by_collection_path(session, collection.id, str(normalized_path))
    if existing is not None:
        raise DuplicateLibrarySourceError(existing)
    now = datetime.now(UTC)
    source = LibrarySource(
        id=uuid.uuid4(),
        name=_require_non_empty(name, "name"),
        path=str(normalized_path),
        collection_id=collection.id,
        enabled=True,
        watch_enabled=True,
        recursive=recursive,
        status="active",
        last_error=None,
        updated_at=now,
    )
    session.add(source)
    session.flush()
    return source


def list_library_sources(session: Session) -> list[LibrarySource]:
    return list(session.scalars(select(LibrarySource).join(Collection).order_by(Collection.name, LibrarySource.name)))


def list_library_source_files(session: Session, library_source_id: UUID, *, status: str | None = None) -> list[LibrarySourceFile]:
    statement = select(LibrarySourceFile).where(LibrarySourceFile.library_source_id == library_source_id)
    if status:
        statement = statement.where(LibrarySourceFile.status == status)
    return list(session.scalars(statement.order_by(LibrarySourceFile.relative_path)))


def get_library_source(session: Session, library_source_id: UUID) -> LibrarySource | None:
    return session.get(LibrarySource, library_source_id)


def update_library_source(
    session: Session,
    settings: Settings,
    library_source_id: UUID,
    *,
    name: str | None = None,
    path: str | Path | None = None,
    collection_name: str | None = None,
    enabled: bool | None = None,
    watch_enabled: bool | None = None,
    recursive: bool | None = None,
) -> LibrarySource:
    del settings
    source = get_library_source(session, library_source_id)
    if source is None:
        raise ValueError(f"Unknown library source: {library_source_id}")

    if name is not None:
        source.name = _require_non_empty(name, "name")
    if path is not None:
        source.path = str(_validate_existing_directory(path))
    if collection_name is not None:
        collection = _get_collection(session, collection_name)
        source.collection_id = collection.id
        source.collection = collection
    if enabled is not None:
        source.enabled = enabled
    if watch_enabled is not None:
        source.watch_enabled = watch_enabled
    if recursive is not None:
        source.recursive = recursive

    now = datetime.now(UTC)
    if source.enabled:
        _validate_existing_directory(source.path)
        source.status = "active"
        source.last_error = None
    else:
        source.status = "disabled"
    source.updated_at = now
    session.flush()
    return source


def delete_library_source(session: Session, library_source_id: UUID) -> dict[str, object]:
    source = get_library_source(session, library_source_id)
    if source is None:
        raise ValueError(f"Unknown library source: {library_source_id}")
    files = list_library_source_files(session, library_source_id)
    active = [row for row in files if row.status in ACTIVE_LIBRARY_FILE_STATUSES]
    if active:
        raise ValueError("Cannot delete library source while files are queued or ingesting")
    payload = {"id": str(source.id), "deleted_files": len(files)}
    session.delete(source)
    session.flush()
    return payload


def library_source_to_response(source: LibrarySource) -> dict[str, object]:
    return {
        "id": str(source.id),
        "name": source.name,
        "path": source.path,
        "collection_id": str(source.collection_id),
        "collection": source.collection.name if source.collection is not None else None,
        "enabled": source.enabled,
        "watch_enabled": source.watch_enabled,
        "recursive": source.recursive,
        "last_scan_at": source.last_scan_at,
        "status": source.status,
        "last_error": source.last_error,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def library_source_file_to_response(row: LibrarySourceFile) -> dict[str, object]:
    article_id = str(row.article_id) if row.article_id else None
    return {
        "id": str(row.id),
        "library_source_id": str(row.library_source_id),
        "external_path": row.external_path,
        "relative_path": row.relative_path,
        "filename": row.filename,
        "content_hash_sha256": row.content_hash_sha256,
        "file_size_bytes": row.file_size_bytes,
        "mtime_ns": row.mtime_ns,
        "article_id": article_id,
        "ingestion_job_id": str(row.ingestion_job_id) if row.ingestion_job_id else None,
        "status": row.status,
        "last_seen_at": row.last_seen_at,
        "last_ingested_at": row.last_ingested_at,
        "last_error": row.last_error,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "article_url": f"/ui/articles/{article_id}" if article_id else None,
    }


def library_scan_result_to_response(result: LibraryScanResult) -> dict[str, object]:
    return {
        "library_source_id": result.library_source_id,
        "discovered": result.discovered,
        "unchanged": result.unchanged,
        "duplicates": result.duplicates,
        "missing": result.missing,
        "queued": result.queued,
        "status": result.status,
        "error": result.error,
    }


def scan_library_source(session: Session, settings: Settings, library_source_id: UUID) -> LibraryScanResult:
    del settings
    source = get_library_source(session, library_source_id)
    if source is None:
        raise ValueError(f"Unknown library source: {library_source_id}")

    now = datetime.now(UTC)
    root = Path(source.path)
    if not root.exists() or not root.is_dir():
        source.status = "missing"
        source.last_error = f"Library folder is unavailable: {source.path}"
        source.last_scan_at = now
        source.updated_at = now
        return LibraryScanResult(
            str(source.id),
            discovered=0,
            unchanged=0,
            duplicates=0,
            missing=0,
            status=source.status,
            error=source.last_error,
        )
    if not os.access(root, os.R_OK):
        source.status = "error"
        source.last_error = f"Library folder is not readable: {source.path}"
        source.last_scan_at = now
        source.updated_at = now
        return LibraryScanResult(
            str(source.id),
            discovered=0,
            unchanged=0,
            duplicates=0,
            missing=0,
            status=source.status,
            error=source.last_error,
        )

    discovered = 0
    unchanged = 0
    duplicates = 0
    seen_paths: set[str] = set()
    for pdf_path in _iter_pdf_files(root, recursive=source.recursive):
        external_path = str(pdf_path.resolve())
        seen_paths.add(external_path)
        stat = pdf_path.stat()
        content_hash = sha256_file(pdf_path)
        existing = _get_source_file_by_path(session, source.id, external_path)
        duplicate_article = session.scalar(select(Article).where(Article.checksum_sha256 == content_hash))

        if existing is not None and existing.content_hash_sha256 == content_hash:
            existing.file_size_bytes = stat.st_size
            existing.mtime_ns = stat.st_mtime_ns
            existing.last_seen_at = now
            existing.last_error = None
            existing.updated_at = now
            if duplicate_article is not None:
                existing.article_id = duplicate_article.id
                existing.status = "duplicate"
                duplicates += 1
            else:
                unchanged += 1
            continue

        source_file = existing or LibrarySourceFile(id=uuid.uuid4(), library_source_id=source.id, external_path=external_path)
        source_file.relative_path = str(pdf_path.resolve().relative_to(root.resolve()))
        source_file.filename = pdf_path.name
        source_file.content_hash_sha256 = content_hash
        source_file.file_size_bytes = stat.st_size
        source_file.mtime_ns = stat.st_mtime_ns
        source_file.article_id = duplicate_article.id if duplicate_article is not None else None
        source_file.ingestion_job_id = None
        source_file.status = "duplicate" if duplicate_article is not None else "discovered"
        source_file.last_seen_at = now
        source_file.last_error = None
        source_file.updated_at = now
        if existing is None:
            session.add(source_file)
        if duplicate_article is not None:
            duplicates += 1
        else:
            discovered += 1

    missing = _mark_missing_files(session, source.id, seen_paths, now)
    source.status = "active" if source.enabled else "disabled"
    source.last_error = None
    source.last_scan_at = now
    source.updated_at = now
    session.flush()
    return LibraryScanResult(
        str(source.id),
        discovered=discovered,
        unchanged=unchanged,
        duplicates=duplicates,
        missing=missing,
        status=source.status,
    )


def scan_and_queue_library_source(
    session: Session,
    settings: Settings,
    library_source_id: UUID,
    *,
    queue_limit: int | None = None,
) -> LibraryScanResult:
    result = scan_library_source(session, settings, library_source_id)
    if result.status != "active":
        return result
    queued = queue_discovered_library_source_files(session, settings, library_source_id, limit=queue_limit)
    return LibraryScanResult(
        result.library_source_id,
        discovered=result.discovered,
        unchanged=result.unchanged,
        duplicates=result.duplicates,
        missing=result.missing,
        status=result.status,
        queued=queued,
        error=result.error,
    )


def queue_discovered_library_source_files(
    session: Session,
    settings: Settings,
    library_source_id: UUID,
    *,
    limit: int | None = None,
) -> int:
    del settings
    source = get_library_source(session, library_source_id)
    if source is None:
        raise ValueError(f"Unknown library source: {library_source_id}")
    if not source.enabled:
        return 0

    statement = (
        select(LibrarySourceFile)
        .where(LibrarySourceFile.library_source_id == library_source_id)
        .where(LibrarySourceFile.status == "discovered")
        .order_by(LibrarySourceFile.created_at)
    )
    rows = list(session.scalars(statement))
    if limit is not None:
        rows = rows[:limit]
    queued = 0
    now = datetime.now(UTC)
    for row in rows:
        pdf_path = Path(row.external_path)
        if not pdf_path.is_file():
            row.status = "missing"
            row.last_error = "Library file is unavailable before ingestion queueing"
            row.updated_at = now
            continue

        checksum = row.content_hash_sha256 or sha256_file(pdf_path)
        stat = pdf_path.stat()
        row.content_hash_sha256 = checksum
        row.file_size_bytes = stat.st_size
        row.mtime_ns = stat.st_mtime_ns

        duplicate_article = session.scalar(select(Article).where(Article.checksum_sha256 == checksum))
        if duplicate_article is not None:
            row.article_id = duplicate_article.id
            row.status = "duplicate"
            row.last_ingested_at = now
            row.last_error = None
            row.updated_at = now
            continue

        active_job = _get_active_ingestion_job(session, checksum)
        if active_job is not None:
            row.ingestion_job_id = active_job.id
            row.status = "ingesting" if active_job.status == "processing" else "queued"
            row.last_error = None
            row.updated_at = now
            continue

        job = IngestionJob(
            id=uuid.uuid4(),
            input_path=str(pdf_path.resolve()),
            collection_id=source.collection_id,
            original_filename=row.filename,
            checksum_sha256=checksum,
            file_size_bytes=stat.st_size,
            force_ocr=False,
            status="queued",
            updated_at=now,
        )
        session.add(job)
        row.ingestion_job_id = job.id
        row.status = "queued"
        row.last_error = None
        row.updated_at = now
        queued += 1
    session.flush()
    return queued


def is_library_ingestion_job(session: Session, ingestion_job_id: UUID) -> bool:
    return (
        session.scalar(select(LibrarySourceFile).where(LibrarySourceFile.ingestion_job_id == ingestion_job_id).limit(1))
        is not None
    )


def reconcile_library_source_file_statuses(
    session: Session,
    ingestion_job_id: UUID | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    statement = select(LibrarySourceFile).where(LibrarySourceFile.ingestion_job_id.is_not(None))
    if ingestion_job_id is not None:
        statement = statement.where(LibrarySourceFile.ingestion_job_id == ingestion_job_id)
    rows = list(session.scalars(statement))
    now = datetime.now(UTC)
    updated = 0
    for row in rows:
        if row.ingestion_job_id is None:
            continue
        job = session.get(IngestionJob, row.ingestion_job_id)
        if job is None:
            row.status = "failed"
            row.last_error = "Linked ingestion job is unavailable"
            row.updated_at = now
            updated += 1
            continue

        next_status = _library_file_status_for_job(job.status)
        if next_status is None:
            continue
        if next_status == "text_ready" and settings is not None and _has_ready_vector_index(session, row, settings):
            next_status = "ready"
        row.status = next_status
        row.article_id = job.article_id or row.article_id
        row.content_hash_sha256 = job.checksum_sha256 or row.content_hash_sha256
        row.file_size_bytes = job.file_size_bytes or row.file_size_bytes
        row.last_error = job.error_message if job.status == "failed" else None
        if job.status in {"indexed", "duplicate", "failed"}:
            row.last_ingested_at = job.finished_at or now
        row.updated_at = now
        updated += 1
    if updated:
        session.flush()
    return updated


def reconcile_library_source_vector_readiness(
    session: Session,
    settings: Settings,
    *,
    library_source_id: UUID | None = None,
) -> int:
    statement = select(LibrarySourceFile).where(LibrarySourceFile.article_id.is_not(None))
    if library_source_id is not None:
        statement = statement.where(LibrarySourceFile.library_source_id == library_source_id)
    rows = list(session.scalars(statement))
    now = datetime.now(UTC)
    updated = 0
    for row in rows:
        if row.status not in {"text_ready", "ready", "embedding"}:
            continue
        is_ready = _has_ready_vector_index(session, row, settings)
        next_status = "ready" if is_ready else "text_ready"
        if row.status == next_status:
            continue
        row.status = next_status
        row.updated_at = now
        updated += 1
    if updated:
        session.flush()
    return updated


def _get_collection(session: Session, collection_name: str) -> Collection:
    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")
    return collection


def _validate_existing_directory(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    if not candidate.exists():
        raise FileNotFoundError(candidate)
    if not candidate.is_dir():
        raise NotADirectoryError(candidate)
    if not os.access(candidate, os.R_OK):
        raise PermissionError(f"Library folder is not readable: {candidate}")
    return candidate


def _iter_pdf_files(root: Path, *, recursive: bool) -> list[Path]:
    candidates = root.rglob("*") if recursive else root.iterdir()
    return sorted(
        path
        for path in candidates
        if path.is_file() and path.suffix.lower() == ".pdf" and not path.name.startswith(TEMPORARY_PDF_PREFIXES)
    )


def _get_source_file_by_path(session: Session, library_source_id: UUID, external_path: str) -> LibrarySourceFile | None:
    return session.scalar(
        select(LibrarySourceFile)
        .where(LibrarySourceFile.library_source_id == library_source_id)
        .where(LibrarySourceFile.external_path == external_path)
    )


def _get_source_by_collection_path(session: Session, collection_id: UUID, path: str) -> LibrarySource | None:
    return session.scalar(
        select(LibrarySource).where(LibrarySource.collection_id == collection_id).where(LibrarySource.path == path).limit(1)
    )


def _get_active_ingestion_job(session: Session, checksum_sha256: str) -> IngestionJob | None:
    return session.scalar(
        select(IngestionJob)
        .where(IngestionJob.checksum_sha256 == checksum_sha256)
        .where(IngestionJob.status.in_(ACTIVE_INGESTION_STATUSES))
        .where(IngestionJob.force_ocr.is_(False))
        .order_by(IngestionJob.created_at)
        .limit(1)
    )


def _library_file_status_for_job(job_status: str) -> str | None:
    if job_status == "queued":
        return "queued"
    if job_status == "processing":
        return "ingesting"
    if job_status == "indexed":
        return "text_ready"
    if job_status == "duplicate":
        return "duplicate"
    if job_status == "failed":
        return "failed"
    return None


def _has_ready_vector_index(session: Session, row: LibrarySourceFile, settings: Settings) -> bool:
    library_source_id = getattr(row, "library_source_id", None)
    embedding_model = getattr(settings, "embedding_model", None)
    if library_source_id is None or not embedding_model:
        return False
    source = session.get(LibrarySource, library_source_id)
    if source is None:
        return False
    state = session.scalar(
        select(VectorIndexState)
        .where(VectorIndexState.collection_id == source.collection_id)
        .where(VectorIndexState.embedding_model == embedding_model)
    )
    return state is not None and state.status == VECTOR_INDEX_READY and state.active_generation_id is not None


def _mark_missing_files(session: Session, library_source_id: UUID, seen_paths: set[str], now: datetime) -> int:
    rows = list(session.scalars(select(LibrarySourceFile).where(LibrarySourceFile.library_source_id == library_source_id)))
    missing = 0
    for row in rows:
        if row.external_path in seen_paths or row.status == "missing":
            continue
        row.status = "missing"
        row.last_error = "Library file was not seen during the latest scan"
        row.updated_at = now
        missing += 1
    return missing


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized
