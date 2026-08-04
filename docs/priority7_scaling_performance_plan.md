# Приоритет 7: масштабирование и производительность

## Статус документа

Это подробный технический план для согласования. Описанные benchmarks, caching,
mmap, concurrency tests и API limits ещё не считаются реализованными.

Этап начинается только после функциональной стабильности приоритетов 1-6.
Оптимизация без измерений не допускается.

## 1. Цель

Сохранить приемлемое время ответа и устойчивость при росте корпуса,
одновременном ingestion, rebuild и search.

На этом этапе система должна получить:

- воспроизводимый benchmark harness;
- latency/throughput метрики;
- безопасные API limits;
- кэш проверенного vector index;
- проверку concurrent search + ingestion + rebuild;
- документацию hardware/environment для сравнения результатов.

## 2. Текущее основание

Сейчас:

- vector index v3 проверяется и загружается при semantic/hybrid search;
- rebuild строит full matrix;
- exact search работает через PostgreSQL ILIKE;
- hybrid вызывает exact и semantic;
- API limits частично есть для upload/top_k, но не для всех response sizes;
- нет устойчивого benchmark command для latency/rebuild/concurrency.

## 3. Границы этапа

### Входит

- benchmark CLI;
- измерение ingestion throughput;
- измерение vector rebuild time;
- измерение exact/semantic/hybrid latency;
- кэширование loaded vector index по manifest checksum;
- safe invalidation cache при смене current pointer/manifest;
- optional NumPy mmap для embeddings;
- API upper bounds для top_k/candidate_k/context;
- pagination для больших result sets, если требуется;
- concurrency smoke tests;
- documentation of hardware and corpus version.

### Не входит

- pgvector/FAISS/vector database migration;
- distributed workers;
- GPU scheduling;
- изменение retrieval scoring;
- новый embedding model;
- cloud benchmark;
- оптимизация OCR/extraction качества.

## 4. Benchmark command

Добавить:

```powershell
python -m app.evaluation.cli benchmark --collection literature
```

Параметры:

```text
--queries docs/evaluation_questions.yaml
--methods exact,semantic,hybrid
--warmup 3
--runs 10
--top-k 10
--include-rebuild
--include-ingestion-smoke
--output data/exports/backend_benchmark_*.json
```

Report:

```json
{
  "created_at": "...",
  "hardware": {
    "platform": "...",
    "python": "...",
    "cpu_count": 8,
    "memory_total_bytes": null
  },
  "corpus": {
    "articles": 17,
    "chunks": 388,
    "vector_manifest_sha256": "..."
  },
  "search_latency_ms": {
    "exact": {"p50": 0, "p95": 0, "max": 0},
    "semantic": {},
    "hybrid": {}
  },
  "rebuild": {
    "seconds": 0,
    "chunk_count": 388,
    "generation_id": "..."
  }
}
```

## 5. Vector index cache

### 5.1. Key

Cache key:

```text
collection_id + embedding_model + active_generation_id + active_manifest_sha256
```

Never cache by model name alone.

### 5.2. Safety

Before using cache:

- read DB state;
- confirm status ready;
- confirm active revision equals desired revision;
- confirm cached manifest checksum equals DB state;
- optionally confirm current pointer checksum if cheap enough.

If any mismatch, discard cache and reload.

### 5.3. Scope

Process-local cache only. No distributed cache in this priority.

Settings:

```text
VECTOR_INDEX_CACHE_ENABLED=true
VECTOR_INDEX_CACHE_MAX_ITEMS=2
VECTOR_INDEX_USE_MMAP=false
```

## 6. Memory mapping

Evaluate `np.load(..., mmap_mode="r")`.

Acceptance requires:

- no mutation of loaded embeddings;
- no stale generation use after pointer switch;
- Windows file locking behavior verified;
- cleanup does not delete active mmap generation.

If Windows locking makes cleanup fragile, mmap remains disabled by default.

## 7. API limits

Add or enforce:

```text
SEARCH_MAX_TOP_K=100
HYBRID_MAX_CANDIDATE_K=500
CONTEXT_MAX_CHARS=...
RESULT_PAGE_SIZE_MAX=100
```

Rules:

- invalid too-large requests get `422` or consistent `400`;
- defaults remain current behavior;
- evaluation can still override within safe local limits if needed.

## 8. Concurrency scenarios

Smoke tests:

1. semantic search while index ready;
2. ingestion marks stale;
3. exact continues to work;
4. semantic/hybrid return 503 while stale/rebuilding;
5. worker rebuilds;
6. semantic/hybrid work again;
7. old generation remains until cleanup.

Concurrent tests should use bounded threads/processes and local test corpus, not
uncontrolled load tests.

## 9. Tests

Required:

- cache key tests;
- cache invalidation on manifest change;
- no stale cache after desired revision change;
- mmap load tests if enabled;
- API limit tests;
- benchmark report serialization tests;
- cleanup protection with cached active generation;
- concurrency smoke test where practical.

## 10. Acceptance criteria

Этап готов, если:

- benchmark command produces reproducible JSON;
- repeated semantic search avoids unnecessary reload/validation when cache is
  valid;
- stale generation is never served from cache;
- API response sizes are bounded;
- concurrent ingestion/rebuild/search preserves priority 3 lifecycle guarantees;
- before/after latency numbers are documented;
- tests, Ruff, mypy pass.

## 11. Rollback

Disable caching/mmap through settings:

```text
VECTOR_INDEX_CACHE_ENABLED=false
VECTOR_INDEX_USE_MMAP=false
```

If code rollback is needed, remove cache layer and return to per-request load.
Generated benchmark reports remain local artifacts.
