# Контекст из прошлого чата

> Это handoff-файл для передачи контекста в новую сессию. Прочитай, подтверди коротким "принял", и жди следующего сообщения пользователя.

**TL;DR:** Nafion-RAG стабилизирован как Phase 2 exact retrieval baseline; следующий план работ: tracked corpus manifest, поддержка DOI-less evaluation, усиление метрик retrieval, расширение eval до 20-25 вопросов, очистка pytest warning, затем Phase 3 semantic/hybrid design gate.

## О чем был чат

Работа шла в репозитории `D:\Nafion-RAG`. Проект рассматривается как локальная научная система ingestion/retrieval для корпуса Nafion/PFSA literature. По правилам `AGENTS.md` это не ORCAVEDA; нельзя заявлять embeddings, semantic search, hybrid search или RAG answers как реализованные, пока это не подтверждено source.

К началу этой части работы проект уже был доведен до чистого Phase 2 exact retrieval baseline: корпус восстановлен, `doctor` PASS, retrieval evaluation 4/4 PASS, изменения были закоммичены в `0fb983c Stabilize phase 2 retrieval baseline`.

## Что уже сделано в этой сессии

- Расширен `docs/evaluation_questions.yaml` с 4 до 15 exact retrieval gold-вопросов.
- Добавлены DOI-backed проверки по Kim, Welch, Mohammadi/Rabiee, Cho, Istomina, Reznitskikh, Kayumov, Chernyuk, Dai, Ma, Sanginov.
- Добавлены русскоязычные запросы для российских статей.
- Реализована CLI-команда:

```powershell
python -m app.ingestion.cli corpus-report
```

- `corpus-report` пишет полный JSON в `data/exports/corpus_report_*.json` и печатает компактный JSON с summary и latest retrieval eval.
- Отчет включает article/DOI coverage, totals по pages/chunks/text layers, distributions по `chunk_source_type` и `chunk_text_layer`, missing original/OCR counts, missing-DOI titles, latest retrieval eval summary.
- Команда задокументирована в `docs/operations.md`.
- Добавлены unit tests в `tests/unit/test_ingestion_cli.py`.

## Текущее подтвержденное состояние

Последние проверенные цифры corpus report:

- `articles`: 16
- `articles_with_doi`: 12
- `articles_without_doi`: 4
- `pages`: 321
- `chunks`: 379
- `text_layers`: 642
- `missing_original_files`: 0
- `missing_ocr_files`: 0

Последний retrieval eval:

- `total`: 15
- `passed`: 15
- `failed`: 0
- `empty_result_queries`: 0
- method: `exact_ilike`
- `top_k`: 10

## Команды и проверки, которые реально запускались

```powershell
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-report
.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval docs\evaluation_questions.yaml --top-k 10
.\.venv\Scripts\python.exe -m app.ingestion.cli doctor
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app
```

Финальные результаты:

- `corpus-report` написал `data\exports\corpus_report_20260803T064937Z.json`.
- retrieval eval написал `data\exports\retrieval_eval_20260803T064929Z.json` и показал 15/15 PASS.
- `doctor` all PASS.
- `pytest -q`: 60 passed, 1 warning по `.pytest_cache` access denied.
- `ruff check .`: passed.
- `mypy app`: passed.

## Измененные source/docs файлы в рабочем дереве

- `app/ingestion/cli.py`
  - добавлены `_latest_retrieval_eval`, `_count_by_value`, `_build_corpus_report`, `_write_corpus_report`;
  - добавлена команда `corpus-report`.
- `docs/evaluation_questions.yaml`
  - расширен exact retrieval eval set до 15 вопросов.
- `docs/operations.md`
  - добавлена инструкция по `corpus-report`.
- `tests/unit/test_ingestion_cli.py`
  - добавлены тесты для `corpus-report` и `_latest_retrieval_eval`.

На момент последней проверки эти изменения были uncommitted.

## Главные проблемы проекта сейчас

1. **Корпус не полностью воспроизводим между машинами**

   Локально все чисто, но PDF/OCR лежат в ignored `data/*`, не в git. При переносе проекта corpus надо восстанавливать отдельно.

2. **Gold eval все еще мал и частично top-k-oriented**

   Сейчас 15/15 PASS, но это smoke/baseline, не строгая оценка качества поиска. Некоторые вопросы проверяют попадание expected DOI в top-10, а не top-1.

3. **Exact retrieval путает близкие статьи**

   Широкие запросы про Nafion/solvents иногда поднимают старые или DOI-less материалы выше целевой статьи. Это ограничение текущего `exact_ilike`, не баг semantic retrieval.

4. **DOI-less статьи плохо представлены в evaluation**

   Есть 4 статьи без DOI:

   - Moore и Martin 1988
   - Sanginov 2021 - sup
   - Диссертация Чернюк С.Д.
   - Чернюк 2024

   Текущая eval-схема ожидает DOI, поэтому DOI-less материалы лучше проверять через title/checksum/article id после расширения схемы.

5. **Нет committed lightweight snapshot/manifest корпуса**

   `corpus-report` есть, но export-файлы ignored. Нужен tracked manifest без PDF, но с checksum/title/DOI/counts.

6. **`PytestCacheWarning`**

   `pytest` проходит, но есть `WinError 5` на `.pytest_cache`.

## План реализации

### 1. Tracked Corpus Manifest

Цель: зафиксировать проверяемый отпечаток корпуса без коммита PDF.

Изменения:

- Добавить команду `python -m app.ingestion.cli corpus-manifest`.
- Генерировать tracked файл, например `docs/corpus_manifest.json`.
- Включить `checksum_sha256`, `title`, `doi`, `pdf_original_basename`, `pdf_ocr_basename`, `status`, page count, chunk count, text-layer count.
- Не включать полные локальные пути и не включать PDF.
- Добавить режим проверки: `corpus-manifest --check docs/corpus_manifest.json`.

Критерий готовности:

- На текущей машине manifest генерируется и check проходит.
- При отсутствующем, лишнем или измененном article check возвращает non-zero и JSON diagnostics.

### 2. DOI-less Evaluation Support

Цель: нормально проверять Moore/Martin, Sanginov sup, диссертацию Чернюк, Чернюк 2024.

Изменения:

- Расширить `EvaluationQuestion`: поддержать optional `expected_article_titles` или `expected_article_checksums`.
- Сохранить backward compatibility с `expected_article_dois`.
- Обновить `docs/evaluation_questions.yaml`: добавить 4-6 вопросов по DOI-less материалам.
- Добавить unit tests на DOI-only, title/checksum-only и mixed expected targets.

Критерий готовности:

- Retrieval eval проходит на DOI-backed и DOI-less вопросах.
- Ошибки явно report missing DOI/title/checksum separately.

### 3. Stronger Retrieval Metrics

Цель: превратить smoke eval в baseline для сравнения будущих методов.

Изменения:

- В report добавить `top_1_passed`, `recall_at_k`, `rank_of_expected`.
- Для каждого вопроса фиксировать ранг первого expected article.
- Summary: `passed`, `top_1_passed`, `mean_rank`, `empty_result_queries`.
- Не менять retrieval scoring.

Критерий готовности:

- Старые PASS не ломаются.
- Появляется честное различие между "нашлось в top-k" и "первый результат правильный".

### 4. Eval Expansion To 20-25 Questions

Цель: покрыть реальные темы корпуса до Phase 3.

Категории:

- solution/recast Nafion
- casting solvents: DMF/DMSO/NMP/EtOH/DMAc
- Li-Nafion EC/SL/diglyme conductivity
- Russian queries
- DOI-less dissertation/supporting info
- table/method/source-type-specific queries
- intentionally broad ambiguity queries for measuring top-1 weakness

Критерий готовности:

- Все вопросы evidence-backed из indexed chunks.
- Baseline report показывает не только PASS, но и ранги.

### 5. Clean Test Environment Warning

Цель: убрать шум `PytestCacheWarning`.

Изменения:

- Проверить ACL/атрибуты `.pytest_cache`.
- Если это локальный permission artifact, удалить/пересоздать cache directory.
- Если не стоит чинить в коде, документировать как local environment limitation.

Критерий готовности:

- `pytest -q` без warning, либо явно зафиксированная limitation без кода.

### 6. Phase 3 Design Gate

Цель: только после сильного baseline проектировать semantic/hybrid.

Deliverable:

- `docs/phase3_retrieval_plan.md`.
- Описать методы, зависимости, storage, metrics, rollback, comparison against exact baseline.
- Не реализовывать embeddings до готового manifest + expanded eval.

## Рекомендуемый порядок

1. Tracked Corpus Manifest
2. DOI-less Evaluation Support
3. Stronger Retrieval Metrics
4. Eval Expansion To 20-25 Questions
5. Clean Test Environment Warning
6. Phase 3 Design Gate

## Ограничения и что не сломать

- Не заявлять embeddings, semantic search, hybrid search или RAG answers как готовые.
- Не менять retrieval scoring в задачах manifest/eval metrics без отдельного решения.
- Не коммитить PDF/OCR/export/backups из `data/*`.
- Сохранять source traceability: article, PDF path, page range, source type, selected text layer, exact text fragment where applicable.
- Не прятать ingestion/OCR/database/retrieval failures broad `try/except`.

## Что ожидаемо сделать дальше

Следующий практический шаг: реализовать `corpus-manifest` и `corpus-manifest --check docs/corpus_manifest.json`, добавить tests, сгенерировать tracked `docs/corpus_manifest.json`, прогнать `doctor`, `pytest`, `ruff`, `mypy`, retrieval eval и corpus report.
