# Пункт 4: ограниченная сборка composition/capacity/CE

9 ноября 2026, Asia/Yekaterinburg.

Changed:

По разрешению пользователя реализована первая versioned source-role assembly
`source_role_assembly_v0.1`. Новый модуль `app/generation/source_role_assembly.py`
связывает composition, capacity retention и coulombic efficiency из отдельных
raw parents уже выбранного evidence. Связь требует явного одинакового маркера
`Electrolyte LABEL.` в начале соответствующего абзаца, а не только article_id,
концентрации или местоимения. Числа внутри LABEL не интерпретируются.

Ограничения входа: uniquely resolved author/year work, все названные авторы
в front matter, поддерживаемые query constraints, один article/source_type/
зарегистрированный text_layer. Composition находится в том же first-page
parent, который подтверждает автора. Обе requested cells точно совпадают
с владельцами capacity и CE. Все support spans роли должны находиться после
маркера в том же ограниченном4500-char paragraph; blank lines, следующий
marker или section heading закрывают область. Разные labels/значения/условия,
неполный source, отрицание/будущее/предположение/чужая работа дают unresolved.

Существующие recipes повторно вычисляют все поля, неизвестные условия и
эпистемический статус. Между ролями не переносятся числовые условия.
Повтор одинакового candidate в overlapping chunks не является независимым
подтверждением; разные кандидаты не выбираются по удобству.

В `answer_facts.py` добавлен отдельный assembly context только для новой ветви:
question/reference/layers, literal label и точные role/marker bindings.
Records имеют source_assembly version. При чтении весь graph пересобирается
из raw parents и сравнивается с сохранёнными records/context. Частичное удаление
manifest, parent, изменение поля/маркировки/версии/ссылки отклоняется. Отдельная
проверка raw parent binding сохраняется. Это не защита от произвольной подмены
всех доверенных серверных sources; регистрация источников остаётся отдельной границей.

В `service.py` новый конечный admission rule вызывается только при наличии
markers и неполном прежнем fact path. Старый полный путь приоритетен.
Extractive и English answer requests не входят в новую ветвь. Required
concepts/relations сохраняют veto; старый gate baseline и reason сохранены.
Неполный assembly сам не разрешает генерацию. Если ранее был допустим отдельный
полный quotation path, это прежнее разрешение не превращается в assembly admission.
Глобальные gate thresholds и retrieval не менялись.

F-ID/citation completeness, recomputation и source provenance сохранены.
В actual native prompt присутствуют и fact quotes, и точный marker quote.
UI показывает буквальную текстовую связь разделов и исходный marker рядом
с цитатами; транспортный JSON не выдаётся за PDF. В scientific ownership
по-прежнему false: literal label relation не является научной приёмкой.

Итого: три старых app файла изменены (`answer_facts.py`, `service.py`, `ui.py`),
один новый модуль. Нет DB/schema/PDF/index/public top-level/retrieval/filter/
top_k/context budget изменений. Старые uncommitted файлы и outputs сохранены;
commit/deployment не выполнялись.

Tests run:

- Перед app edits заморожены192 app Python files плюс YAML, протокол,
  snapshot/hashes и81 full-service/native baseline. `freeze_v01` сохранён.
-22 constructed controls: два complete outcomes (обычный и повтор идентичного
  parent),20 negatives. Контролируются label/cell/identity/units/статус,
  разные work/type/layer, missing marker/fields, paragraph break и ambiguity.
  Это искусственные проверки поведения, не новые опубликованные результаты.
- Неизменённый реальный Lin Abstract+Methods+Conclusion блокируется по
  `assembly_source_scope_unresolved`: Methods parent зарегистрирован как
  `figure_caption`, остальные как `main_text`. Классификация не исправлялась
  на лету. Отдельный real Abstract+Conclusion control без Methods блокируется
  `assembly_missing_explicit_role_composition`: прямого label в Abstract нет.
  Это два способа проверки одной раскрытой работы, не два независимых примера.
- Финально **763 tests passed** (713 предыдущих +50 новых), errors/failures/
  skips0; external-network audit guard denials0. Полный набор с ASGI запущен
  вне sandbox из-за ранее воспроизводившихся там TestClient hangs.
  Starlette/httpx deprecation warning сохранён.
- Шесть новых direct service/ASGI controls: complete/abstain/invalid F-ID,
  по два способа исполнения. Actual ASGI statuses200/200/502 соответственно.
  Все provider replies SYNTHETIC. Неполные required concepts/relations отдельно
  останавливают provider. Проверены приоритет legacy complete/English path,
  raw/F-ID/citation/context/marker/layer/reference/unknown-fields integrity,
  malformed payloads и отображение точных markers в UI.
- Три записанных frozen-channel прогона по81 actual service execution:
  freeze_v01, compare_v01 и итоговый compare_v02, всего243. Все5 current и76
  old полных результатов и5 actual native bodies неизменны. Новая ветвь на
  них не активируется, поэтому они подтверждают регрессию, не новое качество.
- Actual constructed native body сформирован provider на подменённой transport
  boundary, без отправки:7944 bytes,
  SHA256 `33ab45b8b7fe0f6dd250e0ffc0da091f4df7594c242ce12c85e2a3e157292263`.
  Три decoded F records, marker quotes и fact quotes точно соответствуют
  constructed raw parents. Параметры Max/1200/120s прежние. Это не модельный ответ.
- Review отдельно записывает три actual direct service executions на искусственном
  входе: русский source-bound ответ, abstention и GenerationOutputError для F999.
  Эти дополнительные исполнения не включены в243 frozen-channel счётчик.
-33 original PDF hashes проверены. Для реального контроля повторно прочитаны
  PDF1,3,7 Lin; raw parents точно равны frozen corpus. HTML QA:5 прежних case
  sections,33 TAC строки/eight columns/57 существующих PDF ссылок; constructed
  sources не привязаны к выдуманным PDF.
- Ruff девяти app/test/driver файлов и полный mypy app193 passed.

Сохранённые итерации и diagnostics:

1. `service_before.xml`:3 failed — до нового rule complete/abstain/invalid
   controls не достигали provider. Это ожидаемый pre-edit baseline.
2. `controls_after_v01.xml`:1 failed/30 passed/6 deselected. Конечный `\s*`
   marker regex поглощал paragraph break. Исправлен на ограниченный whitespace/
   один newline; исходный failure сохранён, criteria не менялись.
3. Первый Ruff выявил imports/длинную строку; reviewer Ruff отдельно поймал
   loop-variable binding в Synthetic adapter. Исправлены, исходные logs сохранены.
4. `tests_affected_v01.xml`:760 passed до UI marker display; v02:761 passed
   после UI. Затем добавлены две проверки различения реальных type/label
   блокировок; финальный v03:763 passed. Существующие assertions не удалялись.
5. `review_v01` сохранён. Final `review_v02` добавляет отдельный неизменённый
   Abstract+Conclusion assessment. В протокол дописана явно помеченная
   post-measurement assessment note, source/admission rules не изменены.

Limitations:

Complete assembly подтверждён только на constructed случаях с точным marker
форматом. Нового успешно собранного natural production case нет. На пяти
старых вопросах прирост не измерен: результаты/контекст/native прежние.
Естественные labels в других формулировках, анафора, solvent/additive aliases
и цепочка через Methods не поддержаны. Mixed source_type остаётся отдельным
ограничением; исправление classification/source-role policy требует отдельной
проверки, а не молчаливого ослабления текущего контракта.

Finite guards не устанавливают общую scientific ownership, causal relation,
сопоставимость экспериментов или истинность статьи. Заполненные raw поля и
неизвестные условия сохраняются раздельно. Прежние76 exposed cases не являются
скрытой независимой оценкой новой ветви.

Реальных model/OAuth calls и новых slots0. Контекст пяти не менялся; fresh DB/
rollback preparation не выполнялась. Browser/PDF visual QA, full suite,
cache-ORM/concurrency/deployment и независимая научная оценка не выполнены.
Все live scopes закрыты, автоматической отправки нет.

Verdict:

Минимальная source-role assembly подключена к сервису с явным доказательством
одинакового label, полным F-ID contract и строгими отказами. Общий article_id
не разрешает сборку. Реальный Lin правильно остаётся unresolved по объявленным
ограничениям; это не новый научный успех или новый live ответ.

Следующий реальный scope: отдельно проверить исходную разметку Methods parent
и построить bounded identity bridge по явно заданным определениям электролита,
солей/растворителей/добавки и sample codes. Не связывать Abstract и Conclusion
по одной1.35 M или сходству имён. Нужны frozen real positives/negatives и
отдельная версия; этот следующий scope здесь не реализован. Пункт4, независимая
оценка и прежний75% прогресс проекта остаются открытыми.

- [HTML-обзор](../output/source_role_assembly_20261109/review_v02/review.html)
- [Полный report](../output/source_role_assembly_20261109/review_v02/report.json)
- [HTML QA](../output/source_role_assembly_20261109/review_v02/qa.json)
- [Протокол](records/source_role_assembly_protocol_2026-11-09_v0.1.md)
- [Предыдущий реальный grammar audit](natural_source_grammar_2026-11-09.md)
