from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

import fitz  # type: ignore[import-untyped]
from fastapi import UploadFile

from app.core.config import Settings

ALLOWED_MIME_TYPES = {"application/pdf", "application/octet-stream"}


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StagedUpload:
    path: Path
    original_filename: str
    checksum_sha256: str
    file_size_bytes: int


def uploads_root(settings: Settings) -> Path:
    return settings.data_root.resolve() / "uploads"


def incoming_upload_dir(settings: Settings) -> Path:
    return uploads_root(settings) / "incoming"


def queued_upload_dir(settings: Settings) -> Path:
    return uploads_root(settings) / "queued"


def ensure_upload_dirs(settings: Settings) -> None:
    incoming_upload_dir(settings).mkdir(parents=True, exist_ok=True)
    queued_upload_dir(settings).mkdir(parents=True, exist_ok=True)


def safe_client_filename(filename: str | None) -> str:
    name = Path(filename or "").name.strip()
    if not name:
        raise UploadValidationError("missing_filename", "Uploaded file must have a filename")
    return name


async def stage_upload_file(upload: UploadFile, settings: Settings) -> StagedUpload:
    ensure_upload_dirs(settings)
    original_filename = safe_client_filename(upload.filename)
    if Path(original_filename).suffix.lower() != ".pdf":
        raise UploadValidationError("invalid_extension", "Only .pdf files are accepted")
    if upload.content_type not in ALLOWED_MIME_TYPES:
        raise UploadValidationError("invalid_mime_type", "Only PDF upload MIME types are accepted")

    part_path = incoming_upload_dir(settings) / f"{uuid.uuid4()}.part"
    max_bytes = settings.upload_max_file_size_mb * 1024 * 1024
    digest = hashlib.sha256()
    total = 0
    prefix = b""

    try:
        with part_path.open("wb") as handle:
            while True:
                chunk = await upload.read(settings.upload_read_chunk_bytes)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UploadValidationError("file_too_large", "Uploaded PDF exceeds the configured size limit")
                if len(prefix) < 5:
                    prefix += chunk[: 5 - len(prefix)]
                digest.update(chunk)
                handle.write(chunk)

        if total == 0:
            raise UploadValidationError("empty_file", "Uploaded PDF is empty")
        if not prefix.startswith(b"%PDF-"):
            raise UploadValidationError("invalid_pdf_signature", "Uploaded file does not start with a PDF signature")
        _validate_pdf_structure(part_path)
        return StagedUpload(
            path=part_path,
            original_filename=original_filename,
            checksum_sha256=digest.hexdigest(),
            file_size_bytes=total,
        )
    except Exception:
        if part_path.exists():
            part_path.unlink()
        raise
    finally:
        await upload.close()


def move_to_queued(staged: StagedUpload, settings: Settings, job_id: uuid.UUID) -> Path:
    ensure_upload_dirs(settings)
    target = queued_upload_dir(settings) / f"{job_id}.pdf"
    staged.path.replace(target)
    return target


def remove_staged_file(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except FileNotFoundError:
        return


def _validate_pdf_structure(path: Path) -> None:
    try:
        # A failed path-based open can retain a Windows file handle in the
        # parser traceback, preventing cleanup of a rejected staged upload.
        # Upload size has already been bounded before this in-memory check.
        with fitz.open(stream=path.read_bytes(), filetype="pdf") as document:
            if document.needs_pass:
                raise UploadValidationError("encrypted_pdf", "Encrypted PDFs are not accepted")
            if document.page_count < 1:
                raise UploadValidationError("empty_pdf", "PDF must contain at least one page")
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError("invalid_pdf_structure", "PDF structure could not be read") from exc
