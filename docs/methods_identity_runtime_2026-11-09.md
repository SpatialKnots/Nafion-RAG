# ARIADNE: opt-in связь через Methods

9 ноября 2026, Asia/Yekaterinburg.

Changed:

Добавлена конечная политика `ordered_methods_identity_v0.2`. Настройка
`RAG_METHODS_IDENTITY_POLICY` по умолчанию `disabled`; `.env` не менялся.
Включение — явный выбор этой версии. Неизвестная версия настройки отклоняется.

Один новый модуль `app/generation/methods_identity.py` и четыре существующих
файла: config, answer_facts, service, ui. Нет изменений retrieval/filter/top_k/
context budget, DB/schema/PDF/index, extraction/classifier, общих source grammars
или публичных верхнеуровневых полей API. Независимая оценка не выполнена.

Новый путь выбирается только при включённой политике, поддерживаемом provider,
русском ответе, распознанном запросе composition/cycling с разрешённой авторской
ссылкой и трёх исходных родителях, содержащих Methods и Conclusion. Проверяется
одна работа, один зарегистрированный text_layer, уникальные chunk/citation IDs
и границы страниц. Abstract/Conclusion должны оставаться main_text. Methods
может сохранить исходный main_text/formula_block/figure_caption; роль внутреннего
Material Preparation span проверяется отдельно. Caption/table внутри этого span
оставляет связь unresolved. Ничего не переклассифицируется и не записывается назад.

Граф заново разбирает точные определения aliases, соответственно сопоставленные
списки solvent/ratio/base-code, отдельный список additive-dose/product-code,
literal target в Conclusion и весь состав Abstract. Проверяются соль, концентрации,
все растворители, объёмное соотношение, добавка/доза и источник reported total.
Цифры из кода не декодируются; структурные дефисы перед newline сохраняются.
CE Abstract и Conclusion должен совпадать по cell/value/unit/conditions; capacity
остаётся привязанной к Abstract. Условия других операций не переносятся.

Сопоставление списка доз и списка продуктов **по порядку — явное допущение этой
политики**, не универсальное semantic entailment/scientific ownership. Оно
отображается в русском ответе и UI. В request-local metadata сохраняется весь
граф; при выборе F1..F3 он полностью пересчитывается из всех трёх raw родителей,
включая definition-only Methods. Смена факта, raw текста, ссылки, слоя, типа,
границы, policy или потеря родителя отклоняется. Новая синтетическая полная
сборка сохраняет все три источника в final citations, включая Methods.

Модели предлагаются прежние ASCII F-ID и source-bound факты; дополнительно
передаются семь exact witness quotes с provenance. Сервер сам формирует русский
текст и финальные citations. Для этой версии применяется её полный графовый
валидатор; старый one-quotation/one-citation validator не умеет представлять
definition-only parent и проверенные множественные ссылки. Остальные пути
сохраняют старые проверки. Required-concept/relation veto остаются до provider.
Неудача выбранного графа приводит к abstention, без тихого fallback.

**Уточнение исходной гипотезы:** полный трёх-parent пакет реального Lin2020
уже проходит старый фактографический путь через Abstract. Старые сообщения об
unresolved относятся к отдельной функции source_role_assembly_v0.1, а не
доказывают отказ всего `/answer` на этом пакете. Новая политика может явно
заменить complete legacy bundle на этом ограниченном входе; disabled/default,
другие complete bundles, English и Extractive сохраняются. На реальном примере
получена проверяемая цепочка с дополнительными definitions/citations, но **новый
ответ или снижение отказов не установлены**. Стандартные пять вопросов не
содержат выбранного трёх-parent пакета; activation новой версии там и в 76
старых случаях — ноль. Самостоятельного изменения retrieval не было.

Tests run:

- До runtime edits: freeze_v01 сохранил 193 app Python files/YAML, протокол и
  исходные controls; 81 фактический offline service run и пять native bodies
  воспроизвели предыдущий baseline.
- Финальный затронутый набор: **883 passed**, из них 87 новых policy tests,
  сохранены JUnit и scope; external-network denials в финальном run — 0.
  Это затронутый набор, не весь repository test suite. Starlette предупреждает
  о deprecated httpx/TestClient integration; зависимости не менялись.
- Ruff десяти окончательных app/test/script файлов passed. Полный mypy app:
  **194 source files**, success. `git diff --check` passed с обычными предупреждениями
  Git о будущей LF→CRLF нормализации.
- Два финальных frozen-channel прогона: **162 actual service executions**,
  disabled и v0.2 enabled. Во всех 81 случаях полный результат идентичен
  baseline, все пять native bodies каждого прогона побайтно идентичны. Новый
  граф там не активируется — это регрессия, не проверка его активной ветки.
  Дополнительный ранний enabled v0.1 run 81 сохранён отдельно; не считается
  проверкой финальной версии.
- 29 исходных controls: один exposed real positive, четыре constructed positives
  и 24 negatives; плюс scope/regions/status/complete-graph corruption controls
  в 87 новых тестах. Новые coherent values/opaque codes/joint permutations не
  являются независимым научным эталоном.
- Активный путь отдельно проверен actual service и ASGI с synthetic complete/
  abstain/invalid selection: HTTP 200/200/502. Model prose не использован. Проверены
  отказ до provider при провале выбранного графа и оба required-coverage veto.
- Из действительной новой service trace снят unsent native body **22688 bytes**,
  SHA256 `723bbf958df66144f6eb88fa3a44c43efd4b891885c98ccedfaa26ea9341396e`.
  Декодированные три fact records и семь witness quotes каждого проверены по raw
  источникам и фактическим request-local E IDs. Fake OAuth и transport boundary
  заменены; отправок и резервирования slots не было. Tokens/cost не измерялись.
- 33 original PDF hashes, 3 свежие страницы Lin PDF1/3/7, 53 raw-anchor observations
  /51 уникальный адрес прошли сверку по raw spans и свежим PDF в declared page
  ranges. Все три свежих рендера визуально просмотрены; копии сохранены в review.
- Статический HTML QA: 5 прежних case sections, 33 TAC works/eight columns,
  57 существующих PDF links. Сохранены оригинальный runtime UI fragment,
  3 claim cards и локальная копия с 10 явно сопоставленными runtime ссылками на
  исходные PDF. Только локальный обзор переназначает эти ссылки; приложение нет.

Сохранённые неудачные прогоны и поправки:

1. probe_v01: 71 passed/6 deselected. Новые adverse controls в probe_v02 дали
   3 false admissions для другого electrolyte/cell/system. Финальная отдельная
   v0.2 расширяет только свой guard и проверяет target→CE interval.
2. probe_v02 также выявил три fixture errors: отсутствующий synthetic provider
   для двух legacy-путей и отсутствующий max_claims для Extractive. Python guard
   заблокировал **две попытки DNS к OAuth до соединения**; scope сохраняет обе
   denials. Реальных OAuth exchanges/model POST не было. Исходники неудачной
   версии заморожены отдельно в adverse_v01. В финальном scope denials 0.
3. probe_v03 завис на sandbox ASGI; остановлены проверенные PID22552/16344.
   Тот же код вне sandbox в probe_v04 завершился 5failed/80passed: выявлена
   описанная выше неверная гипотеза о новом маршруте на complete real Abstract.
   Это не объявлено regression scientific failure.
4. probe_v05:4failed/83passed — definition-only parent не поддерживался generic
   quote validator; ASGI fixture не патчил реальный app.main.get_settings lookup.
   Исправлены новая integration branch и фикстура, без изменения API routes.
5. tests_v01:27failed/856passed — старые SimpleNamespace settings без нового
   поля. Добавлен совместимый disabled default; прежние tests не переписывались.
   tests_v02:883passed. Первые import/type/closure lint diagnostics также исправлены.
6. review_v01 сохранён после несовпадения witness citations: exporter ошибочно
   сравнивал старые diagnostic E IDs с новой нумерацией service. review_v02
   сопоставляет по неизменному chunk_id и проверяет actual service numbering.
   Native bytes и runtime не менялись. Вспомогательная проверка сначала указала
   неправильный уровень вложенного service/service directory; исправленный
   read-only подсчёт подтвердил activation0, оригиналы не менялись.
7. Визуальный HTML review через встроенный браузер **заблокирован политикой
   file:// URL**. Обход не выполнялся. Browser execution и layout HTML не
   подтверждены; статический QA и отдельный визуальный просмотр PDF состоялись.

Limitations:

Одна раскрытая работа и конечные source patterns; это не общий identity resolver,
не независимая научная проверка и не доказанная переносимость на новые статьи.
Снижение отказов/повышение accuracy/скорость проверки человеком не измерены.
Нет новых реальных model/OAuth calls, DB preparations, ingestion или deployment.
Свежая работа с БД, реальное поведение модели на новом prompt, browser layout,
cache/ORM, concurrency и полный repository suite остаются непроверенными.
Политика по умолчанию выключена. Прежние live scopes закрыты.

Verdict:

Минимальное ограниченное расширение реализовано и проверено offline. Новый
контракт собирает полный реальный пакет при явном выборе политики, сохраняет
тип Methods и exact definitions, а отказы/повреждения диагностирует. Новых
научных результатов и новых успешных live-ответов нет. Исходный план остаётся
**75% работ**, независимая оценка открыта.

Следующий отдельный шаг: карта требований/пробелов одного семейства на существующей
подготовке ответа. Она должна различать отсутствие source span, неподдержанную
грамматику и unresolved identity; новый retrieval action — только отдельным
измерением. Этот шаг не объявлен начатым и не требует нового model call.

- [HTML review](../output/methods_identity_runtime_20261109/review_v02/review.html)
- [Синтетический UI на реальных источниках](../output/methods_identity_runtime_20261109/review_v02/runtime_ui.html)
- [Полный report](../output/methods_identity_runtime_20261109/review_v02/report.json)
- [Протокол v0.1](records/methods_identity_runtime_protocol_2026-11-09_v0.1.md)
- [Amendment v0.2 и сохранённые ошибки](records/methods_identity_runtime_amendment_2026-11-09_v0.2.md)
