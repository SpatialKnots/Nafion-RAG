# ARIADNE: локализация пропуска контрпримера Li-Nafion

30 октября 2026 года, Asia/Yekaterinburg. Итерация 1
[плана качества ответов](answer_quality_plan_2026-10-30.md).

Changed:

- Добавлены отдельный `scripts/retrieval_loss_audit.py`, read-only capture driver
  `scripts/run_swelling_retrieval_audit.py` и offline replay/HTML exporter
  `scripts/review_swelling_retrieval_audit.py`. В production code изменений нет.
  Настройки, scoring, thresholds, top-k, prompt/schema и научная логика не менялись.
- Повторён исходный вопрос из сохранённого API request 29 октября с теми же
  параметрами: `literature`, `hybrid_cross_lingual`, top-k 5, `claims`/`auto`.
  Локальный embedding inference использует существующий offline cache/индекс.
  PostgreSQL transaction — `REPEATABLE READ, READ ONLY`; `SHOW transaction_read_only`
  вернул `on`, завершение — rollback. Генерация заменена явной остановкой до
  provider; ни реального, ни фиктивного ответа модели не создавалось.
- Wrapper записал 19 наблюдений внутренних границ, включая исходные каналы,
  cross-lingual fusion, legacy ranking, обе article diversification, feature
  window/ranking, language diversity, top-k и generation evidence. Сохранены
  полные тексты, article/chunk IDs, страницы, source type и text layer.
  Наблюдения ветвящихся каналов не представлены как последовательная цепочка.
- Проверены hashes прежних app/data input bindings и исходных PDF.
  Из исходного PDF заново извлечена с.75 и проверен точный counterexample span
  с прежними offsets. Текст о ≈1.8 не подмешан в retrieval или evidence:
  он используется только как явно post-hoc цель диагностики.

Результат воспроизведения:

| Граница | Наблюдение для двух chunks с точным фрагментом с.75 |
| --- | --- |
| Original exact channel, 187 результатов | места 13 и 20 |
| Original semantic channel, 500 результатов | места 42 и 59 |
| Original hybrid после fusion/top-100 | места 11 и 29 |
| RU glossary exact top-100 | места 17 и 22 |
| EN glossary exact top-100 | точный фрагмент отсутствует |
| Cross-lingual fusion input | оба chunks присутствуют в 213 кандидатах; порядок входа, не отдельная сортировка RRF score |
| Legacy ranking | места 28 и 37 |
| Article-diverse selection перед feature window | места 71 и 80; оба входят в окно 100 |
| Feature ranking | места 17 и 18 |
| Финальная article diversification | места 60 и 61 |
| Language diversity | оба остаются на местах 60 и 61 |
| Top-5 | оба исключены |
| Answer evidence selection / generation evidence | точного фрагмента нет; пять результатов |

**Полная итоговая трасса (`retrieval`, `evidence`, `metadata`) совпала с
сохранённой трассой 29 октября.** В новом прогоне удаление контрпримера происходит
при top-5 до answer evidence selection. Первичный поиск и окно feature ranking
этот фрагмент не теряют. Фактические внутренние стадии вчера не сохранялись;
это диагноз воспроизведения при совпавших input files/коде и полном финальном
результате, а не задним числом записанный historical trace.

Дополнительная наблюдаемая диагностика ranking:

- `_has_swelling_comparison_intent` для исходного вопроса без variants — false,
  с glossary variants — true. Это наблюдение о конечном правиле ranking,
  не семантическая интерпретация намерения пользователя.
- Первые два chunks получают `numeric_table_bonus=2`, result scores 37.8 и 30.2;
  оба целевых chunks — bonus 0, result score 21.400000000000002. Числа сохранены
  без округления в JSON. Первые два набора features повторно вычислены и совпали
  с сохранённым `top_features`.
- Код сортирует numeric table bonus перед article/result scores. После ranking
  article diversification откладывает все chunks одной статьи сверх первых двух.
  Это объясняет наблюдаемые перемещения. Ни отключение одного признака, ни
  изменение top-k сами по себе здесь не проверялись как исправление.
- Потенциальный класс для последующего дизайна: `compound_intent_ambiguity`
  (glossary добавляет контекст сравнения форм), с приоритетом табличных признаков
  и нехваткой проверки области максимума. Не добавлены запрос-/article-specific
  promotion, изменение весов или увеличение лимита ради известной страницы.

Tests run:

- **82 tests passed**, JUnit
  `output/swelling_retrieval_audit_tests_20261030_v02.xml`: 15 новых проверок
  source-anchor retention и прежние retrieval/search, cross-lingual, reranking.
  Новый тест отличает page-range overlap от точного текста, другую статью/страницу,
  title/snippet от full source, множественные chunks, потерю/возврат и неверные anchors.
- Предыдущий узкий прогон: 15 passed, одна `PytestCacheWarning` из-за недоступного
  `.pytest_cache`. В финальном прогоне использованы отдельные project-local cache
  и basetemp; эти 15 тестов входят в 82, числа не суммируются.
- Ruff четырёх новых source/test files passed; mypy чистого diagnostic module —
  no issues. Ruff дополнительного QA script также проверен. `git diff --check`
  passed с существующими LF/CRLF warnings; нового full-suite success не заявляется.
- Offline replay запустил настоящий hybrid fusion, cross-lingual fusion/ranking,
  diversification и answer evidence/adequacy код на сохранённых outputs каналов.
  Проверены девять внутренних границ и полная итоговая трасса; совпали.
  `Engine.connect` явно запрещён; DB connections 0, embedding inference 0,
  model/OAuth calls 0. Искажённый expected output финальной diversification
  отдельно отклонён именно на этой границе.
- Статическая QA итогового HTML: 33 TAC rows, восемь согласованных columns,
  35 существующих file links, search input/handler. Все зарегистрированные
  Abstract доступны целиком, отсутствующие/несобранные поля отмечены. Hashes
  input/output verified. Browser render и исполнение поиска не проверялись.
- Успешный read-only capture — `capture_v03`. Предыдущий `capture_v01` остановлен
  песочницей на localhost:5432 (`Permission denied`, 10013); вне песочницы
  `capture_v02` завершил retrieval, но новый exporter ошибочно удвоил префикс
  `data`. Исправление использует существующий `resolve_article_pdf`.
  Каталоги сохранены; `failed_attempts.json` содержит явно обозначенные summaries
  terminal failures, а не вымышленные полные raw logs.

Артефакты:

- [Итоговая HTML-таблица](../output/swelling_retrieval_audit_20261030/review_v02/review.html).
  Scope: все 33 работы, встреченные в записанных кандидатах, а не только три
  работы финального evidence. Это coverage, не 33 научных подтверждения.
- `output/swelling_retrieval_audit_20261030/capture_v03/capture.json` — полные
  данные capture; `boundaries.json` сохраняет внутренние списки отдельно.
- `review_v02/report.json` — hashes, путь потери, features и результаты replay;
  `review_v02/source_snapshot/` — точные новые script/test/plan copies.
- `qa_v01.py`, `qa_v01.json`, `failed_attempts.json` — отдельные QA/diagnostics.
- `review_v01` сохраняет первоначальный отчёт без последующей feature diagnostics;
  `review_v02` — финальный, прежние outputs не переписаны.

Воспроизведение offline (новый output, без БД/модели):

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.review_swelling_retrieval_audit --captured output/swelling_retrieval_audit_20261030/capture_v03 --output output/swelling_retrieval_audit_20261030/review_replay_new
```

Exporter fail-closed проверяет input hashes. Последующие изменения зависимостей
могут потребовать отдельного воспроизведения из frozen snapshots; обходить guard
или переписывать исторические bindings нельзя.

Limitations:

Один знакомый вопрос и assistant-selected post-hoc counterexample; независимой
разметки/accuracy или научной приёмки нет. Общий максимум Li-Nafion по корпусу и
литературе не установлен. Не исправлены ranking, семантическая принадлежность
величин, полнота доказательств, оформление production answer и provider filtering.
Длительно работающий сервер и дефект cache/ORM repeated requests не проверены:
capture использует свежий процесс. Нет новых API/OAuth attempts, reservations
или разрешений; все закрытые бюджеты и исходные ответы сохраняются.

Verdict:

Пункт 1 выполнен: стадия потери локализована воспроизводимым diagnostic code и
точным replay. **Выполнение четырёхпунктного плана: 25% (1/4)**, с равным весом
пунктов; это не оценка научной точности. Следующий пункт — offline-проверка
области максимума, температуры, смесей и принадлежности величины операции.
