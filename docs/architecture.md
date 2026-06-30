# Architecture

Nafion RAG is local-first. Phase 1 only implements source-preserving PDF ingestion.

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

## Not In Phase 1

- Embeddings.
- Semantic or hybrid search.
- RAG generation.
- External metadata lookup.
- Complex frontend.
