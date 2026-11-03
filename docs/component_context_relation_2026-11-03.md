# ARIADNE: component context и observed nominal null, v0.3 → v0.4

3 ноября 2026 года, Asia/Yekaterinburg. Offline-продолжение
[typed partial v0.2](typed_partial_relation_2026-11-02.md).

**Регрессия observed-null исправлена; корпусного выигрыша нет.** Новая конечная
грамматика связывает явные component declarations на controls, но не на реальном
Welch-контексте при объявленных границах. Это результат проверки кандидата,
а не отсутствие научной связи в источниках. В рабочий gate ничего не внедрено.

Changed:

- До реализации/измерения записан [протокол v0.3](records/component_context_relation_protocol_v0.3.md).
  Новые модули и outputs отделены от неизменных v0.1/v0.2. Кандидат повторно
  использует их mapped source view/segmentation, variable/target/property readers.
- Named-component ratio получает source-context binding только от точного
  повторения упорядоченной пары: в том же либо непосредственно предыдущем
  предложении одного абзаца/source. Предыдущее предложение требует явной
  синтаксической привязки declaration к Nafion dispersion; совпадения title,
  другого источника, отдалённой фразы или другой формы не наследуются.
- Explicit solvent components и explicit dispersion components различаются.
  Dispersion context сам по себе не заполняет solvent scope. Dimension/numeric
  ratios не становятся растворителями. Компоненты читаются синтаксически,
  без каталога химических названий; chemical identity остаётся unverified.
  Accepted/rejected declarations имеют точные pair/sentence/target raw anchors
  и diagnostics. Конечные status/object/material cues блокируют наследование;
  общей семантической идентификации произвольных материалов нет.
- Восстановлен `observed_nominal_null` и добавлены конечные EN/RU nominal-effect
  templates. Наблюдаемое отсутствие эффекта сохраняется как отдельный status;
  bare negation, unperformed/future/uncertain/absent evidence не становятся
  подтверждением. Все performed/material/value-owner/scientific-admission
  flags остаются false. Числа/температуры/концентрации не переносятся из context,
  constrained queries по-прежнему не получают textual completeness.
- На v0.3 после измерения обнаружены **два ложных текстовых допуска**:
  `alphaandbeta` распознавалось как пара и `absence of evidence for the effect`
  как наблюдаемый эффект. Их фактические outputs сохранены в
  `output/component_context_relation_20261103/posthoc_adverse_probes_v01.json`.
  Исторические v0.3 код/controls/report/manifest не исправлялись задним числом.
- До следующего измерения записан отдельный [протокол v0.4](records/component_context_relation_protocol_v0.4.md).
  Отдельный `component_context_relations_v04.py` требует самостоятельных слов
  `and`/`и` либо slash и блокирует явные RU/EN absence/lack-of-evidence/data cues.
  Все53 controls v0.3 сохранены; восемь exposed/constructed отрицательных
  вариантов добавлены до v0.4 corpus run. Это development negatives, не
  независимая оценка. Измеренный v0.4 после корпусного результата не менялся.
- Итоговый HTML:
  [review_v04](../output/component_context_relation_20261103/review_v04/review.html).
  Все33 TAC работы/eight columns, expandable metadata/source/graph diagnostics,
  поиск и41 original PDF/page link сохранены. Отдельный измеренный v0.3:
  [review_v02](../output/component_context_relation_20261103/review_v02/review.html).

Фактическое сравнение:

Для каждой завершённой версии v0.3 и v0.4 использованы одни и те же328 frozen
inputs:304 historical retrieval-arm sets и24 window-candidate sets. В каждом
прогоне реально исполнены328 production-service full trace/status replays и
1968 top-level arm executions: три diagnostics, каждый дважды. Вложенные readers
не являются дополнительными независимыми измерениями. V0.4 сравнивает v0.1,
v0.2 и v0.4; fresh v0.2 во всех328 случаях точно совпал с прежним saved output.
Исторический v0.3 manifest и329 bindings отдельно проверены. Все292 out-of-scope
baseline сохранены; нового retrieval/ranking или model answer нет.

| Diagnostic | Partial sets | Full textual requirements | Новые context-bound edges |
| --- | ---: | ---: | ---: |
| v0.1 | Не реализовано | 0 | Не реализовано |
| Typed v0.2 | 20/36 | 0 | Не реализовано |
| Context v0.3 | 20/36 | 0 | 0 |
| Corrected context v0.4 | 20/36 | 0 | 0 |

39 partial edge observations по-прежнему соответствуют **одной уникальной
exposed raw Welch relation**, а не39 независимым подтверждениям. Изменённых
scoped edge records относительно v0.2 нет. Отсутствие допустимого same/previous
sentence context binding оставлено unresolved; окно не расширялось ради gain.

Все шесть прежних real windows и шесть full-parent diagnostics сохранены
отдельно. У real windows прежняя1/6 partial dependency; parent diagnostics
также не дают новых context bindings или complete requirements. Повторы одной
relation в parent records не объявляются новыми независимыми positives.

Final controls:48 v0.1 +30 v0.2 +53 v0.3 +8 v0.4 =139 constructed controls,
отдельно шесть exposed real windows и шесть parent diagnostics. Все объявленные
ожидания новых/сохранённых controls воспроизведены; старые полные controls у
v0.4 не потеряны. У исходного v0.2 потеря `observed_nominal_null` остаётся в
сравнении видимой. Control agreements не являются scientific precision/recall.

Tests run:

- **283 affected tests passed**, включая105 новых тестов трёх новых test modules;
  `output/component_context_relation_20261103/tests_v04.xml`. Проверены13 test
  modules: новые candidates/guards и прежние typed/relation/window/ablation/Kim
  diagnostics. Более ранние повторные прогоны не прибавляются к283.
- Ruff всех девяти новых Python files passed. Mypy не запускался.
- Final v0.4:328 exact full-service replays,1968 repeated diagnostics;
  corrupted retrieval source и baseline metadata отклонены. Raw-component/
  context-pair corruption, invented owner/kind и ложное promotion constrained
  query проверены meaningful negative tests и exact graph replay.
- Проверены338 current bindings,33 original PDF hashes, восемь fresh reference
  windows и шесть fresh real development windows без нормализации ради match.
  1806 corpus graph raw spans; с controls/parents —2842 graph spans и92
  context/rejection spans. Полные parent texts дополнительно не объявляются
  заново извлечёнными из PDF: fresh containment относится к шести real windows.
- Static HTML QA:33 TAC rows/eight columns/41 existing PDF links/search и
  exact graph replay passed. QA:
  `output/component_context_relation_20261103/qa_v04.json`.
- Ошибки и промежуточные проверки сохранены в
  [execution notes](records/component_context_execution_notes_v0.3.md).
  В частности, первоначальный preflight1 failed/87 passed и pytest-cache
  warnings, ранние Ruff diagnostics, а также незавершённый review_v01 с328
  records и hash-guard failure из-за добавленного lint-комментария verifier.
  Его guards/snapshot не переписаны; новый v0.3 review_v02 завершён отдельно.
  Ещё два v0.3 ложных допуска сохранены как post-measurement negatives.

Limitations:

- Корпусного improvement нет: context bindings0, full textual requirements0.
  Это не подтверждение отсутствия ответа в литературе. Явные ссылки и контекст
  за пределами same/previous sentence не интерпретируются; порядок компонентов,
  формы материала и raw source boundaries не приравниваются автоматически.
- Статусы и attachment — finite textual grammar, не general semantic validation,
  causal inference, scientific adequacy, полнота каталога или подтверждение
  выполнения опыта. V0.3 adverse failures показывают пределы unit/control
  coverage; v0.4 не получает статуса общей надёжности от восьми исправленных
  отрицательных примеров. Источники и development cases ранее были раскрыты.
- Browser execution, новая visual PDF QA, full suite, mypy и concurrency не
  проверялись. Adapter остаётся serial/offline. Новые positive model outputs
  не получены; scientific acceptance и independent accuracy не установлены.
- App/runtime/gate/index/PDF/prompt/public schema/thresholds не менялись.
  Новых DB/search/embedding/model/OAuth/native requests/downloads/slots0;
  все live budgets закрыты. Чужие существовавшие изменения worktree сохранены.
  Independent evaluation и cache/ORM defect остаются открытыми.

Verdict:

**Выполнена отдельная offline-проверка; кандидат v0.4 сохраняет старые controls,
восстанавливает nominal observed-null и устраняет два выявленных ложных допуска.
Положительного corpus benefit нет; внедрение в рабочий gate не обосновано.**

Следующая отдельно объявленная гипотеза — источник-локальная цепочка явных
component/dispersion references с проверяемыми границами subject/status, на
точных реальных фрагментах и отрицательных controls. Нельзя просто расширить
окно, считать любую ratio растворителем или переносить соседние условия.
Query rewriting остаётся отдельным отложенным экспериментом. Независимая
оценка остаётся открытой до новых внешних эталонов.

**План качества ответов75% работ**, scientific accuracy/acceptance не установлены.
