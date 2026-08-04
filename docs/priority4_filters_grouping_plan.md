# Приоритет 4: фильтры и группировка результатов

## Статус документа

Это подробный технический план для согласования. Описанные API, параметры
поиска, UI-элементы и изменения evaluation ещё не считаются реализованными.

План начинается после закрытия приоритетов 1-3: PDF/page access, ingestion jobs
и lifecycle векторного индекса уже должны быть доступны. Этот этап не меняет
извлечение текста, OCR, chunking, embedding model, RRF scoring и жизненный цикл
индекса.

## 1. Цель

Сделать поиск управляемым на растущем корпусе и уменьшить дублирование выдачи,
когда один запрос возвращает много чанков из одной статьи.

После завершения этапа пользователь должен уметь:

- ограничить поиск по реально хранимым metadata;
- применять одинаковые фильтры к `exact`, `semantic` и `hybrid`;
- получать выдачу либо как список чанков, либо сгруппированную по статьям;
- ограничивать число чанков от одной статьи;
- видеть диагностику: какие фильтры применены, сколько результатов осталось,
  какие исходные ранги были у сгруппированных чанков.

## 2. Текущее основание

На момент подготовки плана:

- search API поддерживает `q`, `collection`, `top_k`, `source_type`, `method`;
- `exact`, `semantic` и `hybrid` возвращают `SearchResponse`;
- результат содержит article id, chunk id, page range, source type, text layer,
  snippet, score, retrieval method и PDF links;
- hybrid использует RRF поверх exact и semantic;
- в БД есть `Article`, `Chunk`, `Page`, `ArticleTag`, `Collection`;
- DOI, year, journal, title, source type, text layer и tags уже хранятся, но
  качество заполнения metadata неодинаково;
- UI search page имеет базовые поля query/collection/source_type/method/top_k.

## 3. Границы этапа

### Входит

- фильтры по полям, которые уже есть в БД;
- единый объект фильтров для exact/semantic/hybrid;
- фильтрация по article id, DOI, year/year range, journal, source type,
  text layer, tag type/value;
- author filter только если текущая JSONB-структура позволяет безопасный и
  воспроизводимый запрос;
- группировка результатов по article;
- `chunks_per_article` limit;
- API serialization для grouped и ungrouped режимов;
- UI controls для основных фильтров;
- evaluation-сравнение grouped vs ungrouped;
- тесты на одинаковую семантику фильтров.

### Не входит

- изменение ranking формул;
- изменение chunking/OCR/extraction;
- нормализация или enrichment metadata через внешние сервисы;
- полнотекстовый PostgreSQL search вместо текущего exact baseline;
- новый embedding model;
- LLM/reranker;
- правка качества DOI/title/year в существующем corpus, кроме тестовых фикстур.

## 4. API contract

Расширить `GET /search`.

Новые query parameters:

```text
article_id=UUID
doi=10.xxxx/example
year=2015
year_from=2000
year_to=2024
journal=Journal name
source_type=method
text_layer=ocr
tag_type=material
tag_value=Nafion
group_by=none|article
chunks_per_article=1
include_group_diagnostics=true|false
```

Правила:

- `group_by` по умолчанию `none`, чтобы не ломать существующий API.
- `chunks_per_article` применяется только при `group_by=article` или при явном
  request на per-article limiting.
- `year` нельзя смешивать с `year_from/year_to`, иначе `422` или
  согласованный `400`.
- пустые строки фильтров игнорируются после `strip`.
- неизвестная collection остаётся ошибкой.
- фильтры не должны silently fallback на broader search.

Пример ungrouped response остаётся совместимым:

```json
{
  "query": "Nafion conductivity",
  "results": [],
  "metadata": {
    "filters": {
      "source_type": "method",
      "year_from": 2010
    }
  }
}
```

Grouped response:

```json
{
  "query": "Nafion conductivity",
  "groups": [
    {
      "article_id": "...",
      "title": "...",
      "doi": "...",
      "year": 2015,
      "journal": "...",
      "best_score": 0.91,
      "best_page_start": 4,
      "best_page_end": 5,
      "result_count": 3,
      "results": []
    }
  ],
  "metadata": {
    "group_by": "article",
    "chunks_per_article": 3,
    "filters": {}
  }
}
```

## 5. Internal design

### 5.1. Filter object

Добавить dataclass или Pydantic model:

```python
SearchFilters(
    article_id: UUID | None,
    doi: str | None,
    year: int | None,
    year_from: int | None,
    year_to: int | None,
    journal: str | None,
    source_type: str | None,
    text_layer: str | None,
    tag_type: str | None,
    tag_value: str | None,
)
```

Нормализация должна быть централизована, чтобы API, UI, CLI/evaluation не
расходились.

### 5.2. SQL filter application

Сделать helper:

```python
apply_search_filters(statement, filters)
```

Он должен:

- применять article/year/journal/doi filters через `Article`;
- применять source/text layer filters через `Chunk`;
- применять tag filters через join/subquery на `ArticleTag`;
- не менять order_by и scoring;
- не дублировать строки при tag joins.

Для semantic search нельзя сначала взять top-k без фильтра, а потом фильтровать:
иначе результаты за пределами top-k потеряются. Нужно фильтровать candidate rows
до score sorting или строить filtered row set на DB-side и применять scores
только к допустимым chunk ids.

### 5.3. Grouping

Группировка выполняется после получения ranked chunk results.

Правила:

- порядок групп определяется лучшим ranked chunk внутри article;
- `best_score` берётся из лучшего chunk;
- `result_count` отражает число chunk results в группе до `chunks_per_article`
  или отдельно `total_result_count`, если нужно;
- внутри группы chunks сохраняют исходный порядок метода;
- diagnostics хранят method ranks/scores для hybrid.

## 6. UI

Обновить `/ui/search`:

- добавить поля year/year range;
- DOI;
- journal;
- source type;
- text layer;
- tag type/value;
- group by article checkbox/select;
- chunks per article numeric input;
- показывать grouped table: Article, best pages, method, best score, chunks.

UI не должен превращаться в landing page. Это рабочий search dashboard.

## 7. Evaluation

Добавить scenarios:

- фильтр `source_type=method` не возвращает non-method chunks;
- фильтр по DOI возвращает только одну статью;
- grouped output содержит expected article;
- `chunks_per_article=1` не возвращает второй chunk той же статьи;
- exact/semantic/hybrid при одинаковых фильтрах ограничены одним и тем же
  corpus subset.

Не менять существующие метрики, но добавить отдельный report section:

```text
filter_mode
group_by
chunks_per_article
candidate_count_before_grouping
group_count
```

## 8. Tests

Минимальный набор:

- unit tests для normalization и validation filters;
- unit tests для SQL statement filters;
- exact search filter tests;
- semantic search filter tests с fake loaded index;
- hybrid search filter tests;
- grouping tests;
- API serialization tests;
- UI route tests;
- evaluation tests для новых параметров.

## 9. Acceptance criteria

Этап готов, если:

- filters не возвращают результаты вне заданных условий;
- exact, semantic и hybrid одинаково понимают filters;
- grouping не теряет лучший фрагмент и PDF page link;
- `chunks_per_article` работает детерминированно;
- существующий unfiltered search остаётся совместимым;
- API/UI покрыты тестами;
- full unit suite, Ruff и mypy проходят;
- smoke test на локальном corpus подтверждает grouped search.

## 10. Rollback

Откат не требует re-ingestion и rebuild индекса, если этап не меняет corpus и
scoring. Для rollback достаточно вернуть search API/UI/service changes. Новые
evaluation reports можно оставить как generated artifacts.
