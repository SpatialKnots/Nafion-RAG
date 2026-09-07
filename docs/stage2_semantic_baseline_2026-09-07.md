# Этап 2: semantic baseline

Дата: 2026-09-07. HEAD `4958bf0` с рабочими изменениями этапов 1–2.

## Changed

Получен отсутствовавший semantic baseline на extended наборе из 46 вопросов.
Код поиска, модель, индекс, gold и пороги не менялись.

Конфигурация: collection=literature, top_k=10, method=semantic,
group_by=none, без фильтров и chunks_per_article. Backend local_vector_index,
BAAI/bge-small-en-v1.5, 384 измерения, cosine, 619 чанков.
Manifest SHA-256:
`d1d13f2271c28f2c1082e8251bff572f7b93e9ba25a77daa4b2087a84e6b1569`.
Правило evaluator: `lower_latin_ligatures_v1`.

## Tests run

Через `.venv/Scripts/python.exe`:

- `-m app.ingestion.cli doctor`: все проверки PASS, 33 статьи,
  два состояния индекса ready, stale/failed отсутствуют.
- `-m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json`:
  match, изменений состава и статей нет.
- При `PYTHONPATH=.`: `tmp/stage2_semantic_evaluate.py` завершился с кодом 0.
  Скрипт вызывает `run_extended_retrieval_evaluation` для
  `docs/evaluation_questions_extended.yaml`, затем проверяет semantic-пороги
  из `docs/evaluation_thresholds.yaml`. Лог: `tmp/stage2_semantic.log`.

Unit-тесты повторно не запускались: этот шаг не меняет исполняемый код.

## Evaluation

Отчёт: `data/exports/retrieval_eval_extended_semantic_20260907T171034Z.json`.
Сводка с порогами: `tmp/stage2_semantic_results.json`.

| Метрика | Semantic |
| --- | --- |
| PASS | 46/46 |
| Article Recall@10 | 1.0 |
| Chunk Recall@10 | 1.0 |
| MRR | 0.874373 |
| nDCG@10 | 0.840802 |
| Top-1, answerable | 31/38 |
| Unanswerable PASS | 8/8 |
| False answerable | 0 |
| Evidence trace complete | true |
| p50 / p95 latency, ms | 80.54 / 1136.69 |

Все пять действующих semantic-порогов выполнены.

Для контекста: прежний hybrid на том же наборе и snapshot имел
Recall@10=1.0, MRR=0.891228, nDCG=0.847951 и Top-1=31/38
(`retrieval_eval_extended_hybrid_20260907T052329Z.json`). Его evaluator ещё
не раскрывал лигатуры. Это сравнение двух методов, не before/after улучшение.
Latency прежнего запуска напрямую не сравнивается.

При сопоставлении ranks выделяются следующие расхождения:

- `qext020_moore_martin_waxd_recast`: hybrid rank 1, semantic rank 7.
- `qext022_sanginov_quantum_swelling`: 1 → 4.
- `qext034_chernyuk_dissertation_title_ru`: 1 → 3.
- `qext035_chernyuk_dissertation_solvent_table_ru`: 3 → 1.
- `qext024_sanginov_sup_m05_tzvp_smd`: 2 → 1.

Поэтому одинаковый общий Top-1 не означает одинаковую выдачу. Оснований
заменять текущий поиск чистым semantic по этому baseline нет.

## Limitations

- Набор небольшой; успешный retrieval не доказывает научную полноту ответов.
- Фильтры и article grouping не включались, их сквозная приёмка остаётся.
- Это одиночный прогон с текущим состоянием кэшей, не cold/warm benchmark.
- Semantic не оценивался здесь на дополнительных user/cross-lingual наборах.
- Отчёт содержит исторический provenance для docs/corpus_manifest.json;
  фактический актуальный snapshot проверен отдельной командой выше.

## Verdict

Semantic baseline принят: действующие пороги выполнены, полный отчёт сохранён.
Этап 2 остаётся открытым. Следующий ограниченный шаг — сквозная проверка
фильтров и ограничения фрагментов одной статьи на текущем корпусе.
