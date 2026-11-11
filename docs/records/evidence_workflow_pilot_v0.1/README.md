# Пустые шаблоны evidence workflow pilot v0.1

Эти файлы описывают будущую регистрацию. Они не являются набором задач,
эталонами, действительными outputs, исполнимым API request или разрешением вызовов.
Все неизвестные значения оставлены null/пустыми списками. Не создавать24
фиктивных строки и не выдавать отсутствие labels за отрицательный reference.

Основной документ: [протокол](../../evidence_workflow_pilot_protocol_2026-11-10.md).
Состав полей, offsets и правила source attribution: [руководство куратора](annotation_guide.md).

- [question_manifest.template.json](question_manifest.template.json): только
  вопрос, source/group identity, split и inference scope; gold сюда не добавляется.
- [reference_private.template.json](reference_private.template.json): provenance,
  answerability, required roles, source spans/relations/caveats и disagreements.
  **Заполненные private references должны храниться вне shared agent workspace**
  с действительно ограниченным доступом. Этот пустой template защиты не обеспечивает.
- [run_registration.template.json](run_registration.template.json): конкретный
  набор, hashes, private/public boundary, runtime/scoring freeze и execution scope.
  Текущий budget0/authorization=false; никакой слот не создан.
- [assessment.template.json](assessment.template.json): будущие actual outputs,
  claim projections/judgments, diagnostic coverage, конечное качество и timing.
  Значения not_run/null не являются результатами эксперимента.

Для каждого фактического case создать отдельную новую версию из template, указать
ID/группу/источники и проверить hashes/offsets. Case/reference до outputs фиксирует
куратор; inference получает только разрешённые question/source inputs. Хранить
первоначальную annotation, позднюю коррекцию и причину отдельно. Unknown exposure,
LLM assistance или scientific grouping не заполнять догадкой.

Source span должен содержать проверенный PDF hash/page/layer/raw interval и точный
quote. Нельзя подставлять fabricated SHA, F-ID, выдуманную страницу или общий
article_id вместо доказательства связи. Unresolved mapping остаётся unresolved.

Проверка JSON syntax и полноты полей не доказывает научную пригодность reference.
Scorer/projection adapter и private storage в этой работе не реализуются.
