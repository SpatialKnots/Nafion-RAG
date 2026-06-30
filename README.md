# Nafion RAG

Local-first scientific literature retrieval system for Nafion/PFSA and lithium-ion battery research.

The first implementation phase covers repository infrastructure and PDF ingestion only:

- Local Python application and worker processes.
- Local PostgreSQL database managed outside this repository.
- SQLAlchemy models and Alembic migration.
- Local PDF import with immutable original copy and SHA-256 duplicate detection.
- Text-layer quality check and optional OCRmyPDF execution for PDFs without usable text.
- Page-level text extraction with PyMuPDF.
- Deterministic chunking with page ranges.
- CLI for ingesting one PDF or a folder.

Not included in phase 1: embeddings, semantic search, RAG answers, and complex UI.

## Quick Start

Prerequisites:

- Python 3.11 or newer.
- A local PostgreSQL server.
- A PostgreSQL database matching `DATABASE_URL` in `.env`.
- OCRmyPDF and Tesseract language packs if scanned PDFs must be OCR-processed.

Copy configuration:

```powershell
Copy-Item .env.example .env
```

Install the project into the local virtual environment:

```powershell
python -m pip install -e ".[dev]"
```

Run migrations:

```powershell
python -m alembic upgrade head
```

Start the API:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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
