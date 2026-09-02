from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

LibrarySourceStatus = Literal["active", "disabled", "missing", "error"]
LibrarySourceFileStatus = Literal[
    "discovered",
    "queued",
    "ingesting",
    "text_ready",
    "embedding",
    "ready",
    "duplicate",
    "missing",
    "failed",
]


@dataclass(frozen=True)
class LibraryScanResult:
    library_source_id: str
    discovered: int
    unchanged: int
    duplicates: int
    missing: int
    status: str
    queued: int = 0
    error: str | None = None


class LibrarySourceCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    collection: str = "literature"
    recursive: bool = True


class LibrarySourceResponse(BaseModel):
    id: str
    name: str
    path: str
    collection_id: str
    collection: str | None = None
    enabled: bool
    watch_enabled: bool
    recursive: bool
    last_scan_at: datetime | None = None
    status: LibrarySourceStatus
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LibrarySourceFileResponse(BaseModel):
    id: str
    library_source_id: str
    external_path: str
    relative_path: str
    filename: str
    content_hash_sha256: str | None = None
    file_size_bytes: int | None = None
    mtime_ns: int | None = None
    article_id: str | None = None
    ingestion_job_id: str | None = None
    status: LibrarySourceFileStatus
    last_seen_at: datetime | None = None
    last_ingested_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    article_url: str | None = None


class LibrarySourcesResponse(BaseModel):
    items: list[LibrarySourceResponse]


class LibrarySourceFilesResponse(BaseModel):
    items: list[LibrarySourceFileResponse]


class LibraryScanResponse(BaseModel):
    library_source_id: str
    discovered: int
    unchanged: int
    duplicates: int
    missing: int
    queued: int
    status: LibrarySourceStatus
    error: str | None = None
