# ARIADNE: память о выборе архитектуры MVP

Дата: 22 октября 2026 года, Asia/Yekaterinburg.

Статус: направление MVP, сохранённое по просьбе пользователя после обсуждения.
Документ фиксирует соображения и границы обещаний, а не завершение реализации,
научную приёмку, проверенный спрос или утверждённые условия конкретного провайдера.

## Направление

Первый MVP развивать как локальную систему подготовки и поиска научных источников
с анализом выбранных доказательств через заменяемый LLM API. Первым использовать
существующее подключение OpenAI. YandexGPT, GigaChat и модели российских облачных
провайдеров рассматривать как кандидатов для отдельных адаптеров и сравнения.

Готовую коробку с полностью локальной моделью сохранить как возможную последующую
комплектацию под подтверждённую потребность заказчика в автономности и закрытом
контуре. Универсальный локальный инференс и аппаратная поставка не являются
предварительным условием первого API-based MVP. Это меняет приоритет проработки,
но не объявляет прежние offline/recovery задачи выполненными или отменёнными.

## Разделение работы

| Слой | Ответственность | Статус и ограничения |
| --- | --- | --- |
| Локальные источники | Неизменные оригинальные PDF, текст/OCR, страницы, слои, chunks, хеши, индексы и поиск | Реализованные подсистемы; текущие состояния и ограничения описаны в README и отчётах |
| Автоматическая организация | Структура, Terms, числовые кандидаты, связи-кандидаты и диагностика неопределённости | Экспериментальные части не считать подключёнными к production pipeline без отдельной реализации; обязательный ручной разбор каждого Terms не вводить |
| Пакет доказательств по запросу | Вопрос, выбранные исходные фрагменты, source IDs и контекст, необходимый для интерпретации | Базовая передача question/evidence существует; универсальное сохранение научных связей таблиц/условий ещё не принято |
| Анализ моделью | Предложения связей свойства, образца, значения, метода и условий; сопоставление статей и ответ с источниками | OpenAI answer provider и отдельные records API experiments существуют; переносимость и научное качество других провайдеров не проверены |
| Локальная проверка | Проверка структуры и citation IDs, source integrity; явные ошибки, пропуски и неопределённости | Проверки структуры/источников существуют в своих путях; семантическая истинность ответа ими не доказана |
| Расчёты | Числовые преобразования и сравнения по явно заданным проверяемым формулам | Принцип дальнейшей реализации; общий вычислительный модуль не объявляется готовым |

## Что означает «концентрат информации»

Целевой пакет содержит исходные доказательства, а не только пересказ или список
уже назначенных категорий. Для таблиц нужны связанные заголовки, единицы, строки
и сноски; для измерений — относящийся к ним контекст методики/подготовки. Сохранять
article, PDF identity, страницу/диапазон, source type, выбранный текстовый слой,
точные фрагменты и координаты там, где они установлены. Модель не должна
восстанавливать отсутствующие сведения из предположений.

`no_literal_cue` не является основанием исключать исходный текст из поиска.
Unsupported, ambiguous и missing cases остаются доступными с диагностикой.
Подготовка пакета не должна требовать, чтобы локальная грамматика предварительно
разрешила все научные связи. Сокращение текста само по себе не доказывает
сохранность условий, экономию оплаченных токенов или качество ответа.

## Заменяемость API и допустимые заявления

Существующий `AnswerProvider` задаёт внутреннюю границу, но runtime factory
поддерживает только `openai`. В records используется отдельный native Responses
backend. Оба пути следует учитывать при будущих изменениях: адаптация одного
не делает автоматически переносимым другой.

Для нового провайдера нужны адаптер авторизации, запросов, схемы/разбора ответа,
лимитов и диагностики; отдельная проверка source integrity и научного поведения.
OpenAI-compatible endpoint не гарантирует совпадение всех параметров и семантики.
Один внутренний контракт должен сохранять выводы, source references, отказы и
неопределённости. Транспортную ошибку или обрезанный ответ нельзя выдавать за
научное отсутствие данных. Этот документ не создаёт новые конфигурационные ключи.

Текущая допустимая формулировка:

> Реализована интеграция с OpenAI API. Архитектура предусматривает подключение
> других LLM-провайдеров через адаптеры, включая российские сервисы.

Конкретного провайдера указывать как поддерживаемого только после реализации
и проверки. Не обещать «любую API» или одинаковое качество моделей. Заменяемость
здесь относится к финальному анализу; смена embedding-модели — отдельное изменение
индекса, требующее собственной проверки совместимости и пересборки.

Российская разработка модели и российская инфраструктура обработки — разные
критерии. У облачного каталога могут быть внешние маршруты. Для выбранного
endpoint отдельно проверять обработку, хранение, логирование, обучение и доступ;
не переносить гарантии одного сервиса на остальные. `store=false` не является
общей гарантией отсутствия хранения. В этом шаге новые передачи корпуса не выполнялись.

## Сравнительная оценка из обсуждения

Субъективная оценка ассистента для первого MVP при текущих вводных:

- Локальная база и проверки плюс заменяемый API: **8/10**.
- Готовая коробка с локальной моделью: **6/10**.
- При обязательном полностью автономном/закрытом контуре потенциальная оценка
  коробки повышается до **8–9/10**, если качество локальной модели подтверждено.

Основание оценки API-варианта — возможность раньше проверить полезность
сравнительных научных таблиц без одновременной доводки аппаратной поставки.
Коробка требует эксплуатации локальной модели и оборудования; потребность
покупателя в отдельном устройстве и готовность платить не установлены.
Оценки не являются benchmark, метриками accuracy, прогнозом выручки или
результатом пользовательского исследования. Ценность ARIADNE предполагается
в подготовке источников, traceability и проверке выводов; это подлежит проверке
на реальных задачах исследователей.

## Следующее инженерное решение

Обновление после [этапа 49](records_stage49_dsc_experiment_2026-10-27.md),
27 октября: frozen DSC experiment contract готов offline — 8712-byte request,
один будущий вызов с historical alias/settings, без retries/fallback, 4096 output
tokens / 180 s. Reply/source criteria и unexecuted result format зафиксированы;
usage/model/cost остаются unknown до фактического ответа. Alias/schema/pricing
не проверялись у провайдера. 57 affected tests, Ruff/mypy, HTML/PDF-link QA прошли.
API/model/retrieval/embedding/DB calls нет. Далее — пункт 4 после явного снятия
API prohibition и реализации durable attempt/result recording; сама фиксация
контракта не является сетевым разрешением или scientific acceptance.

Обновление после [этапа 48](records_stage48_dsc_admission_2026-10-27.md),
27 октября: новый DSC-пакет прошёл 14/14 source checks и пригоден для подготовки
frozen-эксперимента. Эта eligibility не является научной приёмкой и не меняет
старые production gates, отказы или historical 0/4. Network readiness false;
API prohibition, отсутствие frozen experiment contract и provider envelope
сохранены отдельно. 85 affected tests, Ruff/mypy, HTML/PDF-link QA прошли.
API/model/retrieval/embedding/DB calls нет. Далее — пункт 3, prospective frozen
experiment contract. Provider, архитектура и thresholds не менялись.

Обновление после [этапа 47](records_stage47_dsc_context_2026-10-27.md),
27 октября: новый DSC-контекст запрошенной Istomina собран отдельно — четыре
identity anchors и полный раздел 2.4, 4346 bytes wire, exact source registry
отдельно. Старые packets/PDF/metadata сохранены; 59 affected tests, Ruff/mypy,
source/HTML/PDF-click QA прошли. API/model/retrieval/embedding/DB calls нет.
Это завершение пункта 1 pre-API плана, не admission или runtime activation.
Далее — пункт 2: отдельная проверка допуска нового пакета. Текущий provider,
архитектура, thresholds и требование явных unknown не менялись.

Обновление после [этапа 46](records_stage46_evidence_gaps_2026-10-27.md),
27 октября: четыре прежних вопроса получили offline gap checklists и отдельную
source-review сводку. Полный текст 11 PDF / 273 страниц проверен; DSC методика
Istomina найдена в отдельном source supplement, физическая стр. 4, вне прежнего
packet. Это конкретный пробел отбора, не основание повысить admission или объявить
автоматические научные связи. 90 targeted tests, Ruff/mypy и source/HTML/PDF-link
QA прошли; старые packets/metadata/PDF сохранены, model/API/retrieval/embedding/DB
calls нет, admission 0/4. Далее — отдельно подготовить контекст запрошенной статьи
с полным разделом и прежними guards. Архитектура и текущий provider не менялись.

Обновление после [этапа 45](records_stage45_sample_identifiers_2026-10-27.md),
27 октября: sample/table references проверяются локально, с отдельной source-only
таблицей на физической странице 6. Её 21 строка не добавлена в старый model wire;
native model candidates не применяются. Старый stage23 replay не объявлен
восстановленным: изменённый pyproject.toml явно записан, source hashes и текущая
PDF text/block/line геометрия перепроверены отдельно. Три selected sample mentions
имеют по кандидату строки, но остаются unresolved; методика/условия не назначены.
8/8 source checks, 1/1 catalog check, 78 targeted tests и Ruff/mypy прошли,
все десять TAC документов сохранены. API/model/embedding/retrieval/DB calls нет,
admission 0/4; source selection/thresholds/provider не менялись. Далее — повторная
локальная проверка полноты sample/method/condition chains с source endpoints,
без вывода scientific identity или applicability из соседства. Ниже — история.

Обновление после [этапа 44](records_stage44_condition_applicability_2026-10-27.md),
27 октября: same-event condition-link proposals реализованы локально, без API.
В 155 selected events — 38 condition occurrences, включая два measurement-context
и четыре protocol-parameter proposals; подготовка и unresolved сохранены отдельно.
Range/step/accuracy не нормализуются в measured temperatures, sample class не
становится конкретным образцом. Scientific applicability остаётся открытой;
отбор, wires и все прежние запреты сохранены, admission 0/4. 12/12 checks,
48 targeted tests и Ruff/mypy прошли. CLI запрещает Python socket/DNS operations;
model/embedding/retrieval/DB calls нет, provider не менялся. Далее — source-bound
explicit sample/table identifiers и ссылки на них с abstention cases; API для
этой локальной работы не требуется. Ниже — история решений.

Обновление после [этапа 43](records_stage43_source_origin_2026-10-27.md), 27 октября:
при временно недоступном API выполнен отдельный offline origin/applicability audit
на прежних frozen inputs. Отбор 62 блоков / 155 events и model-facing wires
побайтно сохранены; все 561 source blocks / 1148 events учтены. Literal section
и origin cues не устанавливают own work, sample identity или applicability;
134 selected events остаются origin unknown, ещё 16 citation-only unknown.
21/21 development checks, 51 targeted tests, HTML-тест и Ruff/mypy прошли; все
десять TAC документов сохранены. Локальные prepare/run/export запрещают Python
socket/DNS operations, model/embedding/retrieval/DB calls нет, admission 0/4.
Следующая локальная задача — source-bound method/condition applicability и
abstention cases; API status probing, смена provider и загрузка моделей для неё
не требуются. Ниже — история решений.

Обновление после [этапов 41–42](records_stage42_sample_selection_2026-10-26.md),
26 октября: finite sample-class audit реализован отдельно от отбора. Для вопроса
о мембранах отложены четыре целых Guo/SEI units: 142 → 62 блока, wire 81189 →
67247 байт, current full pages 1 → 0. Unknown, mixed и query без finite класса
сохраняют прежний отбор. Это воспроизводимое предложение selection, не доказанная
научная ненужность SEI-методик или сохранность всех условий. 40/40 development
expectations, 60 targeted tests и Ruff/mypy прошли. Все полные parents остаются
локально; оба этапа имеют отдельные review/TAC HTML для десяти документов.
API admission 0/4, все прежние отказы сохранены; новых runtime/DB/retrieval/model
calls нет. Далее — source-based origin и applicability retained фрагментов с
явным unresolved и отдельными false-retention/deferral checks, до нового решения
об admission. Нельзя объявлять ноль full pages достаточностью scientific context.
Ниже — история решений.

Обновление после [этапа 40](records_stage40_query_selection_2026-10-24.md), 24 октября:
новая finite query-aware selection уменьшила wire 200221 → 81189 байт и full-page
occurrences 22 → 1, выбрав 142/561 блоков целыми units. Это не lossless перепаковка:
116 прежних окон остались целыми, 37 частичными, 374 отложены; все parents локально
сохранены побайтно. Пять protected-group occurrences отложены целиком, scientific
irrelevance не доказана. 11/11 exposed development checks не устанавливают полную
научную сохранность. Guo/SEI показывает over-inclusion при отсутствии implicit
sample/material scope. API admission 0/4, runtime/providers/DB не менялись, новых
retrieval/model calls нет. Следующий bounded шаг — sample/material scope с явным
unknown и source-based false-inclusion/exclusion checks до admission upgrade.
Меньше bytes не означает доказанную экономию inference или scientific acceptance.

Обновление после [этапа 39](records_stage39_context_completeness_2026-10-24.md), 24 октября:
все 22 полных text-page occurrences обусловлены union прежних окон, а не размером
JSON или добавленными dependency blocks. Отдельный source audit сохранил все
1148 events/449 dependencies и прежние packets; одна уникальная cooccurrence
proposal не доказывает sample identity или applicability условий. Подготовка
в аргоне не наследуется измерениями; numeric interval/step/accuracy остаются
разными неразрешёнными ролями. API admission 0/4, новых DB/retrieval/model calls
нет. Следующий bounded шаг — отдельно замороженный query-aware selection experiment
с полным parent локально и проверкой потерь связанных условий/защищённых групп.
Это изменение отбора evidence, а не эквивалентная lossless перепаковка. Новая
selection или появление literal proposal не снимают guards/отказы и не заменяют
независимую научную оценку перед ограниченным inference comparison.

Обновление после [этапа 38](records_stage38_compact_context_2026-10-24.md), 24 октября:
компактный offline wire уменьшен с 8156634 до 200221 байта на прежних четырёх
вопросах. Точные 561 блок, 527 окон и 449 зависимостей сохранены; полные
diagnostics остаются побайтно неизменными локально. Все четыре wire проходят
прежний byte ceiling, но network-ready 0/4: полнота и scientific applicability
не установлены, 22 full-page occurrences и прежние отказы не сняты. Runtime,
provider и источники не менялись; DB/retrieval/model calls нет. Следующий bounded
шаг — source-based проверка полноты контекста и применимости условий с разбором
незавершённых границ, без ослабления full-page guard. Меньше bytes не означает
измеренную экономию inference, токенов или scientific acceptance.

Обновление после [этапа 37](records_stage37_source_context_packet_2026-10-24.md), 24 октября:
локальный сборщик точных блоков/зависимостей сохраняет 527 окон и 19 baseline
Evidence; разрыв методики через формулу входит в одну структурную группу.
6/6 development retention checks не доказывают научную применимость условий.
Дедупликация текста окон 354553 → 127532 байта не доказывает экономию inference:
полный wire с диагностикой занимает 8156634 байта на четыре вопроса, каждый
превышает 100000; network-ready 0/4. Ни runtime, ни provider не менялись;
DB/retrieval/model calls нет. Следующий bounded шаг — компактное представление
для модели с полными локальными диагностическими sidecars, неизменным точным
текстом и отдельно замороженным coverage comparison. Полные страницы и прежние
отказы не разрешать через перенос диагностики или уменьшение сериализованного размера.

Обновление после [этапа 36](records_stage36_metadata_quality_2026-10-23.md), 23 октября:
на всех 23 документах вне stage35 выполнен отдельный source-based аудит прежнего
извлекателя. Ассистент заморозил эталоны до новых предсказаний: авторы 18/23,
год 21/21 известных, журнал 16/21 строгих совпадений. Четыре отказа по авторам,
один `III`/`111` из text layer и пять расхождений пунктуации/пробелов не исправлялись.
Это конечный quality baseline, не независимая научная приёмка или новый holdout.
БД/PDF, provider и runtime не менялись; 76 tests, Ruff/mypy, HTML/source/DB/replay
проверки прошли. Дальше — сохранность научных связей при подготовке контекста;
прежние четыре заблокированных пакета не становятся разрешёнными после этого аудита.
Независимая оценка остаётся отдельной от автоматического рабочего процесса Terms.

Обновление после [этапа 35](records_stage35_bibliography_bridge_2026-10-22.md):
прежний локальный TAC metadata extractor соединён с ingestion и provenance API/UI.
Миграция 0006 хранит source-bound предложения и историю, существующие значения
сохраняются, автоматическая проекция имеет явную ownership-проверку. В 10 статьях
заполнены 26 пустых полей; authors/year 9/10, journal 8/10 — coverage, не accuracy.
Другие 23 статьи и данные вне метаданных неизменны. 2158 tests и Ruff/mypy прошли,
API generation/retrieval не запускались. Повторно писать extractor не потребовалось.
Следующий шаг — independent quality evaluation с сохранением unknown/ambiguous;
архитектура local evidence + replaceable API и текущий provider не меняются.

Обновление после [этапа 34](records_stage34_risk_preparation_2026-10-22.md): аудит
подключён к явному API/UI подготовки с точным текстом, PDF-ссылками, поиском и
полным прежним результатом. На четырёх финальных read-only запросах preparation
совпадает со stage32, audit — со stage33; выбор и scientific admission неизменны,
0/4 network-ready. 2134 tests, Ruff/mypy прошли; generative API calls нет.
Следующий bounded шаг — source-supported author/year diagnostics из начала статьи
с exact provenance и сохранением unknown/ambiguous, без guesses из references.
Текущий provider и архитектура local evidence + replaceable API не менялись.

Обновление после [этапа 33](records_stage33_context_risks_2026-10-22.md): offline
аудит локализует наблюдаемые layout/visual признаки в whole-block/protected
окружении, сохраняя исходные stage32 результаты. 527 диагностических окон,
1549 asset occurrences, 90 trigger records; 29 страниц-вхождений сохраняют
нелокализованную диагностику. Удалённый bbox не доказывает нерелевантность;
22 page occurrences целиком покрываются объединениями диагностических окон.
Это не candidate packet: выбор, qualifiers, byte limits и исходные запреты
сохранены. Retrieval/API calls нет. Далее — показать аудит в UI подготовки без
изменения допуска. Scientific exclusion и качество ответов требуют отдельной
проверки; текущий API-провайдер и архитектурное решение остаются прежними.

Обновление после [этапа 32](records_stage32_block_context_2026-10-22.md): режим
целых PDF-блоков подключён явно к API/UI и сохраняет весь baseline. Реальный
scope — 19 evidence, 35 page occurrences / 863 block occurrences; 30 страниц-
вхождений отложены, 105 предложений относятся к уже отклонённому вопросу, 0/4
technical passes. Перекрывающиеся окна вместе покрывали три полные страницы;
новый union guard блокирует это даже при отсутствии literal matches. Генерации
нет, улучшение научных ответов/экономия не измерены. Далее — versioned локальная
привязка layout/visual risks к блокам и protected context, новый frozen comparison
с сохранением неизвестных/невыбранных источников. Не обходить guard обрезкой,
удалением диагностик или повышением ceiling. Ниже — история решений.

Обновление после [этапа 31](records_stage31_answer_preparation_2026-10-22.md): явный
режим подготовки подключён к API и UI (`/answer/prepare`, `/ui/answer/prepare`).
Он показывает qualifier/source diagnostics и весь выбранный текст без генерации;
старый `/answer` не менялся. На четырёх реальных read-only запросах все прежние
19 evidence сохранены, все контексты блокируются полными страницами. Necessary
qualifiers допускают один; это не scientific acceptance. Следующий шаг — исходные
block contexts с сохранёнными условиями, отрицаниями и unresolved boundaries,
затем новое frozen comparison. Не обходить guard обрезкой старого контекста.
Ниже — история решений; прежние missing metadata задним числом не заполняются.

В live smoke stage31 у выбранных статей отсутствуют авторы/год в записанных
метаданных БД. Режим сохраняет unknown. Source-supported автоматическое заполнение
метаданных — отдельная задача; положительная проверка имени покрыта constructed
tests, а не реально заполненной bibliographic записью в этом прогоне.

Обновление после [этапа 30](records_stage30_query_qualifiers_2026-10-22.md): отдельная
versioned necessary-mention проверка и injectable provider guard реализованы.
Явные material phrases, автор/год и finite method/property mentions должны быть
в одной статье; missing metadata остаётся unknown. На четырёх сохранённых контекстах
допуск 3 → 1, все 19 evidence сохранены. 24/24 constructed agreements не являются
независимой scientific accuracy. Production default и thresholds не менялись;
никаких новых API/retrieval calls. Следующий шаг — явный режим подготовки ответа
с диагностикой новой проверки, отдельно оцениваемые дополнительные вопросы и
сохранение отдельного complete-page guard. Наличие mentions не доказывает научный
вывод; stage29 packets по-прежнему 0/4 network eligible. Ниже — история решений.

Обновление после [этапа 29](records_stage29_query_packet_2026-10-22.md): additive
query evidence packet реализован отдельно от runtime. На четырёх замороженных
вопросах сохранены все 19 baseline evidence; две привязки относятся к одному
отдельному контролю, transfer-привязок нет. Полные страницы остаются во всех
пакетах: 0/4 network eligible, сжатие и улучшение ответов не установлены. Новых
generative API calls нет; существующие локальные query embeddings использовались.
Gate пропускает вопросы при missing Istomina/DSC и Mars/regolith. Следующий шаг —
отдельно замороженная проверка обязательных уточнений запроса и достаточности
evidence до платного сравнения ответов и compaction. Production thresholds и
прежние результаты не исправлялись. Нижележащие абзацы сохраняют историю решения.

Обновление после [этапа 28](records_stage28_protocol_association_2026-10-22.md):
отдельный sentence-ID contract и native Responses comparison реализованы на пяти
exposed development контекстах. Все 11 целей source-integrity-valid; API/baseline
category agreement 6/7 transfer и 4/4 separate control не устанавливает научную
точность. DSC/conductivity различены в предложениях, origin остаётся непроверенной
декларацией; production integration и другие провайдеры не подключены. Следующий
bounded шаг — query evidence packet с сохранением связанных предложений и
неопределённостей, затем отдельное сравнение контекстов ответа. Пятизапросный
live budget stage28 исчерпан. Следующие абзацы сохраняют исходное решение до
реализации stage28, а не требуют повторить этот прогон.

Сохранить цель этапа 28: связь «свойство → метод → условия», включая различение
DSC и проводимости. API-based сравнение на замороженных пакетах рассматривать
как способ проверить эту задачу наряду с локальным baseline, а не как доказанный
способ её решения. Точный протокол следующего этапа ещё предстоит зафиксировать.

До сравнения заморозить вопросы, источники, правила подготовки контекста,
референсы/их статус, настройки, бюджеты и метрики. Оценивать правильность научных
связей, неподтверждённые утверждения, пропуски и отказы, время и фактический расход
по usage всех запросов. Сохранять запросы, raw responses, модель/версию, source
и code hashes; offline replay ответа не выдавать за детерминизм нового вызова.
Независимая научная оценка остаётся отдельной от разработки и от рабочего процесса
Terms. Реализация адаптеров, новые API-вызовы и аппаратные закупки в этом шаге
не выполняются.

## Основания и ссылки

- [`app/generation/providers.py`](../app/generation/providers.py): `AnswerProvider`,
  `OpenAIAnswerProvider`, структурированные claims/citation IDs.
- [`app/generation/service.py`](../app/generation/service.py): runtime factory,
  evidence selection, adequacy gate и проверка citation IDs.
- [`app/records/openai_backend.py`](../app/records/openai_backend.py): отдельный
  Responses backend и source checks.
- [Stage04](records_stage04_openai_2026-10-20.md): реальные API-попытки и отклонённая
  отсутствующая цитата; конечный development scope не доказывает общую accuracy.
- [Stage27](records_stage27_condition_multilingual_2026-10-22.md): границы конечной
  RU/EN policy и пример generic DSC measurement wording.
- [Yandex: структурированный вывод](https://aistudio.yandex.ru/ru/docs/ai-studio/operations/generation/completions-structured).
- [GigaChat: структурированный вывод](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output).
- [Cloud.ru: внутренние и внешние модели](https://cloud.ru/docs/foundation-models/ug/topics/overview__available__models).
- [OpenAI: обработка данных](https://developers.openai.com/api/docs/guides/your-data).

Документация провайдеров просмотрена в обсуждении 22 октября 2026 года; конкретные
модели, тарифы и условия необходимо повторно проверить перед подключением.
