# ARIADNE: explicit particle attachment and direction v0.7

3 ноября 2026 года, Asia/Yekaterinburg. Offline-продолжение
[source-reference chains v0.6](source_reference_chain_2026-11-03.md).

**Локальная принадлежность частиц и привязка свойства извлекаются отдельно от
направления зависимости и достаточности ответа. Полных solvent-query requirements
по-прежнему0.** Новые результаты описывают source syntax, не научную приёмку.

Changed:

- Read-only inspection всех33 frozen PDFs/493 pages сохранила все40 страниц,
  содержащих target + morphology/shape + particle/dispersion. Это локальная
  инспекция исходных PDF, не новый production search, DB или embedding call.
  Нативные MuPDF diagnostics сохранены для15 страниц; они не подавлялись.
  v01 exploratory scan и v02 с per-page diagnostics сохранены отдельно;
  массивы отобранных страниц совпали точно. Старый source hash v01 не переписан.
- До реализации analyzer записаны [протокол](records/particle_attachment_protocol_v0.7.md),
  [recipe](records/particle_attachment_recipe_v0.7.json) и
  [packet](records/particle_attachment_cases_v0.7.json):14 точных окон из шести
  работ — Kim2015, Welch2012, Chernyuk2024, диссертация Chernyuk, Ma2009 и Moore1988.
  Сохранены exact page/span/PDF hashes, selection markers, полные page texts и
  предварительные source-inspection annotations. Выбранные14 окон относятся к
  страницам без зарегистрированных MuPDF diagnostics; это не visual QA.
- Packet содержит явные particle-owner/dispersion/shape descriptions, ratio
  dependency, likely-cause hypothesis, concentration/null, unperformed correlation,
  модельный контекст и membrane/film distractors. Автор labels — ассистент;
  разметка сделана после чтения источников, до candidate outputs, на exposed
  development corpus. Она не является независимым scientific gold.
- Новый `particle_attachment_audit.py` оборачивает неизменный v0.6 и добавляет
  отдельные `atomic_sources`, `particle_relations`, `particle_requirements_met`,
  `exact_particle_groups`. Старые поля/решения v0.6 сохранены точно. Public API,
  generation/gate/ranking/index не менялись.
- Конечная grammar поддерживает TARGET particles / particles of TARGET / RU
  частицы TARGET, прямую привязку morphology/shape и явный have/form predicate.
  Dispersion привязывается локальным синтаксисом, непосредственно к частицам
  или к их прямо привязанному свойству. Liquid media не становятся dispersion.
  Соседние материал, title, paragraph или другое source не снабжают owner.
- Directed dependency проверяется отдельно: active/passive direction, нужный
  предлог и endpoint tail. Transitive 'morphology changes solvent', обратный
  passive, contamination/unknown-subject tails не получают requested completeness.
  Description, гипотеза, unperformed/absent evidence, bare negation и observed
  shape-null имеют разные diagnostics/status. Ratio не становится solvent по
  названию компонентов; temperature/concentration отвечают другой переменной.
- Все source links имеют exact raw anchors. Role links — текстовые связи,
  не подтверждение выполнения опыта, scientific material/value owner или
  причинности. Все соответствующие admission/owner/performed flags false.
  Значения, условия и percent basis не переносятся и не пересчитываются.

Фактическое сравнение:

Те же328 frozen preparations:304 historical +24 window-candidate traces.
Выполнены328 actual production-service full trace/status replays и1968 repeated
top-level diagnostics: v0.4/v0.6/v0.7, каждый дважды. Nested readers не являются
дополнительными независимыми измерениями. Fresh v0.6 точно совпал со всеми328
saved outputs;292 outside-scope baseline сохранены. Никакой source selection
или нового модельного ответа не создавалось.

| Измерение v0.7 | Результат |
| --- | ---: |
| Scoped morphology evidence sets | 36 |
| Sets с explicit particle-owner syntax | 24/36 |
| Sets с locally attached dispersion syntax | 21/36 |
| Eligible local attachment observations | 158 |
| Unique exact raw attachment units | 7 |
| Role-complete link observations | 17 |
| Full original solvent-query requirements | 0 |

**158 observations — повторные локальные привязки в семи raw fragments, не158
научных фактов или независимых подтверждений.** Термин eligible в v0.7 означает
допустимую локальную owner/property syntax, а не поддержанный фактический тезис.
Реальные источники повторяются между queries/arms/copies; provenance не удалён.

Разбор семи raw units:

| Source reading | Observations | Ограничение |
| --- | ---: | --- |
| Welch: particle morphology affected by named ratio | 39 | Направление есть; local dispersion/solvent binding unresolved |
| Welch: three morphology types in liquid media | 33 | Краткое описание, без направленной переменной; liquid media не dispersion |
| Kim: owned particles in dispersions, cylindrical morphology | 9 | Shape description, не directed solvent dependency |
| Welch: 'we investigate' | 21 | Method/intent mention, не конкретный morphology result |
| Welch: previous studies examined / page continuation | 21 | Method/context fragment, не конкретный result |
| Welch: modeling for describing | 27 | Незавершённый method/modelling fragment |
| Kim: concentration-linked nonformation of lamellar structure | 8 | Observed null/different variable; concentration owner unverified |

17 role-complete observations относятся к двум raw types:9 shape descriptions
и8 concentration/null records. Это полнота локальных текстовых связок по grammar,
не полнота ответа о природе растворителя. Нельзя считать concentration или
описание формы доказательством требуемой solvent dependence.

Новый packet и контроль ошибок:

- На14 real windows source-presence observations particle owner/attached
  dispersion совпали с предварительными annotations:28 отдельных boolean
  checks. Explicit owner обнаружен в7/14, attached dispersion в3/14. Это не
  scientific precision/recall, general accuracy или независимая оценка.
- Kim geometry и concentration/null дают разные locally complete role links;
  requested solvent requirements остаются false. Welch ratio сохраняет
  directed relation/owned particles, но не получает выдуманный medium owner.
  Likely cause, no-attempt, wrong membrane/film, model-only и unbound material
  windows не становятся достаточным particle answer.
- Положительных полных original solvent-query labels в real packet нет;
  научную false-refusal rate полного допуска на нём определить нельзя. Положительные
  unqualified complete relations проверены отдельно constructed controls.
- 46 новых constructed controls и193 старых replay проверяют grammar/guards и
  exact v0.6 preservation. Совпадения controls не объявляются научной accuracy.

Post-measurement limitation:

Source review обнаружил избыточно широкий ярлык `morphology_description`:
**69/158 observations (три unique units) являются method/intent/modelling mentions**,
а не конкретными результатами о морфологии. Это существенный предел семантической
классификации v0.7. Он не скрыт и не исправлен после измерения. Отдельное
[post-hoc чтение](../output/particle_attachment_20261103/semantic_caution_v02.json)
сохраняет все raw fragments/addresses и origin assistant post-measurement review,
не заменяет algorithm output и не получает статуса independent gold.
v01 cue-reader не учёл один перенос строки и отметил48; отдельный v02 исправляет
только whitespace matching этого post-hoc helper до69, не raw source/candidate.

Tests run:

- **423 affected tests passed**,68 новых в двух test modules,18 modules всего.
  Финальный JUnit: `output/particle_attachment_20261103/tests_v01.xml`.
  Preflight60/65/68 и прежние355 — перекрывающиеся прогоны, не добавление к423.
- Ruff всех семи новых Python files passed. Mypy не запускался.
- 328 full-service replays/1968 repeated diagnostics, corrupted retrieval source
  и baseline metadata отклонены. Guards проверяют corrupt raw owner span,
  invented value owner, shape→requested-dependency promotion, unsupported
  direction, condition scope и193 exact older decisions.
- 374 current bindings и33 original PDF hashes проверены. Fresh containment:
  восемь reference anchors, шесть старых real windows, два prior-chain windows
  и14 новых source windows. Полная fresh extraction всех corpus parent texts
  или одинаковое визуальное отображение PDF не заявляются.
- Static HTML QA passed:33 TAC rows/eight columns/41 working original PDF links,
  search/full expandable metadata, все14 real cases с raw texts/diagnostics.
  1806 base graph spans/6079 atomic spans и exact atomic/base replay passed.
  QA: `output/particle_attachment_20261103/qa_v01.json`.
- Предыдущие marker ambiguity/diagnostic-source drift, E501, два preflight
  ratio failures/63 passed и исправления до corpus measurement сохранены в
  [execution notes](records/particle_attachment_execution_notes_v0.7.md).
  Нативные MuPDF warnings не подавлялись. Измеренный v0.7 не менялся.

Limitations:

- Full requested particle/solvent relation остаётся0. Локальная syntax и role
  completeness не устанавливают scientific adequacy или ownership условий.
- Method/result/model semantics ещё не разделены достаточно строго:69 mentions
  имеют слишком общий description label. Эти observations нельзя передавать
  как извлечённые научные facts или использовать для допуска ответа.
- Конечная grammar не разрешает общую анафору, неявных subjects/quantity owners,
  любые variable forms или повторные particle mentions. Например, water-fraction
  direction при отсутствующем material в dissertation window остаётся unresolved;
  generic ratio/temperature/concentration не заполняют solvent requirements.
- Exposed assistant development labels/selected windows, не независимая оценка.
  New live answers, scientific correctness/acceptance и broad false-admission/
  false-refusal rates не измерены. Фиксация ошибки алгоритма не является её
  исправлением в рабочем runtime.
- Browser execution, PDF visual QA, full suite, mypy и concurrency не проверялись.
  Adapter serial/offline, production integration отсутствует. App/gate/index/
  prompt/public schema/scientific thresholds unchanged; новых DB/production
  search/embedding/model/OAuth/native requests/downloads/slots0. Локальный PDF
  scan493 pages учтён отдельно. Все live budgets закрыты; independent evaluation,
  cache/ORM и deferred rewriting остаются открытыми по прежним решениям.

Verdict:

**Offline-аудит выполнен: exact particle attachments и направление проверяются
раздельно, прежние решения сохранены. Кандидат помогает разбирать источники,
но полную требуемую solvent dependency не восстановил и имеет known mention/
result-label limitation. В рабочий gate не подключать.**

Итоговый [HTML review_v01](../output/particle_attachment_20261103/review_v01/review.html).
Следующая отдельно версионированная работа должна сначала различать mention/
method/model/actual result и измерить этот слой на frozen real negatives и
positives; нельзя наращивать admissions по счётчику owner/property syntax.
Независимая научная оценка остаётся открытой до новых внешних вопросов/эталонов.

**План качества ответов75% работ**, scientific accuracy/acceptance не установлены.
