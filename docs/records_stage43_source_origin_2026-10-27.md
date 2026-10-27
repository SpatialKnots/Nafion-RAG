# Records stage43: локальный аудит происхождения и применимости

Подготовка начата 26 октября, реальный audit и завершение — 27 октября 2026 года,
Asia/Yekaterinburg. Каталог `output/records_stage43_20261026/` сохраняет дату
начала и не переименовывался после заморозки. `source_origin_audit_v0.1`.
[Проспективный протокол](records/source_origin_protocol_v0.1.md),
[предыдущий stage42](records_stage42_sample_selection_2026-10-26.md).

Changed:

- Добавлены отдельные offline audit/CLI и read-only HTML. Scope: четыре frozen
  stage42 questions, все 561 исходных block occurrences / 1148 events и все десять
  исторических TAC документов. Изучаются и selected, и deferred источники.
- Конечный RU/EN inventory находит полные строки заголовков. Leading heading
  и preceding same-page/column heading дают только геометрические предложения.
  Используются прежние source offsets/bboxes; между страницами/колонками/статьями
  состояние раздела не переносится. Отсутствующее подтверждение остаётся unknown.
- Для каждого прежнего события отдельно записаны exact own-work, reported-work
  и numeric-citation cues. Числовая ссылка сама по себе не назначает чужую работу,
  а Methods heading или отсутствие ссылки не устанавливают собственную работу.
  Все прежние block-wide guards и incomplete boundaries сохраняются.
- Measurement/preparation/conditioning — inventory прежних cues, не новые
  научные назначения. Во всех событиях own-work origin, sample identity и
  per-result applicability остаются `not_established`; field inheritance запрещён.
- Selection, model-facing wire, thresholds, database, retrieval, provider и
  runtime routes не менялись. Полные parent files и diagnostics сохраняются.

## Заморозка и результаты

21 source-bound assistant development expectation сохранён до новых origin
outcomes: 17 block diagnostics и четыре unchanged-selection/refusal checks.
17 block checks используют девять уникальных source blocks; часть повторена
в двух вопросах. Это exposed development references, не independent gold.
SHA256 `development_checks_v01.json`:
`d79f7f2fc03ab9d2455e5c87adbb0535a953fa974876271e612c3ba13b387ff3`.

Финальная prospective code snapshot `baseline_before_run_v03`: 614 source files,
fingerprint `90b3935c15f899ba90162229e87c1ebd73f96cd1063c645e1fc1fc4ab8b45f89`;
missing dependencies и requirement mismatches отсутствуют. Installed snapshot
не portable lockfile; private corpus/DB/model weights в archive не входят.
Финальный `prepared_v02`: четыре вопроса, 21 case, **0 новых origin outcomes**.

**21/21 development checks прошли**. Parent selection не менялась: 62 selected
blocks и 155 selected events; всего учтены все 561 blocks и 1148 events.
Счётчики относятся к question-scoped occurrences, не независимым измерениям.

| Origin diagnostic выбранных событий | Количество |
| --- | ---: |
| unknown | 134 |
| citation_only_origin_unknown | 16 |
| guarded_origin_cues | 4 |
| own_work_cue_proposal | 1 |
| Всего | 155 |

Единственный unguarded own-work cue — фраза «в данной работе» в предложении
о составах пластификаторов и рисунке/таблице. Она не превращена в методику,
подтверждённый experimental record или доказанную применимость условий.
Четыре guarded cues не освобождены от старых ограничений. Научная правильность
origin attribution не измерена. Положительного bibliography-origin случая в
selected scope нет; bibliography-heading поведение проверено constructed tests.

Section hints для 62 selected blocks: methods 6, materials 4, introduction 2,
unknown 50. Это геометрические предложения, не scientific section accuracy.
В частности, продолжение методики после формул в другой колонке остаётся
section unknown, хотя прежняя целая co-preservation unit полностью сохранена.
Procedure-role inventory выбранных events: measurement cues 6,
preparation/conditioning cues 2, unknown 147. Это не число фактических измерений
и не полнота обнаружения подготовки: finite прежние грамматики имеют ограничения.

## Полностью локальное исполнение

Prepare, run и повторные exports выполняются wrapper
`output/records_stage43_20261026/offline_runner_v01.py`, который запрещает
CPython audited socket/DNS operations до импорта CLI. Каждый этап сохраняет
отдельный `network_*.json`. Ограничение wrapper не является OS firewall или
монитором сетевого поведения native libraries; сами новые пути работают только
с замороженными локальными файлами, inference/retrieval/download кода не вызывают.
Недоступность API не проверялась и не обходилась заменой provider.

Run summary: model/embedding/retrieval calls **0**, database access **false**,
generation/external request construction **false**. Admission остаётся **0/4**,
все прежние blockers сохранены, никаких новых удалений/deferrals нет.

## Проверки

Tests run:

- Финальный source-origin/sample-scope прогон: **51 passed**, один существующий
  Starlette/httpx warning, `output/commit_check_20261026/origin_v02.xml`.
  Проверены source spans, exact events/guards, unknown/citation/mixed origin,
  heading geometry, подготовка без field inheritance, frozen source/code/PDF drift,
  exclusive outputs и повторные exports. Полный run/export constructed pipeline
  проверен с запрещёнными socket connections; попыток соединения не было.
- После правки только HTML-фильтра: **1 passed**, тот же warning,
  `origin_html_v03.xml`. Этот тест пересекается с предыдущим прогоном.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues, 165 source files.
- Postflight: все 561 блока / 1148 событий, 190 exact origin spans и 83 exact
  heading spans проверены по исходному page text. Все семь parent files на
  каждый вопрос, включая wire, побайтно совпали со stage42; historical TAC
  metadata не менялась. Проверены десять original/selected PDF paths/hashes.
  Все 37 файлов обоих exports побайтно совпали с run; каждый manifest проверил
  1175 bindings. Все 571 PDF-links и 37 relative artifact links ведут к файлам.
- Headless Chrome 156.0.8078.48: четыре question cards, 561 исходный блок,
  selected filter 62 блока, conductivity filter 33 блока, empty DSC scope с
  прежними отказами, поиск/reset, раскрытие полного method block и events,
  TAC десять строк/восемь колонок прошли. JS errors/network requests отсутствуют;
  три screenshots просмотрены. PDF click behavior не проверялось.
- Prepare_v02, run_v01 и оба exports завершились с запретом audited Python
  socket/DNS operations; соответствующие четыре `network_*.json` содержат
  `completed: true` и пустой список connection/DNS attempts.

Первый прогон: 24 passed, 1 failed. Drift-тест создал новый файл по ошибочно
угаданному имени вместо изменения фактического frozen input. Исправлен тест:
путь берётся из captured report и проверяется существование файла до mutation.
Production guard не ослаблялся. Перед первым реальным audit обновлён source
snapshot и prepared_v02. HTML дополнительно сохраняет видимость empty/refused
questions при фильтрации; научные исходы после run не подгонялись.
Elapsed times pytest включают длительную паузу среды между 26 и 27 октября;
они не используются как performance benchmark.

Full application suite, live database/retrieval, новые model calls и независимая
научная оценка не выполнялись. Новый runtime provider или local LLM не добавлен.

## Артефакты и повтор

`output/records_stage43_20261026/`: frozen checks, baseline, `prepared_v02`,
`run_v01`, `review_v01`, `review_repeat_v01`, network guard evidence и QA.
В `review.html` доступны все exact source blocks, events/guards, heading spans,
PDF-links, поиск и read-only фильтр прежнего отбора. Пустой DSC scope и отказы
остаются видимыми. `metadata_review.html` сохраняет все десять TAC документов,
восемь колонок и прежние expandable texts; Terms не пересчитываются.

Повтор требует новых output directories и новых network evidence filenames:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m output.records_stage43_20261026.offline_runner_v01 output/records_stage43_new_network.json export --captured output/records_stage43_20261026/run_v01 --output-dir output/records_stage43_new_review
```

Прямой CLI также доступен: `python -m scripts.source_origin prepare|run|export`.
Изменения bound code/source/PDF/checks останавливают воспроизведение явно.

Limitations: finite literal cues и geometric section proposals не решают
own-work attribution, semantic reading order, полноту section boundaries,
sample identity или scientific applicability. Unknown не считается отсутствием
доказательств. Никакие scientific accuracy/recall, экономия inference или
production readiness этим аудитом не установлены.

Verdict: ближайший API-independent этап реализован как отдельный воспроизводимый
аудит с сохранением источников и прежнего отбора. Следующая локальная задача —
source-bound проверка применимости конкретных method/condition фрагментов к
измерению и образцу, с отдельным frozen protocol и abstention cases; до этого
не снимать запреты и не выводить origin/applicability из соседства текста.
