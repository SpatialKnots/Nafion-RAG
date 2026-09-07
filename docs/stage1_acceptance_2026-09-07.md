# Этап 1: проверка рабочего цикла ARIADNE

Дата: 2026-09-07. Базовый HEAD: `4958bf0`; исправления находятся в рабочем дереве,
новый commit не создавался. Проверки выполнялись в `D:\Nafion-RAG`.

## Changed

Исправлены пять воспроизведённых дефектов:

1. **Индекс переставал обновляться после трёх сборок.** В БД основной индекс
   имел `stale`, desired=23, active=20, attempts=3, без текущей ошибки. Worker
   возвращал отсутствие работы: SQL ограничивал попытки, а успешная сборка
   не сбрасывала счётчик. Теперь успешная, в том числе вытесненная новой ревизией,
   сборка сбрасывает бюджет. Новая ревизия вне активной сборки также сбрасывает
   его. Добавлены три regression tests. Через штатный запрос rebuild создана
   ревизия 24; настоящий FastEmbed rebuild завершён, active=desired=24, attempts=0.
2. **Повреждённая загрузка скрывала причину отказа за WinError 32.** PyMuPDF
   удерживал файловый дескриптор при неудачном открытии по пути. Удаление `.part`
   выбрасывало PermissionError вместо `invalid_pdf_structure`. Структурная
   валидация теперь открывает ограниченный по размеру upload как поток байтов.
   Добавлен regression test: исходная диагностика сохранена, `.part` удалён.
3. **Ссылка на контекст страниц возвращала HTTP 422.** Динамический маршрут
   `/pages/{page_number}` перехватывал `/pages/context`. Статический маршрут
   зарегистрирован первым; добавлен HTTP regression test.
4. **Отказ доступа ошибочно считался отсутствием файлов.** При запуске worker
   в sandbox рекурсивный `Path.rglob` подавил отказ доступа к внешней папке
   cellosolve; 16 записей получили missing, хотя PDF физически присутствовали.
   Теперь обход использует `os.walk` с передачей ошибок, а при OSError библиотека
   получает status=error без изменения статусов файлов. Добавлен тест отказа
   доступа. После разрешённого запуска worker вне sandbox повторный scan
   восстановил все 16 записей; originals в хранилище не затрагивались.
5. **Missing-файл показывал processing spinner.** Теперь этап discovery для
   missing отображается как ошибка без анимации обработки; добавлен тест.

Добавлен `scripts/stage1_smoke.py`: воспроизводимая изолированная проверка
PostgreSQL/API с настоящими PDF extraction, OCR и FastEmbed. Обновлены README,
архитектурная и эксплуатационная документация о фоновом rebuild.

На старте Python-процессов API/worker не было. API и worker запущены скрыто,
API отвечает на `http://127.0.0.1:8000/health`. Периодическое сканирование обеих
подключённых библиотек подтверждено обновлённым `last_scan_at`.

## Tests run

Команды Python ниже запускались через `.venv\Scripts\python.exe`.

| Проверка | Результат |
| --- | --- |
| `-m pytest -q`, до исправлений | 341 passed, 1 warning |
| `-m pytest -q`, после всех исправлений | 348 passed, 1 warning |
| `-m ruff check app tests scripts/stage1_smoke.py` | PASS |
| `-m mypy app` | PASS, 68 source files |
| `-m ruff format --check app tests`, исходный baseline | FAIL: 20 файлов требуют форматирования; массовое форматирование не выполнялось |
| `-m app.ingestion.cli doctor`, до и после | Все проверки PASS; основной stale устранён; Alembic head `0005_library_sources` |
| `-m app.ingestion.cli corpus-manifest --check docs/corpus_manifest.json` | MISMATCH: 17 extra, 0 missing, 0 changed |
| `-m app.ingestion.cli corpus-report` | 33 статьи, 493 страницы, 619 чанков, 814 текстовых слоёв; отсутствующих PDF/OCR нет |
| `scripts/stage1_smoke.py`, финальный запуск | PASS, включая OCR и page-range context |
| Реальные HTTP endpoints | health, главная страница, libraries, ingestion, articles, answer UI — 200; hybrid search и ссылки PDF/chunk/page context — PASS |
| SHA-256 всех 33 оригинальных PDF | Совпадают с сохранёнными checksum |
| Очистка тестовых схем | В PostgreSQL не осталось схем `audit_*` |
| In-app Browser | Проверены DOM и screenshot Libraries; cellosolve 16/16 Ready, Nafion-RAG 17/17 Ready |
| `git diff --check` | PASS |

Первый запуск smoke обнаружил WinError 32 и завершился ошибкой. После исправления
запуски прошли. Сбой live HTTP-проверки обнаружил 422, повторная проверка после
перезапуска API прошла. Эти первоначальные сбои не считаются успешными запусками.

Изолированный smoke проверил:

- создание библиотеки, сканирование и отсутствие нового задания при повторном scan;
- ingestion нового текстового PDF, stale → реальная сборка → ready;
- exact, semantic, hybrid и hybrid_cross_lingual с трассировкой на статью;
- байтовую идентичность выдаваемого оригинала и переход к тексту/контексту;
- duplicate upload с existing article, отказ повреждённой загрузке;
- failed job с диагностикой для повреждённого PDF в библиотеке;
- захват задания, искусственное истечение heartbeat, возврат в очередь;
- `MissingStagedFile` после повторного захвата отсутствующего файла;
- отсутствие статей от ошибочных заданий;
- очередь сканированного PDF через upload, настоящий OCR, OCR-копию,
  восстановление слова Nafion и неизменность исходного скана.

Для изоляции использованы отдельная схема и outer transaction с savepoints:
коммиты worker/API не попадали в production tables. Схема откатывалась в finally.
Рабочий корпус остался на 33 статьях. Синтетические документы явно помечены
как pipeline fixtures и не являются научными данными.

## Baseline поиска

Одинаковая коллекция `literature`, top_k=10; scoring и evaluation thresholds не менялись.

| Набор / метод | PASS | Top-1 | Дополнительно |
| --- | --- | --- | --- |
| Базовые 24 / exact | 23/24 | 16/24 | recall=0.95833, mean rank=1.52174 |
| Базовые 24 / hybrid | 23/24 | 21/24 | recall=0.95833, mean rank=1.21739 |
| Extended 46 / hybrid | 45/46 | 30 из 38 answerable | article recall=0.97368, MRR=0.86491; 8/8 unanswerable PASS, false_answerable=0 |

Extended threshold gate пройден без изменения порогов, evidence_trace_complete=true.
p50=1923.8 ms, p95=3019.2 ms — наблюдение этого запуска, не нагрузочный benchmark.
Unanswerable PASS относится к evidence-adequacy проверке, а не к реальному вызову LLM.

Неразрешённый случай: `q20_ma_table_solvent_aggregation_2009` и соответствующий
`qext003_ma_table_solvent_set`. Вопрос о Nafion casting solvents
DMF/DMSO/NMP/EtOH/DMAc не находит целевую статью с DOI
`10.1016/j.polymer.2009.01.060`. Exact diagnostics включают mandatory terms
DMF/DMSO/NMP/DMAC. Причина пропуска ещё не установлена; разбор — первый кандидат
этапа 2. Подгонка scoring под этот вопрос в рамках инфраструктурной проверки не делалась.

## Артефакты

- `data/exports/corpus_report_20260907T044650Z.json`
- `data/exports/corpus_manifest_stage1_20260907.json` — новый отдельный snapshot;
  старый tracked manifest сохранён для сравнения.
- `data/exports/retrieval_eval_exact_20260907T044802Z.json`
- `data/exports/retrieval_eval_hybrid_20260907T045309Z.json`
- `data/exports/retrieval_eval_extended_hybrid_20260907T045527Z.json`
- `tmp/stage1_smoke_final.log`
- `tmp/stage1_smoke_81877583654d4adca4a91e9f4c2b1c26/report.json`
- `tmp/stage1_live_report.json`, `tmp/stage1_live_final.log`
- `tmp/stage1_api_final.out.log`, `tmp/stage1_api_final.err.log`
- `tmp/stage1_worker_full.out.log`, `tmp/stage1_worker_full.err.log`

Exports и runtime logs локальные, не являются tracked тестовыми результатами.

## Limitations

- Libraries проверен визуально и по DOM; анимация во время длительного
  OCR и переход встроенного PDF viewer к `#page=N` не проверялись.
- Восстановление job проверено с искусственно просроченным heartbeat;
  принудительное убийство процесса во время OCR не выполнялось.
- Полная матрица конкурентных rebuild, сетевых сбоев и аварийного восстановления
  не выполнена; существующие unit tests не заменяют такую приёмку.
- OCR проверен на синтетическом англоязычном скане; качество русских сканов,
  таблиц и формул требует этапа 3.
- Полный semantic/cross-lingual quality baseline и научная проверка LLM-ответов
  не выполнялись. Второй multilingual индекс показывается ready в БД, но его
  актуальность относительно всего корпуса этим отчётом не подтверждается.
- PyMuPDF validation теперь читает bounded upload в память: дополнительный
  буфер до настроенного лимита файла (100 MiB в текущей конфигурации).
- Сохраняется StarletteDeprecationWarning о httpx TestClient и исходный долг
  форматирования. Первоначальный `ruff ... .` также сообщил ошибки обхода
  каталогов с отказом доступа; проверка исходников `app tests` прошла без них.
- В БД до проверки присутствовали 15 старых failed jobs; они не удалялись и
  не объявляются исправленными. Новый корпус включает прежний документ
  `priority3_e2e_upload`; происхождение этой записи требует отдельной ревизии.
- Launcher проверяет наличие API, но при уже работающем API не запускает
  отсутствующий worker. В этом запуске worker поднят отдельно; постоянный
  supervision процессов и исправление launcher остаются эксплуатационным долгом.

## Verdict

Основной цикл подтверждён, пять обнаруженных функциональных дефектов исправлены,
индекс восстановлен, API и worker работают. Полная приёмка всех требований
этапа 1 не объявляется завершённой: перечисленные аварийные и визуальные
сценарии остаются открытыми. Ближайшая работа по качеству — разбор пропуска Ma
с неизменной разметкой и измерение cross-lingual поиска.
