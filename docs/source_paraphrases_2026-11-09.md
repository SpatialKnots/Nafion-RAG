# Пункт 4: ограниченные перефразировки источников

Дата: 9 ноября 2026, Asia/Yekaterinburg.

Changed:

Пользователь разрешил начать реализацию ранее запланированного пункта 4.
Выполнен первый ограниченный scope: три английские source roles двух
существующих семейств Q02/Q04. Новые формы распознаются и в source coverage,
и при повторном извлечении полей факта:

- обработка Li-фольги газообразным O2: `were treated with`, диапазон
  `from ... to ...` либо `between ... and ...`, температура и время;
- электролит: `electrolyte containing ... M LiPF6 in EC/DEC (... by volume)`
  либо `volume ratio`, со строгим различением M/m;
- выдержка: `An isothermal treatment lasting ... days was performed/conducted
  at ... ◦C. This treatment did not change the measured W values.`

Это конечные альтернативы, а не свободная перефразировка моделью. Вопросы,
expected IDs, авторы, страницы и ожидаемые значения в новую grammar не входят.
Все числа извлекаются из исходного текста. Химические обозначения и W сохраняют
точный регистр; raw spelling и units не исправляются.

Два существующих runtime файла изменены: `app/generation/answer_fidelity.py`
и `app/generation/fact_recipes.py`. Новый общий модуль:
`app/generation/source_paraphrases.py`, версия `source_paraphrases_v0.2`.
Новые role anchors получают grammar_version; metadata содержит
`source_paraphrases.version/roles` только при фактической активации.
На старых конструкциях metadata остаётся прежней. Новых top-level public
fields, DB/schema/index/PDF изменений нет.

F-ID, полная обязательная выборка, exact citation binding, серверный пересчёт
чисел/полей/русского текста и explicit unknowns сохранены. Выдержка остаётся
наблюдением; гипотеза необратимости не становится доказанным фактом.
Прежние source patterns и guards сохраняют своё поведение. Retrieval,
scores/order, gate thresholds, context-completion budget и пункт 3 не менялись.

Исходное состояние зафиксировано до app edits: 191 Python binding плюс YAML,
протокол, script snapshot, пять полных текущих traces/native bodies и 76 старых
full-service baselines. Снимок: `output/source_paraphrases_20261109/freeze_v01`.
Точный runtime drift к нему проверяется в report: только два старых app файла
и один новый модуль. Не было git reset/clean/commit; прежние пользовательские
uncommitted файлы и outputs сохранены.

Tests run:

- Финальный затронутый набор: **673 passed** (581 прежний +92 новых),
  failures/errors/skips0. Запущен вне песочницы с external-network audit guard;
  denials0. Starlette/httpx deprecation warning сохранён.
- Основной набор source controls: 3 неизменённых реальных source windows,
  9 искусственных положительных перефразировок и 45 искусственных negatives.
  Исходные 9 variants до патча давали false refusals; v0.2 даёт полный bundle
  на всех9. Все45 negatives остаются неполными/unresolved. Это constructed
  behavior controls, не точность на независимой литературе.
- Новые tests дополнительно проверяют изменяемые числа, конфликтующие значения,
  разные работы, равенство фактических полей/арифметики/русского текста
  эквивалентным originals, raw bindings и tampering полей/summary/citation/F-ID.
- Восемь новых actual service/ASGI controls: два семейства × complete/abstention
  × прямой service/HTTP. Четыре HTTP200 проверки, два synthetic answered и два
  synthetic abstentions; direct service проверен отдельно. Все ответы синтетические,
  не реальные новые результаты модели. В первых неудачных direct controls
  адаптер отбрасывал часть исходной выдачи; исправлен только test adapter.
- Три записанных frozen-channel прогона по81 фактическому service execution:
  freeze, compare_v01 и окончательный compare_v02 — всего243. Пять текущих
  полных результатов и 76 прежних полных результатов v0.2 равны pre-edit baseline.
  Все пять native bodies v0.2 байт-в-байт прежние, Q03 сохранён.
- Для девяти положительных variants сформированы действительные native bodies
  через provider с подменённой transport boundary. После декодирования
  source-bound records точно равны server prompt records; каждая support quote
  присутствует в соответствующем искусственно изменённом raw parent.
  Это unsent native preparations из constructed fact bundles, не production
  retrieval по изменённым статьям и не ответы реальной модели.
- Проверены33 SHA исходных PDFs,10 свежих reference pages и19 raw spans.
  HTML QA:5 case sections,33 TAC строки/eight columns/существующие PDF ссылки.
  Диагностика, исходные цитаты и57 source controls доступны раскрывающимися блоками.
- Ruff восьми изменённых/новых implementation/test/driver файлов и полный
  mypy `app`:192 source files — passed. Первый Ruff поймал две длинные строки
  reviewer script; переносы исправлены, исходный lint log сохранён.

Сохранённые неудачи и отдельная версия v0.2:

1. `controls_before.xml`:24 failed/39 passed. Девять false refusals и15
   зависимых проверок tampering не могли стартовать без полного bundle.
2. `controls_after_v01.xml`:174 passed; затем полный `tests_affected_v01.xml`:
   664 passed. Первоначальные48 source controls недостаточно покрывали риски.
3. Отдельный post-measurement adverse probe: `adverse_v01.xml`,9 failed.
   Новые alternatives принимали явную отсылку к предыдущей работе/другому
   образцу и неправильный регистр Li/LiPF6/W. Это реальные недостатки v0.1,
   а не ошибка evaluator. v0.1 и compare_v01 сохранены.
4. До исправления записан amendment v0.2 и расширен frozen control set.
   Только новые alternatives получили guards previous/prior work, reported that,
   another/other/different sample/material/experiment и точный регистр формул/W.
   Девять новых отрицательных проверок теперь проходят; positives сохранены.
5. Sandbox `controls_after_v02` завис при TestClient, финальный JUnit не создан,
   pass не назначен. Read-only CIM сначала запрещён песочницей; разрешённый
   host query установил PID5948/19340. Остановлены только эти процессы.
   Офлайн-прогоны с сетевым guard вне песочницы завершились. Причина hang
   не установлена. `service_adapter_v02.xml` отдельно сохраняет два успешных
   direct controls после исправления test adapter.

Limitations:

Три source roles, две семьи и искусственные перефразировки ранее раскрытых
примеров. Это первый bounded scope пункта 4; гибкость остальных grammars и
обобщение на новую литературу не подтверждены. На исходных пяти вопросах
изменения и измеренного прироста нет; старые76 не активируют новую grammar,
поэтому подтверждают регрессию, но не её смысловую правильность.

Finite prefix guards консервативны и не решают общую scientific ownership.
Длинные/сложные конструкции, другая терминология, другой layout и иные языки
могут оставаться unresolved. Нельзя объявлять отсутствие роли в parser
отсутствием сведений в статье. Значения/units/status не переносятся автоматически.

Новые real model/OAuth calls и slots:0. Все прежние live scopes закрыты.
Контекст и native inputs пяти реальных вопросов не изменились, поэтому новая
fresh DB/rollback подготовка не выполнялась и не выдаётся за выполненную.
Browser, новая PDF visual QA, full suite, cache-ORM/concurrency/deployment и
независимая научная оценка не выполнены в этой итерации.

Verdict:

Ограниченное расширение распознавания реализовано: девять объявленных
эквивалентных перефразировок перестали приводить к неполному fact bundle,
а заданные отрицательные и tampering controls проходят. На прежних запросах
контекст, результаты и native bytes сохранены. Научная приёмка, общий scope
пункта 4 и общий прежний прогресс75% этим результатом не закрываются.

Следующее расширение выбирать по новым реальным source excerpts после фиксации
протокола и positive/negative controls. Дополнительный live-тест возможен только
как отдельный новый scope, без автоматического использования старого allowance.

- [HTML-обзор](../output/source_paraphrases_20261109/review_v01/review.html)
- [Проверки HTML](../output/source_paraphrases_20261109/review_v01/qa.json)
- [Полный report](../output/source_paraphrases_20261109/review_v01/report.json)
- [Протокол v0.1](records/source_paraphrases_protocol_2026-11-09_v0.1.md)
- [Amendment v0.2](records/source_paraphrases_amendment_2026-11-09_v0.2.md)
- [Предыдущий план пункта 4](next_session_2026-11-07.md)
