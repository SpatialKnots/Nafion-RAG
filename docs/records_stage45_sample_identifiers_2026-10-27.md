# Records stage45: идентификаторы образцов и ссылки на таблицы

27 октября 2026 года, Asia/Yekaterinburg. `sample_identifier_audit_v0.1`.
[Проспективный протокол](records/sample_identifiers_protocol_v0.1.md),
[предыдущий stage44](records_stage44_condition_applicability_2026-10-27.md).

Changed:

- Отдельный offline аудит извлекает exact sample/table/figure mentions из всех
  561 прежних блоков / 1148 событий четырёх frozen questions. Прежние 62 selected
  blocks / 155 events, model-facing wires, PDF, metadata, отказы и admission не менялись.
- Числовой/буквенный identifier не нормализуется. Plural lists/ranges сохраняются
  целиком без разворачивания; generic sample без identifier не назначается строке.
  Кандидат строки ограничен одновременно article ID и original PDF hash.
- Same-event table reference имеет приоритет. Без неё требуется отдельный exact
  article-numbering anchor; наличие единственной доступной таблицы недостаточно.
  Ссылки на рисунки учтены, но curve/figure mapping не реализован.
- Multiple scopes/rows, чужая статья/PDF, original guards/boundaries, reported/
  cited context, bibliography, mixed sample event и shared layout вызывают abstention.
  Все кандидаты и причины сохранены. Literal row proposal в constructed control
  не является scientific identity или доказанным применением методики.

## Отдельный source-only supplement

В прежнем stage44 packet нет страницы с Kayumov Table 2. Явно добавлен отдельный
source supplement: физическая PDF страница 6, печатная страница 512, зарегистрированный
region `385e111be1918a676bd928dd2e1490bab2016f216cc7a4da4a8c43e7677d23ad`.
Supplement не добавлялся в model-facing wire и не меняет прежний выбор контекста.
Это та же статья/PDF из прежнего десятидокументного scope, не новый документ.

Источник: прежний stage23 source report и stage19 page geometry. Native model
candidates/values не копировались в новый каталог и не применялись. Повторно
использованы неизменённые `build_cell_ledger` и `relation_map` — только их
детерминированные source-coordinate/cue функции.

Первый prepare остановился на изменённом историческом binding:
`Frozen multi-record input/source/code changed: D:\Nafion-RAG\pyproject.toml`.
Старый запуск stage23 **не объявлен воспроизведённым**. Файл действительно изменён:
старый hash `7705859b19b41c0e3de988e974aa7b883a06c95c9b247415f8da2be617da1d71`,
текущий `445d252e510751eed272a94cd5d9d8c0692a548fd60e4a23234acbfa1af0d66a`.
Остальные проверенные старые bindings совпали. Неуспешный prepare/network evidence
сохранён отдельно; причины не скрыты и historical manifest не исправлялся.

До новых binding outcomes реализован новый source-only capture contract:
historical source-report и geometry artifacts должны совпасть со своими старыми
hashes, оба PDF hashes также обязаны совпасть. Затем текущим локальным парсером
заново извлечены PDF text, blocks и lines и проверено точное совпадение с прежней
геометрией/текстом. Все прочитанные текущие файлы bound отдельно; mismatch старого
runtime остаётся в `supplement.json`. Это новая регистрация источника с текущим
кодом, не ослабленный historical replay и не подтверждение старых модельных выводов.

Таблица визуально проверена целиком: PyMuPDF rendering и независимый Poppler
`pdftoppm`, физическая страница 6. В каталоге **21 печатная строка**. Заголовок
поля — «Состав пластификатора», basis — «(масс. доли)». Сохраняются exact row,
column, group и basis spans. Они не объявляются составом конечной мембраны или
внешней средой измерения. Shared layout строк 12/13 не ремонтируется.

## Заморозка и результаты

До новых исходов сохранены восемь block/refusal cases: четыре exposed source-block
expectations и четыре unchanged-source/refusal checks. Отдельный catalog check
фиксирует row 2 и её четыре endpoints: row label, printed `EC`, column header и basis.
SHA256 `development_checks_v01.json`:
`96f275515c9e19f1b3b5b1278856207c67ad9e94e74e8de656f897f2e086fb16`.
Это assistant source-development expectations, не independent scientific gold.

Финальная prospective source snapshot `baseline_before_run_v02`: 626 files,
fingerprint `9d52eb5c7ab1d347c72981edaafc3d2c37bfbd4e0ac889d025f8483b5ab8eff4`;
missing dependencies и requirement mismatches отсутствуют. Installed snapshot
не portable lockfile; private corpus/DB/model weights в archive не входят.
Финальный prepare — `prepared_v03`: четыре вопроса, одна supplemental page,
восемь source cases, **0 новых identifier bindings**. После реальных исходов
policy/references не подгонялись. Код parser/геометрии старых этапов не менялся.

**8/8 block/refusal checks и 1/1 catalog check прошли.** Сводка прежнего selected scope:

| Диагностика | Occurrences |
| --- | ---: |
| Singular sample mentions | 3 |
| Table references | 3 |
| Figure references | 4 |
| Неразвёрнутый sample list/range | 1 |
| unresolved_with_row_candidate | 3 |

Три singular mentions — обозначения образцов 1, 2, 3 в Kayumov discussion clause.
При unique source numbering anchor они имеют ровно по одному кандидату строки
Table 2; в печатной plasticiser column стоят SL, EC, G2. Все три binding states
остаются **unresolved**, поскольку событие содержит несколько образцов и прежние
block guards. Для них sample identity и per-result method applicability остаются
`not_established`; условия не переносятся. Это не три новых измерения и не
scientific acceptance этих связей.

В том же исходном block N79 есть ссылка на Table 1 в другом событии — о температуре
плавления EC. Она не была перенесена к sample mentions и не подменила Table 2.
Sample/table candidate не превращает общий method block в метод каждого результата.
Missing Istomina/DSC и Mars/regolith не заменяются новым source. Admission **0/4**.

## Проверки и локальное исполнение

CLI `python -m scripts.sample_identifiers` требует `--network-evidence` и
запрещает CPython audited socket/DNS operations до application imports. Нет
новых API/model/embedding/retrieval calls, database access или загрузок моделей.
Это Python-level guard, не OS firewall или монитор native-library networking.

Tests run:

- Первый identifier run: **22 passed**.
- После добавления catalog-source reference check: **77 passed** по identifiers,
  прежним table relations и condition applicability.
- После нового source-only recapture contract: финальный **78 passed**, один
  существующий Starlette/httpx deprecation warning,
  `output/commit_check_20261026/identifiers_v03.xml`. Прогоны пересекаются и не
  складываются как число unique tests.
- Проверены same-event/numbering scopes, repeated IDs в разных статьях/PDF/
  таблицах, wrong/missing table/sample rows, leading zeroes, unexpanded ranges,
  reported/cited/mixed cases, original guards, shared source layout, current-source
  capture при stale runtime, changed required geometry, source/code/PDF/reference/
  supplement drift, exclusive outputs, escaping и детерминированные exports.
  Constructed run/exports выполнялись с запрещёнными network connections.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues, 169 source files.
- Postflight: все 561 blocks / 1148 events, 55 exact reference/anchor spans и
  12 binding occurrences по полному scope проверены. Все девять parent files
  на вопрос, включая wire/applicability/origin, побайтно совпали со stage44;
  historical TAC metadata не менялась. Проверены десять PDF paths/hashes.
  Каталог содержит 21 строку; shared rows 12/13 остались с unresolved composition.
  Все 47 файлов обоих exports побайтно совпали с run; каждый manifest проверил
  1280 bindings. Все 572 PDF-links и 46 relative artifact links ведут к файлам.
- Headless Chrome 156.0.8078.48: отдельный supplement, четыре question cards,
  561 исходный блок, selected filter 62 блока / conductivity 33 блока, N79 sample
  candidates/abstentions, empty DSC scope, search/reset, раскрытие источников и
  TAC десять строк/восемь колонок прошли. JS errors/network requests отсутствуют;
  три screenshots просмотрены. PDF click behavior не проверялось.
- Final prepare_v03, run и два exports завершились без socket/DNS attempts.
  Postflight также выполнен с запрещёнными socket/DNS operations, попыток нет.

Full application suite, live retrieval/DB, inference, независимая научная оценка
identity/applicability не выполнялись. Положительные synthetic literal-row controls
не означают scientific acceptance трёх реальных unresolved candidates.

## Артефакты и повтор

`output/records_stage45_20261027/`: исходные renders, checks, baseline,
`prepared_v03`, `run_v01`, `review_v01`, `review_repeat_v01`, network/QA evidence.
`catalog.json` / `supplement.json` отделены от прежних parent files и wires.
`review.html` показывает все blocks/events, candidates, anchors и exact endpoints,
отдельную supplemental table, PDF links, поиск/selected filter и empty refused scope.
`metadata_review.html` сохраняет десять TAC документов, согласованные восемь колонок,
исторические expandable TAC и Terms без пересчёта/ручного per-Term workflow.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.sample_identifiers --network-evidence output/records_stage45_new_network.json export --source output/records_stage45_20261027/run_v01 --output-dir output/records_stage45_new_review
```

Каждый output directory и evidence filename должен быть новым. Изменения bound
code/source/PDF/reference/supplement останавливают воспроизведение явно.

Limitations: finite literal source links не решают общую coreference/anaphora,
figure/curve mapping, aliases образцов, изменение нумерации между supplement/main
или scientific identity. Plasticiser composition не становится membrane composition
или measurement environment. Source supplement зарегистрирован отдельно; старые
generation packets по-прежнему не допускаются. Unknown не считается отсутствием.

Verdict: локальный этап identifier/table evidence audit реализован без API.
Следующий bounded шаг — повторная проверка полноты цепочек «образец → метод →
условия» с этими source endpoints и явными unresolved cases, без автоматического
назначения методик/условий строкам таблицы и без повышения admission.
