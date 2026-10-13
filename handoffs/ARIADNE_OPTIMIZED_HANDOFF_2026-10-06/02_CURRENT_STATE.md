# Реальное состояние
Дата фиксации: 2026-10-06.

## Подтверждённый задел по сохранённому аудиту
PDF ingestion, OCR-инструменты, PostgreSQL, хранение страниц и текстовых слоёв, deterministic chunks, exact/semantic/hybrid retrieval, provenance, ответы через OpenAI API, rule-based численные кандидаты, диагностика и журнал экспертных решений.

Reranking эвристический; обученный нейронный reranker не подтверждён. Численный кандидат не равен полной экспериментальной записи. Значения confidence 0.80/0.70/0.60 — фиксированные эвристики типа фрагмента, не откалиброванная вероятность правильности.

## Ранее выполненные проверки 06.10.2026
- pytest: 595 passed, 1 warning, 9.72 s.
- Ruff app/tests/scripts: All checks passed.
- mypy app: no issues found in 74 source files.
- doctor: перечисленные категории PASS.
- БД: 33 статьи, 493 страницы, 619 chunks, 814 текстовых слоёв.
- Hybrid extended retrieval: 46/46, article Recall@10=1.0, MRR=0.8912280701754386, threshold_failures=[].
- Это development/regression набор, не новый независимый holdout.
- Внешняя генерация ответов в этом аудите не запускалась.
- Первый retrieval-запуск встретил WinError 10013; повторный запуск с разрешением вне sandbox завершился успешно, загрузив embedding-модель. Полная автономная установка этим не доказана.
- Warning Starlette/httpx сохранён; зависимости ради аудита не менялись.

При создании архива эти проверки НЕ повторялись. Полные результаты и команды: materials/ariadne_readiness_audit_2026-10-06.md.

## Осмотр генерации в поздней части разговора
app/generation/providers.py содержит ExtractiveAnswerProvider и OpenAIAnswerProvider; последний отправляет /chat/completions с json_schema. Это задел для проверки OpenAI-совместимого локального сервера, но локальная конфигурация end-to-end не испытана. Наличие ExtractiveAnswerProvider не подтверждает поддерживаемый runtime режим извлекающего провайдера.

## Не подтверждено
Полная Scientific Record, научная приёмка численных записей и ответов, восстановление таблиц в общем случае, чистая установка, offline полный workflow, backup/restore, большие корпуса, сетевой доступ и изоляция, серийная поставка, лицензии всего комплекта.

## Рабочая копия
Изменены README.md, app/facts/extraction.py, app/main.py, app/ui.py, docs/roadmap.md, tests/unit/test_structured_facts.py. Есть многочисленные untracked материалы и review-скрипты. При упаковке git status повторно показал изменения и предупреждения доступа к старым tmp/pytest каталогам. Архив не сохраняет весь этот код; нужен отдельный осознанный snapshot для воспроизведения реализации.

