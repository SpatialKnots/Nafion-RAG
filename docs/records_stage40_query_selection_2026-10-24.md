# Records stage40: отдельный отбор контекста по вопросу

Дата: 24 октября 2026 года, Asia/Yekaterinburg.

Changed: реализован `query_context_selection_v0.1`, отдельный offline experiment
поверх четырёх frozen stage39 tasks. Отобраны 142 из 561 прежних block occurrences
через 18 целых co-preservation units. Точный выбранный текст — 37900 вместо 127532
байт, четыре wire суммарно — **81189 вместо 200221 байта**. Каждый wire проходит
прежний лимит 100000. Полные текстовые страницы-вхождения: **22 → 1**.

Это изменение selection, не lossless перепаковка. 419 блоков, 884 events и пять
protected-group occurrences отложены локально. Из 527 прежних окон 116 сохранены
целиком, 37 частично, 374 не передаются в candidate wire. Все полные parents,
audits, diagnostics и 19 baseline Evidence сохранены локально побайтно.
Научная сохранность такого отбора не установлена; API admission остаётся **0/4**.

## Контракт и реализация

[Протокол v0.1](records/query_context_selection_protocol_v0.1.md) зафиксирован до
новых selection outcomes. Вход: `output/records_stage39_20261024/run_v01`, все
четыре вопроса, все десять TAC документов, прежние source hashes/метаданные.
Retrieval, БД, provider, PDF, исходные units и старые schema не менялись.

- `app/generation/query_context_selection.py`: finite query-family/intent policy,
  article/material necessary mentions, exact block seeds, whole-unit closure,
  sparse parent references, all-block/all-window ledgers и current guards.
- `app/evaluation/query_context_selection_run.py`: frozen prepare/run/export,
  current PDF registration, development checks, deterministic HTML.
- `scripts/query_context_selection.py`, `tests/unit/test_query_context_selection.py`:
  CLI и проверки целостности/неопределённостей/повторяемости.

Finite families — conductivity и thermal analysis. Для protocol intent выбираются
блоки с literal family + method/measurement cue и совместимые method-family hits
в anchored article. При явном запросе preparation/conditioning добавляются их
literal indicators и старые cues. Guards, reported work, incomplete и unsupported
event states сами по себе не исключают совпавший текст. Локальная grammar не
должна предварительно разрешить все научные связи для попадания блока в candidate.
Неизвестная релевантность отложенных блоков остаётся явно неизвестной.

Явные author/year и `containing …` material constraints проверяются прежней
query-qualifier grammar внутри одной статьи по frozen baseline Evidence/metadata.
Unknown metadata и отсутствующие mentions не заменяются текстом другой статьи.
Неявный sample/material смысл вопроса эта finite policy ещё не разбирает — это
существенный предел, проявившийся на реальном remaining full-page case ниже.

Closure выбирает целый parent unit при попадании любого seed. Порядок и весь
текст блоков, formula interleaves, unresolved dependencies и original flags
сохраняются; поля между предложениями не наследуются. Integer references могут
быть sparse и сохраняют original parent positions. Отдельные `dependency_refs`
и `unit_refs` связывают отфильтрованные списки с полным parent. В wire перечислены
только целиком сохранённые старые окна; partial/deferred окна учтены локально.

Числа диапазона, шага и instrument accuracy не нормализуются и не превращаются
в отдельные температуры измерения: передаётся полный исходный блок методики.
Объединение selected source intervals, decoded visible text и actual serialized
JSON проверяются прежним full-page guard. Oversized/complete units не обрезаются.
Все старые запреты сохранены; добавлен scientific-retention-not-validated blocker.

## Измеренные результаты

Количество блоков/окон/events/units — occurrences в четырёх question scopes,
не независимые научные наблюдения. Байты — реальные canonical UTF-8 wire files
без завершающего newline, не token counts и не измеренная стоимость inference.

| Вопрос | Блоков parent → selected | Текст selected, байт | Wire parent → selected, байт | Полных страниц parent → selected | Целых / частичных / отложенных окон |
| --- | ---: | ---: | ---: | ---: | ---: |
| conductivity_protocol | 163 → 113 | 25106 | 60066 → 42717 | 6 → 1 | 96 / 23 / 31 |
| dsc_protocol | 0 → 0 | 0 | 6345 → 6788 | 0 → 0 | 0 / 0 / 0 |
| preparation_atmosphere | 173 → 29 | 12794 | 54298 → 22640 | 6 → 0 | 20 / 14 / 131 |
| absent_material | 225 → 0 | 0 | 79512 → 9044 | 10 → 0 | 0 / 0 / 212 |
| Всего | 561 → 142 | 37900 | 200221 → 81189 | 22 → 1 | 116 / 37 / 374 |

23 seed blocks замыкаются в 142 selected blocks, 18 units и 124 dependencies.
264 events остаются в выбранных блоках, 884 отложены с полным parent. В выбранных
блоках 82 guarded event occurrences; ещё 392 guarded occurrences остаются локально.
Это отчёт о потере model-facing покрытия, а не утверждение о потере или сохранении
конкретных научных фактов. Полная scientific loss/recall evaluation не выполнена.

Все пять protected-group occurrences отложены целиком, не частично. Поэтому
проход all-or-none check **не означает**, что все таблицы переданы модели или
научно признаны ненужными. Известная таблица свойств растворителей осталась целиком
в diagnostics; development check фиксирует retained 0/5 при сохранении целостности.
Методика impedance/equilibrium с formula interleave и полный preparation block
с аргоном/O2/H2O сохранились. Для DSC/Istomina и Mars regolith substitute source
не выбран. Это не corpus-wide absence claim.

## Оставшийся full-page case и пределы релевантности

`conductivity_protocol`: Guo 2020, физическая страница 6, region
`c13dd85d5895994ce03eb62ab741f62e1bf57700e272a026bf7b75da1682efe8`.
Источник содержит обсуждение Li2O/LiF SEI на литии, EIS и conductivity. Эти
literal hits и whole-unit closure собирают полное текстовое покрытие страницы.
Вопрос спрашивает про мембраны, но sample/material соответствие здесь не
установлено finite query qualifiers. Это наблюдаемый пример избыточного отбора,
а не подтверждённый релевантный protocol. Полный source и seed reasons доступны
в HTML/JSON; страница не вырезана ради получения нуля full pages.

Этот случай выявлен после prospective run. Он не добавлялся задним числом к
11 development checks и не исправлялся скрытой подгонкой v0.1. Нужна отдельная
версия sample/material scope policy и source-based проверка её false exclusions:
простое исключение всех неизвестных samples может потерять нужную методику.

## Заморозка и проверки

`development_checks_v01.json` создан до нового отбора, SHA256
`4170185a35427065348e47dd242c7c52d709e749706827944d6485e77298ee50`.
11/11 checks прошли: четыре exact-node requirements, один protected all-or-none,
два no-substitute и четыре no-admission-upgrade. Несколько checks перекрываются
одним source block; это exposed assistant development evidence, не independent gold.

`baseline_before_run_v01`: 600 source files, fingerprint
`f1d79bebbad765c9431a98dd56b472bce92b513faa4149bfc95f512f7cc090f3`,
нет missing dependencies/requirement mismatches. Prepare: 1038 verified bindings,
new selection outcomes — 0. Run и оба exports: по 1063 verified bindings.
Private PDFs/DB/weights не входят в source archive; installed snapshot не lockfile.

Tests run:

- **179 passed**, один существующий Starlette/httpx deprecation warning,
  `pytest_target_v02.xml`. Scope: новый query selection, completeness audit,
  compact/source packets и query qualifiers.
- Ruff `app tests scripts`: passed. Mypy `app`: без ошибок, 161 source files.
- Postflight: 142 exact selected blocks, 18 whole units, 116 whole original
  contexts и 48 exact seed spans. Проверены все ledgers, flags, protected-group
  all-or-none, page unions и source PDF hashes. Десять документов/19 baseline
  Evidence сохранены; parent packets/audits/diagnostics совпали побайтно.
- Все **25 файлов** обоих повторных exports побайтно совпали с run.
  152 PDF-links и 25 relative artifact links ведут к существующим файлам.
- Headless Chrome 156.0.8078.47: четыре question cards, поиск 1/0/4, раскрытие
  полного selected unit, TAC десять строк/восемь колонок, search/reset, правильный
  `metadata.json`. JS errors/network requests/writable forms отсутствуют.
  Три screenshots просмотрены. PDF click behavior в браузере не проверялось.

Первый targeted run: 178 passed, 1 failed. Новый HTML-тест ошибочно требовал
deferred marker в fixture из единственного целиком выбранного блока. Проверка
исправлена на наличие полного diagnostic link; escaping/source checks сохранены.
Успех относится к отдельному финальному запуску v02. Ruff замечания loop closure
и длины строки исправлены до final run; guards не ослаблялись. Full application
suite, live retrieval, DB integration и inference не запускались: runtime не менялся.

## Артефакты и повтор

Каталог: `output/records_stage40_20261024/`.

- `review_v01/review.html`: четыре вопроса, все selected units с отдельными
  полными блоками/PDF-links, seed reasons, coverage losses, article restrictions,
  all-block/all-window ledgers и ссылки на полные parents.
- `review_v01/metadata_review.html`: все десять TAC документов, согласованные
  восемь колонок, full expandable historical TAC, proposed metadata, unknown и
  Terms без пересчёта/обязательных ручных решений.
- В каждой question directory: `selection.json`, точный `wire.json`, прежние
  `parent_audit.json`, `parent_packet.json`, `diagnostics.json`.
- `report.json`, `manifest.json`, `metadata.json`, postflight/browser QA,
  tests/screenshots и source snapshots сохранены отдельно от прежних stages.

Команды требуют новых output directories:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.query_context_selection prepare --checks output/records_stage40_20261024/development_checks_v01.json --output-dir output/records_stage40_20261024/prepared_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.query_context_selection run --prepared output/records_stage40_20261024/prepared_v01 --output-dir output/records_stage40_20261024/run_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.query_context_selection export --captured output/records_stage40_20261024/run_v01 --output-dir output/records_stage40_20261024/review_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.query_context_selection export --captured output/records_stage40_20261024/run_v01 --output-dir output/records_stage40_20261024/review_repeat_v01
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/unit/test_query_context_selection.py tests/unit/test_context_completeness.py tests/unit/test_compact_context_packet.py tests/unit/test_source_context_packet.py tests/unit/test_query_qualifiers.py -q --basetemp output/records_stage40_20261024/tmp_target_v02 -o cache_dir=output/records_stage40_20261024/cache_target_v02 --junitxml output/records_stage40_20261024/pytest_target_v02.xml
```

Limitations: 419 blocks и 411 прежних окон уже не представлены целиком в candidate;
независимая научная сохранность не измерена. Неявный sample/material scope не
реализован; Guo/SEI показывает over-inclusion. Остаётся одна полная текстовая
страница и все прежние scientific/qualifier/source refusals. Numeric-role semantics
и per-result applicability не решены. Генерации/внешнего request/DB/retrieval calls
нет, network-ready 0/4. Снижение bytes не доказывает экономию токенов или inference.

Verdict: отдельный воспроизводимый selection experiment реализован; известные
методические фрагменты сохранены, потери старого покрытия явно учтены. Production
и scientific acceptance не достигнуты. Следующий bounded шаг — sample/material
scope с явным unknown и source-based проверкой false inclusions/exclusions,
включая Guo/SEI против вопроса о мембранах, до любого admission upgrade.
