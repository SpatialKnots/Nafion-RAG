# ARIADNE: проверки статуса, роли и ограниченной полноты ответа

10 ноября2026, Asia/Yekaterinburg. User: «Выполняй» после предложения проверить
научный статус/роль/полноту. Выполнен offline этап, без нового live scope.

Changed:

- Добавлен `app/generation/answer_support.py`, текущая версия
  `finite_answer_support_v0.2`. Существующие service/provider/prompts/routes/
  thresholds/retrieval/DB/PDF/index не изменялись. Default routing/config не
  импортирует/не включает новую обёртку; подключение только явное opt-in.
- Отдельный аудит свободных GeneratedClaim; прежний `claim_checks.py` по-прежнему
  проверяет явные tuples/quotations и не выдаётся за автоматический prose checker.
- Четыре конечных contracts, только по действительно процитированному raw text:
  literal identified/идентифицирован versus not identified для связанного
  chemical/product subject; SEI/CEI ownership для одного composition fingerprint;
  total cathode/anode mass basis для source-bound Wh/kg; EC qualifier для
  source-bound EC–COMPONENT cycling-efficiency data. Values/labels извлекаются
  из источника, не из QA-эталона, авторов, годов, article IDs или PDF pages.
- Role binding — явная composition clause либо соседние XPS-role/these-species
  clauses, минимум2 совпавших chemical tokens; простое наличие SEI/CEI в mixed
  chunk недостаточно. Multiple roles/source states/cross-work binding/derived
  source/unrecognized grammar остаются unresolved/not_evaluated.
- Каждый finding содержит raw SHA/offset/text/citation/article/chunk/source type/
  page range. Не выполняются scientific prose repair, unit conversion, retries,
  частичная выдача, retrieval expansion или перенос значений между источниками.
- `AuditedAnswerProvider` — explicit wrapper над одним исходным provider result.
  На conflict/gap возвращает whole-answer abstention; separate callback фиксирует
  native_answerable versus guarded_answerable и deterministic origin. Нативный
  result/claims не меняются, второго provider call нет. Нераспознанное остаётся
  `not_blocked_by_finite_checks`, что НЕ означает scientifically verified.

Versioned diagnostics:

- Initial core controls:2failed/52passed — mixed-subject segmentation и negated
  mass basis. Исправлены до первого frozen measurement; JUnit сохранён.
- Actual service/ASGI regression:1failed/237passed — source `about73%` spacing
  не связывал EC qualifier. Поддержка approximation/numeric spacing+regression
  добавлена; final v0.1 suite242passed. Ruff5/full mypy app204 passed.
- Затем заморожены v0.1 code/test/protocol и60 prior records, выполнен replay.
  Дополнительные scientific-boundary probes дали7failed/1passed: characterization/
  establishment смешивались с identification, произвольные sample prefixes с
  co-solvent semantics, error-reporting с endorsement. Это реальные обнаруженные
  недостатки v0.1, не удалённые и не заявленные успешными.
- Отдельный v0.2 amendment сузил статус до identification, EC qualifier до EC,
  explicit error reporting оставил вне утверждения. Generic `установили` из одного
  constructed affirmative control заменён на точное `идентифицировали`; original
  source/test snapshot сохранён. Added conductivity-vs-identity adverse control.
- Старый v0.1 core/test hash теперь отличается от current: ДВА точных mapping
  на `output/answer_support_20261110/freeze_v01/source_snapshot/...` записаны в
  final verification. Все остальные historical bindings unchanged. Frozen v0.1
  модуль независимо загружен с bytecode disabled и воспроизвёл все30 audits exact.
  Оба original v0.1 manifests не менялись; current v0.2 имеет отдельный freeze/run.

Tests run:

- Final251 passed:74 новых controls/integration и177 existing generation/GigaChat/
  fidelity regressions. Пять constructed scenarios прошли direct service и actual
  ASGI /answer (10 executions): status/role/energy/mixture withheld, positive retained.
  HTTP200 answered/insufficient bodies exact direct versus ASGI. Это synthetic
  transports, не real model/provider responses и не real DB.
- External-network audit guard denials0. Real model/OAuth/DB/retrieval calls0,
  slots0; все прежние budgets закрыты. Starlette/httpx deprecation warning сохранён.
- Ruff6 final files/full mypy204 app source files passed. New module is one app
  addition; old app source hashes unchanged. Full repository suite не запускался.
- Для финального replay заморожены все60 original/v0.1/v0.2 observations — все20
  cases каждого набора. Whitelist projection содержит исходные вопросы/actual
  claims/raw evidence/native provenance, без reference answers/заданных оценок.
  Projected original service/API bodies canonical hashes сохранены. Первоначальные
  gate-rejected bodies были результатами production service preparation, не
  новыми/придуманными HTTP executions.
- Проверены30 actual answered records/27 distinct native request identities;
  reused samples считаются отдельно, не independent/new answers. Прочие30
  refusals/errors/rewrite rejects сохранены без новых выводов об их правильности.
-32 raw→actual-prompt anchor observations/9 distinct raw addresses verified,
  только existing whitespace collapse; не32 scientific confirmations. Parent
  model/API/native/PDF files/bindings unchanged.60 HTML sections/291 links checked.
-7 exposed positive development records(Fan09 original; Satoh05/08/Fan04 v0.1/
  v0.2) retained unchanged. Это retention checks, не independent positive gold.

Measured replay:

|Набор|Исходных answered|Удержать conflict|Удержать incomplete|Без veto, не verified|
|---|---:|---:|---:|---:|
|Original|4|0|0|4|
|Rewriting v0.1|11|0|2|9|
|Rewriting v0.2|15|2|1|12|

- Satoh07 v0.2: positive identification versus actual cited `not been identified`
  and possible compounds → identification_status_conflict.
- Fan05 v0.2: composition CFx/POxFy присвоена SEI, actual cited XPS witness связан
  с CEI on LCP → interphase_role_conflict.
- Satoh06 v0.1/v0.2: повторение cycling percentage для ether без EC qualifier
  source sample → missing_mixture_qualifier.
- Fan10 v0.1: source-bound Wh/kg без total cathode/anode mass denominator →
  missing_energy_mass_basis. V0.2 Fan10 остался исходной API error, не проверялся
  как новый ответ.

Все60 decisions между frozen v0.1 и corrected v0.2 на этих реальных records
совпали; исправления изменили adverse controls, не переписали observed results.
Projection — offline counterfactual opt-in decision, не новый API/model outcome.

Limitations:

- Finite English-source/Russian-or-English-claim grammar, не general semantic
  entailment/ownership/completeness. Characterization/establishment/generic
  scientific findings, произвольные mixture prefixes, complicated multi-predicate
  syntax, unsupported quotations и unrecognized properties не подтверждены.
- Не проверены все names/quantities/units/conditions. Например, Satoh01 corrupted
  chemical names, Satoh03 missing transformed density, Satoh04 prior wrong cause,
  Fan01 partial component functions не получают scientific acceptance лишь потому,
  что этих veto нет. Retained12 не означает12 correct.
- Exposed datasets/agent post-hoc diagnostics. Independent scientific accuracy,
  authenticity/generalization/new-literature transfer и overall score не измерены.
- No fresh PDF extraction/visual inspection/browser layout, UI integration,
  production DB/live generation/deployment. Original supplements/Fan07 caveats
  сохранены. Existing claim-review UI автоматически не переподключалась.

Verdict:

Конкретные status/role ошибки и два вида пропусков теперь обнаруживаются и могут
удерживаться explicit wrapper без ремонта и нового model call. Offline stage
завершён; production default не включён. Полная научная проверка/источник каждого
утверждения и broader completeness остаются открытыми; общий план75%.

- [Финальная таблица60 cases](../output/answer_support_v02_20261110/review_v01/review.html)
- [Exact report/source witnesses](../output/answer_support_v02_20261110/review_v01/report.json)
- [Независимая integrity/replay verification](../output/answer_support_v02_20261110/verification_v01/result.json)
- [Первый v0.1 результат сохранён](../output/answer_support_20261110/review_v01/review.html)
- [v0.2 amendment](records/answer_support_audit_2026-11-10_v0.2.md)

Использование явно, без изменения default factory:

```python
from app.generation.answer_support import AuditedAnswerProvider

guarded = AuditedAnswerProvider(existing_provider, on_report=save_separate_audit)
```

`save_separate_audit` здесь — callback приложения пользователя, не объявление
существующей production функции. Аудит не добавляет собственный внешний вызов.
