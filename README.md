# Nafion RAG

Nafion RAG is a local-first tool for working with a small scientific PDF corpus about Nafion, PFSA membranes, and related lithium-ion battery literature.

It ingests PDFs, stores source-preserving text evidence, searches the corpus, and can produce evidence-grounded answers with article, chunk, and page citations.

The project is intentionally conservative: original PDFs are kept immutable, generated answers must cite retrieved evidence, and weak evidence is refused instead of silently inventing an answer.

## Project Map

```text
PDF files
  |
  v
Upload or CLI ingestion
  |
  v
Text extraction / optional OCR
  |
  v
PostgreSQL
  - articles
  - pages
  - chunks
  - ingestion jobs
  |
  +--> exact search
  |
  +--> local vector index
         |
         v
       semantic search
  |
  v
hybrid search
  |
  v
evidence check
  |
  v
answer provider
  - extractive
  - OpenAI
  - Ollama
  - DeepSeek
  |
  v
answer with citations
```

Main entry points:

- API: `app/main.py`
- Local HTML UI: `app/ui.py`
- PDF ingestion: `app/ingestion/`
- Retrieval: `app/retrieval/`
- Answer generation: `app/generation/`
- Evaluation: `app/evaluation/`
- Operational details: `docs/operations.md`

## What It Can Do

- Import one PDF or a folder of PDFs.
- Keep the original PDF unchanged in local storage.
- Extract page text with PyMuPDF.
- Use OCRmyPDF when a PDF has no usable text layer.
- Split text into deterministic page-linked chunks.
- Search by exact, semantic, or hybrid retrieval.
- Build a local FastEmbed vector index.
- Answer questions with source-linked citations.
- Refuse answers when the retrieved evidence is too weak.
- Suggest likely domain query fixes, for example `litation -> lithiation`.
- Evaluate retrieval and answer behavior with YAML question sets.

Not implemented as a completed feature:

- External metadata lookup.
- A full conversational chat UI.
- Automatic vector-index rebuild after every upload.

## Quick Start

Prerequisites:

- Python 3.11 or newer.
- A local PostgreSQL server.
- A database URL in `.env`.
- OCRmyPDF and Tesseract only if scanned PDFs must be processed.

Create local config:

```powershell
Copy-Item .env.example .env
```

Install the project:

```powershell
python -m pip install -e ".[dev]"
```

Run database migrations:

```powershell
python -m alembic upgrade head
```

Start the API and UI:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the UI:

```text
http://127.0.0.1:8000/ui/answer
```

Start the ingestion worker in another terminal:

```powershell
python -m app.workers.worker
```

## Example

Ask a question through the local UI:

```text
Li-Nafeon membrane litation pratocole
```

The UI should suggest a corrected query:

```text
Li-Nafion membrane lithiation protocol
```

After using the suggestion, the answer layer searches the corpus, checks whether the evidence is strong enough, and returns a cited answer or a refusal.

API example:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer `
  -ContentType application/json `
  -Body '{"question":"Li-Nafion membrane lithiation protocol","method":"hybrid","top_k":5,"answer_style":"mini_review"}'
```

Search example:

```text
GET /search?q=Li-Nafion%20conductivity&collection=literature&top_k=10&method=hybrid
```

## Add PDFs

Put PDFs in `data/inbox/`, then ingest one file:

```powershell
python -m app.ingestion.cli file data/inbox/example.pdf --collection literature
```

Or ingest a folder:

```powershell
python -m app.ingestion.cli folder data/inbox --collection literature
```

You can also upload through the browser:

```text
http://127.0.0.1:8000/ui/ingestion
```

An upload marked `indexed` means PostgreSQL article/page/chunk evidence is ready. Semantic and hybrid retrieval still require a current local vector index.

## Build The Vector Index

Build the local semantic index:

```powershell
python -m app.retrieval.cli build --embedding-model BAAI/bge-small-en-v1.5 --batch-size 64
```

Then use semantic or hybrid retrieval:

```text
GET /search?q=proton%20transport&collection=literature&top_k=10&method=semantic
GET /search?q=proton%20transport&collection=literature&top_k=10&method=hybrid
```

## Answer Providers

Default:

```text
RAG_PROVIDER=extractive
```

The extractive provider returns evidence snippets without calling an external model.

Optional providers:

```text
RAG_PROVIDER=openai
RAG_OPENAI_API_KEY=...
RAG_OPENAI_MODEL=...
```

```text
RAG_PROVIDER=ollama
RAG_MODEL=...
```

```text
RAG_PROVIDER=deepseek
RAG_DEEPSEEK_API_KEY=...
RAG_DEEPSEEK_MODEL=...
```

Generated claims are rejected if they omit citations or cite unknown evidence IDs.

## Evaluation

Run the baseline retrieval evaluation:

```powershell
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10
```

Run the extended evaluation:

```powershell
python -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --top-k 10 --method hybrid --check-thresholds
```

Run answer evaluation:

```powershell
python -m app.evaluation.cli answers docs/evaluation_questions.yaml --top-k 5 --method hybrid
```

## Development Checks

```powershell
ruff check .
ruff format --check .
mypy app
pytest -q
```

For the full operational checklist, see `docs/operations.md`.
