<p align="center">
  <img src="app/static/brand/ariadne-logo-horizontal.png" alt="ARIADNE" width="520">
</p>

# ARIADNE

Локальная система для работы с научной литературой о Nafion/PFSA и связанных аккумуляторных материалах. Сохраняет оригинальные PDF, извлекает текст по страницам, строит фрагменты с привязкой к источнику и предоставляет поиск, просмотр доказательств и ответы с цитатами.

Состояние сверено с исходниками **13 октября 2026 года**. Версия Python-пакета — `0.1.0`; концепция проекта `v1.1` в презентациях не является версией программного релиза. Рабочая директория исторически называется `Nafion-RAG`.

## Что реализовано

| Подсистема | Возможности в исходниках | Ограничения |
| --- | --- | --- |
| PDF ingestion | Импорт файла/папки через CLI, загрузка через UI/API, постоянные локальные библиотеки, очередь и worker | Нужны PostgreSQL, миграции и доступные файлы |
| Текст и источники | PyMuPDF, OCRmyPDF, оригинальный/OCR/выбранный текстовый слой, детерминированные чанки, контроль PDF и ссылки на страницы | Ошибки OCR, повреждённые глифы и сложная геометрия PDF остаются возможны |
| Retrieval | `exact`, `semantic`, `hybrid`, `hybrid_cross_lingual`, фильтры и группировка; локальные FastEmbed-векторы | Семантическим методам нужен индекс; ограничения группировки могут скрывать нужные фрагменты |
| Индекс | Состояния и поколения индекса, очередь пересборки, фоновая пересборка и очистка поколений | Готовность текста и готовность векторного индекса различаются |
| Ответы | OpenAI provider, проверка citation IDs, отказы по эвристике достаточности, mini-review по статьям | Цитата и прохождение эвристик не доказывают научную корректность утверждения |
| Числовые кандидаты | Извлечение, source/context diagnostics, аудит изменений и локальный review UI | Научное принятие извлечения и массовое обновление фактов остаются открытыми |
| Experimental records | Draft contract, точные source regions, manifests, проверка evidence integrity, review worksheets, локальный smoke и offline comparison | Development harness; автоматически принятые научные записи не реализованы |
| TAC и Terms | Экспериментальные скрипты извлечения Title/Abstract/Conclusions, метаданных, аудита границ и предложений терминов; HTML review | Не подключены к production indexing; результаты требуют review |

Внешний поиск метаданных и полноценный разговорный chat UI не реализованы. `GROBID_URL` и `ENABLE_EXTERNAL_METADATA_LOOKUP` в конфигурации сами по себе не подтверждают наличие работающей интеграции.

## Текущий экспериментальный статус

Основной pipeline ingestion → retrieval → ответы присутствует в коде. Октябрьские циклы отдельно исследуют experimental records и TAC; их номера этапов относятся к разным экспериментам.

**Experimental records, S01–S06.** Реализованы профиль Li-Nafion, контракт кандидатов, экспорт источников и сравнение сохранённых single-field ответов. Предварительный эталон содержит 3 development случая / 30 полей и имеет статус `needs_independent_review`. При повторной проверке сохранённых ответов 12 октября у Qwen2.5-1.5B и Qwen2.5-3B было по 3/30 совпадения с этим эталоном, все — отказы. Это не независимая оценка научной accuracy и не доказательство готовности автоматического extraction adapter. Разметка, связь sample/conditions/method/origin и научное принятие остаются открытыми. Подробнее: [план разработки](docs/ariadne_development_plan_2026-10-09.md), [S06 comparison](docs/ariadne_s06_reference_comparison_2026-10-09.md), [проверка сессии](docs/ariadne_session_review_2026-10-12.md).

**TAC, stages 05–07.** Проверены границы сохранённых предложений, исправлены два варианта административных stop headings, добавлены source-bound Terms proposals. Текущие версии: `tac_section_proposals_v0.6` и `tac_term_candidates_v0.3`. Замороженный development snapshot содержит 33 документа, 493 выбранные страницы и 619 чанков, включая повторную загрузку Welch. В сохранённом результате stage 07: 377 предложений терминов / 1 087 точных evidence occurrences. Это количество результатов, не precision/recall. Ошибки границ и повреждённые исходные глифы сохраняются в диагностике; независимая точность 95% не подтверждена. Подробнее: [stage 05](docs/tac_stage05_boundary_audit_2026-10-12.md), [stage 06](docs/tac_stage06_stop_headings_2026-10-12.md), [stage 07](docs/tac_stage07_terms_2026-10-12.md).

Размер корпуса и результаты выше относятся к указанным сохранённым входам. Они не являются новым измерением состояния живой БД. Исторические retrieval и numeric audits доступны в [roadmap](docs/roadmap.md) и [аудите numeric occurrences](docs/stage3_numeric_occurrences_2026-09-14.md).

## Быстрый запуск

Нужны Python 3.11+, PostgreSQL и доступная локальная БД. Для сканированных PDF дополнительно нужны OCRmyPDF, Tesseract с языками из `OCR_LANGUAGES` и Ghostscript. Начальная конфигурация OCR использует `eng+rus`.

Из корня репозитория в PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Копируйте `.env.example` только при первоначальной настройке. В `.env` задайте `DATABASE_URL` для существующей БД и проверьте `DATA_ROOT`, OCR и параметры индекса. `.env` не хранится в Git.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.ingestion.cli doctor
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

В другом терминале запустите worker:

```powershell
.\.venv\Scripts\python.exe -m app.workers.worker
```

Откройте [локальный dashboard](http://127.0.0.1:8000/ui/) или [API docs](http://127.0.0.1:8000/docs). После настройки окружения доступен Windows launcher `scripts/ARIADNE.cmd`.

`GET /health` возвращает состояние HTTP-приложения; он не заменяет `doctor` с проверкой БД, миграций, файлов и OCR. Подробности: [operations](docs/operations.md).

## Добавление PDF

```powershell
.\.venv\Scripts\python.exe -m app.ingestion.cli file data/inbox/example.pdf --collection literature
.\.venv\Scripts\python.exe -m app.ingestion.cli folder data/inbox --collection literature
```

`example.pdf` здесь — путь к вашему входному файлу. В UI доступны [загрузка](http://127.0.0.1:8000/ui/ingestion) и [локальные библиотеки](http://127.0.0.1:8000/ui/libraries). Добавьте папку через Add Library и запустите Scan Now. При `LIBRARY_SCAN_ENABLED=true` worker периодически сканирует включённые библиотеки.

Оригинальные PDF сохраняются отдельно и должны оставаться неизменными. OCR создаёт отдельный производный файл. У evidence сохраняются article, PDF path, страница/диапазон, source type, выбранный текстовый слой и исходный текст.

Статус ingestion `indexed` означает готовность article/page/chunk evidence в PostgreSQL. Семантический поиск зависит от отдельного состояния индекса.

## Поиск и векторный индекс

Для семантического поиска постройте поколение индекса:

```powershell
.\.venv\Scripts\python.exe -m app.retrieval.cli build-generation --collection literature
.\.venv\Scripts\python.exe -m app.retrieval.cli status --collection literature
```

Модель задаётся `EMBEDDING_MODEL`; начальное значение — `BAAI/bge-small-en-v1.5`. Первое использование может потребовать загрузки модели. При `VECTOR_AUTO_REBUILD_ENABLED=true` и `WORKER_ROLE=vector` или `all` пересборка запускается в фоне, а запросы на неё объединяются.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/search?q=Li-Nafion&collection=literature&top_k=10&method=exact'
Invoke-RestMethod 'http://127.0.0.1:8000/search?q=proton%20transport&collection=literature&top_k=10&method=hybrid'
```

Доступны также `semantic` и `hybrid_cross_lingual`. Последний использует варианты запроса и доменный RU/EN glossary; это не гарантия универсального перевода или полноты retrieval. Группировку и число фрагментов на статью оценивайте на задаче: ограничения одного/двух чанков уже приводили к потере нужного evidence в audits.

## Ответы с цитатами

Поиск и просмотр источников доступны без ключа генерации. Для ответов через настраиваемый provider в `.env` нужны:

```dotenv
RAG_PROVIDER=openai
RAG_OPENAI_API_KEY=YOUR_API_KEY
RAG_OPENAI_MODEL=YOUR_MODEL
```

Provider отправляет вопрос и выбранные фрагменты настроенному OpenAI API endpoint. Таким образом, хранение и retrieval локальные, а этот путь генерации использует внешний сервис. Локальный model smoke для experimental records — отдельный harness.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer `
  -ContentType application/json `
  -Body '{"question":"Li-Nafion membrane lithiation protocol","method":"hybrid_cross_lingual","top_k":5,"answer_style":"mini_review"}'
```

[Answer UI](http://127.0.0.1:8000/ui/answer) показывает ответ/отказ и evidence. Проверка отбрасывает claims без цитат или с неизвестными evidence IDs. Mini-review группирует evidence по статье; citation markers ведут на исходную PDF-страницу. Эвристические проверки достаточности и контекста не устанавливают научную истинность или корректность каждой связи между утверждениями.

## Локальный TAC review

Основные колонки HTML: **Title, Authors, Journal, Year, Abstract, Conclusions, Terms, ссылка на исходный PDF**. Таблица содержит поиск, раскрытие полных текстов, source diagnostics и optional boundary assessments. Terms остаются предложениями с точными цитатами; score не является вероятностью корректности.

Для существующей рабочей копии итоговый stage 07 HTML находится в `output/tac_stage07_terms_20261012/ARIADNE_TAC_terms_2026-10-12.html`. Оригиналы, замороженные snapshots и отчёты с текстом литературы остаются локальными и не входят в Git. Свежий clone этих файлов не содержит.

Повторная генерация по сохранённым локальным входам в **новые** файлы:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_terms --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage06/profiles_final.json --boundary-review data/experiments/tac/20261012_stage06/boundary_review_final.json --output output/tac_readme_replay/terms.json
.\.venv\Scripts\python.exe -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage06/profiles_final.json --metadata data/experiments/tac/20261012_stage06/metadata_final.json --boundary-review data/experiments/tac/20261012_stage06/boundary_review_final.json --terms output/tac_readme_replay/terms.json --output output/tac_readme_replay/review.html --source-root .
```

Скрипты отказываются перезаписывать существующие результаты. Sidecars связываются с snapshot/profiles через hashes и точные source spans. Проверка целостности не подтверждает научное решение рецензента. Полные рецепты и ограничения — в отчётах stages 05–07, перечисленных выше.

## Проверки и evaluation

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest -q
```

На рабочей копии 13 октября 2026: **851 passed, 1 warning**, `ruff check` прошёл, `mypy app` — без ошибок в 84 source files. Warning — существующий `StarletteDeprecationWarning` об использовании httpx с Starlette TestClient. Полный pytest выполнен вне sandbox с новым `--basetemp` после задержки sandbox запуска; прерванному запуску успешный результат не приписывается. Эти проверки не заменяют live integration, независимый научный review или проверку установки в чистом окружении.

Evaluation на собственной настроенной БД и индексе:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10
.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --top-k 10 --method hybrid --check-thresholds
.\.venv\Scripts\python.exe -m app.evaluation.cli answers docs/evaluation_questions.yaml --top-k 5 --method hybrid
```

Answer evaluation использует настроенный provider. Новые live retrieval/model benchmarks при актуализации README не запускались. Данные development audits и агентские reference agreements нельзя выдавать за независимый gold.

## Навигация по репозиторию

| Путь | Назначение |
| --- | --- |
| `app/main.py`, `app/ui.py` | FastAPI и локальный HTML UI |
| `app/ingestion/`, `app/extraction/`, `app/chunking/` | PDF, текст/OCR и source-linked chunks |
| `app/library/`, `app/workers/` | Постоянные библиотеки и фоновые задачи |
| `app/retrieval/`, `app/generation/`, `app/evaluation/` | Поиск, ответы и evaluation |
| `app/facts/`, `app/records/` | Числовые кандидаты и experimental record harness |
| `scripts/tac_*.py` | Изолированные TAC/metadata/Terms эксперименты |
| `alembic/`, `tests/` | Миграции и тесты |
| `docs/`, `handoffs/` | Контракты, планы, отчёты и материалы передачи контекста |
| `presentations/` | Концепция проекта и презентации; не runtime приложения |

Границы научных утверждений и правила разработки: [AGENTS.md](AGENTS.md). Контракт experimental records: [experimental_record_contract.md](docs/records/experimental_record_contract.md). Локальные runtime logs, corpus exports в handoff-пакетах, содержащие их ZIP, промежуточные сборки и renders исключены из Git; исходники и готовые презентационные материалы сохраняются отдельно от приватного корпуса. Исторические handoff manifests описывают полные локальные пакеты, включая исключённые evidence/archives; clone не воспроизводит эти пакеты целиком. `presentations/ariadne-box-site/` — отдельный вложенный Git-репозиторий статической страницы, исключённый из Git ARIADNE.
