# Требования к фактическому reference

Этот документ дополняет [протокол](../../evidence_workflow_pilot_protocol_2026-11-10.md).
Приведённые ниже имена полей — спецификация будущих annotations, не примеры
измерений и не реализованный JSON Schema/scorer. Пустые arrays в templates не
означают, что в статье ничего нет.

## Порядок работы куратора

1. До просмотра outputs объявить eligibility, полные source bounds, work group,
   question и собственную provenance. Читать релевантные original PDF/supplements,
   включая фразы, которые retrieval не выбрал.
2. Разметить обязательные роли, исходные поля, связи и caveats. Подтверждать
   источником принадлежность числа, а не только совпадение числа/единицы.
3. Указать answerability и допустимые виды полного/частичного ответа или отказа.
   Сохранить unresolved, если источник или interpretation не позволяет решения.
4. Проверить source anchors, затем зафиксировать неизменяемую reference revision
   с временем и hash во внешнем private store. До outputs зарегистрировать split.
5. После outputs выполнять judgments отдельно; reference revision не исправлять
   молча. При необходимости сохранять исходник, correction reason, новый hash,
   факт prediction exposure и влияние на независимость.

## Source span

Каждый элемент `source_spans` должен иметь:

- `span_id`, `source_id`, `work_group_id` — непустые уникальные IDs;
- `article_id` из зарегистрированного source manifest, а при отсутствии ingestion
  — отдельный source ID без выдуманного DB UUID;
- `original_pdf_sha256`, `pdf_page_number` (с1), `text_layer`, `text_layer_id`
  или явно unknown layer ID, `layer_pdf_sha256` при существовании такого PDF;
- `raw_page_text_sha256`, `start`, `end`, `quote`;
- `page_mapping_status` и основание exact/uncertain mapping;
- `registered_source_type`, `section_or_table_footnote_scope` и inspection note.

`start`/`end` — zero-based Unicode code-point offsets в неизменном raw page text,
end exclusive, как у Python strings. Это не UTF-16 offsets браузера. Должно
выполняться `raw_page_text[start:end] == quote`, SHA256 считается по UTF-8 bytes.
Если нужный текст занимает две страницы, сохранить два отдельных spans и их
явную связь, а не придумать одну страницу. OCR/source normalization или whitespace
repair не переписывают raw. Проверка на оригинальной странице фиксируется отдельно.
Несуществующие hashes/страницы/слои нельзя заменять правдоподобными строками.

## Обязательная роль и поля

Каждый элемент `required_roles` содержит `role_id`, `role_kind`, `required_by`,
`resolution_status`, `expected_fields`, `support_span_ids`, `counterevidence_span_ids`
и `rationale`. Допустимые `role_kind`: composition, capacity, coulombic, role_identity.

Каждое expected field имеет `field_name`, `status`, `raw_surface`, `interpretation`,
`support_span_ids`, `alternatives`, `note`. Статусы различают:

- `source_supported`: есть точные spans и обоснование принадлежности;
- `explicit_unknown`: источник прямо сообщает неизвестность/неопределённость;
- `not_found_in_reviewed_scope`: куратор просмотрел объявленный scope, не нашёл поле;
- `ambiguous`: несколько неразрешённых значений/единиц/владельцев;
- `not_inspected`: нужный scope не просмотрен; это не отсутствие поля.

`not_annotated` допускается только в незаполненном template. При registration
каждая обязательная роль должна иметь явный статус, включая unresolved.
Поле со статусом source_supported требует непустых support spans; названная
единица без доказанного владельца остаётся ambiguous, а не source_supported.

Минимальные expected fields:

| Роль | Поля |
| --- | --- |
| Composition | electrolyte/sample identity; salts, concentrations, solvents, ratio и basis; additive; reported total; method/условия, если обязательны вопросом |
| Capacity | cell/sample; property; raw value/representation/unit; cycles; current и basis/unit; voltage; temperature, если требуется; approximate/bound status; origin |
| Coulombic | cell/sample; efficiency/value/unit; cycles; current и basis/unit; areal capacity/deposition basis; temperature, если требуется; approximate/bound status; origin |
| Role identity | какой состав/код относится к каким measurement roles; source-supported relation, допущения и противоречия |

Сохранить исходное числовое написание, знак/оператор, scalar/range/bound,
uncertainty/approximation, единицу, origin (experimental/calculated/cited/unknown)
и источник интерпретации. Не превращать nominal concentration в измеренную,
retention в CE, соотношение в концентрацию или общий Methods в условия чужой работы.
Не добавлять в эталон универсальный scientific tolerance или конверсию единиц.

## Связи и ограничения

Элемент `role_relations` содержит `relation_id`, `from_role_ids`, `to_role_ids`,
`relation_type`, `resolution_status`, `support_span_ids`, `counterevidence_span_ids`,
`assumptions`, `rationale`. Одного article_id, соседства абзацев, совпадения1.35M
или одинакового автора недостаточно. Раскрытие alias/code, respectively/ordered
lists, материал/операция и условия должны быть обоснованы; допущение не скрывается.

`mandatory_caveats` и `explicit_unknowns` ссылаются на role/field/span IDs и
поясняют, как они ограничивают ответ. Не усиливать гипотезу до факта, future intent
до выполненного эксперимента, «около» до точного числа, same-article до same-sample.

Для conflict сохранить оба значения и области применимости. Для отрицательного
reference записать просмотренный scope и почему запрос не поддержан в нём;
это не свидетельство отсутствия научных данных вообще.

## Проверка перед регистрацией

- question/source/group IDs и hashes существуют и согласованы;
- reference не содержит silently copied system output или assistant proposals;
- все обязательные поля получили статус, а не безымянный null;
- все support refs разрешаются, точные anchors воспроизводятся;
- связи/negative scope/exposure/LLM assistance задекларированы либо unresolved;
- unresolved judgments и disagreements видимы;
- public question/source manifest не содержит gold fields;
- private storage и доступ реально настроены, а не только названы в JSON.

Эта проверка пригодности не является новой product admission policy или научной
экспертизой. Текущий агент не заполняет отсутствующие эталоны от имени куратора.
