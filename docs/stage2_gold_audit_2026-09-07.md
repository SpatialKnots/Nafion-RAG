# Этап 2: аудит эталона Ma и межъязыковой evaluation

Дата: 2026-09-07. Базовый HEAD `4958bf0` плюс незакоммиченные исправления этапа 1.
Коллекция `literature`: 33 статьи, 493 страницы, 619 чанков. Doctor PASS;
корпус совпал с `data/exports/corpus_manifest_stage1_20260907.json`.

## Диагноз Ma: gold_source_mismatch

Исходная гипотеза — поиск пропускает подходящую статью — не подтвердилась.
Эталон требовал статью Ma для списка растворителей, не соответствующего её
экспериментальному разделу. Это ошибка связи вопроса с источником, а не
основание ослаблять обязательные научные термины.

Ожидаемый источник: Ma et al., *Morphology and properties of Nafion membranes
prepared by solution casting*, DOI `10.1016/j.polymer.2009.01.060`.

- Article ID: `5fa65151-6f28-442c-bb1c-7c445002e5d5`.
- SHA-256 оригинала: `3fbac155ded2bbbd38b6094ed69ce2439f5b261a95dff4d2ad3028bb378c9102`.
- PDF: 14 страниц; в БД 22 чанка.
- PDF page 2 / journal page 1765, section 2.1: смола растворена в DMAc, DMF,
  NMF, MeOH–H2O (4/1 g/g), EtOH–H2O (4/1 g/g), IPA–H2O (4/1 g/g).
- PDF page 11 / journal page 1774, Tables 6–8: тот же набор растворителей
  в таблицах SAXS и проводимости.
- NMP не обнаружен как отдельный токен в текстовом извлечении всех 14 страниц.
  Это дополнительно согласуется с экспериментальным списком, а не заменяет его.
- DMSO встречается на PDF page 4 в обсуждении результата Lousenberg [46],
  а не как один из собственных casting solvents Ma.

В исходном запросе `Nafion casting solvent method table DMF DMSO NMP EtOH DMAc`
обязательны DMF/DMSO/NMP/DMAC. Ни один из 22 чанков Ma не удовлетворяет всем
четырём условиям. Поэтому Ma отсутствует до ранжирования. В exact top results
находится Dai, DOI `10.1016/j.memsci.2016.09.014`, который действительно обсуждает
DMF/NMP/DMSO; этот конкурент нельзя объявить просто ошибочным результатом.

Дополнительная осторожность: DMAc у Dai на PDF page 6 упомянут в аналогии
с SPEEK и ссылкой [32]. Это не доказывает, что Dai экспериментально сравнил
все пять растворителей пользовательского запроса. Пользовательские вопросы
про этот полный список сохранены как есть: их retrieval PASS не означает,
что одна статья поддерживает все предпосылки будущего ответа.

## Changed

Исправлены три подготовленных эталонных вопроса. DOI targets, keywords,
метрики, пороги и ranking code не изменены.

| ID / файл | Исходный query | Исправленный query |
| --- | --- | --- |
| `q20_ma_table_solvent_aggregation_2009`, `evaluation_questions.yaml` | Nafion casting solvent method table DMF DMSO NMP EtOH DMAc | Nafion casting solvent method table DMAc DMF NMF MeOH EtOH IPA |
| `qext003_ma_table_solvent_set`, `evaluation_questions_extended.yaml` | Nafion casting solvent table DMF DMSO NMP EtOH DMAc | Nafion casting solvent table DMAc DMF NMF MeOH EtOH IPA |
| `p6_table_ma_solvent_aggregation_2009`, `evaluation_questions_priority6.yaml` | Table casting solvent DMAc DMF DMSO NMP EtOH ionic aggregation Nafion | Table casting solvent DMAc DMF NMF MeOH EtOH IPA ionic aggregation Nafion |

В extended вопрос добавлены error_class, expected_behavior и regression_guard;
notes всех трёх вопросов ссылаются на источник и этот аудит. Исходные формулировки
сохранены выше; исходные YAML также сохранены локально в `tmp/stage2_legacy_*`.
MeOH/EtOH/IPA в исправленных поисковых строках — сокращения; водная природа
смесей и массовое соотношение явно зафиксированы в provenance/notes, не являются
утверждением о чистых спиртах.

В процессе оценки найден отдельный класс дефекта **evaluation_metadata_scope**:
`language_diversity` зависит от вопроса, но evaluator сравнивал его как
инвариант запуска. Реальный cross-lingual запуск обрывался с
`ValueError: retrieval metadata changed during evaluation`.

Минимальный патч `app/evaluation/retrieval.py`:

- исключить `language_diversity` из сравнения неизменной конфигурации, как уже
  исключены `cross_lingual`, `mandatory_terms` и `reranking`;
- добавить полную `retrieval_metadata` каждому вопросу extended отчёта,
  аналогично существующему legacy отчёту. Это явное аддитивное изменение
  отчётной схемы; существующие поля и определения метрик сохранены;
- оставить проверку смены manifest/model и остальных инвариантов строгой.

Это исправление evaluator, а не изменение межъязыкового retrieval.

## Tests run

- Новые regression tests на обоих evaluators до патча: 2 failed / 2 passed
  после исправления тестовой YAML fixture. Смена language diagnostics воспроизводила
  ошибку; смена manifest корректно отвергалась.
- После патча: 4/4 PASS.
- Полный `python -m pytest -q`: 352 passed, 1 StarletteDeprecationWarning.
- `python -m ruff check app tests scripts/stage1_smoke.py`: PASS.
- `python -m mypy app`: PASS, 68 source files.
- `python -m app.ingestion.cli doctor`: PASS.
- `python -m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json`: match.

Команды выполнялись через `.venv/Scripts/python.exe`. Исторический tracked
`docs/corpus_manifest.json` не обновлялся и по-прежнему описывает более ранний
корпус; snapshot этого запуска указан отдельно.

## Evaluation: исправленная разметка

Каждый набор запускался с top_k=10, collection=literature, методами exact и hybrid
через `run_retrieval_evaluation` / `run_extended_retrieval_evaluation` — функции,
используемые CLI. Для extended применены текущие `evaluation_thresholds.yaml`.

| Набор | Exact PASS / top-1 | Hybrid PASS / top-1 |
| --- | --- | --- |
| Базовые 24 | 24/24; 17 | 24/24; 22 |
| Priority 6, 6 вопросов | 6/6; 4 | 6/6; 5 |
| Extended, 46 вопросов | 46/46; 24 из 38 answerable | 46/46; 31 из 38 answerable |

Extended: оба метода проходят пороги, article Recall@10=1.0,
evidence_trace_complete=true, 8/8 unanswerable PASS. MRR exact=0.734858,
hybrid=0.891228.

**Эти значения не являются улучшением поиска относительно 23/24 и 45/46:**
изменился вопрос, а не алгоритм. Для неизменённых вопросов сравнивались метрики
и полный порядок chunk IDs: различий нет (23 legacy exact, 23 legacy hybrid,
45 extended hybrid). Сравнение сохранено в
`tmp/stage2_unchanged_query_comparison.json`.

Отчёты исправленного gold:

- `data/exports/retrieval_eval_exact_20260907T051922Z.json` — baseline.
- `data/exports/retrieval_eval_hybrid_20260907T052012Z.json` — baseline.
- `data/exports/retrieval_eval_exact_20260907T052024Z.json` — Priority 6.
- `data/exports/retrieval_eval_hybrid_20260907T052037Z.json` — Priority 6.
- `data/exports/retrieval_eval_extended_exact_20260907T052155Z.json`.
- `data/exports/retrieval_eval_extended_hybrid_20260907T052329Z.json`.

До коррекции Priority 6 exact: 5/6, top-1=3;
`data/exports/retrieval_eval_exact_20260907T051739Z.json`.
Исходные baseline/extended результаты приведены в отчёте этапа 1.

## Межъязыковой baseline

Первый запуск оборвался из-за описанного дефекта evaluator и не имеет итоговой
метрики. Повторный запуск после исправления завершён на неизменных вопросах:

| Набор | PASS | Article Recall@10 | MRR | Top-1 |
| --- | --- | --- | --- | --- |
| cross_lingual_extended | 30/31 | 0.967742 | 0.772849 | 21 |
| user_cross_lingual | 25/25 | 1.0 | 0.836000 | 19 |
| user_regression_extended | 7/10 | 1.0 | 0.933333 | 9 |

Отчёты: `data/exports/retrieval_eval_extended_hybrid_cross_lingual_20260907T120309Z.json`,
`data/exports/retrieval_eval_extended_hybrid_cross_lingual_20260907T120701Z.json`,
`data/exports/retrieval_eval_extended_hybrid_cross_lingual_20260907T120849Z.json`.
Полнота traceability во всех трёх наборах подтверждена. Регрессионные вопросы
002, 003 и 007 находят статьи, но не требуемые сочетания терминов в чанках.
Отдельный пропуск статьи Чернюк 2024 по английскому запросу об энтальпии
разобран в [отчёте исправления словаря](stage2_interaction_enthalpy_2026-09-07.md).

## Limitations

- Исправление gold не решает частичное соответствие статьи многосоставному
  вопросу и не доказывает научную полноту сгенерированного ответа.
- Нет изменения retrieval scoring, OCR, chunking, индекса или LLM provider.
- Показатели обновлённого gold нельзя напрямую сравнивать как улучшение модели
  с показателями старых вопросов.

## Verdict

Причина Ma установлена и устранена в разметке; запросы не подгонялись под ранги.
Исправлена остановка evaluation на меняющихся языковых diagnostics.
Межъязыковой baseline получен; четыре FAIL сохранены как наблюдаемые ограничения.
