# Состояние реализации и доказательства

**Версия:** 1.1. **Дата:** 6 октября 2026 года. **Часовой пояс:** Asia/Yekaterinburg.


## Источник
Сохранённый аудит 06.10.2026, повторное чтение README/providers и документов в этой сессии. При подготовке v1.1 программные тесты, БД-аудит и оборудование не запускались заново.

Локальный репозиторий: D:\\Nafion-RAG. Исходный handoff указывает https://github.com/SpatialKnots/Nafion-RAG . Рабочая копия шире HEAD bbffc25; есть пользовательские изменённые и untracked файлы. Этот архив не сохраняет всю рабочую копию.

## Исторический аудит
- pytest: 595 passed, 1 warning, 9.72 s.
- Ruff: All checks passed.
- mypy: no issues found in 74 source files.
- doctor: перечисленные категории PASS.
- 33 статьи, 493 страницы, 619 chunks, 814 текстовых слоёв.
- Hybrid extended retrieval: 46/46, Recall@10=1.0, MRR=0.8912280701754386, threshold_failures=[].
- Dataset использовался в разработке, это не untouched independent test.
- Внешняя генерация не выполнялась.
- Первый retrieval столкнулся с WinError 10013; разрешённый повторный прогон завершился, embedding-модель загружалась. Offline этим не доказан.

Подробный аудит и машинные отчёты находятся в evidence/. Временные метрики сохранённого прогона не распространяются на новую станцию.

## Что реализовано
Ingestion/text/OCR tools, PostgreSQL, source layers/chunks, exact/semantic/hybrid retrieval, source navigation, численные кандидаты и review-задел. Reranking эвристический, не подтверждён нейронный reranker. Confidence 0.80/0.70/0.60 — фиксированная эвристика.

OpenAIAnswerProvider отправляет /chat/completions с json_schema. Есть ExtractiveAnswerProvider; наличие класса не означает поддерживаемый runtime режим. Конкретный локальный OpenAI-compatible runtime и модель end-to-end не проверены.

## Целевой новый результат
Связанная Scientific Record, ограниченные checks, научный benchmark, экспертный workflow, локальный deployment и пилот. Схемы/миграции этой концепцией не внедряются.

## Не проверено
Научная корректность всей выдачи, general table parsing, clean install, restore, полноценный offline, большие корпуса, права сетевого доступа, лицензии полного комплекта, серийная поставка. Исходники и БД-факты при упаковке концепции не изменялись.

