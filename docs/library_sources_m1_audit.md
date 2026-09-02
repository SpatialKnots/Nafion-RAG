# Library Sources M1 Audit

Date: 2026-09-01

## Scope

This note records the current source-identity and indexing baseline before adding persistent ARIADNE library sources.

## Current Behavior

- `app.ingestion.service.process_pdf` computes SHA-256 from the input PDF before copying it into immutable storage.
- `Article.checksum_sha256` is unique and is the current PDF content identity.
- When `process_pdf` sees an existing `Article` with the same checksum and `force_ocr` is false, it returns an `IngestionResult` with status `duplicate` and does not rewrite article/page/chunk evidence.
- `app.ingestion.queue.enqueue_upload` checks staged-upload checksum before queueing. Existing checksums create a terminal `duplicate` `IngestionJob` linked to the existing article and remove the staged file.
- `enqueue_upload` also suppresses another active queued/processing job for the same checksum and `force_ocr` value.
- Successful non-duplicate ingestion calls `mark_vector_index_stale` after article/page/chunk replacement and classification.
- `reselect_article_text` also marks the vector index stale after rechunking.
- `mark_vector_index_stale` increments `desired_revision`; if no rebuild is in progress it sets status to `stale`, and if a rebuild is already in progress it preserves the active claim while increasing the desired revision.

## Implications For Library Sources

- Library scanning should remain a discovery layer before ingestion.
- The watched external folder must not become the evidence source of truth.
- Library files can use SHA-256 to identify unchanged files and same-content duplicates.
- Queueing and worker integration should reuse existing ingestion semantics in a later patch rather than writing evidence from the scanner.
- Vector rebuild requests should continue to flow from ingestion/text reselection paths, with later library work focused on batching and avoiding redundant rebuild requests.

## Tests Covering Baseline

- `tests/unit/test_ingestion_queue.py`
- `tests/unit/test_vector_index_lifecycle.py`
- `tests/unit/test_library_sources.py`
