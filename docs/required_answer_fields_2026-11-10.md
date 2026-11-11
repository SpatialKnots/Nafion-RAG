# Обязательные поля ответа: карта, проверка и повторный прогон

10 ноября 2026. User: «Да, давай» после предложения построить source-bound
требования, проверить три незакрытых случая и два контроля, затем повторить
ограниченный прогон. Работа выполнена в отдельном экспериментальном режиме.

Changed:

- Новый `app/generation/required_answer_fields.py`, версия
  `required_answer_fields_experiment_v0.1`. Прежняя карта composition/cycling
  сохранена. Явные `extend_preparation`/`extend_packet` используют её проверку,
  реконструкцию raw parents и pinned packet; оригинальные blockers/packet/legacy
  map не переписываются. Registered adapter проверен на constructed parents;
  новые production DB preparations/packets для пяти вопросов не выполнялись.
- Три конечных семейства: численное сравнение плотностей при заданной температуре;
  удельная энергия с основанием нормировки и явно запрошенным ограничением;
  состав SEI/CEI с отдельным требованием причинного механизма, если задано «почему».
- Объекты извлекаются из вопроса. Неявный второй объект плотности допускается
  только при одном буквальном source pair и явном transformation-topic для
  исходного объекта; это не доказательство химической идентичности/маршрута.
  Числа/единицы/температуры/основание нормировки берутся из точных raw spans.
  Без author/year/QA IDs/ожидаемых значений в логике. Нет пересчёта единиц.
- Для плотностей конечный grammar — source list kg m−3 с печатным множителем
  ×10³; другие представления не конвертируются. Formula-rich SEI/CEI labels —
  буквальные наблюдения, не доказательство механизма или scientific ownership.
  Поддержан один явный causal grammar, не произвольное причинное рассуждение.
- `check` различает recognized/ambiguous/unresolved source fields и наличие
  необходимых literals с собственными object/value/unit/temperature/citation
  bindings. Нет положительного scientific acceptance. Unknown grammar не
  означает отсутствия результата в статье/природе. Altered/stale maps rejected.
- Явный `RequirementGuidedAnswerProvider` передаёт внутреннюю карту перед прежним
  prompt и raw evidence. Public output schema/validators/default factory/routes/
  config/retrieval/DB/PDF/index неизменны. Карта ограничена 12000 characters,
  переполнение даёт явную ошибку, не truncation. Exact selection paths сохранены.
- Post-generation check хранится отдельно. Он **не подключён как автоматический
  veto API** и не исправляет native ответы. При unresolved fields отдельно
  показывается диагностическая проекция удержания, не реальный model/API отказ.

Tests run:

- 519 regression tests passed. После добавления pinned-packet adapter — 53
  focused tests passed; 50 пересекаются. JUnit union: **522 distinct tests**,
  из них 53 новых. Ruff пяти новых Python файлов/full mypy app206 passed.
- Wrong object/value/scale/unit/temperature/role/citation, conflicting sources,
  hedging/negation, noncurrent values, cross-work/derived scope, stale map,
  explicit causal positive, legacy parent/packet pinning, budget, inherited exact
  selection failures, unchanged positive native, new scope isolation проверены.
- Первые 44 unit tests passed, initial Ruff import-order diagnostic исправлен.
  Sandbox regression завис на local API; остановлены только PID19172/22412,
  этот прогон не считается успешным. Вне sandbox финальные519 прошли; один
  прежний Starlette/httpx warning сохранён. Network denials0 в успешных тестах.
- До модели заморожены карта/код/вопросы/источники/requests: три новых cards,
  два побайтно прежних native controls. Отдельный новый scope-local ledger
  разрешён текущим user request; старые идентичные digest slots не переоткрыты.

Реальный прогон:

|Вопрос|Результат относительно предыдущего pilot|
|---|---|
|Satoh07|Неидентифицированность продуктов и предположительность алкоксидов сохранены.|
|Satoh06|EC–TFEME/EC–TFEMEE сохранены. Ответ короче: численный пример 60%/30 циклов исчез; вопрос явно просит влияние, не конкретное число.|
|Fan10|Добавлено основание «общая масса катода и анода», ограничение125 циклов сохранено. Название Li/NMC811/однократный избыток Li в новом ответе не повторены.|
|Satoh03|Обе плотности теперь есть: EME0.8472×10³ и TFEME1.1508×10³ кг/м³ при25°C. Термин «трифторирование» восстановлен. Новая формулировка «после … образуется» не доказывает реальный синтетический маршрут; это вне проверки необходимых численных полей.|
|Fan05|Добавлен LiF. Модель проигнорировала unresolved mechanism и всё равно дала объяснение. Карта/check сохраняют этот пробел; ответ остаётся для удержания/ручной проверки, а не scientific acceptance.|

Ровно **5 actual model POST +5 OAuth**, все native stop/provider_answered,
`GigaChat-2-Max:2.0.30.01`,1200 tokens/120s. Retry/fallback/continuation0,
весь новый лимит и пять новых slots закрыты, remaining0. Native/parsed exact,
actual request=frozen bytes. Ни один native ответ не заменён отказом в отчёте.

Два целевых численных пропуска заполнены, два контроля сохраняют целевые свойства,
один вопрос не закрыт. Это **не 4/5 научно правильных ответов** и не выполненный
критерий отсутствия всех новых ошибок/потерь: детализация и новые утверждения
вне конечных полей требуют отдельной проверки.

Usage native: prompt58113 + completion714 = **58827 tokens**, cache655 отдельно,
стоимость неизвестна. Разница token fields у побайтно одинаковых controls не
трактуется как изменение evidence; cache accounting не исследован.

Отдельная сверка проверила 21 полный raw chunk occurrence в actual Evidence
section,10 requirement anchors/5 source addresses, hashes/native/old slots/
closures/JUnits и HTML5 sections/6 rows/20 links. SourceView spans проверены
обратно по raw; вторичная verification фиксирует позиции именно в raw Evidence
section, даже когда цитата повторяется внутри карточки. Это не независимые
научные подтверждения. DB/retrieval calls0/network denials0.

Limitations:

- Finite English source/Russian-or-English answer grammar. Верная альтернативная
  формулировка может остаться unrecognized. Общий semantic entailment, causal
  validity, экспериментальное ownership и полнота вне этих полей не реализованы.
- Direct provider experiment на прежних источниках, не /answer end-to-end test.
  Historical baseline/single draws/known exposed tasks, независимой оценки нет.
- Нет fresh PDF/visual/browser layout/full repository suite/deployment/default
  rollout. Исходные source_type/page ranges сохранены; supplementary не получены.

Verdict:

Карта и отдельная проверка готовы и испытаны. Модель стала заполнять два
конкретных пробела; нерешённый механизм теперь виден в структурной диагностике.
Автоматическая выдача ответа с unresolved fields остаётся отдельным решением
интеграции; новое число вызовов не открыто. Общий план75%/независимая оценка
не изменены.

- [Сравнение старых/новых ответов и карт](../output/required_answer_fields_20261110/review_v01/review.html)
- [Полный отчёт](../output/required_answer_fields_20261110/review_v01/report.json)
- [Проверка raw evidence и integrity](../output/required_answer_fields_20261110/verification_v01/result.json)
- [Закрытый лимит](../output/required_answer_fields_20261110/closed_v01.json)
- [Протокол](records/required_answer_fields_2026-11-10_v0.1.md)
