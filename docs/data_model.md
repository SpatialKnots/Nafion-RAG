# Data Model

The initial schema follows the implementation plan while keeping vector search out of Phase 1.

## Core Tables

- `collections`: `literature` and `own_data`.
- `articles`: one row per unique PDF checksum.
- `pages`: page-level text and OCR/text-layer flags.
- `sections`: reserved for GROBID-derived sections.
- `chunks`: source fragments with `page_start` and `page_end`.
- `article_tags`: deterministic and manual tags.
- `notes`: user notes linked to articles or chunks.
- `ingestion_jobs`: visible ingestion status and failures.
- `ingestion_jobs`: also acts as the local PostgreSQL-backed upload queue.
- `structured_facts`: source-linked scientific facts for later extraction work.

## Traceability

Every chunk stores:

- `article_id`;
- `page_start`;
- `page_end`;
- `source_type`;
- exact `text`.

This is the minimum required evidence layer for later exact search, semantic search, and RAG citations.

## Ingestion Jobs

Allowed Priority 2 statuses:

- `queued`: upload accepted and waiting for a worker.
- `processing`: atomically claimed by a worker.
- `indexed`: PostgreSQL article/page/chunk evidence was written.
- `duplicate`: matching checksum already existed.
- `failed`: validation, staging or processing failed.

Queue/audit fields include `article_id`, `original_filename`, `checksum_sha256`, `file_size_bytes`, `force_ocr`, `attempt_count`, `worker_id`, `heartbeat_at`, `error_type`, `error_message`, and timestamps. Public API responses do not expose `input_path`.
