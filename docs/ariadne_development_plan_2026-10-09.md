# ARIADNE: подробный план разработки и предзаявочного пилота

Дата плана: 9 октября 2026 года, Asia/Yekaterinburg.

## 1. Назначение и статус

План переводит [аудит MVP от 9 октября](ariadne_mvp_assessment_2026-10-09.md) в последовательность исполнимых задач. Целевой результат: химик получает проверяемую сравнительную таблицу экспериментальных характеристик из ограниченного корпуса PFSA/Nafion, с полными записями, evidence, исправлениями, экспортом и измеренными ошибками/трудозатратами.

Документ фиксирует план **по состоянию на сегодня**, а не обещает выполнить весь проект за сегодняшний день. Начало S01/S02 описано в [первом отчёте](ariadne_s01_s02_execution_2026-10-09.md); техническая схема/source adapter, manifests и completeness checks — в [отчёте S03/S05](ariadne_s03_s05_execution_2026-10-09.md); development cases и offline worksheets — в [отчёте подготовки S04](ariadne_s04_preparation_2026-10-09.md). Остальные интерфейсы остаются планом без отдельного отчёта реализации.

Рабочая цель ближайшего цикла — предзаявочный исследовательский пилот, а не готовая промышленная ARIADNE Box. Текст и простые таблицы входят в предполагаемый scope; графики, произвольные сложные таблицы, второй домен и полноценная predictive-модель отложены до доказательства основного процесса.

## 2. Подтверждённая стартовая точка

Обновление 20 октября, [region OCR stage13](records_stage13_region_ocr_2026-10-20.md): реализован отдельный локальный OCR четырёх frozen-регионов с raw TXT/TSV, source/word coordinates, runtime hashes и явными ошибками процесса. Текст получен в трёх областях; химические обозначения, знаки степеней и единицы содержат ошибки даже при высоком confidence. Все четыре PNG/TXT/TSV совпали побайтово при повторе, stage12 report byte-identical. 1336 tests passed, Ruff/mypy прошли; все четыре crop и word overlays просмотрены. Кандидаты в generation не включены; scientific acceptance открыта. Далее — отдельная версия диагностики научных обозначений и полных/частичных native-region overlaps с независимыми counterexamples.

Обновление 20 октября, [source gaps stage12](records_stage12_source_gaps_2026-10-20.md): реализован отдельный offline реестр растровых вхождений/векторных записей с точными PDF/page/layer hashes, строками и привязкой к selected citations. 35 регистраций, 32 уникальные страницы, 83 растровых вхождения; у 71 нет пересечения с зарегистрированными строками. Научная роль и полнота OCR не определяются этим признаком. Запросы/контексты stage11 неизменны; stages08–11 reports byte-identical. 1301 tests passed, Ruff/mypy прошли; четыре диагностических наложения просмотрены. Полные страницы всё ещё блокируют отправку, новых GPT-вызовов нет. Следующий ограниченный этап — отдельная версия извлечения кандидатов текста из изображений/таблиц с сохранением исходников и независимыми проверками до изменения генерации.

Обновление 20 октября, [ruled tables stage11](records_stage11_ruled_tables_2026-10-20.md): после ограниченного stage10 реализованы source-bound группы по замкнутым PDF-линейкам, целым header/data blocks и явным сноскам. Первая версия отклонена после визуально найденного пропуска строки/буквенной сноски; два counterexamples реально провалились до исправления. В v0.2 две реальные таблицы просмотрены, неполное окончание явно отклоняется; stages08–10 reports byte-identical. Full regression: 1274 passed, Ruff/mypy прошли. Ещё 1 244 символа удалены из положительных контекстов, но полные страницы/графические source gaps остаются; новых GPT-вызовов нет. Следующий приоритет — диагностика графических пробелов и независимые случаи продолжений/сносок, без научной приёмки по одному структурному pass.

Обновление 20 октября, [layout stage10](records_stage10_layout_groups_2026-10-20.md): добавлены защищённые геометрические группы с целыми соседними абзацами и диагностикой открытых/пересекающихся границ. В frozen replay — предложения для двух уникальных рисунков и одной inline reference; реальные таблицы не разрешены. Stages08/09 reports byte-identical; 1253 tests passed, Ruff/mypy прошли. Дополнительное сжатие положительных контекстов — лишь 64 символа. Визуально проверены три PNG; обнаружены практически полная страница (99,25% текста) и графическое содержимое, отсутствующее в text evidence. Полные страницы блокируют отправку; новых GPT-вызовов нет. Следующий приоритет — source-completeness diagnostics для графики и реальные табличные boundaries/continuations; scientific acceptance открыта.

Обновление 20 октября, [context stage09](records_stage09_context_windows_2026-10-20.md): добавлены окна по целым PDF text blocks с exact source alignment, query anchors, защитой условий и соседними блоками. 42 среза проверены; положительные контексты короче на 29,44% относительно stage07 и на 8,52% относительно stage08. 28 широких fallback сохраняют неразрешённые таблицы/рисунки/повреждённые формулы; полные страницы по-прежнему блокируют отправку, новых GPT-вызовов нет. Прежний stage08 report воспроизведён без изменений. 1229 tests passed, Ruff/mypy прошли. Далее — source-bound группы таблиц/подписей/сносок и page continuations, затем новый frozen answer comparison; scientific acceptance открыта.

Обновление 20 октября, [context stage08](records_stage08_context_compaction_2026-10-20.md): консервативный offline prepass проверен на четырёх frozen-вопросах stage07. Удалены пять точных повторов страниц; два reference suffix предложены к исключению, неоднозначная библиография сохранена. 35 срезов совпали с chunk/page offsets; положительные контексты короче на 22,86% по символам. Полные страницы остаются, scope guard блокирует отправку; новых GPT-вызовов нет. Полный regression — 1189 passed; Ruff/mypy прошли. Production defaults не менялись. Следующий этап — versioned sentence/section windows с диагностикой условий, таблиц и сносок, затем новый bounded answer comparison. Scientific acceptance остаётся открытой.

Обновление 20 октября, [сквозной stage07](records_stage07_end_to_end_2026-10-20.md): существующий answer pipeline проверен на четырёх frozen-вопросах через automatic hybrid_cross_lingual retrieval и development Responses-provider. Три GPT-ответа, один gate refusal без API; 11/11 claims имеют известные source IDs, ожидаемые статьи найдены/процитированы в 3/3 положительных случаях. Научная entailment/accuracy не измерена независимо. Выбранные chunks содержат целые страницы — условие протокола о непередаче полного текста страниц не выполнено; фактические запросы сохранены. БД/PDF/индекс совпали с snapshot; восстановлен отсутствовавший query-embedding runtime без пересборки индекса. Полный regression — 1167 passed. Следующий bounded цикл — программное сужение evidence с сохранением условий/подписей/сносок, аудит библиографического/перекрывающегося шума и диагностики повреждённых формул; новые независимые вопросы остаются необходимы.

Обновление 20 октября, [records stage06](records_stage06_fixed_links_2026-10-20.md): добавлен `span_fixed` с именованными nullable linkage slots и отказом при duplicate JSON keys. Все четыре реальные frozen-попытки integrity-valid; три положительных кандидата и правильный bibliography negative. По прежнему эталону: 21 match, 5 mismatch, 34 deferred; scientific acceptance остаётся открытой. Полный regression — 1155 passed, Ruff/mypy прошли, replay stages02–05 сохранён. Структурный сбой duplicate linkage закрыт отдельной версией без исправления прежнего ответа. Следующий цикл — frozen end-to-end вопрос → corpus retrieval → evidence → GPT → citation checks; независимая научная оценка остаётся отдельной задачей.

Обновление 20 октября, [records stage05](records_stage05_token_spans_2026-10-20.md): реализованы версии выбора source-token spans и восстановления текста кодом. Из четырёх frozen случаев выполнены два: compact — 4/4 exact raw fields; таблица отклонена за duplicate linkage role, оставшиеся два запроса остановлены по протоколу. 53 coordinate references разрешились точно, но full-record/scientific acceptance не достигнута. Полный regression — 1138 passed. Прежние scientific replay outcomes stages02–04 сохранены. Следующий минимальный форматный опыт — фиксированные именованные linkage slots без возможности повтора роли; после отдельного frozen сравнения остаются новые независимые случаи и end-to-end retrieval evaluation.

Обновление 20 октября, [records stage04](records_stage04_openai_2026-10-20.md): отдельный OpenAI Responses backend выполнил четыре frozen development-запроса `gpt-6-astra`. Три случая integrity-valid, один отклонён за неточную цитату; короткий фрагмент — 4/4 exact raw fields, bibliography negative — корректный отказ. У Istomina три exact-reference mismatch, полной scientific acceptance нет. Полный regression — 1120 passed, Ruff/mypy прошли. Порядок последних двух вызовов отличался от prose protocol; отклонение сохранено в отчёте. Следующий ограниченный опыт — версия выбора source spans с восстановлением исходного текста по immutable offsets и отдельной проверкой sample/conditions/origin; independent gold и новые случаи всё ещё нужны.

Следующий ограниченный цикл 20 октября: [records stage03](records_stage03_compact_2026-10-20.md) получил завершённый компактный ответ за 9.445 s на одном oracle-фрагменте, но value/unit/temperature не прошли literal validation. Полный regression — 1103 passed; научная приёмка не закрыта. Следующий опыт: выбор source spans с восстановлением исходного текста кодом, без исправления сохранённого ответа stage03.

Обновление 20 октября: после source-only records stage01 реализован [bounded full-record adapter/evaluator](records_stage02_bounded_extraction_2026-10-20.md). Финальный regression — 1090 passed, Ruff/mypy прошли. Три реальные попытки локальной модели завершились transport timeout; успешное извлечение, S04/S06 scientific acceptance и независимый эталон не установлены. Следующий инженерный опыт — завершение ответа в измеренном runtime budget и проверка model-facing format. Целевые 10–15 пригодных независимых публикаций пока не набраны. Прежние статусы и цифры ниже относятся к своим историческим этапам.

| Область | Факт аудита | Что ещё не доказано |
|---|---|---|
| Исходники | Проверена рабочая копия с изменениями и untracked модулями | HEAD сам по себе не восстанавливает этот MVP |
| Тесты | 595 passed; Ruff и mypy прошли | Научная точность и независимая приёмка |
| Форматирование | 36 файлов требуют форматирования | Это технический долг, не причина переписывать pipeline |
| БД и индексы | Doctor PASS; head `0005_library_sources`; 2 ready индекса | Полный recovery и чистая поставка |
| Корпус | 33 статьи, 493 страницы, 619 chunks, 814 text layers | Полнота и правильность всех экспериментальных записей |
| Hybrid regression | 46/46, пороги пройдены | Independent gold и качество full-record extraction |
| Numeric review | 981 изменение, 0 новых решений; 13 исторических аннотаций | Научная приёмка этих изменений |
| Extractor | `rule_based_numeric_v1`, cap 12; кандидаты числа/единицы | Связи sample/property/value/conditions |

Все числа взяты из аудита и его отчётов. Тесты при создании этого плана повторно не запускались.

## 3. Правила реализации

1. Сохранять оригинальные PDF, текстовые слои и source traceability. Производные преобразования фиксировать отдельно с правилом и входным evidence.
2. Создавать full-record prototype в отдельном экспериментальном слое. Не менять production `structured_facts`, ingestion, OCR, chunking или retrieval scoring для удобства эксперимента.
3. Действующий numeric cap 12 и массовый refresh не менять в этом цикле без отдельного анализа изменения выдачи и научной приёмки. Новый prototype не должен наследовать этот cap как научное ограничение без решения по своему scope.
4. Считать единицей результата полную запись. Правильные цифры с неверным образцом или условиями — ошибочная запись.
5. Сохранять исходные единицы, знаки, приблизительность, границы, интервалы и погрешности. Не добавлять числовые допуски или конвертации без явно зафиксированного правила.
6. Разделять machine checks и human confirmation. Успешный JSON validator, наличие цитаты и согласие повторных вызовов модели не означают научного одобрения.
7. Не скрывать parser/model/storage failures общим отказом или пустой выдачей. Сохранять error type, stage и диагностическое сообщение.
8. Минимальный патч на одну проверяемую задачу. Сначала source case и критерий, затем изменение и необходимые проверки.
9. Сохранять существующие незакоммиченные изменения. Не использовать blanket add, reset/clean или автоматический коммит всего дерева.
10. Не менять gold, denominators и thresholds ради результата. После раскрытия test не настраивать систему на нём.

## 4. Роли и решения, от которых зависит работа

| Роль | Зона ответственности |
|---|---|
| Codex / разработчик | Baseline, реализация, диагностические отчёты, тесты, воспроизводимость |
| Руководитель-химик | Scope, обязательные условия сравнимости, научные решения, реальные пользовательские задачи |
| Второй химик | Независимая разметка части корпуса, разбор разногласий, оценка итоговой таблицы |
| Технический reviewer | Чистая поставка, хранилище/транзакции, восстановление, опасные migrations/deployment |

Ни одна из ролей не считается уже обеспеченной этим планом. Если второго химика пока нет, development продолжается, но scientific acceptance и независимая оценка остаются открытыми.

До начала научной реализации нужны конкретные решения:

- Сценарий выбран пользователем: проводимость литиевой формы Li-Nafion с сохранением авторского названия свойства; подтверждение Li-ion отмечается отдельно.
- Обязательные условия первой сравнительной таблицы согласованы пользователем: образец, температура, состав среды и метод. Неполные кандидаты остаются на review; научные правила проверки связей и интерпретаций ещё согласовать.
- Supported scope для первого пилота: какие абзацы/таблицы, типы значений и origin допустимы; как учитывать неподдерживаемые случаи.
- Кто выполняет независимую разметку и сколько времени доступно в неделю.
- Вычислительный ресурс проверен: i5-1135G7, 4 ядра/8 потоков, около 16 ГБ RAM. Пользователь разрешил установку и запуск Qwen2.5-1.5B-Instruct Q4_K_M. После исходных трёх неуспешных прогонов выполнены два упрощённых формата, по 30 запросов каждый. JSON стал полным, но научные связи и отрицательный библиографический случай не пройдены. Сервер остановлен, веса сохранены. Производственная модель по качеству ещё не выбрана.

Отсутствие этих решений не блокирует baseline, инвентаризацию корпуса и проектирование экспериментального слоя. Оно блокирует утверждение финальной схемы и научных критериев.

## 5. Очередь работ и зависимости

S00 выполнен. S01: source snapshot и чистая Python-сборка/запуск проверены; автономная поставка открыта. S02: scope выбран, профиль выполнен, научный shortlist впереди. S03: техническая схема/validator v0.1 реализованы, научная приёмка открыта. S04: подготовлены development cases, протокол разметки и offline worksheets; independent gold/split впереди. S05: single/multi-page adapter и development manifests реализованы; полный протокол экспериментов впереди. S06: локальные веса/runtime, строгий smoke harness, предварительный source-bound эталон и offline comparison реализованы; Qwen2.5-1.5B и 3B проверены на одинаковых настройках, по 30 запросов. Обе дали 3/30 reference agreements, только отказы; качество не принято. S09: completeness diagnostics реализованы, scientific admission открыт. S07–S08, S10–S17 не начаты. Оценки часов предварительные; срок пересчитать после scientific review S02–S04. Фактические S06 ошибки и измерения: [первые прогоны](ariadne_s06_execution_2026-10-09.md), [эталон и сравнение моделей](ariadne_s06_reference_comparison_2026-10-09.md).

| ID | Задача | Зависит от | Основной исполнитель | Предварительно |
|---|---|---|---|---|
| S00 | Аудит текущего MVP | — | Codex | Выполнен 09.10 |
| S01 | Baseline и состав релиза | S00 | Codex | 3–6 ч |
| S02 | Профиль корпуса и выбор scope | S00 | Codex + химик | 3–6 ч |
| S03 | Схема записи и инструкция gold | S02 | Codex + химик | 6–12 ч |
| S04 | Разметка pilot и разделение статей | S03 | Два химика | Оценить на первых 2 статьях |
| S05 | Source region adapter и run manifest | S01, S03 | Codex | 6–10 ч |
| S06 | Локальный модельный smoke | S01, S03; dev примеры S04 | Codex | 4–8 ч |
| S07 | Extraction из текста | S05, S06 | Codex | 8–16 ч |
| S08 | Extraction из простых таблиц | S07; table cases S04 | Codex + химик | 10–20 ч |
| S09 | Проверки и admission policy | S03, S07; затем S08 | Codex + химик | 10–18 ч |
| S10 | Хранилище версий и решений | S03, S05 | Codex | 6–12 ч |
| S11 | Review UI полной записи | S07, S09, S10 | Codex + химик | 10–18 ч |
| S12 | Export и сквозная демонстрация | S11 | Codex + химик | 4–8 ч |
| S13 | Evaluation harness | S03, S04 | Codex | 8–14 ч |
| S14 | Сравнение B/C и отказы | S08, S09, S12, S13 | Codex + химик | 4–8 ч + review |
| S15 | Измерение времени химиков | S12; протокол до опыта | Два химика | По числу сопоставимых задач |
| S16 | Offline, установка и recovery | S01, S06, S12 | Codex + reviewer | 8–16 ч |
| S17 | Evidence pack и решение о заявке | S14–S16 | Руководитель + Codex | 4–6 ч |

S13 реализовать до финального научного прогона; не откладывать определение метрик до получения удобных результатов. S09 и S10 можно вести независимо после согласования схемы. Это порядок задач, не поручение запускать дополнительных агентов.

## 6. Карточки реализации

### S01 — зафиксировать baseline

**Вход:** текущая рабочая копия, результаты S00, Git HEAD и список изменений.

**Действия:**

- Инвентаризировать tracked/untracked исходники, tests, migrations, config templates, scripts и необходимые assets.
- Составить явный inclusion/exclusion manifest релиза. Исключить `.env`, ключи, runtime logs, тестовый мусор и закрытый корпус из публичной части; необходимые review sources учитывать в приватной части.
- Записать Python/пакеты, миграции, хеши выбранных файлов, index/model identifiers, внешние OCR-инструменты и пути, которые придётся перенастроить.
- Сохранить dependency snapshot текущей среды; затем проверить минимальный dependency lock в чистой среде. `pip freeze` сам по себе не доказывает переносимость.
- Проверить isolated checkout/package из выбранного состава. Не копировать рабочую `.env` как готовую конфигурацию поставки.

**Результат:** воспроизводимый snapshot с инструкцией запуска и перечнем недостающих ресурсов.

**Приёмка:** выбранный комплект включает необходимые untracked modules; запуск не зависит от случайных файлов рабочего дерева; secrets не попали в manifest contents; checks привязаны к составу snapshot. Doctor оценивается по JSON categories, не только exit code.

### S02–S04 — scope, Scientific Record и gold

**S02:** read-only профиль 33 статей: потенциально подходящие свойства, типы источников, доступность полного PDF/таблиц, происхождение данных. Автоматические подсказки маркировать как candidates, а не как подтверждённую пригодность. Химик выбирает один сценарий.

**S03:** предложить versioned schema и инструкцию разметки. Минимальные группы полей:

| Группа | Что фиксировать |
|---|---|
| Identity | article/PDF hash, sample label и описание; локальность sample ID внутри статьи |
| Property | Вид проводимости и определение свойства в выбранном scope |
| Value | Raw lexeme/unit, scalar/range/bound, operator, approximation, uncertainty |
| Conditions | Обязательные для сравнимости условия; дополнительные параметры отдельно |
| Origin | experimental/calculated/reference/unknown с evidence |
| Evidence | Page, выбранный text layer, точный fragment/span; evidence связей между полями |
| Missingness | not_reported / not_found_in_context / ambiguous, с основанием |
| Processing | Schema/run/candidate revision, machine status и отдельный review status |

`not_reported` разрешать только при достаточном просмотре заранее определённого источника; модель, видевшая один абзац, не должна делать такое заключение за всю статью. Для cross-page evidence хранить каждый fragment и его собственную страницу. Bbox добавлять только при проверенном mapping.

Химик утверждает обязательные поля и примеры ошибок. Validator проверяет форму, типы, consistency и наличие evidence; его успешный результат не называется scientific validation.

**S04:** подобрать 10–15 публикаций для пилота; по возможности добавить новые для проекта статьи. Уже разобранные исторические ошибки использовать как development cases. Связанные версии/дубли одной работы держать в одном split.

До запусков фиксировать split manifest по статьям: development, validation и untouched evaluation. Точные размеры определить по числу подходящих записей; маленькую оценку не представлять как окончательный годовой test. Holdout не просматривать для выбора модели/prompt/rules. Размечать весь подходящий scope статьи, а не только найденные top-k фрагменты.

Второй химик независимо размечает выделенную часть до показа system outputs. Сохранять annotations обоих, disagreements и adjudication. Отрицательные/неоднозначные естественные случаи и синтетические стресс-примеры учитывать раздельно.

**Приёмка:** согласованная schema; понятный denominator; список excluded cases с причинами; воспроизводимый split; разногласия видны. Плотность записей и время разметки измерены на первых статьях, затем пересчитан объём плана.

### S05 — source regions и manifest запуска

**Реализация:** adapter получает page/layer/source text из существующего хранения. Для первой проверки допускается экспертно выбранный region; это явно маркируется как oracle region. Такой запуск оценивает extraction из данного evidence, а не end-to-end recall.

Следующий вариант — фиксированный сбор подходящих regions всей статьи без подсказок gold. Сохранить правила отбора, неподдерживаемые регионы и detection losses. Не перестраивать retrieval score ради доступа к нужной записи.

**Run manifest:** code/data/schema/model/runtime/parser/prompt/rules hashes, параметры, региональные IDs, timestamps, seed если поддержан, ошибки и ресурсы. Model weights или immutable revision должны быть идентифицированы; одного marketing name модели недостаточно.

**Приёмка:** точные spans проверяются по выбранному source text; source hash mismatch останавливает применение старого evidence; повторный запуск имеет собственный run ID. Повторяемость измеряется, а побайтовая идентичность недетерминированной генерации не обещается.

### S06–S08 — локальный extractor

**S06:** инвентаризировать реально доступные CPU/RAM/GPU и model artifacts, затем проверить 1–2 доступных кандидата на одном фиксированном development наборе. Измерить память, latency, parse errors и случаи неправильной связи полей. Модель выбрать по качеству и доступному ресурсу; не вводить новые закупки как предварительное условие опыта.

OpenAI-compatible локальный endpoint допустим как технический вариант при проверенной конфигурации. В текущем коде есть configurable OpenAI provider; это не свидетельство уже работающего локального full-record extraction. Новый extraction adapter не должен менять поведение существующих answer routes.

**S07:** отдельный adapter «source region → proposed records». Strict output schema, null/status отсутствующих полей, сохранение raw value/unit и evidence. Parse error не заменять пустым успешным массивом. Prompt и фактический model response сохранять в допустимом приватном экспериментальном контуре.

**S08:** сначала простые таблицы с ясными row/column labels, units и conditions. На каждом cell проверять sample/header/value linkage; таблица «температура × образец» даёт отдельные записи. Не размножать значения по пустым cells и не угадывать многоуровневые headers. Зафиксировать границы поддерживаемой структуры; неподдерживаемый layout получает диагностику.

**Приёмка:** реальные положительные и отрицательные development примеры с source evidence. Первый корректный JSON — только smoke, не приёмка качества. Отдельно показаны ошибки attribution, operators, ranges, uncertainty, calculated/reference origin и недостатка context.

### S09 — checks и admission policy

Проверки разделить по назначению:

1. Structural: schema, required fields и допустимые representations.
2. Source integrity: hash, page/layer, exact evidence spans.
3. Numeric: raw/parsed representation, unit compatibility, signs/operators/ranges; конвертации только по утверждённому реестру.
4. Linkage: подтверждение связи sample/property/value/conditions по конкретному evidence, без выдуманного «общего entailment validator».
5. Origin и role: измерение/расчёт/цитирование, response/condition/scale bar и неоднозначность.
6. Scientific identity: одинаковые числа не объединять автоматически; overlapping source representations не выдавать за независимые measurements.

Все checks сохраняют ID/version, result `pass/fail/unknown`, reason и evidence. `unknown` для обязательной связи не превращается в pass. Порог/политика выбираются на development/validation и фиксируются до evaluation.

**Machine states:** proposed → machine_checks_passed либо needs_review/rejected с причинами. **Human states отдельно:** unreviewed/confirmed/rejected/needs_changes. Исправление создаёт новую revision, повторно выполняет checks; human decision связывается с конкретной revision и source hash. Ни один machine state не создаёт human_confirmed автоматически.

**Приёмка:** known counterexamples и положительные controls из dev; measured false blocks и false accepts. Наличие проверки в коде не заменяет измерение её эффекта.

### S10–S12 — хранение, review и export

**S10:** экспериментальные immutable input/run/candidate artifacts плюс транзакционный decision/revision store. Для малого пилота допустима отдельная SQLite рядом с JSON artifacts; выбор оформить коротким design note. Не использовать numeric decisions как approvals полных записей.

**S11:** расширить существующий способ просмотра источников для полной записи: исходная страница/fragment, предложенные поля, evidence каждого поля, check reasons, edit/confirm/reject. Сохранение использует expected revision; конфликт или устаревший source/code/schema context выдаёт явную диагностику. Старые decisions остаются историей.

**S12:** экспорт JSON полной структуры и CSV для сравнительной таблицы. CSV содержит record/revision/run/source IDs и явно отделяет machine status от human status; вложенное evidence остаётся в JSON с reference из CSV. Проверенный по статье source fragment не теряется при экспорте. CSV import не добавлять без отдельной необходимости.

**Приёмка:** исправить поле, перезапустить приложение, открыть ту же revision, увидеть историю и экспортировать. Отказ/неоднозначность также сохраняются. Экспорт не маркирует unreviewed как confirmed. Исходная raw value остаётся после normalization. Проверить concurrency, stale-source и unknown IDs.

Первый demo использует 3–5 доступных реальных источников, включая ошибку/отказ. Только development источники; не раскрывать untouched evaluation ради красивого demo.

### S13–S15 — научная оценка и время

**S13:** evaluator сделать до финального прогона. Matching policy: одна prediction соответствует максимум одной gold-record и наоборот; неверная запись — FP, нужная gold остаётся FN. Дубликаты не увеличивают recall. Equivalence rules, numeric tolerances и обязательные условия фиксируются заранее химиком.

Основной report содержит TP/FP/FN, counts и denominators, record precision/recall, coverage, ошибки по полям/связям, detection losses, false accepts/refusals, text/table/OCR strata, время и память. Для малых наборов показать неопределённость; интервалы учитывать группировку по статье. Не смешивать unsupported scope с отсутствующими prediction внутри supported scope.

**S14:** режимы сравнения:

- A: текущий numeric extractor, только общие поля; никаких full-record claims.
- B: фиксированный локальный schema extractor.
- C: тот же B плюс checks/admission. Сохранённые B outputs можно повторно использовать для изоляции эффекта checks.
- D: C плюс human review; отдельное качество исправленной таблицы и время.

Для B/C одинаковые upstream parsing, region selection, модель и параметры. Отдельно оценить oracle-region extraction и end-to-end pipeline. Сравнить все предложенные записи, допущенные записи и coverage; precision за счёт почти полного отказа не считать достаточной победой.

**S15:** предварительно 8–12 сопоставимых задач между двумя химиками, если доступны. Зафиксировать protocol до опыта; сбалансировать порядок ручного/ассистированного режима, избегать эффекта запоминания. Измерять весь процесс чтение/поиск/проверка/исправление/export и сопоставимое итоговое качество. При меньшем объёме назвать результат exploratory pilot.

**Приёмка:** отчёт можно повторить по artifacts; failures не удалены; gold не менялся после просмотра outputs; conclusions отделены от малой выборки и развития на знакомых cases.

### S16–S17 — эксплуатация и заявочный evidence pack

**S16:** подготовить локальные model files и зависимости; в контролируемой среде отключить внешнюю сеть и пройти import → extraction → checks → review → export. Зафиксировать условия отключения и отсутствие докачки; наличие localhost endpoint не является внешней сетью.

Проверить чистую установку и restore в отдельном каталоге/БД/schema. Backup должен охватывать не только PostgreSQL, но и original PDFs, sidecar runs, review history, index/model references и manifest. Хеши evidence и approvals после restore должны соответствовать исходным. Recovery worker проверять на тестовом job, не завершая рабочие процессы произвольно.

**S17:** собрать приватный воспроизводимый evidence pack и отдельную презентационную часть: scope, architecture, demo cases, независимая разметка, B/C/D results, ошибки, ресурсы, ограничения, роль команды и план исправлений. Закрытые PDF и secrets не публиковать.

**Решение:** продолжать выбранный scope, сужать его или оставить review-first pilot. Невыполненный KPI указывать явно; не переименовывать отказ в выполнение исходной цели. Срок заявки и её актуальные юридические условия в рамках этого плана не проверялись.

## 7. Рабочие KPI и ворота

Ниже сохранены рабочие цели [концепции v1.1](../handoffs/ARIADNE_OPTIMIZED_CONCEPT_v1_1_2026-10-06/02_GRANT_CORE_AND_KPI.md). Они не достигнуты текущим MVP и не становятся договорными обязательствами только из-за появления этого документа.

| Показатель | Рабочая цель | Как проверять |
|---|---|---|
| Full-record precision | ≥90% | Корректные machine_checks_passed / все machine_checks_passed до human edits |
| Full-record recall | ≥60% | Корректные machine_checks_passed / весь supported gold, включая detection losses |
| Provenance | 100% допущенных записей | Evidence непустых fields и обязательных связей; source/rule преобразований |
| Correct abstention | ≥85% | Отдельный negative/ambiguous denominator; false refusals на positives тоже показывать |
| Экономия труда | ≥30% | Медианное полное время при сопоставимом итоговом качестве |
| Offline | Один полный workflow | Контролируемая сеть отключена после установки; внешних API/докачки нет |
| Pilot | Один завершённый | Реальная задача, пользователь, корпус, protocol и report |
| Reproducibility | Manifest каждого run | Полные IDs/hashes/config/runtime и доступные artifacts |

Ворота выполнения:

- **G1 / S01–S04:** версия воспроизводима, scope/schema/gold protocol согласованы. Без этого не объявлять научный baseline.
- **G2 / S05–S09:** полные proposed records и checks работают на dev, ошибки наблюдаемы. Без этого не расширять домен.
- **G3 / S10–S12:** исправление, history и export замыкают реальную задачу химика.
- **G4 / S13–S15:** B/C/D измерены; scientific claims соответствуют фактическому набору и uncertainty.
- **G5 / S16–S17:** offline/restore и evidence pack готовы; решение о scope заявки опирается на результат.

## 8. План на сегодня, 9 октября

Приоритет — сделать начало разработки воспроизводимым и определить научный вход. Все пункты ниже — ещё задачи, а не выполненные действия этого документа.

- [x] S00: свежий аудит MVP и исходного состояния выполнен; результаты доступны по ссылке в начале.
- [x] S01.1: manifest выбранных tracked/untracked файлов, SHA-256 и environment snapshot.
- [x] S01.2: source комплект, dependency closure, ресурсная опись и чистая Python-проверка. Полная автономная поставка остаётся S16.
- [x] S02.1: read-only lexical profile и candidate shortlist; подтверждение научной пригодности впереди.
- [x] S02.2a: пользователь выбрал проводимость литиевой формы с авторским названием и отдельным подтверждением Li-ion.
- [ ] S02.2b: определить обязательные условия сравнимости и научно принять shortlist.
- [x] S03.1: создан черновик schema/annotation guide; окончательная scientific schema ещё не принята.
- [ ] S03.2: перечень спорных вопросов химикам и критерии утверждения schema.
- [ ] S04.1: ручная проба на первых двух статьях для оценки плотности записей и трудоёмкости; независимая вторая разметка при доступности химика.

Если научные решения сегодня недоступны: завершить S01 и S02.1; подготовить schema draft, не выдавать его за утверждённый. Модельный full-record implementation начать после этих решений. Существующий corpus/retrieval baseline уже проверен сегодня; не повторять его без изменения исходников/корпуса или конкретной причины.

**Минимальный результат дня:** baseline manifest + corpus shortlist + schema draft/decision list. При доступном химике — утверждённый scope и первые gold examples. Полный extractor, independent evaluation и offline acceptance за один день не обещаются.

## 9. Ориентир на следующие четыре рабочих недели

Это порядок milestones при доступных разработке, химиках и модели. Calendar deadline не фиксируется; после первых двух размеченных статей и model smoke план пересчитывается.

| Период | Основной фокус | Результат |
|---|---|---|
| Неделя 1 | S01–S06; начать S10/S13 | Версия, scope/schema, gold protocol, source adapter и локальный smoke |
| Неделя 2 | S07–S09; S10 | Текстовый extractor, простые таблицы, checks и история versions |
| Неделя 3 | S11–S13; начать S16 | Review/export, сквозной dev demo, evaluator и подготовка offline |
| Неделя 4 | S14–S17 при готовом gold | Comparative pilot, human time, offline/restore, evidence pack |

При нехватке ресурса сужать supported cases до явного текстового scope, а таблицы честно оставить открытым воротом. Если цель заявки требует таблицы, текстовый demo не закрывает эту цель. Не настраивать на holdout для «успеть к четвёртой неделе».

## 10. Планируемая структура новых артефактов

Предложение для S01/S03/S05; перечисленные компоненты **пока не созданы этим планом**. Названия уточняются минимальным design note до implementation.

```text
app/records/                         # proposed: full-record prototype
  schema.py                         # implemented draft: schema/version/raw representation
  sources.py                        # immutable source regions/evidence
  readiness.py                      # implemented: completeness diagnostics, no scientific admission
  runs.py                           # implemented: development artifact/code manifests
  cli.py                            # implemented: source/validate/schema/manifest
  review.py                         # implemented: offline worksheet; no decisions or interactive UI
  extraction.py                     # extraction orchestration
  providers.py                      # local model adapter
  verification.py                   # checks/admission
  store.py                          # revisions and decisions
  export.py                         # JSON/CSV
  review_ui.py                      # full-record workbench
app/evaluation/records.py            # proposed: evaluator
tests/unit/test_record_*.py          # proposed: meaningful invariants
docs/records/                       # proposed: schema and protocol
data/experiments/records/            # proposed: private run/gold artifacts
```

До записи private artifacts в новую директорию S01 должен проверить `.gitignore` и правила включения. Default — без автоматического импорта этих записей в production `structured_facts`. Production integration и migration требуют отдельной задачи после stable schema и recovery.

## 11. Проверки при реализации

Ниже существующие команды, уже применявшиеся к MVP; запускать по необходимости после релевантных изменений:

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m app.ingestion.cli doctor
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-report
.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --top-k 10 --method hybrid --check-thresholds
```

Для патча сначала targeted tests значимых invariants; full suite на завершённом этапе. Retrieval regression повторять при изменении retrieval/upstream evidence, а не после каждого документа или UI label. Baseline formatting debt не расширять массовым форматированием. Sandbox failures отличать от дефектов и соблюдать штатный механизм разрешений.

Record CLI и meaningful integrity tests реализованы в `app/records/` и `tests/unit/test_record_*.py`; команды и границы описаны в [contract guide](records/experimental_record_contract.md). Development cases вручную подготовлены из локальных источников; это не gold и не результат extractor. Scientific cases брать из согласованного dev evidence; синтетические fixtures маркировать явно.

## 12. Отдельные очереди и правила изменения scope

- Numeric diff review из 981 изменения остаётся отдельной научной приёмкой. Исторические аннотации не переносить автоматически. Для full-record пилота допустим независимый sidecar path; отсутствие полного review legacy diff не разрешает его bulk refresh.
- Улучшения RU ranking — отдельный retrieval backlog; текущие 46/46 не означают идеальный top-1. Вмешательство оправдано measured detection losses нового pilot.
- Форматирование, deprecation warning, CI и packaging — отдельные engineering задачи, связанные с поставкой. Они не заменяют научные результаты.
- Графики, complex tables, много доменов, тысяча статей, enterprise network deployment и predictive engine — post-pilot либо отдельный scope.
- Hardware budget и модельные рекомендации определять после измерения локального workflow; все предполагаемые требования считать гипотезами до benchmark.

Каждая завершённая задача сопровождается коротким отчётом: Changed / Tests run / Limitations / Verdict, ссылками на evidence и обновлением фактического статуса в этом плане. Статус «готово» запрещён без прохождения указанной приёмки.

## 13. Первое поручение для следующего рабочего шага

```text
Выполни S01 плана docs/ariadne_development_plan_2026-10-09.md.
Прочитай AGENTS.md. Сохрани текущие незакоммиченные изменения.
Создай manifest выбранного baseline: необходимые исходники/тесты/migrations,
config templates/assets, хеши, версии runtime/dependencies, внешние инструменты
и model artifacts. Не включай .env, ключи и закрытые PDF в публичный комплект.
Отдели временные/generated файлы от состава релиза. Не делай blanket commit,
reset/clean, production migrations или refresh facts. Зафиксируй, что можно
воспроизвести сейчас и каких ресурсов не хватает. Проверяй только то, что
нужно для этой задачи; уже выполненные 09.10 проверки не повторяй без причины.
Покажи артефакты и отчёт Changed / Tests run / Limitations / Verdict.
```

## 14. Что выполнено при создании плана

Changed: создан этот документ и добавлена ссылка на него из основной roadmap.

Tests run: прочитаны исходные audit/roadmap/schema/config/planning документы; проверены локальные Markdown-ссылки после записи. Кодовые тесты в этом шаге не запускались: runtime не менялся. Числа 595 и 46/46 относятся к S00 текущей даты.

Limitations: scope conductance, финальная schema, corpus split, локальная модель, реальные роли и календарный срок пока не утверждены/не измерены. Оценки часов — плановые.

Verdict при создании плана: очередь разработки сформирована. Последующие S01/S02, S03/S05 и S06 шаги зафиксированы отдельными отчётами. Упрощение model-facing contract и повтор на тех же contexts выполнены: [сравнение форматов](ariadne_s06_format_comparison_2026-10-09.md). Затем реализованы [semantic review rubric](records/semantic_review_rubric.md), предварительный эталон, offline comparison и [сравнение 1.5B/3B](ariadne_s06_reference_comparison_2026-10-09.md). Следующий шаг: независимый review эталона и ограниченный extraction adapter с явной проверкой связывания полей; научная приёмка S06 остаётся открытой. Scientific review связей, grouping и независимая разметка остаются открытыми.

## 15. Дополнительный TAC feasibility cycle, 12 октября

По запросу пользователя выполнен изолированный эксперимент Title/Abstract/Conclusions: [протокол](tac_experiment_protocol_2026-10-12.md), [результаты](tac_feasibility_report_2026-10-12.md). Production retrieval, glossary и extraction не менялись. На 46 development вопросах текущий поиск — 46/46; TAC-only — 41/46; TAC-deep replay — 44/46; с простым добором — 45/46. Визуальный boundary audit выявил пропуски и ошибки границ, включая unlabelled abstracts и нестандартные документы.

TAC как жёсткий gate не принят. Очередной ограниченный эксперимент: source-bound section boundaries, проверяемые work/supplement связи и full-text safety channel; затем отдельная проверка полноты и latency. Автоматическое RU–EN пополнение остаётся предложением до качества границ и правил соответствия. Этот цикл не закрывает S03/S04/S06 scientific acceptance и не заменяет независимый review записей Li-Nafion.

Продолжение 12 октября: [TAC stage 02](tac_stage02_report_2026-10-12.md). Detector v0.3 исправляет fragmented titles/abstracts и endings conclusions; добавлен воспроизводимый HTML-only exporter для пользовательского review всех 33 документов. На прежних 19 development boundaries — 19 совпадений вместо 11; это обучающие случаи, не независимая точность. На неизменных frozen выдачах 46 вопросов strict replay остаётся 44/46, с добором 45/46; strict chunk recall снизился до 0.923077. Production app и PDF hashes сохранены; 757 тестов прошли. Human review, metadata/Terms, supplement links и safety channel остаются открытыми. Финальная HTML-таблица: `output/tac_stage02_20261012/ARIADNE_TAC_stage02_final_2026-10-12.html`.

По следующему запросу реализован [TAC metadata sidecar](tac_metadata_report_2026-10-12.md): Authors/Journal/Year из локальных PDF с exact-source evidence, диагностикой конфликтов/пропусков и publication-year priority. Заполнены 32/29/30 из 33 строк соответственно; это предложения, не independent accuracy. Новая таблица: `output/tac_metadata_20261012/ARIADNE_TAC_metadata_2026-10-12.html`. 782 теста прошли; TAC sections, app и original PDFs не изменялись. Human review, внешняя metadata lookup/ingestion admission, Terms и safety channel остаются открытыми.

По запросу улучшить таблицу перед Terms завершён ограниченный [TAC stage 03](tac_stage03_report_2026-10-12.md): detector v0.4 объединяет продолжения заголовков, пропускает manuscript covers и предлагает unlabelled abstracts по byline/layout. T 33/33, A 30/33, C 27/33; изменены восемь T и одиннадцать A, метаданные сохранены. Это coverage proposals, не independent accuracy. Прежние 19 development boundaries совпали; 797 тестов прошли. Финальная таблица с метками изменений и прежним текстом: `output/tac_stage03_20261012/ARIADNE_TAC_stage03_final_2026-10-12.html`. App и PDF hashes совпали с baseline. Strict replay 44/46, с добором 45/46; losses supplement сохраняются. Обрезания Nagasubramanian/Mohammadi, remaining sections/metadata и human review остаются открытыми; далее продолжения Abstract между колонками и source gaps перед Terms/production admission.

Следующий запрос выполнен как [TAC stage 04](tac_stage04_report_2026-10-12.md): detector v0.5 восстановил оба известных обрезания Abstract, добавил source-bound summary passages Besenhard/Welch и поддержку проверяемого продолжения между соседними колонками/страницами. Пустые/пропущенные страницы не склеиваются. Новое experimental поле `conclusion_kind` отличает явный раздел от итоговых фрагментов. T 33, A 30, explicit C 27; ещё три строки с summary passages, из них две относятся к одной работе Welch. 93/99 заполненных TAC ячеек включают расширение типа C evidence, не означают 94% independent accuracy. 813 тестов прошли, старые 19 development boundaries сохранены; PDF/app hashes и 91 metadata values совпадают с baseline. Replay pass totals 42/44/45 остаются прежними, effects ranking смешанные; hard TAC gate по-прежнему не принят. Финальная таблица: `output/tac_stage04_20261012/ARIADNE_TAC_stage04_final_v02_2026-10-12.html`. Human review, независимая разметка полноты, remaining source/metadata gaps, supplement links, safety channel и Terms остаются открытыми.

Продолжение 13 октября: после аудита stage05, stop-heading repair stage06 и Terms
sidecar stage07 завершён [TAC stage08](tac_stage08_inline_stop_2026-10-13.md).
Detector v0.7 восстанавливает Conclusions Nagasubramanian по доказанной
геометрии слова `results` внутри предложения. На неизменном snapshot только
одно C поле расширено на 505 символов; другие T/A/C и metadata сохранены.
865 тестов прошли; frozen replay полностью совпал со stage06. Финальная таблица:
`output/tac_stage08_20261013/ARIADNE_TAC_stage08_final_v02_2026-10-13.html`.
Terms реализованы как предложения, но scientific relevance/recall и human
acceptance ещё не измерены. Следующий ограниченный цикл — отдельный review
Terms; интеграция в production glossary/index и S03/S04/S06 acceptance остаются
открытыми.

Продолжение 13 октября: [Terms stage12](tac_stage12_review_2026-10-13.md)
закрывает engineering этапа 4 отдельного Terms plan: постоянные решения,
история/restore, source-bound review, очередь, конкурентные правки и backup.
Все 33 TAC документа сохранены в отдельной восьмиколоночной HTML-таблице.
Full pytest: 950 passed; финальные targeted: 16 passed. Независимая научная
приёмка и production indexing Terms остаются открытыми.
