# Nafion RAG

Local-first scientific literature retrieval system for Nafion/PFSA and lithium-ion battery research.

The first implementation phase covers repository infrastructure and PDF ingestion only:

- Docker Compose for PostgreSQL + pgvector, GROBID, app, and worker.
- SQLAlchemy models and Alembic migration.
- Local PDF import with immutable original copy and SHA-256 duplicate detection.
- Text-layer quality check and OCR decision logic.
- Page-level text extraction with PyMuPDF.
- Deterministic chunking with page ranges.
- CLI for ingesting one PDF or a folder.

Not included in phase 1: embeddings, semantic search, RAG answers, and complex UI.

## Quick Start

Copy configuration:

```powershell
Copy-Item .env.example .env
```

Start services:

```powershell
docker compose up --build
```

Run migrations:

```powershell
python -m alembic upgrade head
```

Ingest a PDF:

```powershell
python -m app.ingestion.cli file data/inbox/example.pdf --collection literature
```

Ingest a folder:

```powershell
python -m app.ingestion.cli folder data/inbox --collection literature
```

## Evidence Rules

The system stores source text with article, PDF path, page number, section/source type, and exact fragment. Original PDFs are copied into `data/pdf/` and are not modified.

## Development Checks

```powershell
ruff check .
ruff format --check .
mypy app
pytest -q
```
