# ARIADNE: план реализации контекстных Terms

Дата: 13 октября 2026, Asia/Yekaterinburg.
Основание: [концепция v0.1](terms_storage_concept_v0.1_2026-10-13.md), текущие
исходники и [TAC stage08](tac_stage08_inline_stop_2026-10-13.md).
Статус: **engineering этапов 1–4 выполнен**. Ручной workflow этапа 4 отменён
по запросу пользователя 14 октября: [stage13](tac_stage13_automatic_2026-10-14.md)
вводит автоматическую классификацию и subsets с диагностикой. [Stage14](tac_stage14_table_expansion_2026-10-14.md)
исправляет раскрытие таблицы; [stage15](tac_stage15_context_roles_2026-10-14.md)
добавляет ограниченные автоматические роли/происхождение. [Stage16](tac_stage16_relation_pilot_2026-10-14.md)
реализует ограниченную экспериментальную часть этапа 5: два явных шаблона связей,
неизменяемый sidecar, проверку источников и автоматический abstain. Полный этап 5
и этапы 6–8 остаются отдельной разработкой. Пользователь не должен разрешать контекстные вопросы Terms.
Описания ручного review ниже сохранены как история прежнего плана.
[Stage17](tac_stage17_full_names_2026-10-14.md) добавляет полные названия, taxonomy
v0.4 и автоматическую пересборку на границе JSON-снимка корпуса. Ingestion →
snapshot bridge остаётся отдельным этапом; повторная загрузка не означает equivalence.
Научная приёмка Terms остаётся открытой. Нумерация ниже относится к этому плану.
14 октября выполнен [ограниченный development replay этапа 7](terms_retrieval_comparison_result_2026-10-14.md):
TAC + typed Terms soft fusion проиграл прежнему hybrid_cross_lingual по MRR и
потерял один целевой supplementary результат в top-10. Production integration
не включена; независимая оценка и измерение пользовательского времени остаются открыты.
[Guarded replay v0.2](terms_retrieval_guarded_result_2026-10-14.md) сохранил прежний
top-10 и вернул 46/46, но MRR 0.9035 остаётся ниже baseline 0.9342. Специфичность,
контекстные проверки и fallback реализованы как отдельный эксперимент;
преимущество ранжирования и production integration не подтверждены.
Первые development runs завершены как [TAC stage09](tac_stage09_inventory_2026-10-13.md)
и [stage10](tac_stage10_contexts_2026-10-13.md).

## 1. Цель и границы

Реализовать workflow «полный инвентарь кандидатов → упоминания/контексты →
автоматические категории/диагностика → проверяемые связи → сопоставление работ».
Terms каждой статьи сохраняются отдельно. Subsets — воспроизводимые фильтры
над локальными данными; контекстные связи и mappings не сливают исходные записи.

Первый полезный результат: пользователь видит все произведённые кандидаты,
раскрывает их evidence и группирует их без потери исходных фраз. Дальнейший
результат: проверяемые подборки и явные ограничения сравнения научных данных.

Начать с frozen sidecars и локального HTML. Не менять одновременно production
PostgreSQL, extraction/OCR, chunking, retrieval scoring, answer generation или
glossary. Включение Terms в поиск, production schema и автоматическое scientific
admission — отдельные этапы с собственными проверками. Graph database и новая
модель не нужны для первого prototype; выбор модели отложен до эталона и проверки
конкретного контракта.

## 2. Проверенное исходное состояние

- `scripts/tac_terms.py`: `tac_term_candidates_v0.3`, extraction по T/A/C,
  точные evidence spans, ranking и подавление вложенных фраз. `max_terms=12`
  ограничивает сохраняемый список; discarded candidates доступны только как
  количество. Validator поддерживает эту ограниченную схему.
- `scripts/tac_review_html.py`: восемь согласованных колонок, раскрытие текста,
  поиск, local original-PDF links, metadata и boundary diagnostics; это статический
  exporter, не сервер сохранения пользовательских решений.
- `scripts/tac_boundary_review.py`: source-bound development assessments; не
  независимая scientific annotation и не журнал пользовательского review Terms.
- `app/facts/review_store.py` и `review_ui.py`: immutable numeric snapshots,
  локальный SQLite decision log, ревизии и защита от lost updates. Их существующий
  контракт привязан к numeric records/chunks/occurrences, поэтому нельзя просто
  записывать Terms в ту же таблицу или автоматически переносить решения.
- `app/records/`: draft evidence/record contract и offline review worksheets.
  Наличие evidence/readiness checks не подтверждает sample/condition/origin links.
- Первый development input: тот же frozen snapshot с 33 документами, включая
  повторную загрузку Welch. Сохранённый stage08 — 377 выбранных Terms / 1 087
  occurrences, не весь кандидатный инвентарь и не независимый benchmark.

Рабочее дерево уже содержит изменения stage08 и концептуальный документ.
HEAD сам по себе не представляет полный текущий baseline. Перед первым кодовым
патчем сохранить выбранную рабочую копию через существующий `freeze_baseline`;
не делать reset/clean, blanket commit или перезапись прошлых artifacts.

## 3. Состав минимальных контрактов

До кода оформить versioned contract, правила identity и compatibility. Объекты
ниже **предлагаются**, а не уже существуют:

| Объект | Обязательная информация | Инвариант |
| --- | --- | --- |
| Run manifest | Input/code/glossary/settings hashes, schema и algorithm versions, runtime, declared scope | Run воспроизводим; время создания не выдаётся за стабильную identity |
| Mention | Article identity, original PDF path/hash, layer identity/PDF hash, page text hash, page, start/end, exact quote | Цитата равна точному source slice; original PDF неизменен |
| Article-local term | Local ID, matching/display labels, mention references, generation methods, rank features | Локальная агрегация строк не устанавливает concept equivalence |
| Term use/context | Mention references, ordered exact context regions, section kind, scope/source diagnostics | Разные употребления одного term не получают общую роль автоматически |
| Classification assertion | Target use, axis/category, explicit source/policy basis, producer/version, review state | Unknown/multiple candidates разрешены; размер фразы не определяет тип |
| Relation assertion | Typed endpoints, evidence context references, source/policy basis, producer/version, review state | Lexical containment, co-occurrence и scientific relation различаются |
| Review event | Snapshot/target/policy identities, expected revision, declared reviewer kind, decision/reason/time, superseded event | Human acceptance не создаётся алгоритмом; прошлые решения сохраняются |
| View definition | Filters/sort, taxonomy/policy versions, input snapshot, review revision cutoff | Snapshot view воспроизводим; latest view маркируется как динамический |

Identity source mention должна зависеть от article scope, PDF/layer/page identity
и точных offsets. Проектирование hash payload и canonical serialization — задача
этапа 2, не скрытая реализация этого документа. Пути не должны быть единственной
identity; перемещение файла не означает новый научный источник. Две отдельные
загрузки одинакового PDF сохраняют различные article scope IDs. ID упоминания
отделяется от hash полного run; новый алгоритм не должен переименовывать
неизменное source mention только из-за даты запуска.

Классификации и relations ссылаются на конкретные usages/contexts. Привязка к
правилу taxonomy не подменяет цитату о научной связи. Source integrity,
classification review и relation review — отдельные состояния. Исходная
контаминация TAC не исчезает после назначения категории.

## 4. Этапы реализации

### Этап 1. Полный кандидатный инвентарь и отдельное превью

**Статус 13 октября:** реализован как [TAC stage09](tac_stage09_inventory_2026-10-13.md).
Сохранены 2 266 кандидатов / 4 195 exact occurrences; прежнее превью 377 Terms
совпало для всех 33 документов. Новый формат включается явно, legacy v0.3
сохранён. 892 теста прошли; HTML и источники проверены. Это engineering completion,
не scientific acceptance. Следующее поручение — этап 2.

**Изменения:**

- Зафиксировать новый Terms schema/version и explicit compatibility contract.
  Старые v0.3 artifacts остаются читаемыми отдельной проверяемой веткой; не
  ослаблять прежний validator до принятия произвольных полей/versions.
- Отделить generation/ranking от preview selection. Сохранить каждый произведённый
  кандидат, его точные occurrences, исходный score и состав rank features.
- Сохранить вложенные фразы; вывести display suppression и lexical-overlap
  причины отдельно. Все preview IDs должны ссылаться на inventory entries.
- `preview_limit=12` оставить параметром представления. Старый `max_terms` либо
  поддержать явным compatibility path, либо заменить с диагностикой; не менять
  смысл прежних сохранённых settings молча.
- HTML: в Terms показать полный/preview counts, первые кандидаты и раскрытие
  остальных. Поиск должен находить кандидаты за пределами preview. Для большого
  списка применять pagination/render-on-expand без ограничения хранимых данных.
- Оставить generation anchors, stopwords, unit/broken-word filtering, source
  scope и ranking формулу неизменными в этом патче. Их качество — другая задача.

**Приёмка:** inventory count равен числу кандидатов до preview/suppression;
каждый candidate/occurrence проходит exact-source validation; изменение preview
limit не меняет инвентарь. На том же input старое default preview воспроизводится,
если сохраняется прежняя selection policy. Пропуски candidate generator не
объявляются закрытыми сохранением полного его выхода.

**Артефакты:** новый sidecar, change/count report, source-integrity manifest и
отдельный HTML всех 33 документов с прежними восемью колонками. Научная точность
не оценивается количеством новых отображённых фраз.

### Этап 2. Упоминания, контексты и лексическая структура

**Статус 13 октября:** реализован как [TAC stage10](tac_stage10_contexts_2026-10-13.md).
Все 2 266 Terms сохранены; 4 195 mentions/uses, 98 exact context fragments,
3 635 source-span containments. 913 тестов прошли, mypy охватывает 87 файлов,
HTML и source bindings проверены. Scientific classification/admission не выполнены.
Следующее bounded поручение — этап 3: proposed categories и overlapping subsets.

**Изменения:** ввести stable mention IDs и локальные term/use IDs; вынести source
evidence в проверяемые references. Начальный context — exact containing TAC
section/page fragment. Более узкий paragraph/sentence context использовать
только при однозначно сохранённых offsets; word-per-line PDF не считать обычными
предложениями по newline. Cross-page context — ordered separate regions с явной
непрерывностью, без склейки пропущенных страниц.

Из полного инвентаря вывести лексические вложения конкретных source spans.
`conductivity` внутри длинной фразы — lexical containment. Concept hierarchy,
синонимия и property/material relation этим шагом не выводятся. Прямой containment
можно хранить отдельно от вычисляемого transitive lexical view.

**Приёмка:** одинаковый frozen source даёт стабильные identities; повторное
слово имеет отдельные occurrences; разные статьи/контексты не смешиваются.
Изменённый quote/layer/offset/hash обнаруживается. Все фразы из этапа 1 доступны;
formatting и формулы источника сохранены. Отдельно проверить duplicate Welch и
Nagasubramanian word-per-line geometry как development cases.

**Артефакты:** source/context contract, manifest, containment sidecar и новый HTML.
Переиспользовать подходы `app.records.sources` после проверки совместимости;
не копировать специфическую Li-Nafion scientific schema в общий Terms contract.

### Этап 3. Черновая классификация и пересекающиеся subsets

**Статус 13 октября:** engineering реализован как
[TAC stage11](tac_stage11_classification_2026-10-13.md): draft taxonomy, per-use
type/role/origin assignments, unclassified/unresolved, overlapping subsets,
deterministic sort и graph/review exporters. 934 теста прошли. Восемь ручных
предложений агента в одном abstract демонстрируют контекстные роли/происхождение;
independent domain review, accuracy и scientific acceptance не выполнены.
Следующий bounded этап — 4: persistent review и история.

**Изменения:** versioned taxonomy по осям type, role, origin. Начальные type
categories: material/substance, object, property, process, method, condition и
unclassified. Названия и допустимые сочетания проверить на development review.
Role/origin относятся к конкретному usage, а не строке во всех статьях.

Начать с ручных assertions и ограниченных объяснимых правил. Dictionary/seed
match допускает предложение категории, а не автоматическую scientific acceptance.
Неподдерживаемые, конфликтующие и полисемичные случаи оставлять unclassified
или unresolved. Модельный proposer — optional отдельный эксперимент после
annotation protocol; он не нужен для первого рабочего интерфейса.

Subsets формировать фильтрами над assertions/usages. Один term отображается в
нескольких subsets с одним local ID; основная категория и дополнительные метки
не переписывают источник. Добавить deterministic sort по source/rank или алфавиту;
порядок и policy фиксировать в view definition. Состояния review показывать отдельно
от semantic axes.

**Приёмка:** assignments имеют основание и version; unknown не теряется без
диагностики; subsets воспроизводимы и не дублируют storage records. Возможны
разные roles одной строки в разных contexts. До независимой проверки категория
всегда отображается как proposal. Проверять correctness categories отдельно от
корректности цитат и полноты candidate generation.

**Артефакты:** taxonomy draft, annotation guide, proposed assertions, saved views,
HTML со всеми документами; колонки остаются прежними, subsets внутри Terms.

### Этап 4. Постоянный review и история решений

**Изменения:** immutable Terms snapshots плюс отдельный transactional SQLite
decision log в изолированном локальном review directory. Добавить локальный
Terms workbench к приложению; HTML exporter остаётся read-only и может отображать
зафиксированные решения. Статический HTML сам не записывает scientific decisions
в production или в файлы на диске.

Использовать паттерны существующего numeric review: explicit expected revision,
конфликт параллельных изменений, source/snapshot validation, escaping и CSRF для
write routes. Новый Terms decision contract и storage namespace оформить явно;
numeric history/schema не изменять и не импортировать решения без проверки.
Reviewer identity в локальном UI — заявленная identity, пока нет отдельной
аутентификации; не объявлять агентскую разметку независимой человеческой.

Действия: подтвердить/исправить/отклонить конкретную classification assertion,
отметить ambiguity, просмотреть evidence и историю, экспортировать JSON. Исправление
создаёт новую assertion/revision. Разделить review релевантности term, категории
и научного отношения; одно подтверждение не принимает всё сразу.

При новом input/policy показать diff и stale dependencies. Старое accepted decision
не переносится автоматически на изменённый target/context. Политика reuse при
побайтово неизменном evidence задаётся явно и проверяется отдельно.

**Приёмка:** решения переживают перезапуск; lost updates отклоняются; неизвестный
target, stale snapshot и изменённый evidence не принимаются. History/export
восстанавливают тот же view. Проверить backup/restore SQLite вместе с snapshots
и policy files. Автоматические проверки не создают human-confirmed status.

**Артефакты:** Terms workbench, event log contract, restore recipe, review export и
отдельный HTML snapshot полного stage scope.

### Этап 5. Отдельный пилот научных связей

**Изменения:** начать с ограниченного набора `property-of` и `measured-by`, после
review потребности добавить `component-of`/`under-condition`. Сначала manual
source-bound proposals и небольшое число объяснимых supported patterns. Каждая
relation имеет typed endpoints, полный context, evidence и собственное review.
Co-occurrence остаётся отдельным lexical observation.

Негативные/неоднозначные случаи обязательны: bibliography-only mention,
цитируемый результат, метод текущей статьи рядом с prior result, два образца,
условия общего эксперимента без связи с конкретным значением. Table cells и
footnotes не выводить из плоского TAC текста; такие cases направлять в supported
full-text/record workflow или явно откладывать.

**Приёмка:** человек может проверить endpoints и связь по источнику, исправить
или отклонить её. Научную correctness оценивать на отдельно размеченных relations;
exact quote match или несколько верных отдельных полей не считаются валидной
связью. Retained TAC boundary errors показаны; подтверждение scientific relation
не отменяет source diagnostics.

**Артефакты:** relation contract, gold/annotation protocol, candidate relations,
failure report, relation review UI и отдельный stage HTML. Если scientific review
не завершён, оставить proposals и продолжать engineering tasks без заявления accuracy.

### Этап 6. Сопоставление между статьями и контекстами

**Изменения:** предложенные mapping links между local Terms, сохраняющие обе
записи и contexts. Различать similar label, possible equivalent concept и
scientifically comparable measurements. Не делать автоматическую transitive
склейку mappings и не выводить equivalence по переводу/аббревиатуре.

Экран сравнения показывает материал/форму, образец, температуру, среду/состав,
метод и происхождение результата там, где есть source-bound reviewed data.
Недостаточность/ambiguous linkage — явные состояния. Различие conditions само
по себе не означает противоречие scientific results. Правила сопоставимости
задаёт отдельный domain protocol; возможна задача сравнить различающиеся условия.

Числовые значения и единицы берутся только из собственного record contract;
не извлекать их из имени term и не автоматически принимать legacy structured facts.
Согласовать integration с открытой научной приёмкой Li-Nafion records.

**Приёмка:** совпавшие строки не превращаются в объединённый научный факт;
own/prior result attribution сохраняется. Для решения о comparison есть
согласованная policy, source evidence и reviewer status; unavailable fields
видны. Все links возвращают пользователя к исходным локальным Terms.

**Артефакты:** mapping/comparison protocol, comparison worksheets/views,
проверяемая демонстрация на согласованных случаях и отдельный stage HTML.

### Этап 7. Проверка пользы и ограниченный retrieval эксперимент

**Изменения:** evaluator по отдельным слоям и workflow benchmark. Минимум сравнить
текущий flat preview, полный inventory и proposed contextual workflow на одинаковых
документах/задачах. Для утверждения преимущества перед аналогом отдельно выбрать
продукт, поддерживаемый им workflow и одинаковые критерии сравнения.

Гипотезы: меньше пропусков из-за preview, быстрее review, меньше ошибок sample/
condition/origin linkage. Метрики: term relevance precision/recall, classification
correctness, relation correctness/coverage/abstention, время до проверенной
подборки, corrections/task и полнота evidence traceability. Unresolved/missing/
failed cases остаются в отчёте; output counts и synthetic tests не заменяют gold.

Новые независимые задачи/работы и экспертная разметка обязательны для independent
claim. Все прежние 33 документа уже development; duplicate works/supplements
группировать до split. Для сравнения времени учитывать learning/order effects и
время исправления, а не только inference/runtime. Целевые thresholds и sample
size установить до оценки; сейчас не выдумывать значения эффективности.

Если этого достаточно для experimental retrieval: подключить Terms как отдельный
candidate/filter/boost channel с explicit configuration. Проверить production
full-text baseline, recall и потери evidence; TAC/Terms не делать жёстким gate.
Сначала frozen replay, затем live benchmark/latency после релевантной реализации.
Новый channel должен отключаться с восстановлением прежнего retrieval behavior.

**Приёмка:** инженерная регрессия проходит; measured report отделяет development
от independent results. Пользовательская экономия времени и научные улучшения
объявляются только по фактическим данным. Не принимать retrieval experiment,
если он скрывает нужное full-text evidence или не имеет воспроизводимого rollback.

### Этап 8. Production integration и эксплуатация

**Зависимости:** стабильные contracts, понятная review policy, измеренная польза,
проверенные backup/restore и provenance. Это отдельный объём разработки после
приёмки ограниченного prototype.

Определить production schema/migration, indexes, доступ и ownership, ingestion
jobs и invalidation policy. Оригиналы остаются immutable; старые источники,
решения и schema versions не удаляются ради переноса. Проверить packaging: нынешний
wheel собирает `app*`, поэтому рабочие components должны быть включены явно, а
experiment scripts не объявляются автоматически частью поставки.

Проверить cold/warm timings, память, большие candidate inventories, конкурентный
review и восстановление. Если taxonomy/gold/relations пока нестабильны, сохранить
sidecar scope; не делать migration для демонстрации одного HTML результата.

## 5. Предлагаемая организация кода

Это **планируемые пути**, не существующая реализация:

```text
app/terms/
  schema.py           # versioned inventory, mentions/usages/assertions
  inventory.py        # complete candidates and independent preview selection
  contexts.py         # exact source identity/context binding
  classification.py   # versioned proposal rules; explicit unknown
  relations.py        # lexical and reviewed semantic assertions
  review_store.py     # immutable snapshots + separate transactional events
  views.py            # deterministic subsets and snapshot definitions
  cli.py              # build, validate, snapshot, export
  review_ui.py        # local persistent review after stage 4
  comparison.py       # reviewed cross-article mappings/context comparisons
app/evaluation/terms.py
docs/terms/            # contracts, taxonomy, annotation/evaluation protocols
tests/unit/test_terms_*.py
```

В этапе 1 допустим минимальный patch существующих experiment scripts без
создания всего package. Перенос устойчивой логики в `app/terms/` делать постепенно
при оформлении контракта этапа 2; не поддерживать две расходящиеся реализации
candidate generation. `scripts/tac_terms.py` может стать compatibility wrapper
после проверенного переноса. Имена/команды уточнять перед соответствующим этапом.

Private inputs/outputs: отдельные ignored `data/experiments/tac/<run>/` и
`data/reviews/terms/`; HTML — `output/<stage>/`. Секреты и literature text не
включать в tracked fixtures или публичную поставку. Synthetic fixtures явно
маркировать. Каждый этап имеет input/code/artifact manifest и собственный каталог.

## 6. Общие проверки и ворота

Для каждого изменения сначала meaningful targeted tests: источник/identity,
preview/inventory independence, stale evidence rejection, context attribution,
revision conflicts, lost updates или reproducible views — по реальному scope.
Не писать тесты только для повторения внутреннего implementation.

На завершении кодового этапа выполнить существующие команды:

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Новые modules в `app/terms/` должны входить в mypy scope. Full suite повторять после
новых изменений/неразрешённых failures, а не для каждого label или документа.
Sandbox failure отличать от implementation failure; повторять вне sandbox только
штатным разрешённым способом и сохранять причину/логи. Старые успешные runs не
считать результатом нового этапа.

На каждом завершённом TAC development stage: HTML всех scope documents с Title,
Authors, Journal, Year, Abstract, Conclusions, Terms и hyperlink to original file;
полный expandable текст, поиск, original-PDF links, version/input identities,
missing/unimplemented/proposed fields и diagnostics. Сделать browser/visual QA и
проверить exact display text, ссылки и controls. Не генерировать XLSX без запроса.
Кодовые patches не скрывают failures и не чинят сохранённые scientific outputs вручную.

Проверить physical original PDF hashes и hashes затронутых dependencies. Stage
profile/metadata/app invariance проверять в пределах заявленной scope; при
намеренной UI/module integration явно записывать changed files. Не заявлять
unchanged application после добавления Terms router.

Ворота:

- **Первый demonstrator:** этапы 1–3, exact-source inventory/contexts и proposed
  subsets; научная приёмка отсутствует, пока нет labels/review.
- **Рабочий review:** этап 4, persistence, concurrency, history и restore проверены.
- **Научные links:** этапы 5–6, supported scope и scientific adjudication заданы;
  engineering completion отделяется от независимой acceptance.
- **Измеренное преимущество:** этап 7, заранее зафиксированные tasks/protocol,
  independent evidence там, где делаются соответствующие claims.
- **Production:** этап 8, schema/rollback/operations проверены отдельно.

## 7. Первое конкретное поручение — выполнено

Выполнить **только этап 1** как TAC stage09:

1. Сохранить текущие изменения и source baseline; frozen stage08 artifacts
   использовать как вход. Проверить hashes и `.gitignore` до новых outputs.
2. Оформить новый complete inventory contract с legacy v0.3 compatibility.
3. Сохранить все произведённые candidates/occurrences; выделить preview policy.
4. Обновить HTML exporter: полный список раскрывается, preview — 12; search
   охватывает hidden candidates; nested phrases сохраняются с lexical diagnostics.
5. Проверить invariants и старое preview на том же frozen input. Не менять
   generation/ranking, categories, relations, source sections или production search.
6. Выпустить отдельную HTML-таблицу всех 33 документов, manifests, count/change
   report и Changed / Tests run / Limitations / Verdict.

После этого оценить размер полного inventory и удобство HTML; уточнить реализацию
этапов 2–4 по реальным данным. Календарные сроки и budget не обещаются до этого
измерения; доступность научного reviewer влияет на этапы 3, 5–7.

Поручение выполнено 13 октября как stage09; полный inventory имеет 6–217
кандидатов на документ, финальный HTML — около 3 MB. Это размеры данного run,
не benchmark производительности. Следовавший этап 2 с контрактом exact
mention/context identity и lexical containment также выполнен как stage10;
текущее bounded поручение — этап 3. Не запускать
повтор этапа 1 без новых inputs/изменений или причины проверки.

## Changed / Tests run / Limitations / Verdict

Changed: составлен поэтапный implementation plan с contracts, acceptance gates,
rollback boundaries, proposed code layout и первым bounded поручением. В
production/runtime code этим планом изменения не внесены.

Tests run: прочитаны Terms/exporter/tests, numeric review store/UI, record review
contract, packaging и ignore rules. Проверены локальные ссылки и структура
сохранённого плана. Runtime tests при планировании не запускались.

Limitations: будущие schemas/modules/commands, taxonomy, scientific relations,
independent dataset и efficacy thresholds не реализованы/не приняты. Полный
candidate inventory ещё не измерен; числа stage08 относятся к selected output.

Verdict: очередь реализации определена. Начать с этапа 1; научные связи,
production integration и заявление превосходства требуют отдельных результатов.

Обновление после выполнения: engineering этапов 1–4 закрыт как
[TAC stage09](tac_stage09_inventory_2026-10-13.md), [stage10](tac_stage10_contexts_2026-10-13.md)
и [stage11](tac_stage11_classification_2026-10-13.md), затем
[stage12](tac_stage12_review_2026-10-13.md): постоянный review и история.
Следующий этап — 5, после review конфликтов и определения bounded scope научных
связей. Научная приёмка классификаций, связи и преимущества всего workflow
остаются непроверенными.

14 октября подготовлен [source audit конфликтов stage12](terms_conflict_audit_2026-10-14.md):
17 Terms / 54 употребления, 7 assistant proposals property, 39 condition и
8 нерешённых случаев concentration Doi. Рабочий review ledger остаётся без решений;
это не human scientific acceptance. Сохранены отдельная HTML-таблица всех
33 документов, точные evidence и девять development примеров связей. Определён
[bounded scope этапа 5](terms_relation_pilot_scope_2026-10-14.md), включая отсутствующие
method endpoints и abstain/deferred случаи. Relation extractor/store/UI ещё не
реализованы. Browser visual/runtime QA этого audit HTML не выполнены: file protocol
отклонён browser security policy; статические проверки выполнены отдельно.

После запроса убрать ручное разрешение 14 октября завершён
[stage13 automatic workflow](tac_stage13_automatic_2026-10-14.md). Live UI/API не
принимают manual decisions, v0.2 CLI не принимает manual proposals, subsets
вычисляются по policy/контекстам. Из 54 прежних конфликтных uses 46 имеют
автоматические предложения, восемь concentration Doi остаются в диагностике.
Это development результат, не independent accuracy. Старые решения не влияют
на новые subsets; их архив не удалён. Будущие Terms relations также должны
предлагаться алгоритмом с явной неопределённостью, без обязательной формы
пользовательского разрешения каждого случая. Независимая разметка качества
остаётся отдельной evaluation задачей.

14 октября завершён [stage18 TAC boundary cleanup](tac_stage18_boundary_cleanup_2026-10-14.md):
известные шесть ошибок границ и один пропуск исправлены под явной версией v0.8,
Terms пересобраны автоматически; отдельная таблица сохраняет все 33 документа.
Независимая точность не установлена; метрики прежних 46 поисковых вопросов не изменились.

14 октября завершён [stage19: новые открытые статьи и TAC v0.9](tac_stage19_holdout_result_2026-10-14.md).
Восемь новых PDF и source reference заморожены до первого запуска v0.8;
первый результат — 14/24 совпадений границ, после общих исправлений — 24/24.
Корпус теперь development, независимая точность не установлена. Прежние
99 полей TAC и 91 заполненное значение метаданных сохранены. Automatic Terms
восьми новых документов находятся в отдельном snapshot; production corpus
и retrieval scoring не менялись. Следующая проверка v0.9 требует новых
невиденных документов; metadata parsing остаётся отдельным недостатком.
