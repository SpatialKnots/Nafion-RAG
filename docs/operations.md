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

The default retrieval method is the exact baseline. It can also be selected explicitly:

```text
GET /search?q=Nafion&collection=literature&top_k=10&method=exact
```

The concrete result method is `exact_ilike`; failures mean the current exact indexed chunks did not contain the expected DOI or keywords in the returned snippets. Do not interpret this as semantic retrieval quality.

Run retrieval evaluation only after `docs/evaluation_questions.yaml` contains real expected DOI or keyword evidence:

```powershell
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10
```

Evaluation reports are written to `data/exports/retrieval_eval_*.json`.

The evaluation CLI also accepts an explicit method flag for Phase 3 comparisons:

```powershell
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10 --method exact
```

Only `exact` is implemented at this gate. `semantic` and `hybrid` must not be reported as available until the source implements them and evaluation proves them.

Phase 3 storage planning is recorded in:

```text
docs/phase3_storage_decision.md
```

For the current local environment, `pgvector` is not available, so the planned Phase 3 storage path is a rebuildable local vector index under `data/processed/vector_indexes/`. Generated index files are local artifacts and must remain rebuildable from database chunks and a manifest.

Write a manifest-only local vector index planning artifact after choosing an embedding model and dimension:

```powershell
python -m app.retrieval.cli manifest --embedding-model MODEL_ID --embedding-dimension DIMENSION
```

This command records chunk ids, article checksums, page/source metadata, chunk text checksums, corpus manifest checksum, and model metadata. It does not create embeddings and does not enable semantic or hybrid retrieval.

Evaluation questions can target articles by DOI, title, or checksum:

```yaml
expected_article_dois:
  - "10.1016/j.polymer.2009.01.060"
expected_article_titles:
  - "Диссертация Чернюк С.Д."
expected_article_checksums:
  - "9fc86c22463210456b39107e69c8cdf2589804a08c8da3a9c60e4f34c2293266"
```

Use title/checksum targets for DOI-less material. At least one article target is required, and missing DOI/title/checksum targets are reported separately.

The evaluation summary preserves top-k PASS/FAIL and also reports ranking metrics:

- `passed`: questions where expected article targets and expected keywords were found in the returned top-k snippets.
- `top_1_passed`: questions where the first result matched an expected article and expected keywords were found.
- `recall_at_k`: fraction of questions with an expected article anywhere in top-k.
- `mean_rank`: mean rank of the first expected article among questions where an expected article was found.

Each question also records `rank_of_expected` and per-question `recall_at_k`.

The current exact baseline question set contains 24 questions, including DOI-backed, DOI-less title/checksum, Russian, table-oriented, and intentionally broad ambiguity queries.

Write a corpus/retrieval inventory report after ingestion or evaluation changes:

```powershell
python -m app.ingestion.cli corpus-report
```

Corpus reports are written to `data/exports/corpus_report_*.json`. They include article and DOI coverage, page/chunk/text-layer totals, chunk source/text-layer distributions, missing original/OCR file counts, missing-DOI titles, and the latest retrieval evaluation summary when present.

Write the tracked corpus manifest after intentional corpus changes:

```powershell
python -m app.ingestion.cli corpus-manifest
```

The manifest is written to `docs/corpus_manifest.json`. It records per-article checksum, title, DOI, original/OCR PDF basenames, status, page count, chunk count, and text-layer count. It does not include PDF files or full local filesystem paths.

Check the current local corpus against the tracked manifest:

```powershell
python -m app.ingestion.cli corpus-manifest --check docs/corpus_manifest.json
```

The check emits JSON diagnostics and exits non-zero when an article is missing, extra, or changed relative to the manifest.

Inspect the latest retrieval evaluation report in the UI:

```text
http://127.0.0.1:8000/ui/reports/retrieval
```
