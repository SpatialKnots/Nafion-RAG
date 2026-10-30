# ARIADNE: offline-проверка области ответа и принадлежности величин

30 октября 2026 года, Asia/Yekaterinburg. Итерация 2
[плана качества ответов](answer_quality_plan_2026-10-30.md).
Алгоритм: `answer_scope_audit_v0.2`. Это отдельная диагностическая реализация
пункта 2, без подключения к production answer path.

Changed:

- Добавлены `scripts/answer_scope_audit.py`, runner
  `scripts/run_answer_scope_audit.py`, 49 constructed tests и versioned protocol.
  Новый слой принимает фактические claim/citation IDs, исходные evidence chunks
  и точные зарегистрированные/дополнительные страницы. События из прозы ответа
  не выдумываются; существующая operation-ownership проверка воспроизводится
  отдельно на своих сохранённых входах.
- Конечные RU/EN правила выделяют maximum/swelling/form mentions, explicit
  Celsius points/ranges, room-temperature wording, medium/scope cues, alpha
  assignments и number-for-form relations. Raw offsets восстановлены через
  mapped recognition sidecar; исходный текст не переписан.
- Раздельно проверяются явная форма числа, присутствие численной поверхности
  в действительно процитированном evidence, scope сравнения, локальность
  температуры/среды, ближайшие preceding regression/experiment cues и области
  операций. Ни одно совпадение не становится подтверждением научной связи.
- Room temperature не приравнивается к 25°C, диапазон к точке, проценты к α.
  Числа H-формы не становятся Li-формой. Не переносятся условия из другого
  statement, подписи рисунка, таблицы, работы или операции.
- Alpha matching внутри постороннего идентификатора запрещён; registry должен
  покрывать весь page range supplied evidence, original-PDF identity одной
  работы должна быть согласована. Эта версия допускает только `original` layer;
  OCR требует отдельного source contract. Неизвестные table columns и связи
  caption/value явно отмечены как не реализованные.
- Production code, prompt/schema, thresholds/ranking, API/UI, индексы и
  исходные PDF не изменены. Все старые ответы, отказы и бюджеты сохранены.

Наблюдения на реальном сохранённом ответе:

1. Исходный HTTP 200 / answered с αLi=1.54 сохранён без исправлений. В восьми
   страницах исходного контекста обнаружены две explicit alpha assignments на
   с.96: 1.54 и 1.536. Численная поверхность 1.54 присутствует в действительно
   процитированном E1. Это `present_unverified`, не доказательство общего максимума.
2. Для 1.54 ближайший preceding cue — «регрессии», для 1.536 —
   «экспериментально». Смешанный statement помечен unresolved; ближайший cue
   не объявляется доказанной научной классификацией. Локальной температуры у
   этих значений нет; комнатная температура численно не определена алгоритмом.
3. На четырёх отдельно архивированных post-hoc страницах выделены ещё две
   number-for-form relations на с.75: 2.3 для H-формы и 1.8 для Li-формы.
   Только 1.8 попадает в larger-same-form numeric review candidates для claim
   αLi=1.54. У него остаются нерешёнными property/material/unit/condition связи;
   алгоритм не объявляет ни подтверждённый контрпример, ни новый максимум.
4. Температура 25°C из подписи рисунка и упоминание смеси на странице видны
   в page inventory, но не наследуются relation с 1.8. Таблица с.88 не
   разбирается как набор научно связанных row/column values; это явный gap.
5. Прежняя отдельная проверка источника ассистентом, которая нашла научный
   контрпример на с.75, сохранена в другом поле отчёта. Она не подставляется
   вместо предсказаний нового алгоритма и не становится independent gold.
6. Все **четыре** detected source relations — **unresolved**, научных подтверждений
   **0**. Формальное принятие старого `/answer` не заменено задним числом отказом.

Operation-ownership regression:

- Все 12 constructed cases восстановлены через исходный `validate_reply` и
  воспроизвели сохранённые audits.
- Три настоящих прежних native outputs заново разобраны из `response.bin`;
  restored proposals и audits совпали. Original result/status сохранены.
- Сохранились три `different_explicit_operation_regions` flags и две
  `declared_relation_cue_not_found_in_finite_scope` diagnostics. Проверка source
  regions остаётся конечной диагностикой, а не semantic ownership validation.

Tests run:

- **188 tests passed**, JUnit
  `output/answer_scope_regression_20261030_v04.xml`: 49 новых tests плюс прежние
  operation ownership, requested-information, retrieval-loss и query-qualifier
  controls. Constructed cases проверяют формы, wrong citation/work, source
  identity, температуры, диапазоны, проценты, отрицания, смесь/индивидуальный
  растворитель, регрессию/наблюдение и запрет переноса условий. Это не accuracy.
- Узкий финальный прогон: **49 passed**,
  `output/answer_scope_tests_20261030_v03.xml`. Более ранний исправленный —
  42 passed. Эти проверки входят в 188 и не суммируются.
- Первый новый прогон: **10 failed / 31 passed** — ошибочный regex отвергал
  число перед точкой конца предложения. Ошибка исправлена, исходный JUnit
  `answer_scope_tests_20261030_v01.xml` сохранён.
- Ruff новых module/runner/tests/QA passed. Mypy чистого diagnostic module
  с `--explicit-package-bases` passed. Более широкая проверка module+runner
  **не прошла**: сначала duplicate module names из script paths, затем четыре
  существующие ошибки `gigachat_answer_smoke.py` и untyped `fitz` import runner.
  Успех mypy runner/всего проекта здесь не заявляется; старые модули не изменены.
- Обе версии scope audit повторены на одинаковых inputs с идентичными
  структурами. Отдельно совпали 12 constructed и три native operation replays.
  `Engine.connect` и GigaChat transport запрещены явными guards; audit hook
  запрещает все socket connect/DNS/sendto. DB/provider calls — 0.
- Проверены hashes входов и шести immutable PDF; **18 уникальных страниц**
  совпали со свежим извлечением текста. Каждая detected relation/number/form/
  statement anchor совпала с исходным raw page slice.
- Статическая HTML QA: **6 TAC rows**, восемь согласованных columns, **12**
  существующих file links, search input/handler. Browser rendering и выполнение
  поиска не проверены. Полные доступные Abstract раскрываются; отсутствующие
  Conclusions/Terms отмечены, все архивные варианты метаданных сохранены.
- До первого успешного экспорта runner ошибочно передал fixture wrapper вместо
  restored proposal (`KeyError: raw_selection`), затем обнаружил неверное
  ожидаемое число работ. Реальное объединение трёх swelling works и пяти event
  works содержит шесть, а не пять: Istomina отсутствует в event scope. Protocol
  v0.1 сохранён, v0.2 явно исправляет cardinality. Protocol v0.3 объявляет
  diagnostic output additions алгоритма v0.2. Initial QA использовала неверное
  имя поля `rows`; исправлена на сохранённое `selections` до финальной QA.
  Summaries реальных failures — `development_failures.json`, не полные raw logs.

Артефакты:

- [Итоговая HTML-таблица](../output/answer_scope_audit_20261030/review_v02/review.html).
- `output/answer_scope_audit_20261030/review_v02/report.json` — исходный ответ,
  audits исходного/расширенного контекста, отдельный прошлый scientific review,
  operation replays, все шесть TAC works, bindings и ограничения.
- `review_v02/source_snapshot/` — module, runner, tests, финальный protocol.
- `review_v01` сохраняет первый успешный algorithm v0.1 output; final v0.2
  добавляет explicit medium/universe/layout diagnostics и source-integrity checks.
  Прежние артефакты не переписаны. Source hashes старого отчёта закономерно
  не совпадут с новым текущим module; воспроизведение требует frozen snapshot,
  а не переписывания старых bindings.
- `qa_v01.py`, `qa_v01.json`, `development_failures.json` — QA и журнал ошибок.

Воспроизведение финального offline отчёта в новый каталог:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.run_answer_scope_audit --output output/answer_scope_audit_20261030/review_replay_new
```

Runner fail-closed проверяет source/input hashes; требует существующие frozen
артефакты и локальные PDF. Сеть/БД/LLM не нужны и запрещены.

Limitations:

Это finite source-bound diagnostic, не полноценное семантическое извлечение,
проверка entailment, доказательство максимума или automatic scientific gate.
Не решены table/figure linkage, coreference, полнота корпуса и научная
принадлежность условий. Один знакомый реальный вопрос и constructed controls
не дают независимой оценки точности. Runtime и качество новых model answers
не менялись и не проверялись. Новых API/OAuth calls, reservations и разрешений
нет. Cache/ORM дефект repeated requests остаётся отдельным открытым вопросом.

Verdict:

Пункт 2 выполнен в объявленном объёме отдельной offline-проверки с явными gaps,
counterexamples и unresolved состояниями. Полная semantic validation остаётся
открытой; **50% работ плана (2/4)** не означает 50% научной точности. Следующий
пункт — содержательное и проверяемое представление ответа; затем независимая
научная оценка на отдельно полученных вопросах/разметке.
