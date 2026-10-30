# ARIADNE: дорожная карта

Обновление 2026-10-30, [два разрешённых live-ответа](user_questions_live_2026-10-30.md):
после явного разрешения пользователя выполнены ровно два model POST и два OAuth,
оба HTTP200 / answered / stop, без повторов; оба новых slots consumed/closed.
Usage18822 input +266 output =19088 tokens; денежная стоимость неизвестна.
Исходные ответы сохранены: q1 неверно обобщает большинство строк своей таблицы
(Li>H4/9, Li<H5/9); q2 не обосновывает глобальную лучшую смесь и пропускает
состав/условия. Q3 остался исходным отказом до модели, coverage0.25.
Два offline ASGI replay идентичны целиком; 293 bindings, 13 fresh PDF pages,
восемь визуально проверенных страниц, график и static HTML QA прошли.
Независимого эталона нет, научная приёмка не достигнута; общий прогресс75%.
Следующая работа: offline-разбор численного сравнения/критерия «лучше»/отказа q3.
Новых calls или повторов автоматически нет. Runtime в этой итерации не менялся.

Обновление 2026-10-30, [три новых пользовательских вопроса](user_questions_preparation_2026-10-30.md):
пункт 4 начат, общий прогресс остаётся 75%. Дословные вопросы подготовлены
через настоящий /answer с read-only DB/local index и без внешней генерации.
Первые два достигли provider boundary (55341/40073 bytes), третий — HTTP 200 /
insufficient_evidence, coverage 0.25, без native request. В выбранном E1 есть
описание LiOH exchange; это source hint, не обход gate/независимый эталон.
105 tests, Ruff, 23 fresh PDF pages/5 works и static review QA прошли.
HTML review_v02: все три вопроса, пять TAC works, 18 existing file links.
Новых model/OAuth calls, slots и разрешений нет. Возможный следующий scope —
только два отдельно разрешённых новых вызова для q1/q2, не q3. Темы уже
пересекаются с regression datasets; independent reference answers отсутствуют.

Обновление 2026-10-30, [представление ответа](answer_presentation_implementation_2026-10-30.md):
пункт 3 реализован и проверен offline/в браузере; [прогресс плана](answer_quality_progress_2026-10-30.md)
— 75% работ (3/4), не научная точность. UI показывает title/page links и полный
raw context у claim из request-local observer, сохраняет layer/identity,
отмечает missing context и отделяет derived tables. Новый GigaChat user prompt
задаёт вывод/условия/определение/источник/ограничения; воздействие на новые
model answers не проверено. API schema, scientific validation, ranking и
token limits не менялись. 174 tests + 15 отдельных API tests, Ruff и mypy app
(181 files) прошли; три прежних native outputs/claims сохранены, три новых
prompt candidates не отправлены. Проверены 19 страниц/5 PDF, 12 source contexts,
14 index links. Browser QA: swelling source disclosure и TAC filter Istomina
1/5; mobile/PDF opening не проверены. Final review_v03 сохраняет before/after,
старые отчёты/бюджеты неизменны; новых model/OAuth/DB calls нет. Старые current-code
bindings обнаружат объявленный app/provider drift; не обходить guards.
Независимая оценка остаётся открытой: пользователь подготовит новые вопросы.

Обновление 2026-10-30, [offline-проверка области ответа](answer_scope_audit_2026-10-30.md):
пункт 2 завершён как отдельный finite diagnostic; [журнал выполнения](answer_quality_progress_2026-10-30.md)
фиксирует 50% работ плана (2/4), не accuracy. Сохранённые claims/citations
проверяются по exact page anchors с раздельными universe/form/temperature/medium/
basis/operation diagnostics. Исходный контекст даёт 1.54/1.536 на с.96;
post-hoc страницы добавляют H 2.3 и Li 1.8 на с.75. Только Li 1.8 попадает в
larger same-form review candidates; все четыре relations unresolved,
научных подтверждений 0. Room temperature/25°C, диапазоны/точки, проценты/α,
H/Li, captions/value conditions не отождествляются. 188 tests, Ruff,
diagnostic-module mypy, 12 constructed/3 native operation replays прошли;
18 страниц/6 PDF совпали со свежим text extraction. Более широкий runner
mypy не прошёл на существующем smoke-module и untyped fitz; ошибки сохранены.
HTML review_v02 включает шесть работ union scope и 12 существующих file links;
browser execution не проверен. Production code/ranking и старые результаты
не менялись, новых API/OAuth/DB calls и slots нет. Далее — представление
ответа и независимая оценка; полная semantic ownership validation и
cache/ORM repeated-request дефект остаются открытыми.

Обновление 2026-10-30, [локализация пропуска Li-Nafion evidence](swelling_retrieval_loss_2026-10-30.md):
пункт 1 [четырёхпунктного плана качества](answer_quality_plan_2026-10-30.md)
завершён — 25% работ плана, не научная точность. Отдельный read-only capture
совпал с полной итоговой трассой 29 октября. Два chunks с точным контрпримером
с.75 проходят исходный поиск, fusion и feature window, занимают места 17/18
после feature ranking и 60/61 после article diversification; top-5 исключает
их до answer evidence selection. Это диагноз воспроизведения: исторические
внутренние стадии отсутствуют. Сравнение форм включается glossary variants,
но изменение ranking, лимитов и научная валидация не выполнены. 82 tests,
Ruff, mypy diagnostic module и девять границ/full-trace offline replay прошли;
намеренно повреждённая граница отклонена. HTML review_v02 включает все 33
работы-кандидата, static QA — 35 file links; browser execution не проверен.
Ошибки первых capture (sandbox DB denial и путь exporter) сохранены в отчёте.
Новых model/OAuth calls и slots нет; runtime, PDF и старые outputs неизменны.
Далее — offline-проверка области максимума, температуры, смеси и принадлежности
величин; оформление ответа и независимая оценка открыты. Cache/ORM повторных
запросов остаётся отдельным неисправленным эксплуатационным дефектом.

Решение пользователя 2026-10-29, [оформление научного ответа](answer_presentation_requirements_2026-10-29.md):
зафиксирован предпочтительный формат: вывод → условия и определение величины →
читаемая кликабельная ссылка на работу/страницу → точный подтверждающий фрагмент →
ограничения. Одна короткая фраза с `[E1]` недостаточна; объём определяется
содержанием доказательств, без искусственного удлинения. Реализация и проверка
оформления остаются открытыми; runtime, API schema и бюджеты не изменены.

Обновление 2026-10-29, [вопрос пользователя о максимальном набухании Li-Nafion](user_swelling_answer_test_2026-10-29.md):
реальный ASGI `/answer` с production hybrid_cross_lingual, БД/локальным индексом,
top-k 5 и GigaChat вернул HTTP 200 / answered: «αLi = 1.54». Выполнены ровно
1 OAuth + 1 model POST, без повторов; новый бюджет закрыт. Отдельная сверка
того же PDF выявила контрпример: около 1.8 для Li-формы в воде/2-пропаноле
при 25°C и массовой доле спирта около 0.4-0.5 (с.75, рис.3.8). Страница не
попала в evidence модели. 1.54 на с.96 относится к регрессионному пределу;
таблица индивидуальных растворителей на с.88-89 даёт 1.54 при 25°C, но не
охватывает смеси. Общий максимум по корпусу не установлен. 96 software tests,
Ruff и точный offline ASGI replay прошли; первоначальный replay завис в
песочнице, тот же код вне неё завершился без БД/provider calls. Проверены
8 captured pages, 4 post-hoc страницы и 6 PNG полных страниц. HTML review_v02
сохраняет фактический ответ, научный разбор и 3 TAC rows. Runtime не изменён;
источники/отказы/старые бюджеты сохранены. Нужна проверка покрытия максимума
с учётом смесей и температуры; стадия потери страницы пока не локализована.

Обновление 2026-10-29, [offline-диагностика областей операции и величины](event_value_ownership_audit_2026-10-29.md):
добавлен отдельный finite RU/EN слой по raw source и точным spans, без чтения
reference labels, вопросов и kind модели. На трёх сохранённых replies отмечены
3 переноса из очистки: время в протонирование, время/температура в сушку; ещё
2 at_least не имеют распознанного указателя границы. Это диагностика областей,
не доказательство семантического владельца. На 12 constructed fixtures —
15 local-unverified, 10 unresolved и 39 missing/unevaluated field rows;
научных подтверждений — 0. Initial review_v01 сохранил две ложные тревоги из-за
разрыва на «мас.»; final review_v02 помечает такую границу unresolved.
180 affected tests (40 новых + 140 прежних), Ruff и mypy audit-модуля прошли.
Все 8 страниц / 5 PDF совпали с новым извлечением; три native replay идентичны.
HTML review_v02: 12 случаев, 3 отдельные model sections, 5 TAC rows.
API/OAuth/DB operations и новые slots — 0; `/answer`, старые outputs и закрытые
бюджеты сохранены. Общая семантическая проверка и независимая оценка остаются открытыми.

Обновление 2026-10-29, [live-пилот точных фрагментов v0.2](event_span_live_pilot_v02_2026-10-29.md):
выполнены 3 OAuth и 3 model POST по новым ограниченным slots, без повторов.
Все finish_reason=stop, три output прошли native JSON Schema и local source
integrity. Научная готовность не подтверждена: протонированию и сушке присвоены
2 ч очистки H2O2; в сушку также перенесена температура очистки. Обе длительности
необоснованно помечены at_least. Выдержка 2 часа и критерий без времени выбраны,
но роли/полнота событий остаются проблемными. Diagnostic — Ф / Ф / Д.
140 affected tests (12 новых + 128 прежних) и Ruff новых driver/replay/tests
прошли. Три offline replay воспроизвели полные output; три страницы заново
совпали с PDF, старые отказы/slots сохранены. HTML review_v02: 3 случая / 3 TAC
rows, с явным научным разбором ассистента. Это exposed cases, не accuracy.
Бюджет пилота исчерпан; оставшиеся 9 offline candidates не отправлены и не имеют
автоматического live-разрешения. `/answer` не изменён. Далее — offline-проверка
владельца величины/операции и отдельная независимая оценка.

Обновление 2026-10-29, [контракт событий по точным фрагментам v0.2](event_spans_v02_2026-10-29.md):
реализованы отдельный контракт/parser, нейтральные адреса токенов и 12
неотправленных GigaChat-запросов. Разные операции внутри предложения могут
иметь отдельные фрагменты; diagnostic и status/span alternatives согласованы
в native schema и локальных structural models. Дополнительные ограничения
source integrity явно проверяются локально. 128 affected tests (71 новый + 57
прежних), Ruff пяти новых файлов и mypy двух модулей прошли. Локальный
jsonschema проверил 12 schemas/constructed fixtures и 12 отрицательных/source
integrity controls; поддержка провайдером не проверена. Все 8 страниц / 5 PDF
совпали с новым извлечением. 32 события, 7 связей и 42 полевых проверки составлены
ассистентом для разработки, не являются ответами модели или accuracy.
HTML review_v02: 12 случаев / 5 TAC rows. API/OAuth/DB operations и новые slot
reservations — 0; `/answer` и старые результаты сохранены. Далее — отдельно
ограниченный pilot и независимая научная оценка, без автоматического вызова API.

Обновление 2026-10-29, [offline-сравнение длительности и операции](event_duration_evaluation_2026-10-29.md):
добавлен оценщик по явной предварительной разметке, без семантического
извлечения и подключения к `/answer`. На трёх прежних rejected replies
воспроизведены исходные отказы; отдельно обнаружены два владельца длительности
в одном event: сушка 1 ч и хранение 2 недели. Совпадение трёх raw target duration
fields с разметкой не превращает ответы в принятые и не является accuracy.
Разметка ассистента post hoc; независимой оценки нет. 57 affected tests
(33 новых + 24 прежних), Ruff и mypy evaluator прошли. Два ранних общих прогона
имели ошибки доступа к temp; финальный прогон с новым project-local temp прошёл.
Все три страницы совпали с новым извлечением PDF. HTML review_v01: 3 случая,
3 TAC rows. API/OAuth/DB operations — 0; старые outputs и закрытые slots сохранены.
Далее — семантический метод и независимая оценка, а не runtime-допуск по этим меткам.

Обновление 2026-10-29, [три live-запроса извлечения событий](gigachat_event_pilot_2026-10-29.md):
выполнены 3 model POST и 3 OAuth, без повторов. Все finish_reason=stop,
принятых output — 0. В двух случаях первый отказ вызван ошибкой нашего
контракта: native schema разрешала пустой diagnostic, локальный parser
запрещал. В третьем — not_found с непустыми IDs. Raw-ответы и отказы
сохранены. Отдельный offline-кандидат schema v0.2 добавляет nonblank diagnostic;
не отправлялся, поддержка новых ограничений провайдером не проверена.
17 preflight tests + 7 regression tests прошли. В raw target корректно
отделено отсутствие времени протонирования от 2 ч очистки, но другой event
слил сушку 1 ч и хранение 2 недели. Это не scientific acceptance/accuracy.
HTML review_v02 содержит 3 случая и 3 работы. /answer не изменён. Все три
новых slots и старые бюджеты исчерпаны; дополнительных API calls нет.

Обновление 2026-10-29, [12 реальных экспериментальных фрагментов](real_experiment_cases_2026-10-29.md):
собраны 12 точных интервалов из 5 работ / 8 страниц, с вопросами и
предварительной разметкой ассистента. Все страницы совпали с повторным
извлечением из исходных PDF. Неизменённый прототип нашёл 1 из 7 размеченных
зависимостей, пропустил 6; две помеченные границы операций не нарушены.
Совпадение — уже известный пример Каюмова. Это exposed development set,
не independent gold или accuracy. 8 новых scoring tests, Ruff evaluator
scripts и mypy scorer прошли. HTML review_v02: 12 случаев / 5 TAC rows.
API/OAuth/DB calls — 0; ответы LLM на вопросы не генерировались. Runtime,
старые результаты и закрытые slots сохранены. Дальнейшая семантическая
реализация и независимая оценка остаются открытыми.

Обновление 2026-10-29, [offline-зависимости между фразами эксперимента](experiment_sentence_links_2026-10-29.md):
добавлен отдельный граф явных соседних отсылок; подготовка, смена образца/
метода, отрицания, условия и разрыв абзаца блокируют предложение связи.
113 tests (32 новых + 81 прежних), Ruff и mypy модуля прошли. На 21 exposed
constructed case — 0 расхождений с заданными ожиданиями; это не independent
accuracy. На реальных источниках — 11 повторений одной физической связи
через точку с запятой на p.3 Каюмова. Полноценные межпредложенческие связи
реальными данными не подтверждены. Все прежние 112 context statuses остаются
unresolved; значения и условия не переносятся. HTML review_v02: 8 случаев,
6 документов. API/OAuth/DB calls — 0; runtime и старые slots сохранены.

Обновление 2026-10-29, [offline-связи величины, эксперимента и источника](requested_context_links_2026-10-29.md):
создан отдельный прототип требований вопроса и точных source anchors, с
диагностикой стадии, образца, метода, статьи, условий, отрицаний и диапазонов.
На 8 сохранённых случаях — 112 повторяющихся source candidate occurrences
с точными привязками к страницам; все связи с экспериментом unresolved.
81 test (47 новых + 34 прежних), Ruff, mypy чистого модуля и статическая
проверка HTML прошли. Это ограниченный finite-grammar prototype, не semantic
coverage validator и не runtime gate. HTML review_v04: 8 случаев, 6 документов.
Новых API/OAuth/DB calls — 0. Далее — извлечение событий с явными зависимостями
контекста и независимая оценка; runtime и закрытые budgets/slots сохранены.

Обновление 2026-10-29, [offline-диагностика запрошенной информации](requested_information_audit_2026-10-29.md):
добавлен отдельный лексический аудит длительности, без подключения к `/answer`.
На 8 сохранённых результатах отмечены оба ответа без выражения времени;
3 отклонённых output и 1 отказ модели учитываются отдельно. 34 constructed
unit tests, Ruff, mypy чистого модуля и проверка frozen outputs прошли.
Число с единицей времени остаётся unverified: связи с образцом, методом,
стадией и условиями не доказаны. Границы следующей semantic coverage
реализации записаны в отчёте. HTML review_v02 содержит все 8 случаев и
6 документов. Новых API/OAuth/DB calls — 0; runtime, старые outputs/slots
и ограничения кэша сохранены.

Обновление 2026-10-29, [live-пара: время и критерий](gigachat_answerability_pair_2026-10-29.md):
новая инструкция не устранила повторный сбой: точное время снова заменено
критерием равновесия при HTTP 200 / answerable=true. Контрольный вопрос
о критерии получил provider finish_reason=blacklist и HTTP 502; причина
фильтрации неизвестна. Два offline ASGI replay воспроизвели полные ответы,
Ruff и статическая проверка HTML прошли. Сохранены четыре документа, точные
источники и raw replies. Два model calls и два OAuth использованы, повторов
нет. Это exposed development cases, не независимая accuracy. Далее — offline
проектирование проверки покрытия запроса и диагностики фильтра провайдера;
новые live calls автоматически не разрешены, все старые slots закрыты.

Обновление 2026-10-29, [инструкция ответимости](gigachat_answerability_instruction_2026-10-29.md):
в GigaChat claims/mini_review добавлено общее требование отвечать именно на
запрошенную величину/факт; критерий или соседний этап не заменяет точное
значение. Качественный ответ на вопрос о методе/критерии разрешён. 180 affected
tests, 15 overlapping style cases и Ruff/mypy прошли; новых API calls — 0.
Это user instruction, не local semantic validator: старый недостаточный ответ
по-прежнему принимается format parser при replay. Эффект на модели не проверен.
Следующая отдельная live-пара должна проверить точную величину и допустимый
качественный ответ; старые slots закрыты.

Обновление 2026-10-29, [live двух отказов](gigachat_abstention_live_2026-10-29.md):
оба новых вызова дали HTTP 200 и согласованный формат. Реголит — ожидаемый
false/claims=[]; точная длительность выдержки — answerable=true с критерием
равновесия без требуемого времени. Ожидаемый отказ наблюдался в 1 из 2
повторных development cases, не independent accuracy. Offline ASGI replay
воспроизвёл оба ответа; usage 20926 input / 105 output. Бюджет 2 calls исчерпан.
Далее — offline-уточнение ответимости относительно запрошенной величины,
без hard-coded вопросов, ремонта ответов или автоматических API calls.

Обновление 2026-10-29, [контракт недостаточности данных](gigachat_abstention_contract_fix_2026-10-29.md):
в GigaChat claims/mini_review добавлена явная инструкция answerable=false ->
claims=[] и запрет объясняющих claims при отказе. Схема, parser и строгая
проверка согласованности сохранены. 168 affected tests, Ruff/mypy и offline
ASGI replay прежних 200/200/502/502 прошли; новых API calls — 0. Работа новой
инструкции на модели ещё не проверена. Старый бюджет 4 calls исчерпан.

Обновление 2026-10-29, [четыре новых вопроса GigaChat](gigachat_answer_batch_2026-10-29.md):
четыре model calls завершены: 2 HTTP 200 и 2 HTTP 502. В обоих запросах
с недостаточными данными модель выдала answerable=false с непустым claims;
отказы сохранены, корректными abstentions не считаются. Основные условия
принятых ответов поддержаны источниками, но в сравнении есть смысловой нюанс
и широкая дополнительная ссылка. 82 software tests и 4 offline ASGI replay
прошли; usage 45071 input / 657 output. Исходная подготовка в одном процессе
дала 3 DetachedInstanceError; финальные случаи выполнялись в отдельных
процессах с прежними настройками кэша. Бюджет 4 вызовов исчерпан. Далее —
отдельная offline-правка согласованности answerable/claims; независимой
научной приёмки и общей accuracy нет.

Обновление 2026-10-29, [live после правки IDs](gigachat_citation_live_2026-10-29.md):
один новый вызов текущего ASGI `/answer` вернул HTTP 200 и два утверждения с
точным ID `E1`. Вопрос, автоматические evidence и sources совпали с прежним
тестом; offline ASGI replay воспроизвёл весь ответ. Разбор ассистентом нашёл
поддержку обоих утверждений в E1 / original layer p.3; независимой научной
приёмки и общей accuracy нет. Usage 14106 input / 139 output. Новый слот
исчерпан; далее — отдельный ограниченный набор новых вопросов и отрицательных
контролей, без автоматических model calls. Сжатие контекста остаётся отложенным.

Обновление 2026-10-29, [правка citation IDs](gigachat_citation_ids_fix_2026-10-29.md):
GigaChat получает request-local enum допустимых IDs и явную инструкцию точного
формата для claims/mini_review. Сервис по-прежнему отклоняет `[E1]`, пробелы
и чужие IDs; исправления ответа задним числом нет. 155 affected tests, Ruff/mypy
и offline capture/replay прошли; новых model/API calls — 0. Реальная проверка
новой схемы и научная приёмка открыты; прежние outputs/slots сохранены.

Обновление 2026-10-29, [live /answer smoke](gigachat_answer_smoke_2026-10-29.md):
текущий ASGI `/answer` выполнил один запрос GigaChat на автоматически выбранных
5 фрагментах / 3 документах. Ответ отклонён HTTP 502: `"[E1]"` вместо ID `"E1"`;
JSON разобран, citation validation сработала. Usage 14041 input / 142 output;
69 affected tests и offline replay прошли. Первый OAuth был заблокирован sandbox
до генерации и сохранён отдельно; вне sandbox выполнено одно зафиксированное
продолжение, общий model budget исчерпан. Научной приёмки нет. Далее — отдельная
минимальная правка формата citation IDs, без автоматического повторного вызова.

Обновление 2026-10-29: по решению пользователя основной answer runtime
переключён на `gigachat` / `GigaChat-2-Max`. Фабрика ответов принимает только
GigaChat; OAuth, structured output, TLS и citation validation проверены offline.
Новый live API-запрос в рамках переключения не выполнялся. Локальные embeddings,
индексы, PDF/БД и исторические frozen experiments сохранены. Два DSC-опыта
28 октября описаны отдельно: первый ответ отклонён, named-span версия прошла
source-integrity contract на одном exposed case. Независимая научная оценка
остаётся открытой. [Отчёт переключения](gigachat_runtime_switch_2026-10-29.md).
Прежние обновления ниже относятся к своим историческим snapshots.

Отложенная задача, 2026-10-29: измерять степень сжатия контекста относительно
фактического запроса к LLM. Отдельно учитывать исходный текст, переданные
доказательства с повторами, полный запрос со служебной частью и входные токены
провайдера; не смешивать сокращение объёма с научной сохранностью доказательств.
Идея сохранена для последующей реализации; новый общий счётчик не добавлен.
[Определения и ограничения](mvp_inference_strategy_2026-10-22.md#отложенная-задача-степень-сжатия-контекста-llm).

Обновление 2026-10-27: [stage49](records_stage49_dsc_experiment_2026-10-27.md)
выполнил пункт 3: frozen question/source/prompt/model/budget/criteria и полный
8712-byte Responses request. Budget одного будущего вызова без retry/fallback,
4096 output tokens, 180 s; исторический alias, live compatibility/pricing unknown.
Result template явно not_executed; offline response inspector не является API-run.
57 affected tests, Ruff/mypy, HTML/PDF-link QA и 20 byte-identical export files
прошли. Старые inputs и workflow сохранены; API/model/retrieval/embedding/DB calls
нет, network_ready=false. Далее — пункт 4 при явном снятии запрета API и с durable
attempt/result ledger; реальный executor ещё не реализован.

Обновление 2026-10-27: [stage48](records_stage48_dsc_admission_2026-10-27.md)
выполнил пункт 2 pre-API плана. Новый DSC source packet прошёл 14/14 checks;
source eligibility отделена от научной приёмки и сетевого исполнения. 12 старых
blockers и семь файлов stage47 сохранены; current source blockers — 0,
network_ready=false. 85 affected tests, Ruff/mypy, source/HTML/PDF-link QA и
11 byte-identical export files прошли. API/model/retrieval/embedding/DB calls нет.
Далее — пункт 3: frozen experiment contract, без реальных вызовов при запрете API.

Обновление 2026-10-27: [stage47](records_stage47_dsc_context_2026-10-27.md)
выполнил пункт 1 плана до API: отдельный DSC source packet Istomina, четыре
identity цитаты и полный раздел 2.4 с physical p.4, без соседних WAXD/AC разделов.
Wire 4346 bytes, source registry отдельно; старые пакеты/PDF/metadata неизменны.
59 affected tests, Ruff/mypy, source/HTML/PDF-click QA и 7 byte-identical export
files прошли. API/model/retrieval/embedding/DB calls нет, network_ready=false.
Следующий пункт — отдельная проверка допуска нового пакета; она ещё не выполнена.

Обновление 2026-10-27: [stage46](records_stage46_evidence_gaps_2026-10-27.md)
выполнен по решениям грилла: четыре прежних вопроса, полный original text layer
11 PDF / 273 страниц. Отдельно подтверждён source header Istomina 2021; DSC
раздел на физической стр. 4 найден вне прежнего пакета. 2158 matching blocks /
6657 literal spans — кандидаты, не научное принятие; связи не назначались.
Отрицательный контроль отделён от содержательных вопросов. 90 targeted tests,
Ruff/mypy, source/HTML/PDF-click QA и два экспорта 55 byte-identical files прошли.
Исторические пакеты/metadata/PDF сохранены; API/model/retrieval/embedding/DB calls
нет, admission 0/4. Далее — отдельный source-bound контекст запрошенной Istomina
для DSC-вопроса с полным разделом 2.4 и сохранением прежних guards.

Обновление 2026-10-27: [stage45](records_stage45_sample_identifiers_2026-10-27.md)
добавил отдельный sample/table identifier audit. Прежние 561 blocks / 1148 events,
selection и wires сохранены; одна source-only supplemental table зарегистрирована
отдельно, 21 строка. Текущие PDF text/blocks/lines проверены; старый stage23 replay
не принят при изменённом pyproject.toml, mismatch сохранён. Три selected sample
mentions имеют по кандидату строки Table 2, все три unresolved; методика/условия
строкам не назначены, plasticiser composition не переименована в membrane/environment.
8/8 source checks, 1/1 catalog check, 78 targeted tests и Ruff/mypy прошли.
Все десять TAC документов сохранены; новых API/model/embedding/retrieval/DB calls
нет, admission 0/4. Далее — локальный аудит полноты цепочек sample/method/condition
с новыми source endpoints и unresolved cases, без назначения связей по соседству.

Обновление 2026-10-27: [stage44](records_stage44_condition_applicability_2026-10-27.md)
добавил отдельные same-event condition links без API и без смены отбора. Среди
155 selected events — 38 condition occurrences: 2 measurement-context и
4 protocol-parameter proposals, 10 preparation-only, 22 unresolved. Range/step/
accuracy различены без numeric normalization; generic sample остаётся классом,
scientific applicability не подтверждена. Все 561 blocks / 1148 events, прежние
wires, PDF и отказы сохранены. 12/12 checks, 48 targeted tests и Ruff/mypy прошли.
Все десять TAC документов доступны отдельно. CLI запрещает Python socket/DNS
operations; model/embedding/retrieval/DB calls нет, admission 0/4. Далее — локальные
explicit sample/table identifiers и ссылки на них с отдельными abstention cases;
не назначать конкретный образец из общего соседства текста.

Обновление 2026-10-27: [stage43](records_stage43_source_origin_2026-10-27.md)
добавил полностью локальный origin/applicability audit всех 561 source blocks и
1148 events. Прежний отбор 62 блоков / 155 events, все wires и отказы сохранены.
Section hints — геометрические proposals, own-work origin/sample identity и
applicability не назначены. 134 selected events остаются origin unknown, ещё 16
citation-only unknown; научной приёмки нет. 21/21 development checks, 51 targeted
tests, дополнительный HTML-тест и Ruff/mypy прошли. Поиск/раскрытие/selected filter,
empty refused scope и TAC десять документов/восемь колонок проверены в браузере.
Новых model/embedding/retrieval/DB calls нет; локальные CLI фазы работают с
запрещёнными Python socket/DNS operations. Admission остаётся 0/4. Далее —
source-bound method/condition applicability и abstention cases на frozen inputs;
это локальная работа, не зависящая от доступности API.

Обновление 2026-10-26: [stage41](records_stage41_sample_scope_2026-10-26.md)
добавил finite membrane/SEI scope audit всех 113 parent units, 22/22 development
checks. [Stage42](records_stage42_sample_selection_2026-10-26.md) отложил четыре
целых Guo/SEI units: 142 → 62 блока, wire 81189 → 67247 байт, полных страниц
1 → 0. Unknown/mixed/unsupported-query units сохраняют прежний отбор; sample
identity и scientific relevance не установлены. Все parents/diagnostics остаются
локально; все десять TAC документов доступны в отдельных HTML каждого этапа.
40/40 source expectations и 60 targeted tests прошли, Ruff/mypy — без ошибок.
Scientific loss не измерена; API admission остаётся 0/4. Runtime/DB/retrieval/model
calls нет. Далее — source-based origin/applicability audit retained фрагментов
(собственная методика, обсуждение, bibliography, unresolved), с новым frozen
comparison и отдельными false-retention/deferral cases до admission upgrade.

Обновление 2026-10-24: [records stage40](records_stage40_query_selection_2026-10-24.md)
реализовал отдельный query-aware selection: 142/561 блоков, wire 200221 → 81189
байт, full-page occurrences 22 → 1. Смена selection учтена явно: 116 целых окон,
37 частичных, 374 отложенных; все parents локально побайтно неизменны. Все пять
protected-group occurrences отложены целиком, их научная ненужность не доказана.
11/11 development checks, 179 targeted tests, Ruff/mypy и source/HTML/export QA
прошли; scope TAC — все десять документов. Guo/SEI демонстрирует over-inclusion:
implicit sample/material scope не реализован. Scientific loss не измерена, API
admission 0/4. Далее — sample/material scope с unknown и отдельной проверкой
false inclusions/exclusions; runtime/DB/retrieval/model calls нет.

Обновление 2026-10-24: [records stage39](records_stage39_context_completeness_2026-10-24.md)
разобрал 35 страниц-вхождений, 1148 source events и 449 зависимостей. Все 22 полные
страницы возникают из union прежних окон; single full-page windows и добавления
closure — 0. Одна уникальная literal cooccurrence proposal повторена в двух
вопросах, научная применимость условий не установлена. 9/9 development checks,
170 targeted tests, Ruff/mypy и source/HTML/export QA прошли; все десять TAC
документов сохранены. Прежние packets/diagnostics побайтно неизменны, допуск к API
0/4, DB/retrieval/model calls нет. Далее — отдельный query-aware selection experiment
с оценкой потерь связанных условий/групп; это смена selection, не lossless перепаковка.

Обновление 2026-10-24: [records stage38](records_stage38_compact_context_2026-10-24.md)
уменьшил четыре model-facing wire с 8156634 до 200221 байта. Весь выбранный
текст сохранён: 561 блок, 527 окон, 449 зависимостей; полные diagnostics этапа 37
побайтно сохранены локально. Каждый wire проходит прежний лимит 100000, но
network-ready 0/4: 22 полных страницы-вхождения и прежние отказы не сняты.
125 targeted tests, Ruff/mypy, source/HTML QA и повторный экспорт прошли.
Runtime не подключён, новых DB/retrieval/model calls нет. Далее — source-based
полнота контекста и применимость условий, без обхода full-page guard.

Обновление 2026-10-24: [records stage37](records_stage37_source_context_packet_2026-10-24.md)
добавил отдельный локальный пакет точных блоков и структурных зависимостей.
527 исходных окон восстанавливаются из 561 блока; сохранены 19 baseline Evidence.
Разрыв методики через блоки формулы теперь входит в одну группу; 6/6 development
retention checks прошли без научного назначения условий. Уникальный текст занимает
127532 байта вместо 354553 байт повторяющихся окон, но wire вместе с диагностикой —
8156634 байта на четыре вопроса; все четыре превышают прежний лимит, 22 полные
страницы-вхождения сохраняются, network-ready 0/4. Это не экономия токенов или
научная приёмка. Runtime не подключён; новых DB/retrieval/model calls нет.
94 tests, Ruff/mypy прошли. Далее — компактное представление для модели с полной
локальной диагностикой и отдельно замороженной проверкой покрытия, до платных ответов.

Обновление 2026-10-23: [records stage36](records_stage36_metadata_quality_2026-10-23.md)
проверил неизменённый metadata extractor на всех 23 документах вне scope этапа 35.
Эталоны ассистента и правила заморожены до новых предсказаний: авторы 18/23,
год 21/21 известных, журнал 16/21 строгих совпадений. Четыре отказа по авторам,
один source-text `III`/`111` и пять расхождений точек/пробелов сохранены; последние
не означают пять подмен журналов. Unknown не заполнены; независимой человеческой
приёмки нет, корпус ранее использовался в TAC-разработке. 76 tests, Ruff/mypy,
HTML search/expansion и точные source/replay/DB проверки прошли. БД/PDF и алгоритм
не менялись. Далее — подготовка контекста ответа с сохранением научных связей;
этот аудит не снимает прежний запрет отправки четырёх пакетов модели.

Обновление 2026-10-22: [records stage35](records_stage35_bibliography_bridge_2026-10-22.md)
подключил существующий TAC metadata extractor к импорту/дубликатам/переотбору
текста без изменения его алгоритма. Миграция 0006 хранит exact source evidence,
версии, raw alternatives и историю проекции. Заполнены 26 пустых полей 10 статей:
authors 9/10, year 9/10, journal 8/10; это coverage, не accuracy. 23 другие статьи
и данные вне метаданных не менялись. Read-only API/UI показывает происхождение;
2158 tests и Ruff/mypy прошли, real ingestion/duplicate rollback и idempotence
проверены. Генерации/retrieval нет. Далее — отдельная независимая проверка качества
метаданных и unresolved layouts, без подгонки текущих Guo/Choi под ожидаемые значения.

Обновление 2026-10-22: [records stage34](records_stage34_risk_preparation_2026-10-22.md)
подключил аудит к явному API/UI `/answer/prepare/blocks/risks` и
`/ui/answer/prepare/blocks/risks`. Полный текст, PDF-ссылки, поиск, unknown и прежняя
подготовка доступны вместе; выбранная библиотека сохраняется при переходе.
Четыре финальных read-only API-запроса полностью совпали со stage32 preparation
и stage33 audit: 527 окон / 35 page occurrences, 0/4 network-ready. 2134 tests и
Ruff/mypy прошли. Новых generative API calls нет. Далее — source-supported
author/year diagnostics из front matter; unknown/ambiguous сохранить, не брать
имена из references и не выдавать предложения за подтверждённые метаданные.

Обновление 2026-10-22: [records stage33](records_stage33_context_risks_2026-10-22.md)
добавил offline локализацию рисков без изменения выбора и допуска. На четырёх
сохранённых результатах: 527 диагностических окон, 1549 visual asset occurrences,
90 trigger records; 29 page occurrences сохраняют нелокализованные diagnostics.
Геометрическая удалённость не доказывает нерелевантность. Окна суммарно покрывают
22 страницы-вхождения; это диагностические области, не candidate wire packet.
Все прежние запреты сохранены, retrieval и генерации нет. Далее — вывести аудит
в UI подготовки; отдельно определить и проверить scientific exclusion criteria.

Обновление 2026-10-22: [records stage32](records_stage32_block_context_2026-10-22.md)
подключил API/UI подготовки целых PDF-блоков с неизменённым baseline. Четыре
read-only запроса сохранили 19 evidence; учтены 863 block occurrences / 35 page
occurrences, 30 страниц-вхождений отложены. 105 контекстов относятся к одному уже
отклонённому вопросу; 0/4 technical passes. Aggregate union guard обнаружил три
полные страницы в перекрывающихся окнах при нуле literal matches. 2062 tests,
Ruff/mypy и два identical exports прошли; генерации и scientific acceptance нет.
Далее — versioned local layout/visual risk assessment внутри выбранных блоков и
защищённого окружения, с сохранением unknown/excluded evidence и новым frozen
comparison. Не убирать diagnostics или поднимать byte ceiling по результатам этого прогона.

Обновление 2026-10-22: [records stage31](records_stage31_answer_preparation_2026-10-22.md)
подключил явный API/UI режим подготовки без генерации: `/answer/prepare` и
`/ui/answer/prepare`. Четыре реальных read-only запроса сохранили те же 19 evidence;
все заблокированы полными страницами, qualifiers допускают один. Исходные отказы,
unknown metadata, PDF/layer identities и полный текст видны пользователю.
2017 tests и Ruff/mypy прошли, два offline exports идентичны; scientific accuracy
не оценивалась. Авторы/год выбранных статей не заполнены в БД; unknown сохранён,
source-supported автоматическое заполнение остаётся отдельной задачей.
Существующий `/answer` не менялся, новых generative API calls нет. Далее —
source-supported block contexts с сохранением условий, отрицаний и unresolved
границ, отдельный frozen comparison; guard не обходить обрезкой старого текста.

Обновление 2026-10-22: [records stage30](records_stage30_query_qualifiers_2026-10-22.md)
реализовал отдельную necessary-mention проверку и явно подключаемую provider-обёртку.
Явные material phrases, автор/год и конечный каталог методов проверяются внутри
одной статьи; unknown metadata не подменяется ссылкой из библиографии. Четыре
сохранённых контекста: допуск 3 → 1, baseline refusals и все 19 evidence сохранены.
24/24 constructed agreements, 1977 tests, Ruff/mypy и два byte-identical
exports прошли; независимая scientific accuracy не установлена. Production default
не менялся. Далее — явный режим подготовки ответа с полной диагностикой нового
guard, расширенная отдельно оцениваемая группа вопросов и отдельный scope guard
до генерации. Новых API/retrieval calls нет, старые full-page packets не разрешены.

Обновление 2026-10-22: [records stage29](records_stage29_query_packet_2026-10-22.md)
добавил отдельный additive query packet и сравнил его с четырьмя текущими контекстами
без генерации. Все 19 evidence сохранены; две привязки одного separate control,
transfer-привязок нет. Все пакеты содержат полные страницы, 0/4 network eligible;
экономия и качество ответов не измерены. 1927 tests, Ruff/mypy и два byte-identical
exports прошли. Gate пропускает запросы с missing Istomina/DSC и Mars/regolith;
это наблюдение, не независимая scientific accuracy. Следующий bounded этап —
versioned-проверка обязательных уточнений запроса и достаточности evidence на новом
frozen наборе до платного сравнения ответов или сжатия. Production rules не менялись.

Обновление 2026-10-22: [records stage28](records_stage28_protocol_association_2026-10-22.md)
реализовал отдельный sentence-ID contract и bounded Responses comparison: пять
реальных вызовов, 11 source-integrity-valid целей; baseline/API category agreement
6/7 transfer и 4/4 separate control. DSC/conductivity различены в предложениях,
mixed-role/clipped diagnostics сохранены; scientific accuracy, origin и applicability
не установлены. 1894 tests, Ruff/mypy, frozen hashes и два byte-identical offline
exports прошли; новых измерений нет. Live budget исчерпан. Следующий этап —
versioned query evidence packet с сохранением связанных предложений и unresolved
qualifiers, затем отдельное сравнение с текущим answer context на независимо
оцениваемых вопросах. Stage28 не является production activation или научной приёмкой.

Решение по направлению MVP, 2026-10-22: [локальная база evidence + заменяемый API](mvp_inference_strategy_2026-10-22.md).
Первое подключение — существующий OpenAI provider; российские API требуют отдельных
адаптеров и проверки качества. Автономная коробка сохранена как возможная комплектация
под подтверждённую потребность. Это приоритет дальнейшей проработки, не завершение
интеграций или offline acceptance. Этап 28 сохраняет цель связи property/method/conditions;
API-based сравнение рассматривается как вариант отдельно замороженного протокола.

Обновление 2026-10-22: [records stage27](records_stage27_condition_multilingual_2026-10-22.md)
добавил отдельную frozen RU/EN policy на прежних 52 страницах / 851 блоке.
Пять scope proposals в трёх блоках, один cue-bearing блок с удержанным назначением,
847 no_literal_cue; baseline/control воспроизведены точно. Mixed measurement/
equilibration сохранён ambiguous; generic DSC protocol не привязан к проводимости.
1854 tests, Ruff/mypy, 731 frozen bindings и два byte-identical exports прошли.
Новых измерений/model calls и независимых научных метрик нет; browser acceptance
не проверена из-за запрета file://. Далее — отдельно versioned source-only
property/protocol association с сохранением DSC/conductivity boundary и новым
frozen comparison; независимая научная оценка остаётся отдельной задачей.

Обновление 2026-10-21: [records stage26](records_stage26_condition_transfer_2026-10-21.md)
заморозил полный transfer scope других task-групп: 52 страницы / 851 блок,
два primary tasks и три PDF, включая proposed supplement. Неизменённые правила
дали 851 no_literal_cue и 2252 unclassified events; отдельный контроль Каюмова
воспроизвёл пять событий точно. Перенос cue recognition не продемонстрирован;
условия в статьях не объявлены отсутствующими. 1791 tests, Ruff/mypy, hashes
и два byte-identical exports прошли. Новых измерений/model calls нет.
Далее — отдельная multilingual-версия scope policy с явной negation/reported-work
диагностикой и новым frozen comparison; независимая научная оценка открыта.

Обновление 2026-10-21: [records stage25](records_stage25_condition_scope_2026-10-21.md)
разделил source scope подготовки, кондиционирования и измерения поверх прежних
кандидатов: 101 scoped proposals, четыре unassigned и 43 исходных пропуска.
31 conditioning selection относится к режиму охлаждения при измерении;
атмосфера подготовки не стала средой измерения. Пять исходных фрагментов,
unsupported clause и incomplete tail сохранены. 1753 tests, Ruff/mypy, frozen
hashes и два byte-identical final exports прошли; новых model calls нет.
Далее — отдельно замороженная проверка переноса на контексты других статей;
independent gold, scientific accuracy и per-result applicability остаются открытыми.

Обновление 2026-10-21: [records stage24](records_stage24_material_roles_2026-10-21.md)
добавил отдельную versioned-модель пяти ролей по точным source occurrences:
37 предложений компонентов, 31 — состава пластификатора, 37 — basis; состав
мембраны и среда измерения unknown у всех 37 версий. Все 42 позиции, прежние
поля, шесть пропусков и старые diagnostics сохранены. Новых model calls нет.
1700 tests, Ruff/mypy, frozen hashes и два byte-identical exports прошли.
Далее — source-supported различение preparation/conditioning/measurement
conditions с сохранением ambiguous scope; независимые научные метрики,
method applicability и научное принятие остаются открытыми.

Обновление 2026-10-21: [records stage23](records_stage23_table_relations_2026-10-21.md)
выполнил offline relation audit всех 37 версий / 42 source-позиций. 13 native
batches replayed exactly; состав строки, basis, literal method cue и endpoints
проверены по координатам. Три boundary differences относятся к ширине того же
group heading, а не автоматически к научным ошибкам; revisit сохраняет пять
различающихся полей. Новых model calls нет. 1663 tests, Ruff/mypy, source hashes и
два byte-identical exports прошли. Далее — явная versioned-модель ролей plasticiser
composition / measurement environment и отдельная независимая оценка качества;
научное принятие и method applicability не установлены.

Обновление 2026-10-21: [records stage22](records_stage22_table_remaining_2026-10-21.md)
выполнил восемь frozen calls для 23 оставшихся числовых позиций: 23 новых
кандидата, пропущенных целей нет. По ledger покрыты 36/36 числовых позиций;
четыре shared-позиции unresolved, два тире сохранены. Старые поля/кандидаты не
перезаписаны. 1632 tests, Ruff/mypy, двойной native replay и source hashes прошли.
Научные метрики/принятие не установлены. Далее — независимая оценка качества и
source-supported аудит связей sample/composition/method; учёт позиций не заменяет
научную проверку и не означает полностатейное извлечение.

Обновление 2026-10-21: [records stage21](records_stage21_table_continuation_2026-10-21.md)
добавил source-cell ledger и четыре frozen continuation calls: 9 новых кандидатов,
1 deliberate revisit; 13 из 36 числовых позиций покрыты, 23 остаются.
Все 42 позиции сохранены, включая 2 тире и 4 unresolved shared-cell slots.
Method evidence связан по точным same-article R2 coordinates; это предложение
связи, не научное принятие. 1593 tests, Ruff/mypy, native replay и source hashes
прошли. Далее — оставшиеся 23 числовые позиции с новым frozen budget и отдельная
независимая оценка качества; table-wide/article-wide completeness не установлена.

Обновление 2026-10-21: [records stage20](records_stage20_multi_record_2026-10-21.md)
реализовал отдельный multi-record reply и четыре реальных frozen model calls:
восемь exact-source-valid кандидатов, все incomplete/unreviewed. Partial table
scope и sample/condition gaps сохранены; независимых научных метрик нет.
1559 tests, Ruff/mypy и offline raw replay прошли. Далее — bounded table
continuation/decomposition и source-supported evidence joining; массовый прогон
352 контекстов не объявлен ни выполненным, ни научно принятым.

Обновление 2026-10-21: [records stage19](records_stage19_article_windows_2026-10-21.md)
учёл полный scope 62 страниц / 1112 блоков и сохранил 352 bounded-контекста.
34 страницы и один full-page context остаются deferred с исходным текстом и
диагностикой. Это offline входы, не извлечённые измерения; scientific recall и
независимый пилот открыты. 1530 tests, Ruff/mypy прошли. Далее — отдельный
multi-record contract, offline validation и затем frozen model run.

Обновление 2026-10-21: [records stage18](records_stage18_article_scope_2026-10-21.md)
подготовил три development задачи полного stored-page scope статей и отдельный
предложенный supplement: четыре PDF / 62 страницы. Все 33 документа и 493 текста
страниц сохранены в HTML, 27 screening cases остаются unresolved. Это источник
для следующего bounded article extraction, не научный gold или выполненный
независимый пилот. Stages14–17 добавили checks/export, revisions/UI, evaluator
и same-machine review-store recovery. Актуальная сводка S00–S17 — в
[плане разработки](ariadne_development_plan_2026-10-09.md); исторические записи
ниже не задают новый compulsory manual workflow Terms.

Обновление 2026-10-13: [TAC stage12](tac_stage12_review_2026-10-13.md)
реализует engineering этапа 4 Terms: отдельная SQLite-история решений, review по
употреблению/оси и релевантности term, восстановление ревизий, очереди, контроль
источников и конкурентных правок, backup/restore. Граф отражает решения без
перезаписи proposals; отдельная HTML-таблица сохраняет все 33 документа и восемь
колонок. 950 тестов прошли; финальные targeted 16 прошли. Reviewer заявленный;
научная приёмка отсутствует. Следующий шаг — review конфликтов по источникам,
затем bounded scope научных связей этапа 5.

Обновление 2026-10-13: [TAC stage11](tac_stage11_classification_2026-10-13.md)
реализует engineering часть этапа 3 Terms: draft taxonomy, три оси, 12 585
контекстных assignments и пересекающиеся subsets. Граф поддерживает категории,
сортировку и export subset; новая review-таблица всех 33 документов сохраняет
восемь колонок. 934 теста прошли. Неизвестные и конфликты остаются видимыми;
manual labels агента не являются научным принятием. Следующий этап — persistent review.

Обновление 2026-10-13: [Terms Atlas](terms_graph_2026-10-13.md) добавляет
интерактивный локальный граф всех 33 статей и 2 266 Terms из frozen stage09/10.
Площадь кругов отражает число уникальных локальных term IDs; доступны выбор
T/A/C-группы, пересечения выбранного term и переход к точному контексту/PDF.
919 тестов прошли; браузерный аудит проверяет все 4 195 вхождений и 99 групп.
Это дополнительный read-only view. Научная классификация этапа 3 остаётся открытой.

Обновление 2026-10-13: [TAC stage10](tac_stage10_contexts_2026-10-13.md)
реализует этап 2 плана Terms: 4 195 exact mentions/uses, 98 TAC page contexts
и 3 635 lexical span containments для прежних 2 266 кандидатов. Источники,
inventory и метаданные сохранены; 913 тестов прошли. Контексты и вложения
доступны в отдельном HTML. Следующий этап — proposed classification и subsets;
научная синонимия, иерархия понятий и experimental linkage не установлены.

Обновление 2026-10-13: [TAC stage09](tac_stage09_inventory_2026-10-13.md)
реализует этап 1 плана Terms: полный инвентарь 2 266 кандидатов / 4 195 exact
occurrences и отдельное превью. Все 377 прежних preview entries сохранены.
892 теста прошли; HTML всех 33 документов, lazy expansion и поиск скрытых
Terms проверены. Legacy v0.3 остаётся доступным. Следующий шаг — этап 2:
упоминания, контексты и лексическая структура; категории и научные связи ещё
не реализованы.

Планирование на 2026-10-09: [подробный план разработки и предзаявочного пилота](ariadne_development_plan_2026-10-09.md)
задаёт очередь от воспроизводимого baseline до полной экспериментальной записи,
review/export, сравнительной оценки и offline-проверки. Основание —
[свежий аудит MVP](ariadne_mvp_assessment_2026-10-09.md).
Новые этапы являются планом; их реализация и научная приёмка не объявлены завершёнными.

Обновление 2026-10-13: [TAC stage 08](tac_stage08_inline_stop_2026-10-13.md)
устраняет ложную границу на слове `results` внутри Conclusions Nagasubramanian.
На прежних 33 документах изменилось только одно C поле: добавлены 505 точных
символов до Acknowledgements. Остальные TAC поля и 91 значение метаданных
сохранены; Terms остаются предложениями. 865 тестов прошли, frozen replay
совпадает со stage06. Новая HTML-таблица сохранена отдельно. Независимая
точность и научная приёмка Terms не установлены; следующий шаг — их review.

Планирование 2026-10-13: [план развития Terms](terms_implementation_plan_2026-10-13.md)
задаёт этапы от полного кандидатного инвентаря и отдельного превью до контекстов,
subsets, постоянного review, научных связей и сопоставления работ. Первое bounded
поручение — этап 1, теперь выполненный как TAC stage09. Остальные этапы пока
предложены; production integration и конкурентное преимущество не объявлены
реализованными или подтверждёнными.

Обновление 2026-09-14: [диагностика контекста чисел](stage3_numeric_context_cues_2026-09-14.md)
добавляет точные признаки масштабной линейки, приблизительности, неравенства
и изолированной числовой строки. Все 2347 выбранных фактов на 619 чанках и
прежние решения по 4344 вхождениям сохранены. 579 тестов прошли; Ruff и mypy
прошли. Повторная проверка подтвердила 20 вхождений по живым источникам.
Диагностический JSON теперь версии 2; схема фактов не менялась. Следующий шаг —
проверка групп по признакам и отдельная оценка узкого исключения явных масштабных
линеек с контролем новых кандидатов из освобождённых мест. Признаки не означают
научного одобрения; очередь проверки и запрет массового обновления сохраняются.

Обновление 2026-09-14: [PDF-проверка вхождений](stage3_occurrence_pdf_review_2026-09-14.md)
охватила 14 кандидатов и 13 страниц: в очереди 4 блокирующих решения,
9 допустимых, 968 без решения (включая один проверенный неоднозначный случай).
Подтверждены две потери лимита; выявлены масштабная линейка как измерение,
потеря приближённости и объединение разных синтезов по одинаковому числу.
Привязка разметки к конкретному вхождению проверяется аудитором; 6 целевых
тестов прошли. Следующая реализация — диагностические признаки роли числа,
приближённости и границ; затем продолжение PDF-проверки очереди.
Отбор, лимит 12 и факты в БД сохранены; массовое обновление не принято.

Обновление 2026-09-14: [диагностика численных вхождений](stage3_numeric_occurrences_2026-09-14.md)
реализована: точные позиции, причины отказов, ссылки на дубликаты и пропуски лимита.
На 619 чанках все 2347 выбранных фактов и их порядок совпали с версией до патча.
Полный pytest: 536 passed; Ruff и mypy прошли. Журнал корпуса: 585 отказов,
1029 дубликатов, 383 пропуска лимита. Это весь корпус, а не прежние три потери
относительно Git-baseline. Следующий шаг — проверка вхождений по PDF и очереди
981 изменения; научная приёмка и массовое обновление фактов остаются открытыми.
Лимит 12 сохранён. Для многостраничных чанков точная страница вхождения не угадана.

Последнее обновление: [ссылки на рисунки и единицы скорости](stage3_numeric_reference_fix_2026-09-09.md)
больше не дают проверенные ложные скаляры. Полный pytest: 523 passed;
10/10 ошибочных кандидатов отклонены при проверке реальных источников, baseline 5/10.
Новый diff: 981 непроверенное изменение. Следующая реализация — диагностика
принятых/отклонённых вхождений, дубликатов и пропусков лимита с точными фрагментами.
Лимит 12 сохранён, массовое обновление фактов не принято.

Обновление: [патч шрифтовых знаков и составных единиц](stage3_numeric_glyph_fix_2026-09-09.md)
блокирует три ошибки из PDF-аудита; все семь исторических ошибочных кандидатов
отклонены на реальных источниках. Полный pytest: 506 passed; baseline 5/10.
Новый diff: 939 непроверенных изменений, cap=12 сохранён. Следующий патч —
ложные числа из ссылок на рисунки и обрезанные единицы скорости; затем диагностика
вхождений и пропусков лимита. Массовое обновление фактов не принято.

Продолжение 2026-09-09: [PDF-проверка потерь лимита и новых кандидатов](stage3_numeric_cap_review_2026-09-09.md).
Проверены восемь страниц, размечены девять изменений: 5 блокирующих проблем,
4 допустимых, ещё 869 не проверены. Две потери лимита подтверждены как полезные
вхождения; третья (`≤1.5%`) требует оператора границы. Проба cap=24 добавляет
347 кандидатов, поэтому лимит оставлен 12. Следующий патч: шрифтовый знак ±,
экранированный суффикс обратной единицы и составная единица g Ah⁻¹; затем
диагностика конкретных вхождений и пропусков лимита. Массовое обновление не принято.

Обновление 2026-09-09: [защита границ численных фактов](stage3_numeric_guards_2026-09-09.md)
блокирует четыре ранее проверенные ошибки; повторная проверка реальных источников —
4/4, полный pytest — 492 passed. Baseline теперь 5/10: конечная точка `7–17%`
больше не выдаётся отдельным числом. Обнаружены три потери поздних самостоятельных
вхождений из-за неизменного лимита 12 фактов. Новый diff относительно Git-baseline:
878 непроверенных изменений, массовое обновление по-прежнему не принято.
Следующий шаг — проверка нового diff и потерь из-за лимита; затем явная поддержка
диапазонов, погрешностей и научной записи. Этапы 2 и 3 остаются открытыми.

История проверки 2026-09-08:

Приёмка обновления численных фактов **не пройдена**:
[аудит изменений](stage3_numeric_change_review_2026-09-08.md) зарегистрировал
614 изменений; пять проверены по PDF, из них четыре — блокирующие ошибки,
одно — корректное удаление ложного совпадения из DOI. Ещё 609 не проверены.
Следующий шаг — защита от частей степеней, обратных единиц, погрешностей и
потери знака; массовое обновление сохранённых фактов пока не принимать.

Обновление этапа 3: [типографские числа и единицы](stage3_numeric_typography_2026-09-08.md)
распознаются с сохранением исходной записи; покрытие фиксированных целей выросло
с 4/10 до 6/10. Финальные тесты: 457 passed. На 619 чанках проверено отсутствие
вытеснения прежних распознаваемых фактов из-за лимита; научная проверка остальных
изменений выдачи остаётся открытой. Сохранённые факты не обновлялись.

Этап 3 начат: [baseline численного извлечения](stage3_numeric_baseline_2026-09-08.md).
Визуально проверены три страницы PDF; найдены 4/10 целевых чисел в восьми
контрольных примерах. Это покрытие выбранных целей, не общая точность extractor.
Следующий патч — распознавание типографских чисел/единиц с сохранением исходного
текста. Связь чисел с материалом, оператором и условиями требует отдельного решения.

Дата сверки: 2026-09-07. Исходная ревизия: `4958bf0`.

Обновление 2026-09-08: [проверка локальных экспериментальных связей](stage2_relation_links_2026-09-08.md)
добавила диагностику и отклонила новый veto из-за ложного отказа на местоименную
ссылку и сохраняющегося допуска разных образцов. Финальные проверки: 435 tests
passed; исходная научная разметка — 31/36, этап 2 остаётся открытым. Следующий
практический шаг — аудит извлечения численных фактов этапа 3, разрешённый ниже
параллельно с оценкой evidence. Это не закрывает научную приёмку этапа 2.

Обновление этапа 1: выполнена сквозная проверка и исправлены пять дефектов;
см. [отчёт 2026-09-07](stage1_acceptance_2026-09-07.md). Основной цикл подтверждён
через PostgreSQL, реальные OCR/embeddings и HTTP; Libraries проверен в браузере.
Принудительное завершение процессов и полная матрица сбоев остаются отдельными
проверками.

Обновление этапа 2: [аудит Ma](stage2_gold_audit_2026-09-07.md) установил ошибку
эталонного вопроса, а не ранжирования. Исправлены три формулировки; baseline
exact/hybrid на исправленном extended наборе — 46/46. Исправлена остановка
межъязыковой evaluation на изменяющейся диагностике состава языков.
Узкое [дополнение словаря энтальпии](stage2_interaction_enthalpy_2026-09-07.md)
подняло cross-lingual PASS с 30/31 до 31/31. Остальные 65 запросов сохранили
метрики и порядок выдачи; user regression остаётся 7/10 по полным условиям
при article Recall@10=1.0.

## Цель продукта

Локальная научная библиотека для Nafion/PFSA и связанной литературы:
пользователь подключает папку или загружает PDF, система обрабатывает документы,
находит релевантные источники и формирует проверяемые ответы с переходом к
конкретной странице и исходному фрагменту. Оригинальные PDF неизменны.

Этот документ — актуальная точка входа в планирование. Старые технические планы
сохраняются как описание решений и требований, но их начальные статусы не
являются текущим отчётом о реализации. Порядок ниже — предлагаемый порядок
дальнейшей работы, а не утверждение, что все требования старых этапов закрыты.

## Как читать статусы

- **Реализация есть**: поведение обнаружено в исходниках; это не означает,
  что сейчас проверены все критерии приёмки или работа локальных сервисов.
- **Частично**: есть основа, но заявленная широкая задача требует доработки
  или отдельной оценки качества.
- **Отложено**: не входит в ближайший цикл; возвращаемся при конкретной потребности.

При подготовке карты прочитаны исходники, документация, список тестов и история
Git. Тесты, база данных, OCR, индекс и OpenAI API в рамках этой сверки не запускались.
Наличие тестового файла не означает успешное прохождение тестов. Исторические
числа корпуса и результаты проверок не выдаются за текущий baseline.

## Текущее положение

| Направление | Статус по исходникам | Основание и оставшаяся проверка |
| --- | --- | --- |
| PDF ingestion, OCR, страницы и чанки | Реализация есть | `app/ingestion/`, `app/extraction/`, `app/chunking/`; проверить обработку и трассировку на актуальном корпусе |
| Доступ к PDF и контексту | Реализация есть | `app/documents/`, маршруты в `app/main.py`; проверить реальные страницы, слои и соседние фрагменты |
| Загрузка и очередь | Реализация есть | `app/ingestion/upload.py`, `queue.py`, `app/workers/worker.py`; проверить ошибки, повторы и восстановление |
| Библиотеки локальных папок | Реализация есть | `app/library/`, API и UI; сканирование, очередь, дубликаты, управление источником и прогресс требуют сквозной приёмки |
| Жизненный цикл индекса | Реализация есть | `app/retrieval/index_lifecycle.py`, `index_worker.py`; автоматический rebuild зависит от настройки и работающего worker |
| Exact, semantic и hybrid search | Реализация есть | `app/retrieval/search.py`, `vector_index.py`; качество и состояние индекса проверяются отдельно |
| Фильтры, группировка и контекст | Реализация есть | `SearchFilters`, параметры группировки, endpoints контекста; полноту старого плана сверить с реально хранимыми метаданными |
| Межъязыковой поиск и ранжирование статей | Частично | `cross_lingual.py`, `reranking.py` уже содержат реализацию, включая оценки статей; полнота RU/EN и обобщение требуют evaluation |
| Ответы и мини-обзоры с цитатами | Реализация есть | `app/generation/`; проверка структуры ссылок не доказывает научную обоснованность каждого утверждения |
| Таблицы, формулы, численные факты | Частично | Есть аудит текста и `app/facts/`; извлечение чисел по правилам не равно полноценному пониманию таблиц и условий эксперимента |
| Evaluation и производительность | Частично | `app/evaluation/`, YAML-вопросы и пороги; нужны актуальный baseline, репрезентативная разметка и замеры на растущем корпусе |

Тестовые модули для перечисленных областей находятся в `tests/unit/`, в том числе
`test_library_sources.py`, `test_vector_index_lifecycle.py`, `test_reranking.py`,
`test_structured_facts.py`, `test_generation.py` и `test_evaluation.py`.

## Этап 1. Подтвердить надёжность текущего рабочего цикла

**Статус: основной цикл проверен; ограничения перечислены в отчёте приёмки.**
Результат для пользователя: новая статья из папки
становится доступной для поиска, а состояние обработки понятно и проверяемо.

Работы:

- Зафиксировать ревизию, конфигурацию без секретов, состав корпуса и состояние индекса.
- Проверить путь: папка/загрузка → очередь → extraction/OCR → страницы/чанки →
  обновление индекса → поиск → открытие PDF и контекста.
- Проверить повторное сканирование, одинаковые PDF, повреждённый документ,
  исчезнувший файл, прерывание worker и ошибку перестроения индекса.
- Сверить показанный прогресс с сохранёнными состояниями заданий и файлов.
- Устранить подтверждённые дефекты минимальными патчами.
- Согласовать README и эксплуатационные инструкции с реализацией: утверждения
  об отсутствии автоматического rebuild уже не описывают весь текущий код.

Готовность: сквозной отчёт содержит фактические результаты и диагностику ошибок;
повторная обработка не создаёт непредусмотренные дубликаты; оригиналы сохранены;
готовность текста и векторного индекса различима; ссылки ведут к нужным источникам.

Артефакт: отчёт приёмки с командами, конфигурацией и известными ограничениями.

## Этап 2. Измерить и улучшить поиск источников

**Статус: в работе.** [Аудит ожидаемых чанков](stage2_fragment_audit_2026-09-07.md)
для 002/003 и 007 завершён: evaluator не сопоставлял типографское `Li-Naﬁon`
с `Li-Nafion`. Узкое раскрытие лигатур дало 10/10 regression PASS при полностью
неизменной выдаче; это исправление измерения, не улучшение ranking.
[Аудит группировки](stage2_grouping_audit_2026-09-07.md) завершён для четырёх
методов на 46 вопросах: article Recall=1.0 во всех вариантах; semantic cap=1
снижает chunk Recall с 1.0 до 0.923077 (13 вопросов с chunk targets).
Cap=2 не дал потерь Recall на этом gold. Обнаружен отдельный исходный
hybrid_cross_lingual FAIL на unanswerable PBI-вопросе: adequacy принимает
общее покрытие терминов без polybenzimidazole/phosphoric. Следующий шаг —
проверить его по исходникам; затем проверить cap=2 на дополнительных user/
cross-lingual наборах. Default cap и scoring не менялись.

Обновление 2026-09-08: [аудит adequacy и дополнительной группировки](stage2_adequacy_grouping_audit_2026-09-08.md)
воспроизвёл PBI false positive через production answer service с локальным
extractive provider. В 814 сохранённых original/OCR слоях 33 статей искомые
PBI/phosphoric термины не найдены; визуальная проверка всех PDF не выполнялась.
На user regression cap=2 теряет нужные чанки для exact (вопрос 002) и hybrid
(вопрос 004). Поэтому универсальная безопасность cap=2 отвергнута; для
hybrid_cross_lingual на этих десяти вопросах потерь нет, 10/10 PASS.
Следующая реализация: проверка обязательных понятий запроса для отказа при
только тематическом evidence, с положительными/отрицательными RU/EN примерами;
отдельно определить сохранение полного evidence при компактной группировке.
Production thresholds, default cap и scoring пока не менялись.

Продолжение 2026-09-08: [проверка обязательных веществ реализована](stage2_required_concepts_2026-09-08.md).
Начальный словарь содержит семь идентичностей с RU/EN-алиасами; отсутствие
названного вещества блокирует ответ независимо от общего покрытия терминов.
PBI-вопрос теперь возвращает `insufficient_evidence` на живом корпусе.
Полный pytest: 381 passed. Replay 348 сохранённых выдач выявил семь новых
отказов на выбранном полном evidence для answerable-вопросов в exact/semantic/hybrid;
для hybrid_cross_lingual таких изменений нет. Это ограничение отбора evidence,
а не доказательство отсутствия ответа в корпусе. Следующий шаг: сохранить нужные
фрагменты при отборе, начиная с таблицы диглима; расширять проверенные алиасы
и отрицательные примеры. Этап 2 пока не закрыт.

Следующее обновление 2026-09-08: [сохранение обязательного evidence реализовано](stage2_evidence_retention_2026-09-08.md).
После фильтрации возвращаются только исходные кандидаты, закрывающие недостающее
вещество. Exact/hybrid сохраняют продолжение таблицы диглима (стр. 109–111),
передают его провайдеру и цитируют в локальной проверке. Из 348 сохранённых
выдач изменились только эти два отбора; отказ для PBI сохранён. Полный pytest:
387 passed. Для semantic нужного фрагмента нет в top-10; это пробел поиска
кандидатов, который восстановление после фильтрации не исправляет.

[Аудит расширения кандидатов и соседнего контекста](stage2_candidate_expansion_2026-09-08.md)
показал, что top-25/50 и соседние чанки могут закрыть названия веществ без
подтверждения запрошенной зависимости. Автоматическое расширение не включено.
Следующая приёмка должна различать отдельные растворители и их смесь,
проводимость и набухание, а также влияние температуры смешения; сначала нужна
разметка этих связей в evidence, затем оценка восстановления кандидатов.

[Разметка зависимостей и оценщик](stage2_relation_annotations_2026-09-08.md)
добавлены: 9 случаев, 11 точных фрагментов, 9 визуально проверенных PDF-страниц.
Целостность всех источников подтверждена. На 36 решениях эвристики: 23 совпадения,
8 ложных допусков, 5 ложных отказов; 403 теста прошли. Разметка выполнена
ассистентом, независимая научная проверка отсутствует. Следующий шаг — проверка
научной зависимости при допуске evidence с отдельной оценкой ложных отказов.
Этап 2 остаётся открытым.

[Фильтр экспериментального контекста](stage2_relation_context_2026-09-08.md)
реализован для двух узких типов вопросов. На том же наборе разработки: 31/36
совпадений, 0 ложных допусков, 5 прежних ложных отказов. 414 тестов прошли.
Воспроизведение 348 выдач не изменило решения, но все эти вопросы вне области
правила. Следующая приёмка требует независимых примеров внутри области правила,
включая отрицания и разные способы описания эксперимента. Общая научная
достаточность evidence пока не подтверждена.

[Проверка фильтров](stage2_filters_acceptance_2026-09-07.md): 43 PASS на реальных
БД и индексе через API TestClient. Положительные year/journal не проверены:
поля пусты у всех 33 статей. Лимит применяется после top_k без добора статей.
[Semantic baseline](stage2_semantic_baseline_2026-09-07.md) получен: 46/46 PASS,
Recall@10=1.0, MRR=0.874373; все действующие semantic-пороги выполнены.

Зависимость: воспроизводимый корпус и рабочий индекс из этапа 1.

Результат: запросы на русском и английском находят подходящие статьи, а выдача
не заполняется близкими фрагментами одной работы.

- Получить baseline exact, semantic, hybrid и cross-lingual на одном корпусе.
- Проверить существующий article-level reranking по его плану; не реализовывать
  его заново только потому, что документ помечен как design plan.
- Разметить вопросы по методам, материалам, численным данным, парафразам,
  русским/английским источникам и отсутствующим в корпусе сведениям.
- Разделять ошибки поиска кандидатов, ранжирования и отбора evidence для ответа.
- Проверить фильтры и ограничение фрагментов одной статьи.
- Эксперимент с multilingual embeddings проводить только при подтверждённом
  пробеле покрытия; сравнивать с текущим индексом на одинаковой разметке.

Готовность: сохранено сравнение до/после по Recall@k, MRR и другим применимым
метрикам; нет необъяснённых регрессий и потери трассировки. Действующие пороги
из `evaluation_thresholds.yaml` не меняются молча; недостающие критерии для
cross-lingual фиксируются до оценки новой версии.

Артефакт: отчёт качества поиска с разбором неудачных вопросов и решением,
какие изменения принимать.

## Этап 3. Надёжно извлекать научные данные

Зависимость: baseline поиска; аудит текста можно начать параллельно по времени,
но изменения extraction и chunking оценивать отдельно от изменений ранжирования.

Результат: найденные числа, единицы и условия можно проверить в исходной статье.

- Проверить таблицы, подписи, формулы и выбор original/OCR слоя на контрольных PDF.
- Оценить precision/recall существующего извлечения численных фактов по ручной разметке.
- Проверять связь значения с величиной, материалом и условиями измерения;
  не считать соседство числа и единицы достаточным доказательством этой связи.
- Сохранять точный фрагмент и страницу; координаты добавлять только при надёжном
  извлечении и явно согласованной схеме.
- Улучшать extractor по измеренным ошибкам, сохраняя воспроизводимость и оригиналы.

Готовность: контрольные факты проверены по PDF; неоднозначные значения и OCR-ошибки
видны; изменение качества измерено. Полноценное понимание произвольных формул
и таблиц не является заявленным свойством текущей реализации.

Артефакт: размеченный набор научных данных и отчёт об извлечении.

## Этап 4. Проверяемые ответы и сравнения работ

Зависимость: качество evidence из этапа 2; численные сравнения — после этапа 3.

- Оценить, действительно ли каждый тезис поддерживается процитированным фрагментом.
- Проверить ответы и мини-обзоры на RU/EN, покрытие подходящих работ и отказы
  при недостаточных доказательствах.
- Проверять единицы, условия эксперимента и сопоставимость чисел перед сравнением.
- Различать данные авторов, противоречия между источниками и вывод системы.
- Не подменять проверку научного содержания валидацией citation IDs.

Готовность: ручная научная проверка согласованного набора ответов, отчёт
неподтверждённых утверждений и пропущенных источников, воспроизводимая
конфигурация генерации. Автоматические метрики дополняют эту проверку.

Артефакт: evaluation ответов и список остающихся ограничений.

## Этап 5. Масштабирование и эксплуатация

Зависимость: стабильный функциональный baseline. Блокирующие ошибки
производительности исправляются раньше, когда подтверждены измерениями.

- Согласовать целевые размеры корпуса и допустимые задержки под реальные задачи.
- Измерить ingestion throughput, rebuild, cold/warm search, p50/p95 и память.
- Проверить одновременные ingestion, поиск и перестроение, восстановление после сбоев.
- Проверить кэш, ограничения выдачи и контекста; оптимизировать измеренные узкие места.
- Проверить резервное копирование и восстановление БД, оригиналов и конфигурации;
  воспроизводимость производного индекса описать отдельно.

Готовность: повторяемый benchmark с аппаратной конфигурацией и размерами корпуса,
выполнение заранее согласованных целей, проверенный сценарий восстановления.

Артефакт: benchmark-отчёт и актуальная эксплуатационная инструкция.

## Отложенные направления

- Внешнее обогащение метаданных: отдельный дизайн источников, происхождения полей
  и разрешения конфликтов с локальными данными.
- Полноценный диалоговый интерфейс с историей: после проверки качества одиночных
  ответов; история не должна становиться неподтверждённым источником фактов.

Это возможные расширения, а не обязательства текущего цикла. Календарные сроки
не заданы: сначала нужен baseline этапа 1 и оценка объёма выявленных дефектов.

## Связь с прежними планами

| Документ | Как использовать сейчас |
| --- | --- |
| [Общий backend-план](backend_general_implementation_plan.md) | Исходные восемь направлений и критерии; не перечень отсутствующих функций |
| `priority1`–`priority5` в `docs/` | Чек-листы приёмки уже существующей инфраструктуры, доступа и поиска |
| [Качество текста и OCR](priority6_tables_captions_ocr_plan.md) | Детализация этапа 3 |
| [Производительность](priority7_scaling_performance_plan.md) | Детализация этапа 5 |
| [Evaluation](priority8_extended_evaluation_plan.md) | Сквозная проверка, начиная с этапа 1, а не только в конце |
| [Библиотеки](ariadne_library_sources_implementation_plan.md) | Сверка требований с реализованным workflow на этапе 1 |
| [Cross-lingual](cross_lingual_retrieval_answer_plan.md) | Требования этапов 2 и 4; отдельные части уже реализованы |
| [Ранжирование статей](article_level_reranking_plan.md) | Проверка покрытия плана существующим кодом и оценка качества |
| [Ответы](phase4_rag_answers.md) | Текущий контракт и ограничения генерации |

## Правило обновления карты

После каждого этапа указывать ревизию, фактически выполненные проверки,
ссылки на отчёты и оставшиеся пункты. Наличие кода, успешные unit tests и
приёмка на реальном корпусе — разные свидетельства и отражаются отдельно.
Отчёт изменений сохраняет формат `Changed / Tests run / Limitations / Verdict`.
