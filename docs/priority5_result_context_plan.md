# Приоритет 5: расширенный контекст результата

## Статус документа

Это подробный технический план для согласования. Описанные endpoints, UI views и
форматы ответа ещё не считаются реализованными.

План предполагает, что приоритет 4 уже добавил фильтры и группировку, но сам
приоритет 5 не зависит от изменения ranking. Его цель - показать больше
проверяемого текста вокруг найденного результата.

## 1. Цель

Дать пользователю достаточно контекста для оценки релевантности до открытия
полного PDF.

После этапа пользователь должен уметь:

- открыть полный текст найденного chunk;
- увидеть предыдущий и следующий chunk той же статьи;
- открыть текст страницы или диапазона страниц;
- видеть, какие совпадения query подсвечены в отображении;
- перейти от context view к PDF page;
- получить безопасный ограниченный API response без неограниченного текста.

## 2. Текущее основание

Сейчас search result содержит snippet, page range, source type, text layer и PDF
links. Есть endpoint page evidence:

```text
GET /articles/{article_id}/pages/{page_number}?layer=selected|original|ocr
```

В БД есть:

- `Chunk.text`;
- `Chunk.chunk_index`;
- `Chunk.page_start/page_end`;
- `Page.text`;
- `Page.selected_text_layer`;
- `PageTextLayer` для original/OCR layers.

## 3. Границы этапа

### Входит

- endpoint для chunk context;
- endpoint для page range context;
- optional query highlighting в API/UI presentation;
- previous/next chunks в рамках одной статьи;
- response size limits;
- UI context panel/page;
- tests на article boundary и ordering.

### Не входит

- изменение сохранённого текста;
- новый extraction/OCR;
- table/formula parsing;
- semantic reranking;
- LLM answer generation;
- редактирование PDF;
- fuzzy page alignment.

## 4. API contract

### 4.1. Chunk context

```text
GET /articles/{article_id}/chunks/{chunk_id}/context
```

Query parameters:

```text
before=1
after=1
highlight_query=Nafion conductivity
max_chars=20000
```

Response:

```json
{
  "article_id": "...",
  "chunk_id": "...",
  "title": "...",
  "doi": "...",
  "requested_chunk_index": 4,
  "chunks": [
    {
      "chunk_id": "...",
      "chunk_index": 3,
      "role": "previous",
      "page_start": 4,
      "page_end": 4,
      "source_type": "body",
      "text_layer": "original",
      "text": "...",
      "highlights": []
    }
  ],
  "pdf_url": "/articles/.../pdf?layer=original",
  "pdf_page_url": "/articles/.../pdf?layer=original#page=4",
  "truncated": false
}
```

Rules:

- `chunk_id` must belong to `article_id`;
- previous/next never cross article boundary;
- ordering uses `chunk_index`, then id as tie-breaker;
- `before` and `after` have upper bounds from settings;
- if max_chars is exceeded, truncate at chunk boundaries first; if a single
  chunk is too large, truncate text and set `truncated=true`.

### 4.2. Page range context

```text
GET /articles/{article_id}/pages/context?page_start=3&page_end=5&layer=selected
```

Response:

```json
{
  "article_id": "...",
  "layer": "selected",
  "page_start": 3,
  "page_end": 5,
  "pages": [
    {
      "page_number": 3,
      "resolved_layer": "ocr",
      "has_usable_text": true,
      "text": "..."
    }
  ],
  "pdf_page_url": "/articles/.../pdf?layer=original#page=3"
}
```

Rules:

- page range has max page count;
- `selected` resolves per page;
- unavailable original/OCR layer returns diagnostic `404`;
- text comes from stored DB data only, no re-extraction.

## 5. Highlighting

Highlighting is presentation metadata, not stored text mutation.

Possible representation:

```json
"highlights": [
  {"start": 10, "end": 16, "term": "Nafion"}
]
```

Rules:

- normalize PDF ligatures in the same way as snippets;
- preserve original text offsets where practical;
- if exact offsets become ambiguous after normalization, return highlighted
  fragments instead of claiming exact offsets;
- never write highlighted text back to DB.

## 6. Settings

Add:

```text
CONTEXT_MAX_NEIGHBOR_CHUNKS=3
CONTEXT_MAX_CHARS=30000
CONTEXT_MAX_PAGES=5
CONTEXT_HIGHLIGHT_MAX_TERMS=12
```

Validation:

- all positive;
- max neighbor chunks small enough to avoid huge responses;
- max pages positive and bounded.

## 7. UI

Add context action to search rows:

- "Context" link/button beside PDF link;
- context view shows requested chunk centered between previous/next chunks;
- page range links open PDF at first page;
- query terms highlighted in display only;
- grouped result view can open best chunk context.

The UI should remain a dense operational tool, not a marketing page.

## 8. Tests

Required tests:

- chunk context returns requested, previous and next chunks;
- first chunk has no previous;
- last chunk has no next;
- chunk from different article gives `404`;
- `before/after` validation;
- `max_chars` truncation;
- page range validation;
- selected/original/ocr layer resolution;
- highlighting does not alter stored text;
- UI context route renders expected title/page links.

## 9. Acceptance criteria

Этап готов, если:

- context API returns only text from the same article;
- page numbers match stored pages and PDF links;
- large responses are bounded;
- missing context is explicit, not hidden;
- search UI exposes context for exact/semantic/hybrid/grouped results;
- tests, Ruff, mypy pass;
- smoke test on local corpus opens context and PDF page for a real search result.

## 10. Rollback

No DB migration is required if only endpoints/settings/UI are added. Rollback is
removing context service/API/UI. Stored article/page/chunk data remains
unchanged.
