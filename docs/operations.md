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
- `ocr_command`: OCRmyPDF is resolvable when scanned PDFs may be ingested.
- `tesseract_languages`: Tesseract has all configured `OCR_LANGUAGES`, currently `eng+rus`.
- `ghostscript`: Ghostscript is resolvable for OCRmyPDF.

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

Run exact retrieval through the API after PDFs have been indexed:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then query:

```text
GET /search?q=Nafion&collection=literature&top_k=10
```

Run retrieval evaluation only after `docs/evaluation_questions.yaml` contains real expected DOI or keyword evidence:

```powershell
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10
```

Evaluation reports are written to `data/exports/retrieval_eval_*.json`.
