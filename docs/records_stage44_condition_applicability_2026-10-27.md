# Records stage44: локальные связи «условие → измерение → образец»

27 октября 2026 года, Asia/Yekaterinburg. Алгоритм
`condition_applicability_audit_v0.1`.
[Проспективный протокол](records/condition_applicability_protocol_v0.1.md),
[предыдущий origin audit](records_stage43_source_origin_2026-10-27.md).

Changed:

- Добавлен отдельный offline аудит всех четырёх frozen stage43 questions,
  всех 561 block occurrences / 1148 events. Прежние 62 selected blocks /
  155 selected events, model-facing wires, PDF и исходные отказы не менялись.
  Scope TAC — все десять исторических документов.
- Exact same-event inventory связывает literal property/method/sample mentions
  с условием только внутри прежнего события. Все spans, знаки, единицы и исходный
  Unicode сохраняются. Между предложениями, колонками, units и статьями связи
  не достраиваются; прежние guards/boundaries не ослабляются.
- Температурный диапазон с альтернативами endpoints сохраняется целиком.
  Шаг и точность термостата имеют отдельные protocol-parameter roles; они не
  превращаются в температуры отдельных измерений. Числовые значения не
  парсятся, не нормализуются и не пересчитываются. Вне finite grammar сохраняется
  полный источник и unresolved temperature role. Также учитываются frequency
  ranges/mentions, duration и atmosphere mentions.
- Явный `sample A` / `sample 2` / `образец 2` — только локальное предложение
  literal label. Multiple/coordinated labels вызывают abstention. Generic
  membrane/sample остаётся классом, не конкретным образцом. Даже explicit label
  не доказывает identity между событиями или applicability конкретного результата.
- Локальные measurement-context proposals требуют совместных property, unique
  compatible method, sample mention/label и measurement cue в том же событии,
  без preparation/guard/boundary/origin conflicts. Preparation-only условия
  остаются в подготовке; смешанные случаи abstain. Это предложения evidence
  links, не scientific entailment или admitted experimental records.

## Заморозка

Сохранены 12 assistant development checks до новых outcomes: восемь event checks
на четырёх уникальных Kayumov clauses, повторённых в двух вопросах, и четыре
unchanged-source/refusal checks. Это exposed development expectations, не
independent gold и не корпусная precision/recall evaluation.
SHA256 `development_checks_v01.json`:
`0523c425a2f7b086e45094a0c80e51fb5f6a321129cd14348bddce3e14ff3d02`.

`baseline_before_run_v01`: 620 source files, fingerprint
`d547c3ec668404193b7f9235257b4ae0f54e6d6791351c8deda1b8f9daac75b4`;
missing dependencies и requirement mismatches отсутствуют. Installed snapshot
не portable lockfile; private corpus/DB/model weights в archive не входят.
Prepare: четыре вопроса, 12 cases и **0 новых applicability outcomes**.
Код, protocol и references после реального run не подгонялись.

## Измеренные результаты

**12/12 source development checks прошли.** В прежних 155 selected events найдено
38 condition occurrences. Это occurrences по question scopes, не независимые
научные условия: известная методика повторена в двух вопросах.

| Literal condition role | Selected occurrences |
| --- | ---: |
| temperature_range | 2 |
| temperature_step | 2 |
| temperature_accuracy | 2 |
| temperature_unresolved | 20 |
| frequency_range | 2 |
| duration | 6 |
| atmosphere_mention | 4 |
| Всего | 38 |

| Link diagnostic | Occurrences |
| --- | ---: |
| same_event_measurement_context_proposal | 2 |
| measurement_protocol_parameter_proposal | 4 |
| preparation_context_only | 10 |
| unresolved | 22 |

Два context proposals — один исходный Kayumov measurement clause в двух вопросах.
Он содержит conductivity, impedance spectroscopy, generic membrane mention и
целый диапазон `от –60…–40 до +70…+80°C`. Два step и два accuracy occurrences
отдельно связаны как параметры той же методики. Конкретный образец из этого
предложения не установлен; generic class не превращается в sample identity.

Аргон из отдельного clause подготовки электродов/сборки ячеек остаётся только
в preparation context. Frequency range `1 Гц–3 МГц` в незавершённом фрагменте
не переносится в другой event и не принимается за доказанную применимость.
Формулы и продолжение thermal equilibrium по-прежнему сохранены целой прежней
unit; grammar не исправляет разрыв предложения. Диаметр 5 мм не реализован как
тип условия v0.1 и не извлекается в новое поле: исходный текст сохранён целиком.

Old wires и selection неизменны; **API admission остаётся 0/4**. Runtime routes,
БД, retrieval scoring, schemas и provider не менялись. Нет model, embedding,
retrieval calls, database access или внешних запросов.

## Локальное исполнение и проверки

Новый CLI `python -m scripts.condition_applicability` требует
`--network-evidence` и устанавливает запрет CPython audited socket/DNS operations
до импорта application modules. Evidence filename и outputs — exclusive, ошибки
не скрываются. Это запрет Python socket/DNS operations, не OS firewall или
монитор поведения native libraries. Provider API не вызывался и его доступность
не проверялась; новые зависимости/модели не загружались.

Tests run:

- Первый targeted applicability run: **23 passed**.
- Финальный applicability/source-origin run: **48 passed**, один существующий
  Starlette/httpx deprecation warning, `output/commit_check_20261026/applicability_v02.xml`.
  Прогоны пересекаются; их нельзя складывать как число unique tests.
- Проверены exact range/step/accuracy spans, explicit/ambiguous sample labels,
  preparation-only atmosphere без inheritance, property/method conflicts,
  citation/reported origins, missing components, guarded/incomplete clauses,
  original events/wires, code/source/reference/PDF drift, exclusive outputs,
  escaping и deterministic exports. Constructed run/exports выполнялись с
  запрещёнными connections; actual CLI отдельно проверен в subprocess.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues, 167 source files.
- Postflight: все 561 source blocks / 1148 events, 144 condition occurrences
  по полному scope и 689 exact inventory spans проверены по event/page text.
  Все восемь parent files на вопрос, включая origin и wire, побайтно совпали со
  stage43. Историческая TAC metadata не менялась; проверены десять PDF paths/hashes.
  Все 41 файл обоих exports побайтно совпали с run; каждый manifest проверил
  1224 bindings. Все 571 PDF-links и 41 relative links ведут к существующим файлам.
- Headless Chrome 156.0.8078.48: четыре question cards, 561 исходный блок,
  selected filter 62 блока / conductivity 33 блока, separate range/step/accuracy
  и preparation-only diagnostics, empty DSC scope, search/reset, full source/event
  expansion и TAC десять строк/восемь колонок прошли. JS errors/network requests
  отсутствуют; три screenshots просмотрены. PDF click behavior не проверялось.
- Четыре actual CLI phases завершились с пустыми списками socket/DNS attempts;
  postflight также выполнен с запрещёнными socket/DNS operations, попыток нет.

Full application suite, live database/retrieval, inference и независимая научная
оценка applicability не выполнялись. Положительные explicit sample-label controls
не доказывают, что identity конкретного образца установлена в реальной методике.

## Артефакты и повтор

`output/records_stage44_20261027/`: frozen references, source baseline,
`prepared_v01`, `run_v01`, `review_v01`, `review_repeat_v01` и `network_*.json`.
`review.html` содержит все исходные blocks, selected filter, exact events,
conditions/sample spans, link proposals/abstentions и PDF-links.
`metadata_review.html` сохраняет все десять TAC документов и согласованные
восемь колонок; full expandable TAC и Terms остаются историческими, без пересчёта.
Empty/refused question scopes остаются видимыми.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.condition_applicability --network-evidence output/records_stage44_new_network.json export --captured output/records_stage44_20261027/run_v01 --output-dir output/records_stage44_new_review
```

Для нового prepare/run используйте новые output directories и network evidence
filenames. Изменённый bound source/code/PDF/reference останавливает воспроизведение.

Limitations: это finite same-event evidence-link experiment. Диапазоны не дают
список фактических measured temperatures; label не даёт межсобытийную identity;
literal cooccurrence не доказывает scientific applicability/own-work origin.
Не реализованы общая anaphora resolution, table/figure sample mapping,
геометрические параметры и все возможные condition types. Unknown/unsupported
source не удаляется и не считается научным отсутствием данных.

Verdict: ближайший локальный этап реализован без API, с сохранением исходного
контекста и всех прежних отказов. Следующий bounded шаг — source-bound проверка
явных sample/table identifiers и их ссылок в методике с отдельными abstention
cases, до любого решения о scientific/production admission.
