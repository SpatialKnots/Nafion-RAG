# Architecture

Nafion RAG is local-first. PostgreSQL remains the source of truth for source-preserving PDF ingestion and chunk evidence.

## Services

- `postgres`: local PostgreSQL server managed outside this repository.
- `app`: local FastAPI backend with `/health`, started with `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- `worker`: local placeholder background process, started with `python -m app.workers.worker`; database-backed queue processing is next.

The repository does not start or manage infrastructure services. External services must be installed and operated by the local system or another service manager.

## Phase 1 Data Flow

```text
PDF path
  -> SHA-256 checksum
  -> duplicate check in articles.checksum_sha256
  -> copy immutable original to data/pdf
  -> page text extraction with PyMuPDF
  -> OCRmyPDF when OCR is enabled and the PDF has no usable text layer
  -> page text extraction from the OCR PDF when OCR ran
  -> DOI weak extraction from first pages
  -> article/pages/chunks persisted
```

Original PDFs are never modified. OCR output is written to `data/processed/ocr/` when OCR is required and enabled. If OCRmyPDF is missing or the OCR output still lacks a usable text layer, ingestion fails with a diagnostic instead of silently indexing empty text.

## Retrieval Flow

```text
query
  -> exact (default): PostgreSQL ILIKE ranking
  -> semantic (explicit): FastEmbed query embedding
       -> validated local manifest v2 and normalized embedding matrix
       -> cosine ranking
  -> hybrid (explicit): exact and semantic candidate ranks
       -> equal-weight reciprocal rank fusion
       -> Chunk and Article evidence from PostgreSQL
  -> article, DOI, chunk id, page range, source type, text layer, snippet, score, backend PDF URLs
```

The semantic index under `data/processed/vector_indexes/` is generated data, not a source of scientific evidence. Every semantic request verifies its artifact checksums, model and dimension, corpus manifest, database chunk order, and chunk text checksums. A stale or damaged index fails with a rebuild command.

Hybrid uses ranks rather than attempting to normalize incompatible exact and cosine scores. Component ranks and raw scores remain attached to each fused result for audit.

## Document Access Flow

```text
article_id + layer
  -> Article.pdf_original_path or Article.pdf_ocr_path selected by enum
  -> path resolved under data/pdf or data/processed/ocr
  -> containment, suffix and file checks
  -> FileResponse with application/pdf and inline disposition
```

The document access service treats stored paths as untrusted. Original PDF access is limited to `<data_root>/pdf`; OCR PDF access is limited to `<data_root>/processed/ocr`. Public JSON and HTTP errors do not expose absolute paths. Page text requests read only persisted `Page` or `PageTextLayer` rows and never trigger new extraction or OCR.

Search and page responses use original PDF links as the primary source link. A `#page=N` fragment is included for deep links, but that fragment is handled by the browser PDF viewer rather than the backend.

## Upload And Queue Flow

```text
multipart PDF upload
  -> stream to data/uploads/incoming/*.part with checksum and size checks
  -> validate extension, MIME, %PDF- signature and PyMuPDF structure
  -> deduplicate against articles.checksum_sha256 and active jobs
  -> move to data/uploads/queued/{job_id}.pdf
  -> IngestionJob(status=queued)
  -> worker claim with SELECT FOR UPDATE SKIP LOCKED
  -> existing extraction/OCR/chunking/classification pipeline
  -> IngestionJob(status=indexed | duplicate | failed)
```

PostgreSQL is the durable queue for the local deployment. The HTTP upload route never runs extraction or OCR; it returns after a staged file and job row are committed. The worker processes one claimed job at a time and records attempts, worker identity and heartbeat. Stale `processing` jobs are requeued until `INGESTION_MAX_ATTEMPTS` is exhausted.

Successful upload ingestion updates PostgreSQL evidence immediately. Semantic and hybrid retrieval still depend on the local vector index and require a manual rebuild until the Priority 3 index lifecycle is implemented.

## Answer Flow

```text
question
  -> configured retrieval method (hybrid by default for /answer)
  -> evidence IDs E1..En with article/chunk/page provenance
  -> configured answer provider
  -> structured claims with citation IDs
  -> reject empty claims, uncited claims, and unknown citation IDs
  -> answer text plus claims and source-linked citations
```

The default provider is `extractive`: each claim is an exact returned evidence excerpt. The optional `ollama` provider requests structured claims from an operator-configured local Ollama endpoint. Retrieved text is marked as untrusted data in the generation prompt. Provider output is structurally validated, but citation presence alone does not prove semantic entailment for generated prose.

## Not Implemented

- Runtime verification of generated prose with an installed language model.
- External metadata lookup.
- Complex frontend.
