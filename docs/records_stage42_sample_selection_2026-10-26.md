# Records stage42: эксперимент отбора по классу образца

26 октября 2026 года, Asia/Yekaterinburg. `sample_scope_selection_v0.1`.
[Проспективный протокол](records/sample_scope_selection_protocol_v0.1.md),
[исходный аудит stage41](records_stage41_sample_scope_2026-10-26.md).

Changed:

- Отдельный offline experiment отложил четыре ранее выбранных целых Guo/SEI
  units для вопроса о проводимости мембран. В них обсуждаются Li2O/LiF SEI на
  литии. Это предложение смены selection; scientific irrelevance не доказана.
- Все target-only, mixed, unknown и unsupported-query cases сохраняют прежний
  отбор. В реальном scope сохранены восемь membrane units и шесть units вопроса
  без finite sample class. Ранее выбранных no-class/mixed units здесь нет;
  их retention проверен отдельно constructed tests.
- Текст не обрезается и не исправляется. Sparse references сохраняют исходные
  позиции, все dependencies и co-preservation units целые. Для каждого исходного
  блока/окна остаётся local ledger. Все четыре полных parent files на вопрос
  и историческая TAC metadata сохранены отдельно от нового wire.
- Унаследованные отказы сохранены, добавлен unvalidated-scientific-retention
  blocker. Нулевой current full-page count не снимает исторические запреты.

## Измеренные результаты

Все четыре прежних вопроса и все десять TAC документов остались в scope.
Байты — canonical UTF-8 wire, не tokens и не фактический расход inference.
Counts — occurrences по вопросным scope, не независимые научные наблюдения.

| Вопрос | Блоков stage40 → stage42 | Units stage40 → stage42 | Wire bytes stage40 → stage42 | Полных страниц stage40 → stage42 |
| --- | ---: | ---: | ---: | ---: |
| conductivity_protocol | 113 → 33 | 12 → 8 | 42717 → 27701 | 1 → 0 |
| dsc_protocol | 0 → 0 | 0 → 0 | 6788 → 7146 | 0 → 0 |
| preparation_atmosphere | 29 → 29 | 6 → 6 | 22640 → 22998 | 0 → 0 |
| absent_material | 0 → 0 | 0 → 0 | 9044 → 9402 | 0 → 0 |
| Всего | 142 → 62 | 18 → 14 | 81189 → 67247 | 1 → 0 |

Добавленная provenance увеличивает wire трёх неизменённых selections на 358
байт каждый. Все четыре current packets проходят прежний byte ceiling 100000.
80 прежних selected blocks отложены, scientific loss/recall не измерены.
Из 527 исходных окон сейчас 41 сохранено целиком, 34 частично, 452 отложено;
на stage40 было 116/37/374. Это существенное сокращение model-facing покрытия,
а не доказательство улучшения scientific relevance.

**40/40 predeclared development checks прошли**: 18 unit states, 18 retain/defer
expectations, четыре no-admission checks. Наблюдаемых wrong retention — 0/4
declared SEI deferral cases; wrong deferral — 0/14 declared retention cases.
Знаменатели — overlapping source-bound assistant expectations, не независимые
precision/recall и не научное подтверждение нерелевантности отложенных методик.
Точные membrane method/equilibrium/formula и preparation/argon/O2/H2O блоки
сохранены целиком. Missing Istomina/DSC и Mars/regolith не заменены другим source.

Текущих полных страниц нет; **API admission 0/4**. Все прежние отказы остаются,
ни одного model/retrieval/embedding/DB call в этом этапе нет. Runtime не подключён.

## Проверки и воспроизводимость

Код, оба протокола и все 40 source checks заморожены вместе до новых stage41/42
outcomes. Baseline и история финальных тестов описаны в stage41; code/policy после
новых реальных исходов не подгонялись. Stage42 использует точный stage41 audit.

Tests run:

- Финальный targeted scope/query-selection: **60 passed**, один существующий
  Starlette/httpx warning. Отдельная проверка stages36–40: **214 passed**.
  Эти прогоны перекрываются; их нельзя складывать как unique test count.
- Ruff `app tests scripts` прошёл. Mypy `app` прошёл, 163 source files.
- Constructed checks покрывают mixed membrane/SEI units, query без класса,
  generic films/electrodes/Nafion, отрицательные/цитируемые membrane mentions,
  source offsets, protected/formula-chain integrity, unknown preparation retention,
  oversized text, drift failures и exclusive deterministic exports.
- Postflight: все 62 выбранных блока побайтно совпали с исходными page slices;
  все 113 units, зависимости, ledgers и 527 исходных окон проверены. Шесть
  unsupported-query selected units сохранены. Все пять protected groups остаются
  целиком deferred, как в stage40; их научная ненужность не установлена.
  Все четыре parent files на вопрос, 19 baseline Evidence и metadata десяти
  TAC документов сохранены побайтно; проверены десять PDF paths/hashes.
  Все 33 файла каждого повторного export совпали с run; каждый manifest
  проверяет 1130 bindings. Проверены 317 точных class spans и current page unions.
- Headless Chrome 156.0.8078.47: четыре question cards, все 113 исходных units,
  поиск 1/0/4, раскрытие исходных блоков, отдельная сохранённая method/formula
  unit 3 и вновь отложенная Guo/SEI unit 17, TAC десять строк/восемь колонок.
  Screenshots просмотрены; JS errors/network requests отсутствуют. Все 571
  PDF-links и 29 relative links ведут к существующим файлам. PDF click behavior
  не проверялось. Отложенный source остаётся читаемым в локальном review.

Full application suite, live retrieval, DB integration, научная оценка ответов и
новый inference не запускались. Source bytes reduction не доказывает экономию
tokens или улучшение качества ответа. Full-page и byte guards не ослаблялись.

## Артефакты и повтор

`output/records_stage42_20261026/run_v01` и отдельные `review_v01`,
`review_repeat_v01`. Все deferred units видны с полным исходным текстом/PDF-links
в `review.html`; `metadata_review.html` хранит все десять прежних TAC документов,
с восемью колонками, explicit missing/proposed fields и неизменёнными Terms.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.sample_scope select --source output/records_stage41_20261026/run_v01 --output-dir output/records_stage42_new_run
.\.venv\Scripts\python.exe -X utf8 -m scripts.sample_scope export-selection --source output/records_stage42_20261026/run_v01 --output-dir output/records_stage42_new_review
```

Limitations: SEI и membrane не универсально взаимоисключающие химические классы.
Буквальная competitor-only группа может содержать переносимую методику; её
научная ненужность не установлена. Generic film/electrode/sample и implicit
material aliases не разрешаются; общая статья не подтверждает общий образец.
Own-work/bibliographic origin и applicability отдельных условий остаются открытыми.
Independent scientific acceptance и production admission отсутствуют.

Verdict: два ограниченных инженерных шага stage41/42 реализованы и проверены.
Guo/SEI over-inclusion теперь учтён явным воспроизводимым selection experiment,
без скрытого удаления источников или повышения допуска. Следующая ближайшая
задача — source-based проверка происхождения и применимости retained фрагментов
(собственная методика / обсуждение / bibliography / unresolved), с новым frozen
comparison и отдельными false-retention/deferral cases до admission upgrade.
