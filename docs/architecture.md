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
  -> OCR decision flag
  -> DOI weak extraction from first pages
  -> article/pages/chunks persisted
```

Original PDFs are never modified. OCR output is not yet generated in code; the ingestion result records whether OCR is required so the next patch can add OCRmyPDF execution without changing the page/chunk contract.

## Not In Phase 1

- Embeddings.
- Semantic or hybrid search.
- RAG generation.
- External metadata lookup.
- Complex frontend.
