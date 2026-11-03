# ARIADNE: typed partial source relations v0.2

2 ноября 2026 года, Asia/Yekaterinburg. Следующий offline-кандидат после
[RU/EN relation audit](cross_lingual_relation_audit_2026-11-02.md).

Changed:

- До корпусного измерения записаны protocol, recipe и отдельный real development
  packet: все6 разных near-relation текстов предыдущего отчёта,150 прежних source
  addresses. Старый ca.-truncated span расширен до настоящего конца предложения;
  старые/новые offsets и parent text/hash сохранены. Есть1 явно размеченная
  partial dependency и5 описаний без такой dependency; это assistant post-hoc
  development labels на exposed источниках, не independent scientific gold.
- Добавлен `scripts/typed_partial_relations.py`. Он представляет property,
  variable node, directed predicate и явную target-property attachment отдельно
  от полной достаточности запроса. Все узлы/рёбра имеют exact raw anchors.
- Типы variable: literal solvent, generic named-component ratio, dimension ratio,
  unassigned numeric ratio, temperature, concentration с неизвестным owner или
  явной polymer-concentration surface. Компоненты распознаются по синтаксису,
  без каталога названий ожидаемых растворителей. Химическая идентичность и
  принадлежность переменной к solvent composition не выводятся из имени.
- Generic named ratio может дать partial edge, но не заполняет solvent/medium
  требования автоматически. Numeric ratio не получает выдуманные компоненты;
  temperature/dimension/concentration не подменяют solvent variable. Все
  quantitative owners остаются unverified, запросы с условиями не допускаются
  только по совпадению их числовых поверхностей. Межфрагментных переносов нет.
- Status, target attachment и field readers переиспользуют неизменный v0.1.
  Отдельная segmentation policy поддерживает ca./e.g./i.e./etc. Offline adapter
  временно заменяет только region function в serial call и восстанавливает её;
  он не предназначен для монтирования в production/concurrent API.
- В detail HTML добавлено отдельное сравнение partial/full. Все33 TAC работы,
  прежние8 колонок, полные тексты/graph diagnostics и41 original PDF/page link
  сохранены. Итог: `output/typed_partial_relation_20261102/review_v01/review.html`.

Фактическое сравнение:

Входы прежние:304 retrieval-arm evidence sets и24 window-candidate traces.
Выполнены328 production-service trace/status replays без нового поиска,
все полные результаты совпали. Каждый из трёх diagnostics исполнен дважды:
**1968 top-level arm executions**. Typed arm внутри использует strict reader;
внутренние вызовы не считаются дополнительными независимыми измерениями.
36 наборов в finite morphology scope,292 вне области baseline-preserved.

| Diagnostic | Наборы с partial graph | Наборы с полными textual requirements |
| --- | ---: | ---: |
| v0.1 | Не реализован | 0 |
| Только segmentation fix | Не реализован | 0 |
| Typed partial v0.2 | 20/36 | 0 |

**39 partial edge observations соответствуют одному unique raw relation type.**
Повторы между queries/arms/window qualifiers и source copies не являются39
независимыми экспериментами или научными подтверждениями. Единственная новая
извлекаемая relation — явная фраза Welch о зависимости Nafion particle morphology
от изменений water/2-propanol ratio. Variable имеет тип named_component_ratio;
solvent scope/medium/owners остаются unresolved, полного admission нет.

Частичные edges присутствуют в6 historical и14 window-candidate наборах.
Для original RU вопроса: historical expansion имеет1 observation; window
expansion body/local имеют2/1, combined body2. Для EN paraphrase встречаются
повторные copies до4 в одном evidence set. Все source addresses и точные
группы raw-relation hashes сохранены; никто не удалён из retrieval/evidence.

Constructed controls:

- Отдельно сравниваются48 прежних constructed controls,30 новых constructed
  controls и6 реальных development windows. Все30 новых ожидаемых поведений
  и6 real window labels воспроизведены; real packet содержит только1 positive.
  Эти числа не объявляются scientific precision/recall или независимой accuracy.
- Есть **1 потеря прежнего complete control**: `observed_nominal_null`.
  Старый analyzer понимал наблюдаемое «no effect of solvent on morphology»;
  graph требует predicate между endpoints и не связывает эту номинальную
  конструкцию. Потеря не скрыта, v0.2 после измерения не подгонялась.
- Source grammar, wrong material/object/property, reversed direction,
  intervening other property, future/absence/uncertainty, multiple variables,
  raw hyphen/ligature offsets, component typing и partial/full separation
  проверены явно. Conditions не получают owner от близкого числа.

Tests run:

- **272 affected tests passed**, включая40 новых typed/source-window tests;
  `tests_v01.xml`. Отдельно **2 новых graph-integrity tests passed** в
  `tests_review_v01.xml`. Итого274 различных теста,42 новых. Ранние39-test
  preflight и предыдущие итерации не прибавляются к этому числу повторно.
- Ruff шести новых source/test/QA files passed. Corrupted full retrieval source,
  corrupted baseline metadata, повреждённый component raw anchor и смешение
  partial/full requirement flags отклоняются ожидаемыми guards.
- 328 actual full-service replays,1968 repeated arm executions; fresh v0.1
  diagnostics совпали со всеми328 frozen предыдущими результатами. Проверены
  320 current bindings,33 original PDF hashes и8 fresh Kim reference anchors.
- Static HTML/graph QA прошла:33 TAC rows/8 columns/41 existing PDF links,
  отдельная partial table/search implementation;1806 graph raw spans проверены.
  Дополнительно все6 real development windows точно совпали со свежей PDF
  extraction, без нормализации ради прохождения проверки. QA: `qa_v01.json`.
- Ошибок запуска/failed tests/lint diagnostics в этой итерации не было.
  Preflight был дополнен концентрационным контролем до корпусного измерения,
  измеренный v0.2 после исходов не менялся. Старые guards/outputs не переписаны.

Limitations:

- Это finite partial-extraction diagnostic, не исправление рабочего gate.
  Полных source/query requirements по-прежнему0. Формулировки с номинальным
  эффектом имеют известную regression; неявные связи/общая анафора не решены.
- Компонентная ratio surface не доказывает solvent identity, процентную базу,
  причинность, принадлежность условий или выполнение эксперимента. Source edge
  и scientific entailment остаются разными уровнями.
- Подтверждён один exposed raw relation, а не обобщение по независимому корпусу.
  Более широкий source-coverage/ranking benefit и будущие model answers не
  измерены. Содержание источников не восстанавливалось из эталона.
- Browser execution, новая визуальная PDF QA, full suite и mypy не выполнялись.
  Adapter serial/offline; production integration/concurrency не проверялись.
- App/gate/index/PDF/prompt/public schema/scientific thresholds не менялись.
  Новых DB/search/embedding/model/OAuth/native requests/slots0. Все live budgets
  закрыты; cache/ORM defect и independent evaluation остаются открытыми.

Verdict:

**Кандидат полезен как отдельный слой partial source extraction:** перестал
терять явную named-ratio relation, не превращая её в достаточный ответ.
Для runtime admission/отказов не пригоден: full completeness0 и есть потеря
старого nominal-null control. Не подключать его как gate bypass/veto.

Следующая отдельная версия должна проверить source binding компонентной
переменной к явно описанным solvent/dispersion context и восстановление
nominal observed-null constructions, с теми же raw anchors/negative controls
и запретом переноса условий. Нельзя просто считать любую ratio растворителем.
Query rewriting остаётся отдельным отложенным экспериментом.

Независимая научная оценка открыта до новых эталонов.
**План качества ответов75% работ**, scientific acceptance/accuracy не установлены.
