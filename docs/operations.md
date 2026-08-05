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

Phase 2 remains the exact retrieval baseline for the small real corpus. Later phases add explicit semantic and hybrid methods without changing that baseline or implementing RAG answers.

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
http://127.0.0.1:8000/ui/ingestion
```

Open source PDFs and stored page text through backend routes:

```text
GET /articles/{article_id}/pdf?layer=original
GET /articles/{article_id}/pdf?layer=ocr
GET /articles/{article_id}/pages/{page_number}?layer=selected
```

The `original` PDF route is the primary audit link. OCR PDF access is available only when `Article.pdf_ocr_path` is registered and resolves inside `data/processed/ocr`. Search results include `pdf_page_url` values such as `/articles/{article_id}/pdf?layer=original#page=7`; the page jump depends on the browser PDF viewer honoring `#page=N`, so keep the visible page number from the result as the audit reference.

Document access diagnostics:

- Unknown articles or unavailable PDF/page/layer evidence return `404`.
- Unknown enum values for `layer` return FastAPI validation errors.
- Stored paths outside the allowed root return `500` without exposing the local path.
- Missing files return `404`; restore the PDF/OCR artifact or re-ingest the article after verifying the original checksum.

## Upload Ingestion Queue

Run the API and one worker in separate terminals:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m app.workers.worker
```

Upload through the UI at `/ui/ingestion` or through:

```text
POST /ingestion/uploads
GET /ingestion/jobs
GET /ingestion/jobs/{job_id}
```

Uploads are streamed to `data/uploads/incoming` and moved to `data/uploads/queued` only after validation. Accepted files become `queued` jobs. The worker claims jobs with a database lock, updates `attempt_count`, `worker_id`, and heartbeat, and then runs the existing ingestion pipeline.

Operational notes:

- `indexed` means PostgreSQL evidence is ready; semantic/hybrid vector artifacts are not rebuilt automatically in Priority 2.
- Duplicate uploads return a terminal `duplicate` job with the existing `article_id`.
- Failed jobs keep their queued staged file for diagnostics; cleanups must stay inside `data/uploads` and must not touch `data/pdf`.
- If a worker dies, stale `processing` jobs are requeued after `INGESTION_LEASE_SECONDS` until `INGESTION_MAX_ATTEMPTS` is exhausted.

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

After building a valid local vector index, select semantic retrieval explicitly:

```text
GET /search?q=proton%20transport&collection=literature&top_k=10&method=semantic
```

Semantic results use `retrieval_method=semantic_cosine` and include top-level metadata for the embedding model, dimension, manifest checksum, backend, similarity, and indexed chunk count. `source_type` filtering is supported by all three implemented methods.

Run hybrid retrieval explicitly:

```text
GET /search?q=proton%20transport&collection=literature&top_k=10&method=hybrid
```

Hybrid uses equal-weight reciprocal rank fusion with `HYBRID_RRF_K=60` and retrieves `top_k * HYBRID_CANDIDATE_MULTIPLIER` candidates from each component. The default multiplier is 5. Results use `retrieval_method=hybrid_rrf` and expose `method_scores` plus `method_ranks`. A semantic index failure aborts hybrid retrieval; there is no silent exact-only fallback.

Run retrieval evaluation only after `docs/evaluation_questions.yaml` contains real expected DOI or keyword evidence:

```powershell
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10
```

Evaluation reports are written to `data/exports/retrieval_eval_*.json`.

The evaluation CLI also accepts an explicit method flag for Phase 3 comparisons:

```powershell
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10 --method exact
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10 --method semantic
python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10 --method hybrid
```

`exact`, `semantic`, and `hybrid` are implemented. `exact` remains the default pending a separate default-method decision.

Compare reports produced with the same collection, question set, and `top_k`:

```powershell
python -m app.evaluation.cli compare data/exports/retrieval_eval_exact_TIMESTAMP.json data/exports/retrieval_eval_semantic_TIMESTAMP.json
```

The comparison reports metric deltas, per-question rank changes, regressions where exact passed and the candidate failed, and improvements where the candidate moved a non-top-1 exact result to top-1.

Generate a three-method comparison:

```powershell
python -m app.evaluation.cli compare-methods EXACT_REPORT SEMANTIC_REPORT HYBRID_REPORT
```

This report separates top-k PASS regressions from top-1 regressions and records all three ranks for every evaluation question.

Phase 3 storage planning is recorded in:

```text
docs/phase3_storage_decision.md
```

For the current local environment, `pgvector` is not available, so the planned Phase 3 storage path is a rebuildable local vector index under `data/processed/vector_indexes/`. Generated index files are local artifacts and must remain rebuildable from database chunks and a manifest.

Write a manifest-only local vector index planning artifact after choosing an embedding model and dimension:

```powershell
python -m app.retrieval.cli manifest --embedding-model MODEL_ID --embedding-dimension DIMENSION
```

This command records chunk ids, article checksums, page/source metadata, chunk text checksums, corpus manifest checksum, and model metadata. It does not create embeddings and cannot be used by semantic retrieval because its status is `manifest_only`.

Build the local vector artifacts after FastEmbed is installed and the model choice is accepted:

```powershell
python -m app.retrieval.cli build --embedding-model BAAI/bge-small-en-v1.5 --batch-size 64
```

The build command writes ignored local artifacts under `data/processed/vector_indexes/<model>/`: `embeddings.npy`, `chunk_ids.json`, and `manifest.json`. Manifest schema v2 records SHA-256 checksums for both artifact files, cosine normalization, model metadata, and source checksums.

Semantic retrieval rejects manifest v1, `manifest_only` output, missing or modified artifact files, model/dimension mismatches, non-finite or non-normalized vectors, changed corpus manifests, and any database chunk or text mismatch. Rebuild the index with the build command after intentional corpus, model, or manifest changes.

The first Phase 3 runtime is FastEmbed with `BAAI/bge-small-en-v1.5` as the initial local model. The model has 384 dimensions. First use may download model files from HuggingFace. On Windows, HuggingFace may warn that symlink-based cache optimization is unavailable; this affects cache efficiency, not the validity of the built index.

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

The accepted semantic evaluation and default-method decision are recorded in `docs/phase3_semantic_evaluation.md`.

The accepted hybrid RRF evaluation is recorded in `docs/phase3_hybrid_evaluation.md`.

## Evidence-Grounded Answers

The `/answer` endpoint uses hybrid retrieval by default and returns structured claims plus source citations:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer `
  -ContentType application/json `
  -Body '{"question":"How was Nafion conductivity measured?","collection":"literature","top_k":5,"method":"hybrid"}'
```

Default local configuration:

```text
RAG_PROVIDER=extractive
RAG_RETRIEVAL_METHOD=hybrid
RAG_TOP_K=5
RAG_MAX_CLAIMS=5
```

Extractive mode copies retrieved snippets into claims and therefore supports exact text-level grounding without a model runtime. Every answer includes article ID, chunk ID, title, DOI when available, page range, source type, retrieval score, and component ranks/scores.

Optional Ollama configuration:

```text
RAG_PROVIDER=ollama
RAG_OLLAMA_URL=http://127.0.0.1:11434
RAG_MODEL=<operator-installed-model>
RAG_TIMEOUT_SECONDS=120
```

The application does not install Ollama or download a model. Missing runtime/model returns HTTP 503. Invalid JSON, empty answerable claims, uncited claims, or unknown citation IDs return HTTP 502. Retrieval/configuration errors return HTTP 400.

Run structural and gold-target answer evaluation:

```powershell
python -m app.evaluation.cli answers docs/evaluation_questions.yaml --top-k 5 --method hybrid
```

This evaluation checks target articles, expected keywords, citation coverage, refusals, and exact extractive claims. It does not establish scientific entailment or correctness of prose generated by an external model.

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

## Extended Retrieval Evaluation

Priority 8 adds a separate extended evaluation path. It does not change search
scoring or the legacy `retrieval` command.

Run the seed extended set:

```powershell
python -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --top-k 10 --method exact
```

Run threshold checks:

```powershell
python -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --top-k 10 --method exact --check-thresholds
```

Thresholds live in:

```text
docs/evaluation_thresholds.yaml
```

Extended reports are written to:

```text
data/exports/retrieval_eval_extended_<method>_<timestamp>.json
```

The extended schema supports:

- graded article targets by DOI, title, title substring, checksum, or article ID;
- chunk targets by chunk ID or stable text fragments scoped to an article;
- answerable and unanswerable questions;
- article Recall@k, Precision@k, MRR, nDCG@k, chunk Recall@k, latency, and evidence trace completeness.
- deterministic evidence-adequacy diagnostics for unanswerable controls.

Unanswerable controls are not expected to return an empty retrieval list. They
pass when retrieved snippets fail the shared evidence-adequacy policy and would
therefore be treated as `insufficient_evidence` by the answer layer.
