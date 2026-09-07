<p align="center">
  <img src="app/static/brand/ariadne-logo-horizontal.png" alt="ARIADNE" width="520">
</p>

# ARIADNE

Current planning: [дорожная карта проекта](docs/roadmap.md) — состояние реализации,
ближайшие этапы и критерии готовности (сверка 2026-09-07).

## Current Status — 2026-09-07

ARIADNE is in stage 2 of the [roadmap](docs/roadmap.md): retrieval quality
evaluation. The core PDF ingestion, OCR, indexing, search and source-navigation
workflow has passed an [integration acceptance check](docs/stage1_acceptance_2026-09-07.md).
Full failure-recovery and scaling acceptance remain open.

The checked local corpus contains 33 articles, 493 pages and 619 chunks.
On the 46-question extended gold set, all four audited retrieval methods retained
article Recall@10=1.0. The [grouping audit](docs/stage2_grouping_audit_2026-09-07.md)
found that keeping one chunk per article can hide required semantic evidence:
chunk Recall fell from 1.0 to 0.923077 across the 13 questions with chunk targets.
Keeping two chunks preserved Recall on this set; broader coverage is still unverified.

Evidence adequacy is heuristic: an unanswerable PBI question was incorrectly
accepted as having sufficient evidence by cross-lingual retrieval. Citation
validation does not establish scientific correctness. Scientific acceptance of
numeric extraction and generated answers, plus scaling benchmarks, remains ahead.

## Overview

ARIADNE is a local-first research system for building a trustworthy scientific memory from a focused PDF corpus about Nafion, PFSA membranes, and related lithium-ion battery literature.

The project is built around a simple principle: every answer must remain connected to the document that supports it. ARIADNE takes raw scientific PDFs, preserves the original files, extracts page-level text, breaks the corpus into stable source-linked fragments, and lets the user search or ask questions against that evidence. When the system answers, it returns citations back to the article, chunk, and page instead of treating generated text as a source of truth.

This makes ARIADNE useful as a local research companion for careful literature work: it helps inspect a specialized corpus, compare evidence across articles, catch weak or missing support, and keep scientific claims traceable. The system is intentionally conservative: if the retrieved evidence is not strong enough, it should refuse or expose the limitation rather than invent a confident answer.

## How It Works

ARIADNE turns a folder of PDFs into an auditable retrieval and answer pipeline:

1. Original PDFs are copied into local storage and kept immutable.
2. Page text is extracted from the PDF text layer, with OCR available for scanned documents.
3. Extracted text is stored in PostgreSQL with article, page, chunk, source type, and text-layer provenance.
4. Search can use exact matching, a local semantic vector index, or a hybrid of both.
5. Answer generation receives only retrieved evidence fragments and must cite known evidence IDs.
6. The API and local HTML UI expose search results, citations, PDF page links, and answer diagnostics.

The result is not a generic chatbot over PDFs. It is a source-preserving workflow where ingestion, retrieval, generation, and evaluation each leave evidence that can be inspected.

## Technical Map

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
  - OpenAI
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
- Add persistent local PDF libraries and scan them from the UI.
- Keep the original PDF unchanged in local storage.
- Extract page text with PyMuPDF.
- Use OCRmyPDF when a PDF has no usable text layer.
- Split text into deterministic page-linked chunks.
- Search by exact, semantic, or hybrid retrieval.
- Build a local FastEmbed vector index.
- Answer questions with source-linked citations.
- Produce OpenAI mini-reviews grouped by article.
- Link answer citation markers to the cited PDF page.
- Apply an evidence-adequacy heuristic that can refuse answers when support appears too weak.
- Suggest likely domain query fixes, for example `litation -> lithiation`.
- Evaluate retrieval and answer behavior with YAML question sets.

Not implemented as a completed feature:

- External metadata lookup.
- A full conversational chat UI.

Vector-index rebuilds run in the background when `VECTOR_AUTO_REBUILD_ENABLED=true`
and a worker with role `vector` or `all` is running. Upload completion means text
is ready; semantic/hybrid readiness follows the separate index state. Rebuild
requests are coalesced, so this is not a synchronous rebuild for every upload.

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

After using the suggestion, the answer layer searches the corpus with cross-lingual query variants, checks whether the evidence is strong enough, and returns a cited answer or a refusal.

API example:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer `
  -ContentType application/json `
  -Body '{"question":"Li-Nafion membrane lithiation protocol","method":"hybrid_cross_lingual","top_k":5,"answer_style":"mini_review"}'
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

Persistent local folders can be added at:

```text
http://127.0.0.1:8000/ui/libraries
```

Use `Add Library` to register a folder and `Scan Now` to discover PDFs and queue ingestion jobs. The worker also scans enabled libraries periodically when `LIBRARY_SCAN_ENABLED=true`.

The dashboard, ingestion page, and libraries page show recognition and text-analysis progress from persisted job and library-file statuses, including discovered, queued, in-processing, text/OCR-ready, duplicate, missing, and failed files.

## Build The Vector Index

Build the local semantic index:

```powershell
python -m app.retrieval.cli build --embedding-model BAAI/bge-small-en-v1.5 --batch-size 64
```

Then use semantic, hybrid, or cross-lingual hybrid retrieval:

```text
GET /search?q=proton%20transport&collection=literature&top_k=10&method=semantic
GET /search?q=proton%20transport&collection=literature&top_k=10&method=hybrid
GET /search?q=proton%20transport&collection=literature&top_k=10&method=hybrid_cross_lingual
```

## Answer Providers

Supported provider:

```text
RAG_PROVIDER=openai
RAG_OPENAI_API_KEY=...
RAG_OPENAI_MODEL=...
```

OpenAI generates structured evidence-grounded claims from retrieved source fragments. Generated claims are rejected if they omit citations or cite unknown evidence IDs.

For `answer_style=mini_review`, the answer layer keeps the output article-centered: evidence from the same article is consolidated into one article/work claim with all relevant citation IDs attached once. Citation markers such as `[E1]` and `[E2]` resolve to the original PDF page where the cited fragment starts, while the UI still exposes context links for inspecting neighboring chunks.

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
