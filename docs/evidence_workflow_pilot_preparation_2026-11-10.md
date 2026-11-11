# ARIADNE: подготовлен протокол пилота evidence workflow

10 ноября 2026, Asia/Yekaterinburg.

Changed:

- Подготовлен [протокол v0.1](evidence_workflow_pilot_protocol_2026-11-10.md).
  Проектный объём24 естественные задачи /8 новых групп работ: development6/2
  и hidden evaluation18/6. Квоты answerable/partial/ambiguous/unsupported заданы
  до outputs; пригодность не зависит от успеха текущей grammar. Это design target,
  а не готовая выборка, независимые статьи или статистическая мощность.
- Разделены baseline answer quality, coverage finite diagnostics и human A/B.
  В A/B один и тот же immutable output/source inventory показывается через
  исходные средства проверки и через новый viewer; новые model answers/context
  actions/Reviewer LLM в это сравнение не добавляются. Уменьшение ошибок модели
  от изменения UI не предполагается. Final human artifact и время оцениваются
  отдельно, только при явно сопоставимом конечном качестве.
- Заданы source/claim/role denominators, unknown/unresolved/unavailable outcomes,
  ошибки sample/conditions/units/status, false refusals/unsupported answers,
  projection errors и coverage текущего checker. HTTP200, literal equality и
  finite tuple equality не заменяют смысловую или научную оценку.
- Подготовлены [руководство куратора и шаблоны](records/evidence_workflow_pilot_v0.1/README.md):
  question manifest, private reference, run registration, assessment. Указаны
  обязательные поля/spans/relations/provenance, Unicode code-point offsets,
  PDF/layer hashes, source-bound caveats и независимое создание references до outputs.
  Шаблоны пустые, не содержат выдуманных задач или annotations. Заполненный gold
  должен находиться вне shared development/inference workspace с реальным
  ограничением доступа; один JSON-флаг такого ограничения не создаёт.
- Human подпилот спланирован для двух научных пользователей и куратора, с
  counterbalanced assignment по целым группам и20-minute task cap. Ни одного
  участника или timing observation эта работа не регистрирует. При отсутствии
  участников time/savings остаются null, human часть — not_run.
- Сохранён локальный [planning snapshot](../output/evidence_workflow_pilot_protocol_20261110/registration_v01/planning_snapshot.json)
  текущего dirty tree:212 app source/assets, из них203 Python files, pyproject,
  protocol/templates, selected nonsecret effective settings и installed package
  versions. Snapshot ID:
  `24171f69660838cc6a13a257dbbc810dca77af5789fed65bc3ac8cd0b1429f50`.
  Provider config сейчас GigaChat-2-Max/1200/120s; Methods policy disabled.
  Resolved provider model version не определялась: новых provider calls нет.
  Это planning baseline, а не final post-development execution freeze.
- [Реестр known exposure](../output/evidence_workflow_pilot_protocol_20261110/registration_v01/known_exposure.json)
  сохраняет33 прежних article records и проверенные original PDF hashes.
  DOI отсутствует в этом metadata snapshot и не придумывается; scientific groups
  не установлены. Это нижняя граница известной экспозиции, не33 независимые работы
  и не полный census. Пять текущих/76 старых cases и Kim остаются раскрытой регрессией.
- App/runtime/DB/PDF/index/старые outputs и manifests не менялись; секреты/.env
  содержимое не копировались. Все прежние live scopes закрыты, template budget0.

Tests run:

- Все **4 JSON templates** успешно прочитаны; проверены design arithmetic,
  отсутствие registered case IDs и false/0 execution authorization/budgets.
- Manifest/source hashes snapshot проверены; текущие app/test/review bindings
  совпали с последним claim-review UI stage. **33 original PDF hashes** совпали.
  Новая PDF extraction, визуальная проверка и DB census не проводились.
- Проверки локальных Markdown links, current app inventory и итоговый
  `git diff --check` сохраняются отдельно в verification_v01.
- External-network audit guard denials0. Runtime tests/Ruff/mypy не перезапускались:
  изменены planning documents/templates, runtime-код не менялся. Прежний1306-test
  результат не выдаётся за новый прогон этого этапа.

Limitations:

Новых questions/references/outputs/time observations в этом scope — **0**.
Наличие независимого куратора, новых источников и участников не установлено.
Private store, фактическая eligibility/grouping/split/seed, final execution scope
и projection/scoring implementation не готовы. Полный scorer/JSON Schema для
annotations этой работой не реализован; syntax validation не проверяет научный gold.

Отдельный integration gap: текущий `/packet/checks` повторно готовит fresh packet
и не принимает сохранённый model answer как доверенный artifact. Одного повторения
question недостаточно для одинакового исторического контекста A/B. До запуска
нужен отдельно проверенный replay/binding adapter или зафиксированный ручной
процесс, проверяющий exact question/options/source IDs/order/raw/layer hashes и
связь assertion с исходным answer span. Missing fields нельзя заполнить из gold.
Этот gap включён в требование frozen projection/scoring contract и не объявлен
существующей возможностью viewer.

В дизайне24 задачи, из них18/6 групп в evaluation; не заявляется общая scientific accuracy,
статистическая мощность или причинная экономия времени. Source-support judgment
отдельный от истинности научного эксперимента; scientific validity остаётся
not_evaluated, пока нет отдельно обоснованного экспертного judgment.
Новые model/OAuth/slots/DB/ingestion/deployment — **0**.

Verdict:

Протокол и требования к эталонам подготовлены. Пилот **не зарегистрирован и не
запущен**. Следующий шаг — внешние source/question/reference inputs и проверка
пригодности/доступа; затем development-only подготовка недостающих адаптеров и
новая финальная заморозка перед evaluation. Автоматического перехода к calls нет.
Независимая научная оценка остаётся открытой; общий план качества — **75%**.

- [Протокол](evidence_workflow_pilot_protocol_2026-11-10.md)
- [Шаблоны и руководство](records/evidence_workflow_pilot_v0.1/README.md)
- [Проверка planning snapshot](../output/evidence_workflow_pilot_protocol_20261110/registration_v01/validation.json)
