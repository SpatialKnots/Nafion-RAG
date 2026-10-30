# ARIADNE: проверяемое представление ответа

30 октября 2026 года, Asia/Yekaterinburg. Итерация 3
[плана качества ответов](answer_quality_plan_2026-10-30.md).
Версия: `answer_presentation_v0.1`.

Changed:

- `app/ui.py`: в основном ответе и рядом с каждым утверждением citation IDs
  заменены читаемой подписью «название работы — с. начало-конец». PDF page URL
  остаётся зарегистрированным. Неизвестные title/pages отмечаются явно;
  неизвестный ID не превращается в вымышленную ссылку. Internal IDs и прежняя
  таблица диагностики сохранены.
- UI-запрос передаёт уже существующий `trace_observer` в answer service.
  Новый `app/generation/presentation.py` сохраняет контексты только в пределах
  этого запроса: article/chunk/page identity, исходный текст retrieval result,
  text layer и raw generation Evidence. Дополнительного поиска или чтения БД
  для восстановления удобного фрагмента нет. При несовпадении identity контекст
  не прикрепляется к чужой citation. Между запросами контексты не кэшируются.
- Каждое утверждение получает раскрываемый полный исходный фрагмент без
  обрезания по 520 символам. Это точный raw chunk из той же трассы, со слоем
  original/OCR; наличие текста не объявляется подтверждением entailment.
  Полный текст прокручивается, а не удаляется. Если trace отсутствует,
  показан только display excerpt с явной отметкой ограничения.
- Детерминированные `table_derived` summaries отдельно обозначаются как
  вычисление системы, не цитата из PDF. Исходный chunk и generation Evidence
  не смешиваются. Raw generation Evidence — вход provider formatter, не
  утверждение о побайтовом равенстве отформатированному HTTP message:
  существующее whitespace cleaning провайдера сохранено.
- Полный ответ виден первым, повторяющиеся карточки утверждений/контекстов
  раскрываются отдельно. Source cards и служебная таблица остаются доступны.
  HTML source/claim text экранируется. Дубликат citation ID в одном claim
  не дублирует контекст.
- `app/generation/gigachat.py`: добавлена versioned инструкция представления
  в обоих styles. Модель должна начать с прямого вывода и его scope, далее
  объяснить существенные условия/определение/единицы, различать наблюдение,
  регрессионный параметр и арифметику системы, указать ограничения. Цитаты,
  если используются, должны быть точными; модель не создаёт URL/авторов.
  Объём следует evidence, без padding и фиксированной длины. Это инструкция,
  а не semantic validator; её воздействие на новые ответы не проверено.
- JSON API/native answer schema, claim/citation fields, scientific system
  prompt, strict validation, retrieval, thresholds, max_tokens=1200 и provider
  GigaChat-2-Max не менялись. UI получает расширенный контекст через локальную
  переменную, без новых public API fields. Новых model/OAuth calls нет.

Проверка на сохранённых ответах:

Три successful runtime случая 29 октября: вопрос пользователя о набухании,
условия измерения проводимости, сравнение критериев равновесия. Для каждого
сохранены отдельные before/after HTML и исходный API result. Изменено только
представление; содержимое старых claims и статусы не исправлялись.

В случае набухания display E1 не содержит 1.54, а исходный chunk той же
generation trace содержит 1.54 и пояснение о регрессии. Теперь этот текст
можно раскрыть непосредственно у утверждения. Никакие дополнительные страницы
с 1.8 не подмешаны в его исторический контекст. Общий вывод 1.54 по-прежнему
сохранён как фактически выданный ошибочный максимум, а не исправленный ответ.

Для трёх случаев построены **три неотправленных request candidates**.
Настоящий adapter с полностью заменённым `_post` получил только локальный
OAuth placeholder и сохранённый native response. Три прежних native contents
разобрались в те же claims. Candidate отличается от исходного request только
`messages[1].content`; response schema и остальные request fields совпадают.
Это replay прежнего вывода, не новое поведение модели и не OAuth exchange.
Слоты не резервировались; кандидаты не получают разрешения на отправку.

Tests run:

- **174 passed**, JUnit `output/answer_presentation_tests_20261030_v03.xml`:
  **20 новых** presentation controls плюс прежние UI/generation/GigaChat tests.
  Одна существующая Starlette/httpx deprecation warning. Проверены title/page
  links, полный текст за прежней границей excerpt, exact raw-text escaping,
  несколько работ, unknown metadata, identity mismatch, repeated IDs,
  derived/raw separation, request-local observer и оба prompt styles.
- Дополнительно **15 API tests passed**,
  `output/answer_presentation_api_20261030_v01.xml`, включая answer/search,
  PDF/page/context endpoints на fake services. Эти 15 не входят в 174.
  Предыдущие 146 passed перекрываются с 174 и не суммируются.
- Ruff изменённых module/UI/provider, новых tests/review/QA scripts passed.
  `mypy app`: **181 source files**, no issues. `git diff --check` passed
  с существующими LF/CRLF warnings. Полный pytest suite не запускался.
- В initial sandbox run UI TestClient завис после первых presentation tests.
  Конкретные PID 10700/28044 определены через CIM вне sandbox и остановлены;
  завершённый JUnit/успех этого прогона не заявляется. Тот же affected suite
  вне sandbox завершился. Точная причина зависания не установлена.
- Сначала mypy обнаружил nullable citation narrowing; исправлено до финального
  успеха. Initial Ruff reviewer script отметил unused import и loop closures;
  исправлены до финального экспорта. Ошибки перечислены в отдельном журнале.
- Три frozen native replays и immutable API dictionaries совпали. Проверены
  original PDF hashes и свежим text extraction **19 уникальных страниц / 5 работ**.
  Статическая QA проверила 12 привязок claim/source: каждый полный фрагмент
  в HTML побайтово совпадает с соответствующим raw trace text после HTML decode.
- Финальная TAC-таблица содержит **5 работ** из полного scope трёх answers,
  восемь согласованных колонок и **14** существующих index links. Сохранены все
  архивные варианты метаданных; неизвестные Abstract/Conclusions/Terms явно
  отмечены. Missing year не восстановлен из title. Ранние HTML версии сохранены.
- **Браузерная QA через cua_repl выполнена.** На swelling preview проверены
  читаемая ссылка «Диссертация Чернюк С.Д. — с.96-97», раскрытие claim и полного
  исходного текста с регрессией 1.54/наблюдением 1.536. Снимок показан инструментом;
  отдельный файл screenshot не сохранён. На final review_v03 таблице видны
  названия; фильтр `Istomina` оставляет 1 row и скрывает 4. Исходный вариант
  таблицы скрывал titles за generic details; финальный renderer это исправляет.
- Sandbox static server не отвечал localhost. После остановки его точных
  процессов и запуска preview вне sandbox страницы загрузились. Попытка открыть
  автоматически созданный data: error page была отклонена URL policy;
  ограничения не менялись, использована новая разрешённая localhost-вкладка.
  Preview привязан только к 127.0.0.1; вкладка и временный сервер затем закрыты.
  Это просмотр статических файлов, не live /answer, provider или DB run.

Артефакты:

- [Финальный обзор до/после](../output/answer_presentation_20261030/review_v03/review.html).
- [Набухание: новое представление старого ответа](../output/answer_presentation_20261030/review_v03/swelling_after.html).
- `before/` сохраняет точные app/UI/provider/test copies до этой итерации.
- `review_v01`, `review_v02` сохраняют предыдущие экспорты; `review_v03` — финальный.
  `*_runtime.html` содержит реальные application URL; локальные review copies
  заменяют только зарегистрированные PDF href на file URLs. Другие app links
  требуют работающий сервер. В браузере открытие самих PDF file links не проверено;
  статически проверены существование файлов и правильность page fragments.
- `report.json`: source bindings, unchanged API/native claims, prompt changes,
  неотправленные кандидаты, source/context inventory и ограничения.
- `source_snapshot/`: код/тесты/протокол/основной JUnit; `qa_v01.py/json` и
  `development_failures.json` — отдельные checks и summaries реальных ошибок.

Воспроизведение в новый output (без БД/провайдера):

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.run_answer_presentation_review --output output/answer_presentation_20261030/review_replay_new
```

Исторические manifests и request bytes не переписаны под новый prompt.
Предыдущие stages 1/2 привязывались к старым app/UI/provider hashes: проверка
их current-checkout bindings теперь должна обнаруживать объявленный drift.
Историческое воспроизведение требует frozen snapshots, а не обхода guards.

Limitations:

Реализованы и проверены представление/доступ к исходному фрагменту и новая
prompt guidance. Новые содержательные model answers не получены и не оценены;
модель ещё может не выполнить инструкцию. Полный source fragment не является
автоматически подтверждённой короткой supporting quote или scientific entailment.
Авторов/год нельзя восстановить в citation из отсутствующих там API fields;
renderer использует доступные title/pages и не делает новых metadata queries.
API plain answer string сохраняет internal IDs для клиентов; human labels
добавляет UI из citation metadata. Mobile layout отдельно не проверен.

Научные ошибки, общий максимум, source coverage/ranking и cache/ORM repeated
requests этим этапом не исправлены. Production server не запускался и не
перезапускался. Live end-to-end новый prompt не проверялся. Внешние model/OAuth
requests, DB operations и новые slots — 0; старые бюджеты закрыты.

Verdict:

Пункт 3 выполнен в объёме реализации и offline/source/browser проверки
представления; эффективность новой генерации остаётся непроверенной.
**75% работ плана (3/4)**, не научная точность/готовность.
Пункт 4 открыт. Пользователь сообщил 30 октября: «Я подготовлю новые вопросы».
Их не следует заменять собственными повторными аннотациями ассистента или
считать автоматически разрешением на новые live calls.
