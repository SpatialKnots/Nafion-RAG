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
- `library_sources`: persistent user-selected PDF folders attached to a collection.
- `library_source_files`: discovered external PDF files and their scan/ingestion linkage state.
- `structured_facts`: source-linked deterministic fact candidates derived from persisted chunks.

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

## Library Sources

`library_sources` stores the user-facing external folder path, collection, enabled/watch flags, recursion preference, scan time, status, and diagnostic error text. A library source is not the same thing as a collection.

`library_source_files` stores discovered PDF paths under a library source, including relative path, filename, SHA-256 hash, file size, mtime, optional linked `article_id`, optional linked `ingestion_job_id`, status, scan timestamps, and diagnostic error text.

Allowed library source statuses:

- `active`
- `disabled`
- `missing`
- `error`

Allowed library source file statuses:

- `discovered`
- `queued`
- `ingesting`
- `text_ready`
- `embedding`
- `ready`
- `duplicate`
- `missing`
- `failed`

`scan_library_source` records filesystem state only. It does not copy PDFs into immutable storage, extract text, write pages/chunks, or enqueue ingestion jobs.

`scan_and_queue_library_source` runs discovery and then queues newly discovered files through `ingestion_jobs`. Library ingestion jobs keep `input_path` pointed at the external PDF, so the worker must not delete that path after processing. The immutable PDF copy is still created by the existing ingestion service.

When an ingestion job changes state, reconciliation maps linked `library_source_files` rows as follows:

- `queued` -> `queued`
- `processing` -> `ingesting`
- `indexed` -> `text_ready`
- `duplicate` -> `duplicate`
- `failed` -> `failed`

Library management is exposed through JSON routes under `/libraries` and an HTML workbench at `/ui/libraries`.

## Structured Facts

`structured_facts` stores extracted fact candidates with `article_id`, optional `source_chunk_id`, `entity_type`, `field_name`, text value, numeric value, unit, confidence, and extractor source.

The first extractor source is `rule_based_numeric_v1`. It records only numeric fragments with explicit units found in existing chunks, such as conductivity, temperature, percentage, length, mass/density, energy, and pressure/modulus values. It does not infer table cells, row labels, comparisons, or scientific conclusions.

The source of truth remains the original chunk text and PDF/page provenance. Structured facts are derived evidence aids and can be regenerated from chunks.

Structured facts are inspectable through read-only API/UI routes. They are not yet part of retrieval scoring or answer generation.
