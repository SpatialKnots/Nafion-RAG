# Контекст из прошлого чата

> Это handoff-файл для передачи контекста в новую сессию. Прочитай, подтверди коротким "принял", и жди следующего сообщения пользователя.

**TL;DR:** Nafion-RAG доведен до воспроизводимого Phase 2 exact retrieval baseline: добавлен tracked corpus manifest, DOI-less eval support, ranking metrics, eval расширен до 24 вопросов, все проверено и закоммичено в `8da27f7`.

## О чем был чат

Работа шла в репозитории `D:\Nafion-RAG`. Проект - локальная научная ingestion/retrieval система для Nafion/PFSA литературы.

По `AGENTS.md` это не ORCAVEDA: нельзя переносить ORCA/VEDA/PED-логику и нельзя заявлять embeddings, semantic search, hybrid search или RAG answers как реализованные, пока это не подтверждено source.

Пользователь дал handoff `D:\Nafion-RAG\docs\nafion_rag_next_steps_handoff.md` и попросил ознакомиться с инструкцией и приступить к реализации. Реализованы первые четыре практических шага из плана до Phase 3 gate.

## Главное, что сделано

- Реализован CLI `python -m app.ingestion.cli corpus-manifest`.
- Реализован check-режим `python -m app.ingestion.cli corpus-manifest --check docs\corpus_manifest.json`.
- Создан tracked manifest `docs/corpus_manifest.json` без PDF и без полных локальных путей.
- Manifest включает `checksum_sha256`, `title`, `doi`, `pdf_original_basename`, `pdf_ocr_basename`, `status`, `page_count`, `chunk_count`, `text_layer_count`.
- Check-режим возвращает JSON diagnostics и non-zero exit при missing/extra/changed articles, missing manifest, invalid JSON.
- Существующий `corpus-report` сохранен и используется как inventory report через `data/exports/corpus_report_*.json`.
- DOI-less evaluation support реализован в `app/evaluation/retrieval.py`: `expected_article_titles` и `expected_article_checksums`, backward-compatible с `expected_article_dois`.
- Missing DOI/title/checksum targets теперь report-ятся отдельно.
- Retrieval evaluation metrics усилены:
  - per-question `rank_of_expected`;
  - per-question `recall_at_k`;
  - per-question `top_1_passed`;
  - summary `top_1_passed`, `recall_at_k`, `mean_rank`;
  - старые `passed/failed` сохранены.
- `docs/evaluation_questions.yaml` расширен до 24 вопросов.
- Добавлены DOI-less вопросы по Moore/Martin 1988, Sanginov 2021 supplementary, диссертации Чернюк С.Д., Чернюк 2024.
- Добавлены broad/table/method/russian eval-вопросы, чтобы top-k PASS не скрывал top-1 weakness.
- Локальный `PytestCacheWarning` был вызван поврежденным ACL `.pytest_cache`; каталог удален и pytest пересоздал cache без warning.

## Текущее подтвержденное состояние

Последний commit:

```text
8da27f7 Stabilize retrieval baseline with manifest and expanded eval
```

Commit включает:

```text
app/evaluation/retrieval.py
app/ingestion/cli.py
docs/corpus_manifest.json
docs/evaluation_questions.yaml
docs/operations.md
tests/unit/test_evaluation.py
tests/unit/test_ingestion_cli.py
```

Commit stat:

```text
7 files changed, 1107 insertions(+), 9 deletions(-)
create mode 100644 docs/corpus_manifest.json
```

Текущий `git status --short` после commit:

```text
?? docs/nafion_rag_next_steps_handoff.md
```

`docs/nafion_rag_next_steps_handoff.md` оставлен untracked специально: это исходный handoff-файл, не включался в commit.

## Последние проверки, которые реально запускались

- `.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval docs\evaluation_questions.yaml --top-k 10`
  - summary: `total=24`, `passed=24`, `top_1_passed=18`, `failed=0`, `recall_at_k=1.0`, `mean_rank=1.4583333333333333`, `empty_result_queries=0`
  - latest report: `data\exports\retrieval_eval_20260803T082558Z.json`
- `.\.venv\Scripts\python.exe -m pytest -q`
  - `70 passed`
- `.\.venv\Scripts\python.exe -m ruff check .`
  - passed
- `.\.venv\Scripts\python.exe -m mypy app`
  - passed
- `.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-report`
  - latest report: `data\exports\corpus_report_20260803T082641Z.json`
  - summary: `articles=16`, `articles_with_doi=12`, `articles_without_doi=4`, `pages=321`, `chunks=379`, `text_layers=642`, `missing_original_files=0`, `missing_ocr_files=0`
  - latest eval summary loaded: 24/24 PASS with ranking metrics above
- `.\.venv\Scripts\python.exe -m app.ingestion.cli doctor`
  - all PASS
  - DB reachable, migrations at `0002_dual_text_layers`, corpus files present, OCRmyPDF/Tesseract/Ghostscript resolved, `eng` and `rus` installed
- `.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-manifest --check docs\corpus_manifest.json`
  - `{"status":"match","summary_changed":false,"missing_articles":[],"extra_articles":[],"changed_articles":[]}`

## Важные файлы

- `app/ingestion/cli.py`
  - содержит `corpus-report`, `corpus-manifest`, manifest build/write/check helpers.
- `app/evaluation/retrieval.py`
  - содержит expanded `EvaluationQuestion`, DOI/title/checksum matching, rank metrics.
- `docs/corpus_manifest.json`
  - tracked corpus snapshot.
- `docs/evaluation_questions.yaml`
  - 24-question exact retrieval gold set.
- `docs/operations.md`
  - обновленные инструкции по corpus report, manifest, DOI-less eval targets и metrics.
- `tests/unit/test_ingestion_cli.py`
  - tests для corpus report/manifest.
- `tests/unit/test_evaluation.py`
  - tests для DOI-less targets и ranking metrics.
- `docs/nafion_rag_next_steps_handoff.md`
  - untracked исходный handoff/план; не коммитился.

## Ключевые решения и ограничения

- Retrieval scoring не менялся. Все сделанное - baseline/report/evaluation layer.
- `exact_search` и API search schema не менялись ради checksum matching. Checksums подтягиваются внутри evaluation по `article_id -> checksum`.
- DOI-less статьи проверяются через title/checksum targets.
- `top_1_passed` считается как expected article на rank 1 плюс expected keywords найдены в top-k snippets.
- `passed` означает old-style top-k baseline: expected article targets и expected keywords найдены в returned top-k snippets.
- Broad queries намеренно добавлены, чтобы baseline показывал слабость top-1: сейчас 24/24 top-k PASS, но только 18/24 top-1 PASS.
- Не коммитить PDF/OCR/export/backups из `data/*`; exports остаются ignored.
- Не заявлять semantic/hybrid/RAG как реализованные.

## Что осталось по исходному плану

Следующий шаг из handoff: **Phase 3 Design Gate**.

Ожидаемый deliverable:

- `docs/phase3_retrieval_plan.md`

Содержание по плану:

- методы semantic/hybrid retrieval;
- зависимости;
- storage;
- metrics;
- rollback;
- comparison against exact baseline;
- design gate до реализации embeddings.

Важно: не реализовывать embeddings/semantic/hybrid до готового design plan и явного решения пользователя.

## Риски / что не сломать

- Не менять retrieval scoring в рамках Phase 3 planning без явного решения.
- Не менять output schemas ingestion/retrieval/eval без диагностики и tests.
- Не удалять diagnostics ради "чистого" вывода.
- Не трогать original PDFs после ingestion.
- Сохранять source traceability: article, PDF path/page range/source type/text layer/snippet where applicable.
- Рабочее дерево после commit было чистое по tracked files; единственный untracked файл на тот момент - `docs/nafion_rag_next_steps_handoff.md`.
