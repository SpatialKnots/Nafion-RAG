# Architecture

Nafion RAG is local-first. Phase 1 only implements source-preserving PDF ingestion.

## Services

- `postgres`: PostgreSQL 16 with pgvector extension enabled for later phases.
- `grobid`: local GROBID service for metadata/TEI extraction in later Phase 1 work.
- `app`: FastAPI backend with `/health`.
- `worker`: placeholder background process; database-backed queue processing is next.

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
