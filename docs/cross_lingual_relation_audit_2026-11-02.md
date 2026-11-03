# ARIADNE: offline RU/EN requested-relation audit

2 ноября 2026 года, Asia/Yekaterinburg. Продолжение
[window selection](retrieval_window_selection_2026-11-02.md).
Ограниченная итерация завершена; исправление рабочего gate не достигнуто.

Changed:

- До измерения зафиксированы отдельные protocol и constructed controls в
  `docs/records/cross_lingual_relation_*_v0.1.*`. Добавлены offline analyzer,
  service replay driver, static verifier и отдельная presentation completion.
  В `app/` изменений нет. Query rewriting остаётся отложенным экспериментом.
- Конечная область: исходный вопрос совместно запрашивает Nafion, dispersion,
  particles, morphology/shape и solvent. Требования извлекаются только из
  ORIGINAL question; неизвестные ограничения не отбрасываются.
- Анализатор разделяет роли material/object/medium/property/variable,
  направленную textual dependency и явную привязку свойства к Nafion particles.
  Совместное присутствие слов в chunk/title не достаточно. Допущена одна
  ограниченная adjacent antecedent конструкция Their morphology / Их морфология
  после явного предложения о частицах дисперсии Nafion. Смена формы/объекта,
  абзац, другой субъект и межфрагментное заимствование остаются unresolved.
- Статусы разделены: affirmative assertion, observed null effect с observation
  cue, bare negation unresolved, unperformed, absent evidence, future/proposal,
  uncertain/hypothesis и question. Новая формальная цель не переписывает старые
  22-control labels: измеренное отсутствие эффекта может содержать информацию,
  в отличие от отсутствия исследования. Наблюдение/владельцы не подтверждаются.
- Mapped view для ligatures и line-break word join сохраняет точные raw offsets.
  Числа/единицы/формы не преобразуются. Exact local condition surface отдельно
  от установленного owner; даже точное совпадение запрошенного условия не
  даёт `textual_requirements_met`, пока owner не установлен. Условия из другого
  предложения/другого evidence не переносятся; unknown constraints блокируют.
- Byte-exact повтор evidence диагностируется без удаления или переупорядочения
  источников; все article/chunk/page/source addresses сохранены. Ни один
  результат не устанавливает scientific admission и не меняет baseline gate.

Входы и фактический результат:

- Использованы304 прежних final evidence sets (76 cases × four retrieval arms)
  и24 actual scoped window-candidate traces; всего **328 наборов**.
  На каждом выполнен настоящий production service preparation replay с его
  frozen retrieval output. Полные trace/status совпали; фактического нового
  поиска/БД/эмбеддинга нет. 304 прежних ranking-boundary replay в этой итерации
  не выполнялись повторно и не выдаются за новую проверку ранжирования.
- Анализатор исполнен дважды на каждом наборе: **656 diagnostic executions**,
  все результаты идентичны своим реальным повторам. В область попали36 наборов;
  остальные292 явно сохранили baseline без новой relation assessment.
- **0 полных source proposals / 0 textual-requirements-met sets** на36 scoped
  входах. Это провал покрытия данного analyzer, не отсутствие scientific
  evidence в корпусе. Его нельзя применять как veto или bypass.
- У34 scoped наборов прежний baseline допускает, но sidecar оставляет relation
  unresolved; два RU combined/body набора уже отказаны старым gate. Это
  расхождение критериев, не34 независимо установленных ложных допусков и не
  фактическая новая policy. Все реальные baseline решения сохранены.
- На36 scoped наборах найдено24 byte-exact duplicate source groups; одни и те
  же наблюдения повторяются между query/arm/qualifier. Это не24 независимых
  дубля работ. Удаления источников, изменения схемы/DOI/PDF identities нет.

Разбор реальных пропусков:

В original RU / combined / body evidence Welch PDF pages3–4 есть точная
source-local фраза (mapped recognition устраняет ligatures/line joins):
Nafion particle morphology is strongly affected by changes in the
water/2-propanol ratio. Новый strict analyzer распознал явную target-property
привязку, но не literal `solvent`/`dispersion` в этом предложении и не получил
направленную полную template. Это assistant post-hoc чтение исходного текста,
не независимая разметка/эталон. Exact raw span и все причины видны в HTML.

Другая source-фраза о SANS/three types of Nafion particle morphology in dilute
liquid media разделена после `ca.`: его нет в конечном abbreviation list.
Это наблюдаемый дефект segmentation; эффект одного исправления на допуск не
измерялся и не объявляется достаточным. V0.1 после просмотра результата не
подгонялась. Final presentation содержит150 near-relation span observations
(с повторами между наборами), полный source context и missing-role diagnostics.

Constructed controls:

- 48 assistant-authored development cases. Все48 совпали с явно записанным
  ожидаемым поведением: это проверка реализации заданных правил, не scientific
  precision/recall или обобщение на реальные статьи.
- Affirmative RU/EN, observed null, material/object/property/direction boundaries,
  mapped raw spans, exact versus mismatched temperature/range/percent/form,
  no condition borrowing и duplicate preservation проверены отдельно.
- Два informative development случая намеренно остаются unresolved: implicit
  relation и unnamed solvent variable. Их наличие не скрыто общим PASS.
- 48 правильных формальных behavior checks при0 recovered corpus proposals
  показывают, что добавление ещё одного частного словаря само по себе не
  обосновывает gate rollout. Нужен отдельный дизайн типов переменных и source
  context/ownership на реальных текстах с сохранением отрицательных контролей.

Tests run:

- **229 affected tests passed**, из них58 новых analyzer tests;
  `output/cross_lingual_relation_20261102/tests_v01.xml`.
  Отдельно **3 новых replay/raw-integrity tests passed** в `tests_review_v01.xml`.
  Итого232 различных теста,61 новый. Preflight57/58 повторно не прибавляются.
- Ruff шести новых source/test/QA files passed. Corrupted full raw retrieval
  source и corrupted expected baseline metadata отклонены ожидаемыми guards.
- 328 полных production-service trace/status replays и656 actual diagnostic
  executions; DB/search/embedding/provider guards проверены. Unexpected network
  attempts0; новых native requests/slots/real model/OAuth calls0.
- Проверены33 original PDF hashes,8 reference anchors свежей PyMuPDF extraction,
  307 experiment bindings,310 current final-report bindings и4861 raw spans.
  Historical PDF/requests/responses/labels/guards не изменены; pdftoppm не запускался.
- Static HTML QA:33 TAC rows/8 исходных колонок/41 existing PDF/page link,
  полный expandable source/TAC/diagnostic context, search implementation.
  Итог: `output/cross_lingual_relation_20261102/review_v03/review.html`.
  Static QA: `qa_v03.json`.
- `review_v01` — исходный эксперимент. V02/v03 — только presentation amendment
  с exact failure windows; отчёты v02/v03 без bindings байт-семантически
  идентичны как parsed JSON. При финализации найден1 E501 в presentation helper;
  исправлен переносом string literal. Старый helper snapshot/hash и v02 guard
  сохранены, drift mapping — в `failed_attempts_v01.json`; current-source binding
  v02 теперь historical, final v03 использует исправленный hash. Исходный analyzer,
  controls и результаты не менялись. Никаких failed scientific cases не удалено.

Limitations:

- Нет нового model answer или независимой научной оценки. Реальный morphology
  case остаётся не решён;0 proposals не доказывает отсутствие подходящих связей.
- Полное semantic relation extraction, произвольная анафора, typed solvent
  variable и ownership условий не реализованы. Само наличие source-local
  грамматической template не доказывает entailment/performance/value owner.
- Scope конечный; H/Li comparisons, global optima, другие отношения и старый
  qext044 conflict этот analyzer не решает. Cache/ORM defect не исправлен.
- Browser execution, новая визуальная проверка PDF, full suite и mypy не
  выполнялись. Static HTML QA не объявляется browser verification.
- App/gate/index/PDF/prompt/public schema/thresholds и исходные результаты
  не менялись. Источники не переводились LLM и не размечались как independent
  gold. Все прежние live budgets закрыты; новых вызовов это не разрешает.

Verdict:

Ограниченная offline-итерация завершена и воспроизводима. **Кандидат не готов
к внедрению:** проверяет свои templates, но не покрывает реальную научную прозу.
Порог старого gate не снижен; новый анализатор не подключён как допуск/veto.

Следующий отдельный дизайн — source-level представление частичных связей:
material/object/property, явные типизированные переменные (в том числе ratio),
контекст и unresolved ownership. Оценивать на frozen реальных excerpts плюс
контрпримерах; отдельно учитывать partial relation и полную достаточность.
Не объявлять named ratio solvent без source binding и не добавлять aliases
ради одного известного ответа. Query rewriting остаётся отдельным экспериментом.

Независимая научная оценка открыта до новых внешних эталонов.
**План качества ответов:75% работ.** Научная приёмка/accuracy не установлены.
