# Приоритет 6: таблицы, подписи, формулы и OCR

## Статус документа

Этап реализован как audit-first Priority 6 без отдельной таблицы extracted
evidence и без изменения оригинальных PDF. Реализованы text-quality audit,
reprocess dry-run diagnostics, table/caption/formula source-type detection,
OCR diagnostics и отдельный Priority 6 retrieval evaluation set.

Acceptance smoke на текущем локальном корпусе:

- `python -m app.evaluation.cli retrieval docs\evaluation_questions_priority6.yaml --top-k 10 --method exact`
  - 6/6 PASS, Recall@10 1.0.
- `python -m app.evaluation.cli retrieval docs\evaluation_questions_priority6.yaml --top-k 10 --method semantic`
  - 6/6 PASS, Recall@10 1.0.
- `python -m app.evaluation.cli retrieval docs\evaluation_questions_priority6.yaml --top-k 10 --method hybrid`
  - 6/6 PASS, Recall@10 1.0.

Изменения extraction/chunking, новая storage schema для extracted evidence,
bbox extraction и symbolic formula parsing не выполнялись и остаются отдельными
будущими решениями.

Этот этап научно рискованнее предыдущих: он может изменить состав chunks и
retrieval evidence. Поэтому любые изменения extraction/chunking должны иметь
явную миграционную или reprocessing-процедуру, diagnostics и evaluation.

## 1. Цель

Повысить полноту поиска по научным данным, которые обычное извлечение текста
теряет или искажает:

- таблицы;
- подписи к рисункам и таблицам;
- формулы;
- числовые значения;
- страницы со слабым original text layer;
- OCR-слои.

## 2. Текущее основание

Сейчас система:

- извлекает page-level text через PyMuPDF;
- выбирает original/OCR text layer;
- сохраняет `Page`, `PageTextLayer`, `Chunk`;
- классифицирует chunks по source type;
- может запускать OCRmyPDF;
- не хранит reliable bbox для chunks/tables;
- не имеет отдельной таблицы extracted tables/captions;
- evaluation проверяет retrieval на уровне article/chunk, но не достаточно
  покрывает table/formula evidence.

## 3. Границы этапа

### Входит

- audit качества text layers;
- report страниц с малым/пустым/подозрительным текстом;
- проверка table/caption extraction на текущем corpus;
- добавление новых source types только при подтверждённой пользе;
- reprocessing command для выбранных articles;
- сохранение bbox/page coordinates только если extractor даёт устойчивые данные;
- evaluation questions для tables/captions/formulas/numeric values;
- diagnostics doctor/report для OCR и extraction quality.

### Не входит

- изменение оригинальных PDF;
- cloud OCR;
- внешние metadata services;
- ручная разметка всех таблиц корпуса;
- computer vision model без отдельного benchmark;
- научная интерпретация таблиц;
- LLM extraction.

## 4. Audit first

Перед изменением extraction нужно добавить command:

```powershell
python -m app.ingestion.cli text-quality-report --collection literature
```

Report fields:

```json
{
  "collection": "literature",
  "article_count": 17,
  "page_count": 326,
  "empty_original_pages": 0,
  "short_original_pages": [],
  "ocr_used_pages": 0,
  "suspicious_pages": [],
  "source_type_distribution": {},
  "text_layer_distribution": {}
}
```

Suspicious signals:

- page text empty;
- char count below threshold;
- high ratio of replacement/control characters;
- repeated extraction artifacts;
- page has table-like density but no table/caption terms;
- OCR layer exists but selected original is much shorter.

The audit must not modify DB.

## 5. Extraction strategy

### 5.1. Captions

Detect candidate captions from stored page text:

```text
Table 1.
Figure 2.
Fig. 3.
Рис. 1.
Таблица 2.
```

Initial implementation can classify caption chunks or page fragments without
new storage, if evidence remains traceable.

If new storage is justified:

```text
extracted_evidence
  id UUID
  article_id UUID
  page_number INT
  evidence_type TEXT  -- table_caption, figure_caption, formula_block, table_text
  text TEXT
  bbox JSONB NULL
  source_layer TEXT
  extractor TEXT
  checksum_sha256 TEXT
```

This requires Alembic migration and reprocessing path.

### 5.2. Tables

Options to evaluate:

- PyMuPDF text blocks;
- pdfplumber table extraction;
- Camelot/Tabula only if local dependencies are acceptable;
- simple line/table heuristics for text-layer tables.

Selection criteria:

- reproducible locally;
- preserves page number;
- does not require cloud service;
- failure is diagnostic;
- does not silently invent cell boundaries.

### 5.3. Formulas

Formula support starts as retrieval evidence, not symbolic math parsing.

Initial scope:

- preserve formula-looking lines;
- avoid dropping Greek letters/superscripts where text layer provides them;
- add evaluation queries for known formula-like evidence;
- report where formula extraction is poor.

## 6. OCR improvements

Add diagnostics, not blind retry loops:

- OCR command/version in report;
- selected language packs;
- count pages where OCR chosen;
- compare original vs OCR char count and quality score;
- report OCR completed but still unusable;
- preserve original PDF immutability.

Possible settings:

```text
TEXT_QUALITY_SHORT_PAGE_CHARS=200
TEXT_QUALITY_CONTROL_CHAR_RATIO=0.02
OCR_REPROCESS_ALLOW_EXISTING=false
```

## 7. Reprocessing

If extraction behavior changes chunks, add explicit command:

```powershell
python -m app.ingestion.cli reprocess-article <article_id> --mode text-quality
```

Rules:

- dry-run available;
- backup current chunk/page/text-layer metadata before mutation;
- mutation marks vector index stale;
- duplicate detection remains checksum-based;
- original PDFs are not changed;
- failures leave article in previous usable state or explicit failed repair state.

## 8. Evaluation

Add questions for:

- table captions;
- figure captions;
- numeric conductivity values;
- solvent names inside tables;
- Russian table/caption terms;
- formula-like terms.

Reports should separate:

```text
source_type=table
source_type=figure_caption
source_type=method
text_layer=ocr
```

## 9. Tests

Required:

- text-quality report unit tests;
- caption detection tests in English/Russian;
- table extraction adapter tests with small fixture text/PDF where possible;
- reprocess dry-run tests;
- stale invalidation after reprocess;
- no mutation on audit command;
- doctor diagnostics tests;
- evaluation tests for source type filters if priority 4 is complete.

## 10. Acceptance criteria

Этап готов, если:

- audit report runs on local corpus and is reproducible;
- any new extracted evidence preserves article/page/source layer;
- OCR failures are diagnostic;
- original PDF files are not modified;
- vector index is invalidated after any chunk/evidence mutation;
- evaluation includes table/caption/formula examples;
- tests, Ruff, mypy pass;
- smoke test shows improved or at least better diagnosed retrieval for targeted
  table/caption questions.

## 11. Rollback

Rollback depends on whether schema changes are introduced.

If no schema migration:

- revert extraction/classification/reprocess code;
- rebuild vector index from current chunks if chunks changed.

If schema migration exists:

- stop workers;
- downgrade only new evidence tables;
- keep PDF and original chunks backups;
- rebuild vector index for current corpus.
