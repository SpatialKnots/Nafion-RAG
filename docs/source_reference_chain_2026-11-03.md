# ARIADNE: explicit source-reference chains v0.5 → v0.6

3 ноября 2026 года, Asia/Yekaterinburg. Offline-продолжение
[component context v0.4](component_context_relation_2026-11-03.md).

**Восстановлена одна явная контекстная связка Welch, но не полная цепочка
«компоненты → смесь/дисперсия → частицы → зависимость морфологии».**
В16/36 scoped sets получены27 повторных observations одной unique raw chain.
Полных chain requirements0. Старые решения и рабочий gate не изменились.

Changed:

- Перед реализацией записан [протокол v0.5](records/source_reference_chain_protocol_v0.5.md)
  и заморожен [real packet](records/source_reference_cases_v0.5.json). Он сохраняет
  все шесть прежних окон, три разных полных parent texts,150 inherited near-span
  addresses и два окна со ВСЕМИ найденными конечной grammar demonstrative-medium
  references. Три raw parents не являются тремя независимыми статьями.
- Новые окна выбирались по заранее объявленному finite REF pattern, с предыдущим,
  текущим и следующим region неизменного v0.2 segmenter. Source-inspection labels
  записаны до candidate execution. Один контекст описывает явную ассоциацию;
  второй содержит possible-model cue. Это exposed assistant development labels,
  не независимый научный gold; labels/IDs/provenance в анализатор не входят.
- Новый `source_reference_chains.py` оборачивает неизменный v0.4. Его старые
  поля/partial relations/textual_requirements_met воспроизводятся точно.
  Новые `chain_sources`, `source_chains`, `chain_textual_requirements_met` и
  `exact_chain_groups` — отдельный versioned sidecar, не public API или gate.
- Грамматика читает явные target-dispersion/ordered component-pair declarations,
  затем максимум три последовательных explicit-reference hops. Каждый переход
  требует собственного raw anchor: this/these/the same mixture/dispersion/solvent
  system, конечного particle-containing bridge или связанного property endpoint.
  Unrelated sentences не пропускаются; новая declaration сбрасывает наследование.
  Нет дальней идентификации эксперимента по повторённому названию компонента.
- RU/EN direction/status/target/form/object checks, multiple pairs/references,
  unparsed particle owners/tails, numeric/dimension pairs, paragraph/semicolon/
  contrast/source boundaries остаются blocking diagnostics. `appeared with`
  имеет отдельный тип `context_association`, не `directed_dependency`.
  Missing particles/solvent/direction не заполняются из соседства.
- Каждая declaration, component, reference, predicate, attachment и rejected
  attempt имеет exact raw span. Все chemical identity/performed/material-owner/
  quantitative-owner/scientific-admission flags остаются false. Числа и условия
  не переносятся; constrained/unsupported queries не получают chain completeness.
- После измерения v0.5 отдельный adverse probe выявил ложную chain completeness
  через заголовок при явно названном `Nafion particle morphology`. Исходный
  possessive-heading control этот случай не покрывал. Фактический false result
  сохранён в `output/source_reference_chain_20261103/heading_adverse_probe_v01.json`;
  v0.5 код/report/manifest не переписывались.
- До реализации следующего исправления записан отдельный
  [протокол v0.6](records/source_reference_chain_protocol_v0.6.md). Новый wrapper
  `source_reference_chains_v06.py` отклоняет paths через isolated uppercase либо
  finite conventional RU/EN heading lines, сохраняя rejected proposal/heading
  anchors. Groups/references/completeness пересчитываются по retained paths.
  Шесть дополнительных negative variants зафиксированы до v0.6 corpus run.
  Измеренный v0.6 после исходов не менялся; его границы не являются общим
  распознавателем структуры произвольного документа.

Фактическое сравнение:

Каждая завершённая версия v0.5 и v0.6 использовала те же328 inputs:304 historical
retrieval-arm traces +24 window-candidate traces. В каждом прогоне реально
исполнены328 production-service full trace/status replays и1968 top-level
diagnostic executions: три arms, каждый дважды. Final arms — v0.2/v0.4/v0.6.
Вложенные readers и старые preflights не добавляются как независимые измерения.
Fresh v0.4 точно совпал со всеми328 saved outputs,292 outside-scope baseline
сохранены. Исторический v0.5 manifest/349 bindings отдельно проверен.

| Diagnostic | Прежние partial sets | Новые chain binding sets | Полные chain requirements |
| --- | ---: | ---: | ---: |
| v0.2 | 20/36 | Не реализовано | Не реализовано |
| v0.4 | 20/36 | Не реализовано | Не реализовано |
| v0.5 | 20/36 | 16/36 | 0 |
| v0.6 | 20/36 | 16/36 | 0 |

Старые base textual requirements остаются0 во всех arms. Новые27 paths относятся
к **одной unique exact raw chain**, не27 независимым научным подтверждениям.
Это другая source statement, чем прежняя named-ratio dependency с39 observations;
их повторы нельзя складывать в число независимых исследований.

Фактически извлечённая связка находится в Welch PDF с.2: предложение о Nafion
dispersions in water/2-propanol mixtures и следующее с `this mixed solvent system`
и `appeared with`. Particle antecedent отсутствует; diagnostics сохраняют
`particle_property_attachment_unresolved` и `context_association_is_not_dependency`.
Эти слова не превращаются в достаточную направленную зависимость или выполнение
эксперимента. Никакого нового model answer/ranking/evidence selection не было.

Real diagnostics показываются раздельно: шесть старых коротких окон, два новых
контекстных окна и шесть full-parent records =14 records на трёх уникальных raw
parents. Старые окна не получают выдуманного context. Positive context window
даёт1 partial association/0 full; possible-model window0. Три повторных parent
records содержат ту же positive chain и не являются тремя новыми positives.

Provenance amendment:

- 150 inherited addresses первоначально относятся к старым near-span observations.
  Отдельный [address audit](../output/source_reference_chain_20261103/address_audit_v01.json)
  проверяет их по фактическому frozen evidence:138 полных parent texts совпали,
  12 отличаются. Различие не скрывается и не исправляется нормализацией.
- Все141 применимое новое context-window/address containment сопоставление
  точны, missing0. Это frozen evidence containment, не141 fresh PDF extractions,
  не141 независимое научное подтверждение и не заявление об идентичности всех
  полных parent texts. Actual source hashes/provenance/raw offsets сохранены.

Tests run:

- **355 affected tests passed**,72 новых в трёх test modules. Проверены16 modules;
  финальный JUnit `output/source_reference_chain_20261103/tests_v06.xml`.
  Предыдущие347/64/61/57 и preflights — пересекающиеся прогоны, не добавление к355.
- Ruff всех11 новых Python files passed. Mypy не запускался.
- 54 final chain controls (48 v0.5 +6 heading variants),139 старых constructed
  control replays с exact v0.4 base preservation. Положительные full chains в
  constructed controls не считаются реальными scientific successes.
- 328 actual full-service trace/status replays,1968 repeated arm diagnostics,
  corrupted raw retrieval source и baseline metadata отклонены. Meaningful guards
  проверяют corrupt hop/heading spans, invented owner, partial association→full
  promotion, сохранение исходного v0.5 failure и запрет переноса условий.
- 360 current bindings,33 original PDF hashes, восемь fresh reference anchors,
  шесть old real windows и два new context windows проверены exact fresh PDF
  containment без нормализации ради match. Полная идентичная fresh extraction
  всех parent texts не заявляется.
- Static HTML/source/graph QA passed:33 TAC rows/eight columns/41 existing PDF
  links/search,1806 base graph raw spans и1745 chain raw spans с controls/real
  records. Exact chain/base replay passed. QA:
  `output/source_reference_chain_20261103/qa_v06.json`.
- Попытки и ошибки сохранены в
  [execution notes](records/source_reference_execution_notes_v0.5.md): первая
  packet-preparation inventory failure до analyzer, два E501 до freezing, один
  ошибочный preflight assertion для уже заблокированного numbered heading,
  а также исходный post-measurement v0.5 false admission. Исторические outputs и
  guards не переписаны; финальная v0.6 серия завершена отдельно.

Limitations:

- Полная components→dispersion→particles→directed morphology chain на реальном
  корпусе не восстановлена. Восстановлена конечная context association; scientific
  adequacy, причинность, performed/condition owners и completeness не установлены.
- Конечные RU/EN templates, три consecutive reference hops и heading rules не
  являются общей co-reference/document understanding системой. Unparsed tails,
  implicit subjects и другие языковые/структурные варианты остаются unresolved.
- Только exposed development sources/assistant controls; independent accuracy
  null.27 observations относятся к одной уникальной цепочке. Tests и structural
  QA не заменяют независимую научную оценку.
- Browser execution, новая PDF visual QA, full suite, mypy и concurrency не
  проверялись. Наследуемый segmentation adapter serial/offline; production
  integration не выполнялась. Исходный v0.5 failure сохранён, corrected v0.6 не
  объявляется научно безопасным на основании шести heading negatives.
- App/runtime/gate/index/PDF/prompt/public schema/scientific thresholds unchanged.
  Новых DB/search/embedding/model/OAuth/native requests/downloads/slots0;
  все live budgets закрыты. Существовавшие изменения worktree сохранены.
  Independent evaluation, cache/ORM defect и query rewriting остаются открытыми/
  отложенными согласно прежним решениям.

Verdict:

**Offline-итерация выполнена: явная source context association извлечена с raw
основаниями, граница раздела защищена, старые результаты сохранены. Полных
реальных chain requirements0; подключение к рабочему gate не обосновано.**

Итоговый [HTML review_v06](../output/source_reference_chain_20261103/review_v06/review.html).
Исторический [v0.5 review_v01](../output/source_reference_chain_20261103/review_v01/review.html)
сохранён отдельно. Следующая отдельно объявленная работа должна проверить
явное source particle attachment и направление зависимости на дополнительных
реальных примерах с negatives, без автоматического переноса условий или допуска.
Независимая оценка ждёт новых внешних вопросов/эталонов, frozen до outputs.

**План качества ответов75% работ**, scientific accuracy/acceptance не установлены.
