# Stage 2: влияние группировки на полноту evidence

## Changed

Добавлен воспроизводимый аудит `tmp/stage2_grouping_audit.py`. Код приложения,
gold, scoring, данные и пороги не менялись.

## Протокол

Набор `docs/evaluation_questions_extended.yaml`: 46 вопросов, 38 answerable,
8 unanswerable. Article Recall усредняется по 38 вопросам; chunk Recall —
только по 13 вопросам с ожидаемыми фрагментами. Это разные знаменатели.

Для exact, semantic, hybrid и hybrid_cross_lingual выполняется живой поиск
в `literature`, top_k=10. К одному и тому же окну каждого вопроса применяется
производственная `group_results_by_article`: без лимита, cap=1 и cap=2.
Повторный поиск для каждого cap не выполняется. Добора кандидатов нет.
Оценка использует действующий evaluator и полный текст чанков из БД.

Проверяются сохранение множества статей при каждом cap и сохранение множества
чанков без лимита. JSON сохраняет исходные результаты, скрытые фрагменты
с исходными рангами, пропущенные gold targets, traceability и SHA256 gold.
`elapsed_ms=0` — служебное значение; задержки этим аудитом не измеряются.

## Диагностика semantic cap=1

Вопрос `qext022_sanginov_quantum_swelling`:
`binary plasticiser Quantum chemical calculations Swelling Ionic conductivity`.
Gold требует DOI `10.1016/j.electacta.2021.137914` и совместного наличия
`Quantum chemical` и `Swelling` в тексте чанка.

Статья Sanginov 2021 остаётся в выдаче. Её первый чанк — исходный ранг 4,
`6ae98965-0f5a-46f3-a53c-bec1e5c00607`, страницы 11–12, source_type=table —
не выполняет это условие. Cap=1 скрывает следующий чанк статьи:
исходный ранг 5, `43760e14-85a3-4ed8-8a7b-f0c7f9bd9f29`, страница 1,
source_type=main_text, text_layer=original. Его snippet содержит
`Quantum chemical calculations Swelling Ionic conductivity`.
Cap=2 сохраняет этот фрагмент и восстанавливает выполнение gold.

Наблюдаемая ошибка относится к отбору видимого evidence после retrieval.
Кандидат найден в top-10; менять gold или ranking для устранения этой потери
оснований нет. Сам gold проверяет наличие терминов, а не научную полноту ответа.

## Evaluation

Все 184 живых поиска завершились; оценены 736 представлений выдачи.
Результат: `tmp/stage2_grouping_audit.json`. Article Recall=1.0 и
trace_complete=true во всех 16 комбинациях метода и представления.

| Метод | Chunk Recall flat / без cap / cap=1 / cap=2 | PASS из 46 в том же порядке | Чанков flat / без cap / cap=1 / cap=2 |
| --- | --- | --- | --- |
| exact | 1 / 1 / 1 / 1 | 46 / 46 / 46 / 46 | 460 / 460 / 152 / 248 |
| semantic | 1 / 1 / 0.923077 / 1 | 46 / 46 / 45 / 46 | 460 / 460 / 149 / 263 |
| hybrid | 1 / 1 / 1 / 1 | 46 / 46 / 46 / 46 | 460 / 460 / 159 / 261 |
| hybrid_cross_lingual | 1 / 1 / 1 / 1 | 45 / 45 / 46 / 45 | 460 / 460 / 239 / 434 |

Число чанков суммировано по всем 46 вопросам. Cap=2 не уменьшил article/chunk
Recall относительно flat ни у одного метода на этом gold.

### Отдельный unanswerable FAIL

`qext042_absent_high_temperature_pbi`, запрос:
`polybenzimidazole phosphoric acid anhydrous fuel cell Nafion composite`.
У hybrid_cross_lingual исходная выдача, группировка без лимита и cap=2 получают
`sufficient_distinctive_term_coverage`: совпадают acid, anhydrous, nafion,
composite, coverage=4/6. Polybenzimidazole и phosphoric отсутствуют среди
совпавших distinctive terms. Gold помечает вопрос unanswerable, поэтому FAIL.

Cap=1 убирает composite из совокупного покрытия, coverage становится 3/6,
вердикт меняется на `insufficient_distinctive_term_coverage`, и вопрос проходит.
Это чувствительность эвристики adequacy к отбору snippets; рост PASS нельзя
объявлять улучшением научной корректности или аргументом в пользу cap=1.
FAIL присутствует до группировки, поэтому не является её регрессией.
Поддержка темы полными исходниками в этом аудите отдельно не проверялась.

## Limitations

- Recall после cap означает полноту видимой части исходных top-10, а не поиск
  нового окна из десяти статей.
- Сохранение article Recall не доказывает устранение article crowding:
  множество статей не расширяется.
- Даже chunk Recall=1.0 покрывает только 13 размеченных вопросов.
- Группировка меняет порядок при разворачивании групп. MRR/nDCG такого списка
  нельзя объявлять улучшением исходного ranking.
- UI, сетевой HTTP transport, открытие PDF-ссылок и дополнительные user/
  cross-lingual gold-наборы этим прогоном не проверяются.

## Tests run

Команды выполнялись из `D:\Nafion-RAG`:

```powershell
.\.venv\Scripts\python.exe -m app.ingestion.cli doctor
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json
.\.venv\Scripts\python.exe -m tmp.stage2_grouping_audit
.\.venv\Scripts\python.exe -m pytest tests/unit/test_api_search.py tests/unit/test_evaluation.py -q
```

Doctor: все проверки PASS, ready=2, stale/failed=0. Проверка manifest перед
аудитом и после него: match. Unit-тесты: 42 passed. Предварительная попытка с `-k group`
не выбрала тестов: 42 deselected; она не считается успешной проверкой.
Полный pytest повторно не запускался: код приложения не менялся.

## Verdict

Аудит завершён. Универсальная безопасность cap=1 для evidence отвергнута:
есть подтверждённая потеря semantic chunk target. Cap=2 не дал потерь Recall
на этом наборе; глобальная безопасность и готовность этапа 2 не заявляются.
Следующий шаг: аудит исходников для PBI unanswerable FAIL и эвристики adequacy;
отдельно проверить cap=2 на дополнительных user/cross-lingual gold-наборах.
Пороги, default cap и scoring оставлены прежними.
