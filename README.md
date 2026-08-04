# Nafion RAG

Local-first scientific literature ingestion and retrieval system for Nafion/PFSA and lithium-ion battery research.

The implemented system includes:

- Local Python application and worker processes.
- Local PostgreSQL database managed outside this repository.
- SQLAlchemy models and Alembic migration.
- Local PDF import with immutable original copy and SHA-256 duplicate detection.
- Text-layer quality check and optional OCRmyPDF execution for PDFs without usable text.
- Page-level text extraction with PyMuPDF.
- Deterministic chunking with page ranges.
- CLI for ingesting one PDF or a folder.
- Exact chunk retrieval as the default baseline.
- Optional local semantic retrieval with FastEmbed and a rebuildable vector index.
- Optional hybrid retrieval using reciprocal rank fusion over exact and semantic ranks.
- Retrieval evaluation with exact/semantic/hybrid comparison reports.
- Evidence-grounded `/answer` responses with claim-level article, chunk, and page citations.
- A local extractive answer provider and an optional configurable Ollama provider.

Not implemented: a runtime-verified generative model in the current environment, external metadata lookup, and a conversational chat UI.

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

## Diagnostics And Retrieval

Check the local ingestion environment:

```powershell
python -m app.ingestion.cli doctor
```

Search indexed chunks through the API:

```text
GET /search?q=Nafion&collection=literature&top_k=10
```

Build and use the local semantic index:

```powershell
python -m app.retrieval.cli build --embedding-model BAAI/bge-small-en-v1.5 --batch-size 64
```

```text
GET /search?q=proton%20transport&collection=literature&top_k=10&method=semantic
```

Run equal-weight reciprocal rank fusion explicitly:

```text
GET /search?q=proton%20transport&collection=literature&top_k=10&method=hybrid
```

Request an evidence-grounded answer:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer `
  -ContentType application/json `
  -Body '{"question":"How was Nafion conductivity measured?","method":"hybrid","top_k":5}'
```

The default `extractive` provider returns source excerpts rather than synthesized prose. To use a locally operated Ollama model, set `RAG_PROVIDER=ollama` and configure `RAG_MODEL`; this repository does not install or download a model automatically.

Run retrieval evaluation:

```powershell
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10
```

See `docs/operations.md` for the operational checklist.
