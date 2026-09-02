# ARIADNE Library Sources Implementation Plan

**Date:** 2026-09-01  
**Project:** ARIADNE / Nafion-RAG transition  
**Goal:** implement persistent user article folders as ARIADNE libraries, with automatic PDF discovery, ingestion queueing, and vector-index synchronization.

## Operating Rule For Codex

The user now starts ARIADNE manually from the desktop launcher script.

Codex must not start the application server, worker, browser, or desktop launcher unless the user explicitly asks for a runtime check. Prefer unit tests, focused CLI-level tests, and code inspection. If a running app is needed, ask first.

## Current Baseline

Already implemented:

- local FastAPI backend;
- local HTML UI;
- PostgreSQL database;
- immutable PDF copy into `data/pdf`;
- PDF ingestion from one file;
- one-shot folder ingestion through CLI;
- upload through browser UI;
- ingestion jobs and worker;
- text extraction and optional OCR;
- page-linked chunks;
- exact / semantic / hybrid retrieval;
- local vector index;
- answer generation over retrieved evidence.

Current limitation:

```text
PDF folder -> manual one-shot import -> manual or queued vector index rebuild
```

Target behavior:

```text
Add Library -> persistent watched folder -> automatic scan -> ingestion jobs -> index sync -> searchable documents
```

## Target User Workflow

1. User starts ARIADNE using the desktop launcher.
2. User opens the UI.
3. User clicks `Add Library`.
4. User selects or enters a folder path, for example `D:\Research\Nafion\Papers`.
5. ARIADNE saves this folder as a persistent `Library Source`.
6. ARIADNE scans the folder for PDF files.
7. New PDFs are queued for ingestion.
8. Existing identical PDFs are not re-ingested.
9. Changed PDFs are treated as new source versions, without destroying old provenance.
10. After ingestion, ARIADNE requests vector-index synchronization.
11. UI shows each library and document status.
12. Search and answer pages use only ready evidence.

## Core Design

Do not rewrite ingestion. Add a product layer before the existing ingestion queue.

```text
Library UI
  -> Library Source
  -> Folder Scanner
  -> Source Registry
  -> existing ingestion job queue
  -> existing worker
  -> existing PDF extraction / OCR / chunking
  -> PostgreSQL article/page/chunk evidence
  -> vector index lifecycle
```

The folder watcher must not extract text, run OCR, create chunks, or write article evidence directly. It only discovers filesystem state and queues work through existing ingestion mechanisms.

## Data Model Additions

Add Alembic migration for persistent libraries and discovered sources.

### `library_sources`

Suggested fields:

```text
id UUID primary key
name text not null
path text not null
collection_id UUID not null references collections(id)
enabled boolean not null default true
watch_enabled boolean not null default true
recursive boolean not null default true
last_scan_at timestamptz null
status text not null default 'active'
last_error text null
created_at timestamptz not null
updated_at timestamptz not null
```

Status values:

```text
active
disabled
missing
error
```

Constraints:

- `path` should be unique per collection or globally unique after normalization.
- Store the user-facing external folder path, but treat it as untrusted input.
- Do not equate `library_source` with `collection`.

### `library_source_files`

Suggested fields:

```text
id UUID primary key
library_source_id UUID not null references library_sources(id)
external_path text not null
relative_path text not null
filename text not null
content_hash_sha256 text null
file_size_bytes bigint null
mtime_ns bigint null
article_id UUID null references articles(id)
ingestion_job_id UUID null references ingestion_jobs(id)
status text not null default 'discovered'
last_seen_at timestamptz not null
last_ingested_at timestamptz null
last_error text null
created_at timestamptz not null
updated_at timestamptz not null
```

Status values:

```text
discovered
queued
ingesting
text_ready
embedding
ready
duplicate
missing
failed
```

Identity rules:

```text
same path + same hash -> unchanged
new path + same hash -> same content, moved or renamed
same path + new hash -> new source version
new path + new hash -> new source
```

For MVP, implement the first two safely:

- unchanged files are skipped;
- same hash is treated as duplicate and linked to the existing article when possible.

Do not silently replace old evidence when a file changes.

## Implementation Phases

## M1. Source Identity Audit

Purpose: verify and document current behavior before adding library persistence.

Tasks:

- Inspect existing checksum/dedup behavior in `app/ingestion/service.py`.
- Inspect upload queue behavior in `app/ingestion/queue.py`.
- Inspect vector stale/rebuild behavior in `app/retrieval/index_lifecycle.py`.
- Confirm how `Article.checksum_sha256`, `Article.pdf_original_path`, and `IngestionJob` are used.
- Add or update focused tests only if current behavior is unclear.

Output:

- short markdown note or comments in this plan update describing the current baseline;
- no behavior changes unless a real bug is found.

Acceptance:

- repeated ingestion of identical PDF is understood and test-covered;
- vector index stale marking after ingestion is understood.

## M2. Add Library Source Models

Purpose: persist user-selected folders.

Tasks:

- Add SQLAlchemy models for `LibrarySource` and `LibrarySourceFile`.
- Add Alembic migration.
- Add schemas/serializers if the project pattern uses them.
- Add unit tests for model creation and basic constraints.

Files likely touched:

```text
app/db/models.py
alembic/versions/*.py
tests/unit/
docs/data_model.md
```

Acceptance:

- migration creates tables cleanly;
- tests can create a library source and discovered file;
- no ingestion behavior changes yet.

## M3. Add Library Manager Service

Purpose: centralize library source operations outside UI and CLI.

Create a module such as:

```text
app/library/
  __init__.py
  service.py
  scan.py
  schemas.py
```

Core functions:

```text
create_library_source(session, settings, name, path, collection_name, recursive=True)
list_library_sources(session)
get_library_source(session, library_source_id)
scan_library_source(session, settings, library_source_id)
```

Validation:

- path must exist;
- path must be a directory;
- path must be readable;
- collection must exist;
- only `.pdf` files are considered;
- scanner should ignore temporary files and non-PDF files.

Acceptance:

- service can create and list library sources;
- scanner discovers PDFs without ingesting them yet;
- missing folder sets source status to `missing` with diagnostic.

## M4. Queue Discovered PDFs Through Existing Ingestion

Purpose: connect folder discovery to the existing ingestion queue.

Preferred path:

- reuse `enqueue_upload` only if it fits without pretending watched files are browser uploads;
- otherwise add a queue helper for local source files that creates an `IngestionJob` for an existing external path.

Rules:

- do not copy PDF into immutable storage in the scanner;
- the existing ingestion worker should still run `process_pdf`;
- duplicates must become `duplicate` rather than re-indexed;
- failed jobs must keep diagnostics.

Acceptance:

- scanning a folder with one new PDF creates one ingestion job;
- scanning again without changes creates no new job;
- scanning same content under a different name does not create duplicate article evidence;
- all behavior has unit tests using temporary folders.

## M5. Worker Status Backfill

Purpose: keep `library_source_files` status aligned with ingestion job outcomes.

Tasks:

- when a queued file is claimed, mark it `ingesting`;
- when ingestion completes, link `article_id` and mark `text_ready` or `ready` depending on index state;
- when duplicate is detected, link existing article if possible and mark `duplicate` or `ready`;
- when ingestion fails, mark `failed` and store error text.

Implementation options:

1. Update worker code after `process_one_job`.
2. Add a reconciliation function that maps `library_source_files.ingestion_job_id` to current `IngestionJob` state.

Prefer option 2 if it keeps the ingestion worker simpler.

Acceptance:

- UI can show useful per-file status;
- failures are visible and not swallowed;
- original ingestion tests still pass.

## M6. Automatic Vector Index Synchronization

Purpose: remove the normal-user need for manual CLI rebuild.

Current state: ingestion marks vector index stale. ARIADNE already has vector-index lifecycle APIs and worker code.

Tasks:

- verify current `request_vector_rebuild` and `process_one_vector_rebuild` behavior;
- after a successful scan/ingestion, ensure rebuild is requested when `vector_auto_rebuild_enabled` is true;
- avoid requesting many duplicate rebuild jobs during bulk folder scans;
- add debounce or one rebuild request per collection after a scan batch.

Acceptance:

- after new PDFs are ingested, vector rebuild is requested automatically;
- repeated scans do not flood rebuild jobs;
- exact retrieval works immediately after text ingestion;
- semantic/hybrid retrieval becomes available after vector job completes.

## M7. Library API Routes

Purpose: expose library management to the UI.

Suggested routes:

```text
GET  /libraries
POST /libraries
GET  /libraries/{library_id}
POST /libraries/{library_id}/scan
PATCH /libraries/{library_id}
GET  /libraries/{library_id}/files
```

For HTML UI, also add:

```text
GET  /ui/libraries
POST /ui/libraries
POST /ui/libraries/{library_id}/scan
```

Keep routes local-first. Do not add cloud sync or accounts.

Acceptance:

- user can add a folder from UI by typing/pasting a path;
- user can trigger scan from UI;
- UI shows library status and discovered files.

## M8. Library UI

Purpose: make the feature usable without command line.

Page:

```text
/ui/libraries
```

Show:

```text
Library name
Folder path
Collection
Watching enabled/disabled
Last scan time
Status
Total PDFs
Ready
Queued
Failed
Missing
```

Per-file table:

```text
Filename
Relative path
Status
Article
Last seen
Last ingested
Error
```

Actions:

```text
Add Library
Scan Now
Enable/Disable
Open Articles
Open Failed Files
```

Design rule:

- do not build a marketing page;
- build a dense scientific workbench view;
- preserve ARIADNE brand tokens already present in `app/ui.py`.

Acceptance:

- user can manage libraries without CLI;
- missing/error states are explicit;
- no text overlaps on desktop/mobile.

## M9. Watcher / Periodic Scan

Purpose: make new PDFs appear automatically.

MVP approach:

- do not use OS-specific realtime filesystem watchers first;
- implement periodic scan in the existing worker loop;
- scan enabled `library_sources` every N seconds/minutes;
- make interval configurable.

Suggested settings:

```text
LIBRARY_SCAN_ENABLED=true
LIBRARY_SCAN_INTERVAL_SECONDS=60
LIBRARY_SCAN_BATCH_SIZE=500
```

Why periodic scan first:

- simpler;
- easier to test;
- works with network drives better than pure file events;
- less fragile for local scientific folders.

Later enhancement:

- optional `watchdog`-based realtime watcher.

Acceptance:

- user drops a PDF into watched folder;
- within scan interval, ARIADNE discovers and queues it;
- after worker finishes, document appears in articles/search;
- scanner handles folder temporarily unavailable.

## M10. Documentation And Handoff

Update:

```text
README.md
docs/operations.md
docs/architecture.md
docs/data_model.md
```

Document:

- how `Add Library` works;
- difference between external folder and immutable ingested PDF;
- why ARIADNE keeps a copy;
- how statuses should be interpreted;
- how to recover from failed ingestion;
- how vector index updates happen.

Acceptance:

- a new Codex chat can continue from docs without re-deriving the architecture;
- user-facing docs do not require command-line workflow for normal use.

## Testing Strategy

Use focused tests. Do not require the app to be running.

Minimum tests:

```text
test_create_library_source
test_scan_discovers_pdf
test_scan_ignores_non_pdf
test_scan_missing_folder_sets_status
test_scan_same_folder_twice_no_duplicate_job
test_scan_same_hash_different_name_duplicate
test_scan_changed_file_new_version_or_failed_pending_policy
test_library_ui_renders_sources
test_library_ui_scan_action
test_worker_reconciles_library_file_status
test_vector_rebuild_requested_once_per_scan_batch
```

Run likely test subsets:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_ingestion_queue.py tests\unit\test_vector_index_lifecycle.py -q
.\.venv\Scripts\python.exe -m pytest tests\unit\test_ui_routes.py -q
.\.venv\Scripts\python.exe -m pytest tests\unit\test_library_sources.py -q
```

Do not claim full pass unless full test suite actually ran.

## Important Constraints

- Do not change original PDF immutability.
- Do not make the watched folder itself the source of truth.
- Do not replace existing ingestion with new scanner logic.
- Do not hide scanner, ingestion, OCR, database, or vector-index failures.
- Do not silently alter retrieval scoring or chunk schemas.
- Do not require cloud storage.
- Do not require external LLM for ingestion, search, or indexing.
- Do not start the server from Codex unless the user asks.

## Recommended First Patch

Start with M1-M3 only:

1. Audit existing source identity and ingestion queue behavior.
2. Add `LibrarySource` and `LibrarySourceFile` models.
3. Add migration and basic service functions.
4. Add tests for creating a library and scanning a temp folder.

Do not build UI and watcher in the same first patch. That would mix database schema, filesystem scanning, worker behavior, and frontend changes in one step.

## MVP Definition

The first ARIADNE library MVP is complete when this works:

```text
User starts ARIADNE with desktop launcher
  -> opens /ui/libraries
  -> adds D:\Research\Papers
  -> clicks Scan Now
  -> PDFs are queued
  -> worker ingests them
  -> vector rebuild is requested
  -> UI shows ready/failed states
  -> search and answer pages can cite the imported PDFs
```

Full automatic watcher can be added immediately after this MVP if periodic scan is not included in the first release.

## Suggested Implementation Order For New Chat

Use this order:

```text
1. Read AGENTS.md.
2. Read this plan.
3. Inspect current models, ingestion queue, worker, and vector lifecycle.
4. Implement M1-M3.
5. Run focused tests.
6. Report Changed / Tests run / Limitations / Verdict.
7. Continue with M4-M6 only after M1-M3 are stable.
```

