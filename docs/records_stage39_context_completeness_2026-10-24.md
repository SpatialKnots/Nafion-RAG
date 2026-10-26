# Records stage39: полнота контекста и локальный аудит применимости условий

Дата: 24 октября 2026 года, Asia/Yekaterinburg.

Changed: реализован отдельный `context_completeness_v0.1` audit поверх всех
четырёх immutable stage38 packets. Разобраны 35 страниц-вхождений, 22 случая
полного текстового покрытия, 1148 source-event occurrences и 449 зависимостей.
Причина всех 22 полных страниц — union прежних окон; ни одно отдельное окно
не покрывает страницу полностью, dependency closure новых блоков не добавляет.
Полные native inputs и исходные отказы сохранены побайтно/без изменения.

Обнаружена одна уникальная source-cooccurrence proposal, повторённая в двух
вопросах. Она связывает упоминания conductivity, мембраны, impedance method и
температуры внутри одного исходного события. Это не подтверждённая научная
запись: sample identity, own-work origin и per-result applicability не установлены.
Подготовка в аргоне и незавершённое продолжение методики не присоединяются
к этому предложению автоматически. API admission остаётся **0/4**.

## Контракт и scope

Протокол, написанный до новых outcomes:
[context_completeness_protocol_v0.1.md](records/context_completeness_protocol_v0.1.md).
Input snapshot: `output/records_stage38_20261024/run_v01`, все четыре вопроса,
все 561 selected blocks, 527 original windows, 19 baseline Evidence и десять TAC
документов. Новых retrieval/DB/model calls, metadata lookup или PDF изменений нет.
Поиск соседних страниц и создание нового model-facing payload не выполнялись.

Изменённые компоненты:

- `app/generation/context_completeness.py`: независимо пересчитывает причины
  покрытия, инвентаризирует каждый original event, literal source spans, scope,
  guards и missing fields; сохраняет каждую зависимость и открытые границы.
- `app/evaluation/context_completeness_run.py`: frozen prepare/run/export,
  source-bound development checks, current PDF registration и HTML review.
- `scripts/context_completeness.py`, `tests/unit/test_context_completeness.py`:
  CLI и проверки source integrity, abstention и deterministic replay.

Словарь property families переиспользует stage28 `PROPERTY_CUES` без изменения.
Новые конечные literal inventories находят явные sample mentions, impedance/DSC
method phrases, numeric temperature/time/frequency и atmosphere mentions.
Текст, offsets, units и старые scope rules не переписываются. Наличие всех четырёх
типов упоминаний в одном целом measurement event без guards, boundary problems,
preparation indicators или property/method conflict допускает только предложение
совместного упоминания. Все остальные случаи получают `not_linked` с причинами.
Fields не наследуются между events даже в одной группе/блоке/статье.

Source-cooccurrence не устанавливает конкретный образец или применимость каждого
числа. Например, в единственном уникальном предложении temperature inventory
содержит `+80°C`, `10°C`, `0.1°C`: в полном исходном контексте это endpoint,
шаг и точность поддержания температуры. Алгоритм не превращает их в три температуры
измерения, не восстанавливает полный диапазон по числам и не выделяет precision
как нормализованный параметр. Это явный предел текущего literal audit.

## Результаты на прежних вопросах

Все количества ниже — occurrences в question scope, а не независимые статьи,
измерения или оценки научной точности.

| Вопрос | Страниц | Полное покрытие | Уже полных core unions | Открытых границ | Source events | Cooccurrence proposals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| conductivity_protocol | 10 | 6 | 1 | 5 | 275 | 1 |
| dsc_protocol | 7 | 0 | 0 | 3 | 0 | 0 |
| preparation_atmosphere | 8 | 6 | 3 | 4 | 265 | 1 |
| absent_material | 10 | 10 | 6 | 7 | 608 | 0 |
| Всего | 35 | 22 | 10 | 19 | 1148 | 2 |

22 selected unions совпадают с original-window unions. Десять полны уже по core
blocks, остальные двенадцать становятся полными с окружением прежних окон.
Single complete windows — 0. Added dependency blocks — 0. Следовательно,
сохранение всех прежних окон и их exact text неизбежно сохраняет полные страницы;
удаление повторных JSON references этот факт не меняет. Это техническое основание
для отдельного versioned selection experiment, не разрешение удалить часть evidence.

449 зависимостей распределены так:

- 431 unresolved source-order boundary;
- 13 unresolved cross-page boundary;
- 5 protected source groups с сохранённым составом, неизвестной table semantics.

Все 113 co-preservation units сохранены; ни одно предложение не реконструировано.
Все 19 open page boundaries перечислены с оригинальным состоянием; absent/mixed
neighbors не подменяются предполагаемым текстом. Подготовка ячейки в аргоне
остаётся `preparation_procedure`. Impedance tail и фрагмент thermal equilibrium
сохраняют incomplete/guarded diagnostics. Старые block-wide guards не сужались.

1148 events соответствуют 1027 уникальным event IDs. 613 literal field spans
проверены по точным page offsets. Два предложения соответствуют одному event ID
в физической странице 3 Kayumov 2021, а не двум независимым подтверждениям.
Остальные 1146 event occurrences не связаны в complete literal chain; это результат
конечной и намеренно ограниченной grammar, не доказательство отсутствия научных
сведений в литературе. DSC context по-прежнему пуст; отсутствие Mars/regolith
в выбранном evidence не становится утверждением об отсутствии во всём корпусе.

## Заморозка и development checks

До run создан `development_checks_v01.json`, hash
`a0a5b62523c8eb6f54c5b25c14fadf27bca3759431823718724471d7d5febfda`:
четыре source-event checks, один protected-table check и четыре проверки неизменности
selection/coverage/refusal. Все **9/9** прошли. Эталоны ассистента основаны на уже
известных development sources; independent human confirmation отсутствует.

`baseline_before_run_v01`: 594 source files, fingerprint
`dfb468a4c4dae6a1e8b8b53b8f4a5cafb6f2e00ae0222df26388d0be1eb0ed5f`,
без missing dependencies/requirement mismatches. В `prepared_v01` проверены 1013
bindings, new audit outcomes до run — 0. В run и двух exports — по 1030 bindings.
Архив не содержит приватный корпус/БД и не является переносимым lockfile.

Tests run:

- **170 passed**, один существующий Starlette/httpx deprecation warning;
  `pytest_target_v02.xml`. Scope: новый completeness audit, compact packet,
  source packet, context risks и protocol association.
- Ruff `app tests scripts`: passed. Mypy `app`: без ошибок, 159 source files.
- Postflight проверил exact original context/cue/guard/boundary inventories,
  field spans, все page unions и dependency memberships. Исходные compact packets
  и diagnostics побайтно совпадают со stage38; 19 baseline Evidence сохранены.
  Проверены десять source PDF paths и full TAC provenance всех десяти документов.
- Оба повторных экспорта побайтно совпали с run во всех **17 файлах**.
  1158 PDF-links и 17 relative artifact links ведут к существующим файлам.
- Headless Chrome 156.0.8078.47: четыре cards, поиск 1/0/4, раскрытие exact event,
  metadata десять строк/восемь колонок, search/reset и правильный `metadata.json`.
  Нет JS errors/network requests/writable forms. Три screenshots просмотрены.
  Поведение PDF click в браузере не проверялось.

Первый targeted run: 167 passed, 3 failed. Ошибки новых тестовых fixtures:
ожидали full coverage у неполной выборки, пытались изменить отсутствующую dependency
и присвоить coverage прежнее значение. Fixtures исправлены; рабочие guards не
ослаблялись. Успех приписывается только отдельному финальному запуску v02.
До запуска также исправлены локальные Ruff/mypy замечания. Full application suite,
live retrieval, DB integration и inference не запускались; runtime не менялся.

## Артефакты и повтор

Результаты находятся в `output/records_stage39_20261024/`:

- `review_v01/review.html`: все вопросы, coverage reasons, exact source events,
  literal inventories, abstention reasons, полные units/dependencies и PDF-links;
- `review_v01/metadata_review.html`: все десять TAC документов с согласованными
  восемью колонками, full expandable historical sections, proposed metadata,
  unknown и непересчитанными Terms;
- каждая question directory: `audit.json`, побайтно прежние `parent_packet.json`
  и `diagnostics.json`;
- `report.json`, `manifest.json`, `metadata.json`, `postflight_v01.json`,
  `browser_qa_v01.json`, tests, screenshots и source snapshots.

Команды требуют новых output directories:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.context_completeness prepare --checks output/records_stage39_20261024/development_checks_v01.json --output-dir output/records_stage39_20261024/prepared_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.context_completeness run --prepared output/records_stage39_20261024/prepared_v01 --output-dir output/records_stage39_20261024/run_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.context_completeness export --captured output/records_stage39_20261024/run_v01 --output-dir output/records_stage39_20261024/review_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.context_completeness export --captured output/records_stage39_20261024/run_v01 --output-dir output/records_stage39_20261024/review_repeat_v01
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/unit/test_context_completeness.py tests/unit/test_compact_context_packet.py tests/unit/test_source_context_packet.py tests/unit/test_context_risks.py tests/unit/test_record_protocol_association.py -q --basetemp output/records_stage39_20261024/tmp_target_v02 -o cache_dir=output/records_stage39_20261024/cache_target_v02 --junitxml output/records_stage39_20261024/pytest_target_v02.xml
```

Limitations: конечный literal inventory не является универсальным парсером
научных условий; не решены sample identity, interval/step/accuracy semantics,
anaphora и applicability между предложениями. Независимая scientific accuracy не
измерена. 22 full-page occurrences, 19 open page boundaries и 444 unresolved
order/cross-page links остаются; protected table semantics неизвестна.
Network-ready 0/4, генерации и внешних requests нет. Новых payload selection,
retrieval, Terms workflow или provider routes этот этап не добавляет.

Verdict: инженерный аудит завершён; причины полноты и отсутствующих связей теперь
явные и воспроизводимые. Готовность к inference не достигнута. Следующий bounded
шаг — отдельная versioned query-aware selection policy с exact-source preservation
полного parent локально и проверкой потерь всех связанных условий/защищённых групп.
Потребуется отдельно различать диапазон, шаг и точность и не наследовать preparation
atmosphere по соседству. Смена selection должна оцениваться как новое научное
предложение; она не может считаться эквивалентной lossless stage38 или автоматически
разрешать платный inference.
