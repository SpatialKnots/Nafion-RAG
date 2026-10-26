# Records stage38: компактный контекст с полной локальной диагностикой

Дата: 24 октября 2026 года, Asia/Yekaterinburg.

Changed: реализована отдельная offline-проекция `compact_context_packet_v0.1`.
Четыре model-facing JSON суммарно уменьшены с **8156634 до 200221 байта**.
Каждый меньше прежнего лимита 100000 байт. Весь выбранный исходный текст сохранён:
127532 байта, 561 блок, 527 исходных окон, 449 структурных зависимостей.
Полные native diagnostics этапа 37 скопированы побайтно, включая 19 baseline
Evidence, source events, cue/guard spans, asset registries, все исходные запреты
и неизменённый parent. Это завершение инженерного формата, не допуск к генерации.

## Scope, контракт и воспроизводимость

Использованы все четыре вопроса из
`output/records_stage37_20261023/run_v02`, без нового поиска или чтения БД.
Протокол: [compact_context_packet_protocol_v0.1.md](records/compact_context_packet_protocol_v0.1.md).
Существующие шесть assistant development retention challenges взяты из
`output/records_stage37_20261023/retention_challenges_v01.json` с прежними hashes.
Новые эталоны и независимые человеческие scientific labels не создавались.
Scope TAC: все десять документов исходной стадии, без пересчёта Terms/sections.

Перед замером подготовлены код, тесты, протокол, native inputs и hashes:

- `output/records_stage38_20261024/baseline_before_run_v01`: 588 source files,
  fingerprint `ad3b9c5685fa9c9717670e22d513b73466666ad1336da4c34e6414758da0ef52`,
  нет отсутствующих dependencies или requirement mismatches.
- `prepared_v01`: четыре вопроса, десять документов, ноль новых compact outcomes;
  postflight проверил 984 frozen bindings.
- `run_v01`, `review_v01`, `review_repeat_v01`: по 1005 проверенных bindings;
  все 21 файла каждого экспорта побайтно совпадают с исходным запуском.

Архив исходников и installed-version snapshot не являются переносимым lockfile
или комплектом приватного корпуса. Прежние stage37 и более ранние артефакты не
перезаписывались. Все пути ниже относительно корня репозитория.

## Представление

`app/generation/compact_context_packet.py` проверяет полный stage37 packet
детерминированным replay и строит прозрачные JSON-таблицы с названиями колонок.
Точные тексты блоков видимы в UTF-8; бинарного сжатия и пересказа нет.
Целочисленные ссылки начинаются с единицы и сохраняют порядок исходных списков.
Сохранены article/PDF identity, физическая страница, выбранный слой, offsets,
каждое окно с core blocks, все активные зависимости и co-preservation units.
Одинаковые тексты в разных source positions не схлопываются.

Повторяющиеся event quotes, длинные диагностические строки, геометрические
asset/window matrices и полные идентификаторы остаются в `diagnostics.json`.
Wire связан с ним canonical SHA256; manifest отдельно проверяет байтовый hash
полного файла. В модели видны distinct event states, неподтверждённые proposed
kinds, guard reason codes и boundary flags через общий словарь. Метки блока
не означают, что guard относится к каждому его предложению; точные event spans
доступны локально. Полные визуальные связи и непрочитанная диагностика не
объявляются проверенными моделью. Источник остаётся недоверенными данными.

`app/evaluation/compact_context_run.py` и CLI `scripts/compact_context_packet.py`
поддерживают prepare/run/export, current PDF registration, проверки drift и
полную HTML-выдачу. Это отдельный offline development path; новых runtime routes
или изменений provider factory нет.

## Измеренные результаты

Байты — действительная длина canonical `wire.json`, без завершающего newline,
с учётом JSON escaping и всего служебного содержимого. Это не token count.

| Вопрос | Stage37 wire, байт | Компактный wire, байт | Точный текст, байт | Окон / блоков | Полных страниц-вхождений |
| --- | ---: | ---: | ---: | ---: | ---: |
| conductivity_protocol | 5015307 | 60066 | 39545 | 150 / 163 | 6 |
| dsc_protocol | 286251 | 6345 | 0 | 0 / 0 | 0 |
| preparation_atmosphere | 958743 | 54298 | 34322 | 165 / 173 | 6 |
| absent_material | 1896333 | 79512 | 53665 | 212 / 225 | 10 |
| Всего | 8156634 | 200221 | 127532 | 527 / 561 | 22 |

Проверку нового размера прошли **4/4**, `network_ready` — **0/4**.
Пустой DSC-пакет не получает выдуманного контекста. Старые insufficiency,
qualifier, source-page и historical size blockers не сняты. Старый размер
явно считается историческим; текущий compact byte check хранится отдельно.
Проверяются actual serialized JSON, decoded source text и union page intervals.
Сериализация, ссылки и JSON escaping не скрывают полные страницы.

Шесть прежних retention checks прошли без изменения результатов: разорванная
импедансная методика с формулой, полная защищённая таблица с headers/footnotes,
подготовка в аргоне и три no-refusal-upgrade случая. Эти проверки не подтверждают
научную применимость условий, семантику таблицы или независимую accuracy.

## Проверки и артефакты

Tests run:

- `pytest_target_v02.xml`: **125 passed**, один существующий
  `StarletteDeprecationWarning` об httpx. Targeted scope: новый compact packet,
  stage37 source packet, context risks и record article windows.
- Ruff `app tests scripts`: passed. Mypy `app`: без ошибок, 157 source files.
- Postflight: 527 точных контекстов, 561 точный блок, 1148 неизменённых локальных
  source events, 449 зависимостей, десять проверенных source PDF paths.
  Оба повторных экспорта совпали; 45 локальных PDF-ссылок и 17 относительных
  artifact links ведут к существующим файлам.
- Headless Chrome 156.0.8078.47: четыре question cards, поиск 1/0/4, раскрытие
  исходного контекста, TAC десять строк/восемь колонок, поиск/reset, правильная
  ссылка `metadata.json`; нет JS errors, network requests или writable forms.
  Три screenshots визуально просмотрены. PDF clicks в браузере не проверялись.

Первый запуск pytest (`pytest_target_v01.xml`) имел 125 setup errors:
родительская папка `--basetemp` ещё не существовала. Тесты тогда не исполнялись;
этому запуску успех не приписывается. После создания папки выполнен отдельный
успешный запуск v02. До финального запуска исправлен один mypy type inference
error; широкий exception handler не добавлялся. Full application suite, live
retrieval и provider integration в этом этапе не запускались: runtime не менялся.

Основные результаты:

- `output/records_stage38_20261024/review_v01/review.html` — вопросы, размеры,
  exact contexts, полные diagnostics и ссылки на четыре компактных JSON.
- `output/records_stage38_20261024/review_v01/metadata_review.html` — все десять
  документов, восемь согласованных колонок, полный expandable historical TAC,
  предложения metadata, явные unknown и исходные PDF.
- В каждой question directory: `wire.json`, `packet.json`, `diagnostics.json`,
  `expanded_contexts.json`. Полный sidecar byte-identical исходному stage37.
- `report.json`, `manifest.json`, `metadata.json`, `postflight_v01.json`,
  `browser_qa_v01.json`, screenshots и source snapshots сохранены локально.

Рецепт, каждый output должен быть новым:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.compact_context_packet prepare --output-dir output/records_stage38_20261024/prepared_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.compact_context_packet run --prepared output/records_stage38_20261024/prepared_v01 --output-dir output/records_stage38_20261024/run_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.compact_context_packet export --captured output/records_stage38_20261024/run_v01 --output-dir output/records_stage38_20261024/review_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.compact_context_packet export --captured output/records_stage38_20261024/run_v01 --output-dir output/records_stage38_20261024/review_repeat_v01
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/unit/test_compact_context_packet.py tests/unit/test_source_context_packet.py tests/unit/test_context_risks.py tests/unit/test_record_article_windows.py -q --basetemp output/records_stage38_20261024/tmp_target_v02 -o cache_dir=output/records_stage38_20261024/cache_target_v02 --junitxml output/records_stage38_20261024/pytest_target_v02.xml
```

Limitations: алгоритм не доказывает связь property/method/conditions или достаточность
выбранных источников. 22 полных page occurrences и неопределённые границы остаются.
Все исходные PDF сохранены; операции с БД, embeddings, retrieval и model calls
отсутствуют. Внешний request не создан, платного сравнения нет. Снижение bytes
не доказывает экономию оплаченных токенов, latency или качество модели.

Verdict: компактный формат реализован и проверен на прежнем frozen scope.
Размер перестал быть текущим ограничением этих четырёх wire, scientific admission
остаётся закрытым. Следующий ограниченный шаг — source-based проверка полноты
контекста и применимости условий с явным разбором незавершённых границ, без
механического ослабления full-page guard или прежних отказов.
