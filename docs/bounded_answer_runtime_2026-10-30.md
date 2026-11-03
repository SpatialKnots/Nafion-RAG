# ARIADNE: ограниченные рабочие ответы q1/q3 и защита optimum q2

Changed:

Изменён реальный путь `/answer`, а не только отдельная диагностика. GigaChat
остаётся единственным answer provider: `GigaChat-2-Max`,1200 output tokens,
120с, без retry/fallback. Реальных вызовов после изменений не было.

1. **q3, найденные методики литирования.** Для конечного класса неуточнённых
   Nafion method-overview questions строятся atomic source records: material
   context/form cue, операция, буквально названный ионный обмен/нейтрализация,
   локальный LiOH и поля концентрации/времени/температуры. Используются прежние
   неизменённые source-only parsers; материал/выполнение/владелец условий остаются
   unverified. Числа не переносятся между регионами; grade не додумывается.
   Неизвестное, несколько literal candidates, отрицание, будущее и неопределённый
   контекст не ремонтируются. В выбранном q3 есть одно eligible описание первого
   обмена. Хвост обрывается на следующем этапе; ответ явно ограничен неполным
   фрагментом, без заявления о полном протоколе/каталоге. Post-hoc с.52 не добавлена
   в evidence исходного вопроса. Уточняющие ограничения вне finite scope отклоняются.
2. **q1, H→Li набухание.** Для supported unqualified transition question требуется
   полная поддерживаемая табл.4.5: девять известных строк, Nafion forms, swelling
   quantity и порядок αH перед αLi. Другой материал, другая величина, обратный
   порядок столбцов или неполные строки отклоняются. Decimal вычисляет каждую
   разность и higher/lower/equal counts. Реальные строки дают4/9 выше и5/9 ниже;
   все пары и Δ приводятся, вывод расположен перед списком. N,N-/N- locants
   сохраняют химический регистр. Для равных/однонаправленных контрольных таблиц
   заключение вычисляется заново, не зашито под4/5. Температура, единицы и
   определение α с других страниц не добавляются. В ответе явно отмечено
   арифметическое вычисление системы.
3. **q2, «лучшая смесь».** Superlative Li-Nafion mixture-conductivity questions
   отклоняются до provider: не установлены сопоставимая comparison universe,
   одинаковая material/form basis, состав optimum и температура. Scope в самом
   вопросе не считается доказательством наличия source support. Scoped optimum
   extraction ещё не реализована; это консервативное ограничение покрытия,
   не утверждение, что в литературе нет хороших/оптимальных составов.

В узких q1/q3 профилях GigaChat **выбирает подготовленное утверждение**, а не
свободно вычисляет/пересказывает результат. Native JSON Schema ограничивает
claim.text enum; локальная проверка независимо отклоняет изменение текста,
добавленные условия, неправильную citation, дубликат и смешение с unrestricted
evidence. Q3 — атрибутированные точные цитаты; q1 — помеченная source-table
арифметика. Модель может отказаться. Никакого deterministic fallback при отказе
нет. Для mini_review остаётся не более одного selected statement на работу.
Остальные вопросы сохраняют прежний свободный GigaChat-путь и его ограничения.

API request/response fields не переименованы. Явно добавлены versioned metadata:
`lithiation_overview`, `swelling_transition`, `conductivity_best_scope`, сохранённый
`lexical_baseline`; новые citation source types — `procedure_derived` и
`comparison_derived`. Это расширение значений/metadata, не миграция БД.
UI показывает подготовленные утверждения читаемо, отдельно от raw PDF context;
JSON контракта не подменяет исходный PDF. Внешние клиенты должны учитывать новые
source_type values. Retrieval ranking, chunking, OCR, global term matcher и
embedding/index files не менялись; generation evidence selection изменена явно.

Tests run:

- **369 passed** в11 затронутых unit/API/UI/ownership modules, финальный JUnit
  `output/lithiation_runtime_20261030/tests_v09.xml`. Проверены контрпримеры,
  source scope, отсутствие чужих условий, таблица/ориентация/динамические знаки,
  provider parser/strict local validation, readable UI, API error mapping и
  прежние relation/operation controls. Полный repository suite не запускался.
- Ruff девяти новых/изменённых файлов прошёл. **mypy app:183 files passed**.
- Реальный **ASGI `/answer`**, frozen retrieval, synthetic credentials,
  Engine.connect forbidden, GigaChat `_post` полностью подставной:

| Проверка | HTTP | Результат |
| --- | ---: | --- |
| q1, выбрать допустимый текст |200| answered, девять пар/Δ,4/9 выше/5/9 ниже |
| q2, исходный вопрос |200| insufficient_evidence, provider не вызывается |
| q3, выбрать допустимый текст |200| answered, исходная цитата и неполный протокол |
| q1, повторить старое ошибочное «для большинства» |502| local validation rejects |
| q3, выдумать2ч/полный протокол |502| local validation rejects |
| q3, provider answerable=false |200| insufficient_evidence, без fallback |
| q3, точная словоформа с отрицанием |200| insufficient_evidence до provider |

Здесь10 fake transport calls, **0 настоящих model/OAuth/DB calls**. Это
синтетический выбор для проверки приложения, **не новые ответы нейросети**.
В отчёте исходные реальные ответы сохранены отдельным неизменённым блоком.

- Пять сохранённых native schemas/fixtures проверены установленной Anaconda
  jsonschema: три positive fixtures valid, два negative invalid. Приложение
  использует свой .venv; библиотеки Anaconda в него не подмешивались. Реальная
  поддержка новых string enums провайдером и его поведение **не проверены**.
-23 выбранные страницы пяти PDF совпали со свежим извлечением. Atomic spans
  q3 совпали с raw text; девять paired values/Δ сверены с прежней явной
  post-hoc source transcription, которая не объявляется independent gold.
-223 current bindings,293 historical bindings против оригиналов и **четыре
  объявленных app drifts** проверены. До изменений сохранены точные original
  service/gigachat/presentation/ui files. Старые current-code guards должны
  отклонять stale candidates; их hashes/outputs не переписаны.
- Два разных native request bodies сохранены с bytes/SHA256, **не отправлены
  реальному провайдеру и не зарезервированы** в global live ledger. Старые slots
  остаются consumed/closed. Новая отдельная авторизация не получалась.
- Static HTML QA: пять TAC works, восемь основных колонок,25 existing PDF/page
  links,0 unresolved app-relative URLs. Для standalone review зарегистрированные
  PDF links подставлены вместо app navigation; сырые API bodies не изменены.
  Browser execution и запуск/перезапуск live server не выполнялись.

Разработка и сохранённые диагностики:

- Initial collection: четыре ImportErrors из-за circular import исторического
  GigaChat JSON reader через source parsers. Frozen parsers теперь импортируются
  лениво после инициализации provider; старые модули не менялись. Первый JUnit
  сохранён, broad try/except для скрытия ошибок не добавлялся.
- Первый ASGI runner остановился на отсутствующем .venv jsonschema до запросов.
  Новых dependencies не устанавливали; schema check вынесен в имеющуюся Anaconda.
- Исправлены initial lint diagnostics imports/unused/line length/loop binding.
  Локальные ASGI checks запускались вне sandbox из-за прежних sandbox hangs.
- Сохранено существующее Starlette/httpx deprecation warning; зависимости не
  обновлялись ради чистого лога.
- Overlapping successful test runs173/188/365/367 не суммируются с369.
  review_v01–v04 и прежние JUnit сохранены. Final review_v05 включает guards
  quantity/column orientation, conclusion-first и химический N-регистр.
  Supplementary schema checks находятся вне неизменяемых review manifests.
  Summaries — `output/lithiation_runtime_20261030/development_notes.json`, не
  полные raw terminal logs.

Артефакты:

- [Final HTML](../output/lithiation_runtime_20261030/review_v05/review.html).
- [Протокол](records/bounded_answer_runtime_protocol_v0.1.md).
- `app/generation/lithiation_overview.py`, `comparison_scope.py`, service/provider/
  presentation/UI changes; два новых unit modules.
- `scripts/run_bounded_answer_runtime_review.py`: actual offline ASGI runner.
- `output/lithiation_runtime_20261030/`: original app snapshots, final report/
  manifest/native bytes, source snapshots, JUnit, schema checks, qa_v05.json,
  preserved draft versions и development summaries.

Limitations:

Это узкие exposed development profiles. Парсеры не стали общей semantic
ownership/coverage validation; source quotes не подтверждают истинность опыта,
и physical owners остаются unverified. New native enums не проходили live
проверку. Q2 теперь безопасно отказывает, но extraction сопоставимого scoped
optimum остаётся открытой. Определённые wording/format/condition variations
могут консервативно отказать. Наличие существенного scientific data loss не
измерено; меньший request не считается сохранением информации. Repeated-request
cache/ORM и автономное deployment не исправлены. Independent references/quality
annotation по-прежнему отсутствуют; научная приёмка не заявляется.

Verdict:

Авторизованные runtime-изменения выполнены и проверены offline: q3 получает
source-bound quote path, q1 — полный checked paired comparison, q2 — явную
защиту от неподтверждённого победителя. Настоящих новых GigaChat-ответов нет.
Оригинальные source/model/history/budgets сохранены. **Прогресс исходного плана:
75%** — независимая научная оценка остаётся открытой.
