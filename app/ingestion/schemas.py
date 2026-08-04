from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

JobStatus = Literal["queued", "processing", "indexed", "duplicate", "failed"]
UploadItemStatus = Literal["queued", "duplicate", "active", "failed"]


class IngestionJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    collection_id: str
    article_id: str | None = None
    original_filename: str | None = None
    checksum_sha256: str | None = None
    file_size_bytes: int | None = None
    force_ocr: bool
    attempt_count: int
    worker_id: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    article_url: str | None = None
    pdf_url: str | None = None


class UploadItemResponse(BaseModel):
    filename: str | None
    status: UploadItemStatus
    job: IngestionJobResponse | None = None
    error_code: str | None = None
    error_message: str | None = None


class UploadResponse(BaseModel):
    items: list[UploadItemResponse]


class JobsResponse(BaseModel):
    items: list[IngestionJobResponse]

