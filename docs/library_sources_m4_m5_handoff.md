# Library Sources M4-M5 Handoff

Date: 2026-09-01

## Implemented

- `scan_and_queue_library_source` composes discovery with queueing for files in `discovered` status.
- `queue_discovered_library_source_files` creates `IngestionJob` rows for external PDF paths without copying or extracting PDFs in the scanner.
- Existing article checksum duplicates are marked `duplicate` and linked to `article_id` without creating jobs.
- Same-checksum files with an active queued/processing job reuse that job instead of creating duplicate active jobs.
- `reconcile_library_source_file_statuses` maps linked ingestion jobs back to library file statuses.
- `process_claimed_job` now preserves external watched-folder PDFs for library jobs while keeping staged upload cleanup for normal uploads.

## Status Mapping

- `IngestionJob.queued` -> `LibrarySourceFile.queued`
- `IngestionJob.processing` -> `LibrarySourceFile.ingesting`
- `IngestionJob.indexed` -> `LibrarySourceFile.text_ready`
- `IngestionJob.duplicate` -> `LibrarySourceFile.duplicate`
- `IngestionJob.failed` -> `LibrarySourceFile.failed`

`indexed` maps to `text_ready` because vector index readiness is tracked separately by `vector_index_states`.

## Follow-up Completed

- M6 vector sync hardening is covered by the existing vector-index lifecycle:
  repeated ingestion-level stale marks update one `vector_index_states` row per collection/model and refresh `requested_at`;
  `VECTOR_REBUILD_DEBOUNCE_SECONDS` delays rebuild claiming after the latest stale mark.
- `WORKER_ROLE=all` processes ingestion before vector rebuilds and library scans, so queued PDFs from a bulk scan are consumed before a rebuild is claimed.
- Regression tests cover repeated stale-mark coalescing and worker loop ordering.

## API/UI Follow-up Completed

- JSON API routes are available at `GET /libraries`, `POST /libraries`, `GET /libraries/{library_id}`,
  `GET /libraries/{library_id}/files`, and `POST /libraries/{library_id}/scan`.
- HTML UI is available at `GET /ui/libraries`.
- HTML form actions support adding a library and running `Scan Now`.
- The UI shows source status, scan time, aggregate file counts, per-file status, checksum, article links, and ingestion job links.
- Periodic library scans are available in the worker loop with `LIBRARY_SCAN_ENABLED`, `LIBRARY_SCAN_INTERVAL_SECONDS`, and `LIBRARY_SCAN_BATCH_SIZE`.
