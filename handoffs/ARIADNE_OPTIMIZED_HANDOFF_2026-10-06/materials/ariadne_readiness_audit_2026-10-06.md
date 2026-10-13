# ARIADNE: результаты проверки готовности 06.10.2026

## Объект и границы

Проверялась текущая рабочая копия D:\Nafion-RAG, а не только Git HEAD bbffc25. До этой работы уже изменены README.md, app/facts/extraction.py, app/main.py, app/ui.py, docs/roadmap.md и tests/unit/test_structured_facts.py; есть многочисленные untracked материалы. Эти изменения не откатывались и не коммитились.

Проверены AGENTS.md, README, roadmap, architecture, operations, историческая интеграционная приёмка, часть ingestion, diagnostics, retrieval, generation, facts, review и моделей БД. Это целевой аудит осуществимости, не полный аудит каждой строки, безопасности или лицензий.

## Выполненные команды

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m app.ingestion.cli doctor
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-report
.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --top-k 10 --method hybrid --check-thresholds
```

Последняя команда сначала завершилась ошибкой `ConnectError: [WinError 10013]` при обращении через httpx. Повторный запуск вне sandbox был запрошен через штатный механизм разрешений и успешно завершился. Загружались файлы embedding-модели; появлялись предупреждения HF об отсутствии токена и недоступности symlinks. Не делать вывод, что установка уже полностью автономна: модель оказалась необходима из внешнего cache/download пути.

## Результаты

| Проверка | Фактический результат | Что доказывает |
|---|---|---|
| pytest | 595 passed, 1 warning in 9.72s; exit 0 | Текущий набор тестов прошёл |
| Ruff | All checks passed; exit 0 | Проверены app/tests/scripts |
| mypy | Success: no issues found in 74 source files; exit 0 | Проверка типов текущих исходников |
| doctor | Все перечисленные диагностические категории PASS; exit 0 | Подключение БД, миграции, доступность файлов и OCR-инструментов, конфигурация |
| corpus-report | 33 статьи, 493 страницы, 619 chunks, 814 текстовых слоёв; exit 0 | Текущее число записей и наличие файлов |
| retrieval-extended hybrid | 46/46; threshold_failures=[]; exit 0 | Текущий regression/development набор с действующими порогами |

pytest warning:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

Предупреждение сохранено; зависимости ради этого аудита не менялись.

doctor:

- PostgreSQL reachable;
- migration head: 0005_library_sources, совпадает с ожидаемым;
- data root и upload storage доступны для записи;
- ingestion/text-quality настройки допустимы;
- vector index states: 2 ready, 0 stale, 0 failed;
- corpus files: 33 статьи, файлы присутствуют;
- OCRmyPDF найден;
- Tesseract eng/rus доступны;
- Ghostscript найден.

doctor проверяет состояние и инструменты; фактический новый OCR-прогон или аварийное восстановление worker этим не выполнены. Проба записи doctor и новый corpus-report создают служебные артефакты; исходные PDF не модифицировались.

corpus-report: 25 статей с DOI, 8 без DOI; missing_original_files=0, missing_ocr_files=0. Это не проверка правильности DOI и метаданных.

Свежий retrieval:

- total=46, answerable=38, unanswerable=8;
- article Recall@10=1.0;
- chunk Recall@10=1.0 для размеченных chunk targets;
- article Precision@10=0.5763157894736842;
- MRR=0.8912280701754386;
- nDCG@10=0.8479509621981134;
- top_1_passed=31;
- unanswerable_passed=8, false_answerable=0;
- evidence_trace_complete=true;
- p50=1748.4265 ms, p95=3140.3688 ms — наблюдения этого прогона, не нагрузочная гарантия;
- язык ru: MRR=0.7151515151515151, top_1_passed=6/11; en: MRR=0.9629629629629629, top_1_passed=25/27 answerable;
- threshold_failures=[].

Пороги и вопросы не менялись. Данные оценки допуска ответа относятся к существующему механизму evidence adequacy, а не к независимой научной проверке сгенерированного ответа. Внешняя генерация ответов не запускалась. Набор уже использовался в разработке; это не новый независимый holdout.

## Созданные машинные отчёты

- [corpus report](../data/exports/corpus_report_20261006T052446Z.json)
- [hybrid retrieval report](../data/exports/retrieval_eval_extended_hybrid_20261006T052657Z.json)

Время в именах отчётов — UTC, выставлено существующим приложением. Пользовательская дата аудита — 6 октября 2026, Asia/Yekaterinburg.

## Основные выводы по исходникам

1. Semantic и hybrid реализованы; их существование не приходится выводить только из README.
2. Reranking использует эвристические признаки; нейронный reranker этим аудитом не подтверждён.
3. Runtime answer provider поддерживает OpenAI. Локальный extractive provider используется в части проверок, но build_answer_provider не предоставляет его как поддерживаемую конфигурацию runtime.
4. Численный extractor — rule_based_numeric_v1, cap=12. Он формирует кандидаты числа/единицы, не полную экспериментальную запись.
5. Confidence фиксирован по типу chunk: 0.80/0.70/0.60. Вероятностная калибровка не установлена.
6. Есть review UI, хешированные immutable snapshots и отдельный журнал решений. Полезный задел для экспертного процесса; научная приёмка всей выдачи не выполнена.
7. Схема нынешнего кандидата не представляет полную связанную цепочку material/property/conditions/method.
8. Исторические аудиты указывают на открытые проблемы approximations, bounds, role assignment и разных экспериментов с одинаковыми числами. Старые количества очередей не обновлялись в этом аудите.
9. Lockfile, CI и лицензия не были установлены как готовые компоненты в просмотренном составе; поиск по всему дереву встретил access denied в старых tmp/pytest каталогах. Поэтому это задача дополнительной проверки комплекта поставки, не категорическое заключение об отсутствии во всех возможных местах.

## Ограничения и приоритеты

Не проверены: новый independent gold, полные записи, реальные клиентские задачи, текущий UI в браузере, новый OCR на реальных сканах, offline полный pipeline, чистая установка, backup/restore, нагрузка, авторизация для сетевой поставки и лицензии всех компонентов.

Первый приоритет — воспроизводимая версия текущего задела и короткий целевой эксперимент на 10–15 публикациях. Затем полная запись, экспертный review и измерение трудоёмкости. Тысяча документов, графики и аппаратная поставка не должны вытеснять эти задачи.

Changed: только аналитические документы и generated audit reports; исходники и БД-факты не менялись.

Tests run: перечислены выше с результатами и первоначальной ошибкой retrieval.

Limitations: инженерные проверки не заменяют научную приёмку и продуктовый пилот.

Verdict: технический задел пригоден для узкого продолжения; автоматическая научная верификация и промышленная готовность не доказаны.
