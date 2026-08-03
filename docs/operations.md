# Operations Checklist

Use this checklist before indexing a real corpus or running retrieval evaluation.

## Phase 1 Ingestion Baseline

Run the environment doctor:

```powershell
python -m app.ingestion.cli doctor
```

Required PASS checks for normal ingestion:

- `database`: PostgreSQL is reachable through `DATABASE_URL`.
- `migrations`: the database is at the current Alembic head.
- `data_root`: `DATA_ROOT` is writable.
- `corpus_files`: indexed original/OCR PDF paths still exist on disk.
- `ocr_command`: OCRmyPDF is resolvable when scanned PDFs may be ingested.
- `tesseract_languages`: Tesseract has all configured `OCR_LANGUAGES`, currently `eng+rus`.
- `ghostscript`: Ghostscript is resolvable for OCRmyPDF.

If `corpus_files` reports `WARN`, exact retrieval may still work from stored chunks, but source audit and text-layer reselection are not reproducible until the missing PDFs are restored or the affected articles are re-ingested.

If the missing files belong to obsolete test records or intentionally discarded local entries, inspect and prune them with:

```powershell
python -m app.ingestion.cli prune-missing-corpus
python -m app.ingestion.cli prune-missing-corpus --apply
```

The `--apply` mode writes a JSON backup to `data/backups/` before deleting records from the local database.

If `tesseract_languages` reports missing `rus`, Russian OCR is not ready even though the code is configured for `eng+rus`.

The application also supports a project-local Tesseract language directory:

```text
data/tessdata/
```

When this directory exists, OCR commands run with `TESSDATA_PREFIX` pointed at it. Put `rus.traineddata` there to enable Russian OCR without modifying the system Tesseract installation. Re-run:

```powershell
python -m app.ingestion.cli doctor
```

The `tesseract_languages` check should report `PASS` and include `rus` in `installed`.

## Phase 2 Retrieval Baseline

Phase 2 is an exact retrieval baseline for a small real corpus. It does not implement embeddings, semantic search, hybrid search, RAG answers, or external metadata lookup.

Run migrations before indexing a real corpus:

```powershell
python -m alembic upgrade head
```

Put manually selected PDFs in:

```text
data/inbox/
```

Ingest the corpus into the default literature collection:

```powershell
python -m app.ingestion.cli folder data/inbox --collection literature
```

Inspect indexed articles, selected text layers, chunks, and source page ranges in the UI:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/ui/articles
```

Run exact retrieval through the API after PDFs have been indexed:

Then query:

```text
GET /search?q=Nafion&collection=literature&top_k=10
```

The retrieval method is `exact_ilike`; failures mean the current exact indexed chunks did not contain the expected DOI or keywords in the returned snippets. Do not interpret this as semantic retrieval quality.

Run retrieval evaluation only after `docs/evaluation_questions.yaml` contains real expected DOI or keyword evidence:

```powershell
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10
```

Evaluation reports are written to `data/exports/retrieval_eval_*.json`.

Inspect the latest retrieval evaluation report in the UI:

```text
http://127.0.0.1:8000/ui/reports/retrieval
```
