# ARIADNE: пакет доказательств и диагностический журнал

Начат 9 ноября, завершён 10 ноября 2026, Asia/Yekaterinburg. Имена protocol,
scripts/output сохраняют дату начала; старые файлы не переименовывались.

Changed:

Реализован минимальный JSON-контракт `answer_evidence_packet_v0.1` поверх
`composition_cycling_requirements_v0.1` и журнал `answer_diagnostic_journal_v0.1`.
Старые `/answer`, `/answer/prepare`, requirements API и их решения сохранены.
Новые явные маршруты:

- `POST /answer/prepare/requirements/packet`: canonical UTF-8 JSON attachment;
- `GET /ui/answer/prepare/requirements/packet`;
- `POST /ui/answer/prepare/requirements/packet`.

Они используют прежний request, библиотеку/cookie, read-only подготовку и карту.
Полный request_scope сверяется с возвращённой подготовкой. Клиент не передаёт
packet/path/generate и не выбирает серверный путь записи. API сам не сохраняет
файлы. Отдельный явный `save_packet` экспортирует новый файл через exclusive
creation; существующий snapshot не перезаписывается. `load_packet` требует
canonical bytes и проверку против доверенного текущего parent. Нет автоматической
миграции/ремонта старых пакетов или новой БД.

Относительно freeze196 app Python/YAML изменены два прежних app файла: main
(router) и preparation_routes (навигационная ссылка). Добавлены
`answer_evidence_packet.py` и `evidence_packet_routes.py`. Preparation/service/
requirements/facts/Methods policy/retrieval/filters/context budgets/DB/PDF/index/
inference admission не менялись. Прежние незакоммиченные изменения других этапов
не приписываются этому патчу; они отдельно связаны с исходным snapshot.

Пакет сохраняет:

- весь неизменённый requirement-preparation parent и его hash;
- исходный scope, либо его незаполненное состояние без выдуманных фильтров;
- версии contracts и hashes18 явно перечисленных code dependencies;
- selected raw источники с article/chunk/citation/page-range/type/layer/hash;
- PDF/page/layer identities из registry, если они действительно присутствуют;
- exact anchors, факты-кандидаты с units/conditions/status/unknowns;
- ссылки арифметики на факты и исходный результат существующего recipe;
- требования, исходные blockers и read-only stop.

Source/anchor/fact/transformation IDs вычисляются из содержимого. Существующие
map/derived-graph/Anchor/SourceRegion/aligned_pages проверки переиспользованы.
Каждый anchor проверяется против выбранного raw родителя. Полностью доказанная
привязка anchor к одной странице имеет её точные offsets; cross-page либо
недоступный registry остаются `exact_page_mapping_unresolved`. Пакет не читает
пути PDF из snapshot и не выдаёт declared hash за свежую проверку файла.
Весь parent, включая неоднозначные варианты и повторные наблюдения, сохраняется.
Новых утверждений нет: claims=[]; scientific_support=not_evaluated.

Журнал содержит последовательность наблюдений системы: исходная подготовка,
пересчитанная карта, состояния каждого требования с фактическими diagnostics/
contracts/unknowns и предложенным действием, затем read-only stop. У событий
есть sequence, предыдущий hash, input/output hashes, reason и ссылки на данные.
События не выдают реконструированные действия поиска за выполненные операции.
Action execution=false; человеческих review нет, timestamps/durations не
выдумываются. Журнал не включает модельных токенов, стоимости или OAuth secrets.
Факты генерации и человеческого подтверждения не создаются.

Прочитан existing `records/revision_store.py`: его record editing/decide/restore
и human-confirmation schema относятся к experimental records. Для этого scope
они не перенесены и не менялись. Используются общие source/hash contracts и
совместимый принцип проверяемой последовательности, без подключения SQLite store.

Проверка пакета заново строит его по доверенному current parent и текущим
declared code bindings; pinned packet_id доступен отдельно. Stale code/source/
scope/blockers, чужие/утраченные ссылки, изменённые факты/арифметика/журнал/версии
и лишние поля отклоняются полным сравнением. Hash chain — проверка целостности,
не криптографическое удостоверение автора/источника и не научная приёмка.

Tests run:

- До app edits: freeze196 app Python/YAML, протокола/controls;81 actual offline
  service runs и5 native bodies воспроизвели предыдущий baseline. Финальный
  compare ещё81: все5 current+76 old полные результаты и пять native bodies
  побайтно прежние. Итого162 frozen-channel service executions этого этапа,
  не независимые вопросы и не новые ответы модели.
- **1148 affected tests passed**, включая **71 новый** packet/replay/export/
  source/page/ASGI/UI test. Первый new-only probe:68passed; затем добавлены
  cross-page support, source markup escaping и actual preparation→packet
  no-generation boundary. pytest failures0. Это затронутый набор, не весь repo.
- Покрыты canonical round trip, отказ перезаписи, stale parent/source/code/scope/
  pinned ID, foreign/missing/duplicate refs, факты/арифметика, повреждение/порядок/
  усечение/причина/actor журнала, полные/недоступные/неправильные page registries,
  PDF hash/layer conflicts, explicit library options, API injection422 и UI
  escaping. Actual preparation/service проверена с synthetic DB/source seams
  и запретом provider factory; свежая production DB preparation не заявляется.
- Ruff восьми новых/затронутых app/test/script файлов passed; полный mypy app
  **198 source files**, success. Первые4 typing diagnostics исправлены:
  два пустых dictionary annotations, Optional lookup после цикла и generic
  html.escape(Any). Значения/units/thresholds/научная логика не менялись.
-27 исходных requirement controls экспортированы отдельными canonical JSON
  snapshots. У каждого проверены повторное построение и чтение, pinned identity,
  неизменённый parent и отказ повторной записи без изменения файла.
-181 journal event дополнительно проверен отдельной формулой exporter-а:
  sequence, previous hash, hash тела события, actor, root и packet digest.
  Это независимый технический подсчёт хешей, не независимая научная оценка.
- Основной пример с real Lin raw текстами, но **synthetic preparation**:
  packet_id `6d31a385940de66f0f923c501a07007a5c1f49682c6e2045fd4552d6910cbed0`,
  canonical167833 bytes,3 sources/58 anchors/6 fact observations/1 transformation/
  7 journal events. Два CE bindings не считаются двумя независимыми результатами.
  PDF page registry в этом минимальном parent отсутствует (entries0), поэтому
  исходный blocker source_registry_unproven сохранён. Свежая проверка экспортёра
  не переписала этот parent и не повысила его допуск.
-33 original PDF hashes и3 свежие Lin PDF1/3/7 проверены отдельно. Все58 уникальных
  anchors (67 наблюдений исходной карты) совпали с raw и свежими PDF в declared
  ranges. Три свежих рендера визуально просмотрены и сохранены.
- Статический HTML QA:5 прежних case sections,33 TAC works/eight columns,
  57 существующих PDF links,27 packet UI cases/181 event rows. Runtime fragments
  сохранены; локальная копия явно переназначает real source links на PDF,
  у synthetic IDs ссылки не выдаются за существующие PDF.
- External-network audit denials0. Model POST/OAuth exchanges/new slots/fresh
  DB preparation/ingestion/deployment0. Browser layout не проверялся из-за
  установленной ранее file:// policy block; новых попыток/обходов не было.
  `git diff --check` passed; обычные LF→CRLF notices сохранены.

Limitations:

Один конечный query family, раскрытые источники и synthetic preparations,
без независимого gold или измеренного scientific accuracy/refusal gain.
Self-contained replay не устанавливает актуальность реальной БД/PDF или
подлинность источника; требуется доверенный текущий parent/внешняя provenance.
Code manifest охватывает18 declared files, а не весь runtime/environment.
API не создаёт постоянную серверную историю, revisions/human review или
автоматические retrieval actions. Runtime imports/process reload, browser layout,
cache/ORM, concurrency/deployment, full repo suite и новая модельная работа
на этих данных остаются непроверенными. Прежние live scopes закрыты.

Verdict:

Минимальный версионированный пакет и воспроизводимый диагностический журнал
реализованы offline. Снимки сохраняют родительские данные, blockers и exact
bindings; canonical export/replay и выявление drift проверены. Это ограниченная
реализация второго архитектурного этапа, не научное принятие ответов.
Исходный план качества остаётся **75% работ**, независимая оценка открыта.

Следующий отдельный scope: одно ограниченное действие дополнения контекста
поверх пакета — сначала явные preconditions/лимиты/stop reasons и offline
positive/negative controls. Автоматическое выполнение этим этапом не включено.

- [HTML review](../output/answer_evidence_packet_20261109/review_v01/review.html)
- [UI пакета и журнала](../output/answer_evidence_packet_20261109/review_v01/packet_UI.html)
- [Первый canonical JSON snapshot](../output/answer_evidence_packet_20261109/review_v01/packets/000.json)
- [Все исходы экспорта](../output/answer_evidence_packet_20261109/review_v01/packet_outcomes.json)
- [Протокол](records/answer_evidence_packet_protocol_2026-11-09_v0.1.md)
