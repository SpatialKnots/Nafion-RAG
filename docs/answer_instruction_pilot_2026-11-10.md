# Испытание общей инструкции: пять вопросов

10 ноября 2026. User: «давай проведём испытание». Новый отдельный лимит:
максимум пять model POST + пять OAuth, по одной попытке. Все пять выполнены,
повторов/продолжений нет, оставшийся лимит 0. Production default не включён.

Changed:

- App и инструкция не менялись. Добавлены отдельные runner, controls и review
  scripts. Испытан существующий explicit ExperimentalScientificAnswerProvider
  на замороженных источниках, без повторного поиска, перевода, DB или /answer API.
- До вызовов зафиксированы пять случаев и цели. Четыре baseline из rewrite v0.2;
  Fan10 из v0.1, поскольку v0.2 Fan10 был ошибкой provider, а не ответом.
  Исторические вопросы/источники/порядок/system/schema/model/max_tokens одинаковы
  внутри каждой пары, отличается только фиксированная инструкция.
- Native requests/responses и parsed provider results сохранены без ремонта.
  Finite audit записан отдельно; он не меняет ответ и не запускает retry.
  Baseline — прежние реальные ответы, не новые параллельные вызовы модели.

Результаты сверки целевых дефектов:

|Вопрос|Наблюдение в этом прогоне|
|---|---|
|Satoh07|Исправлено: «не идентифицированы», возможные алкоксиды отделены как предположение авторов.|
|Satoh06|Исправлено: около 60% на 30-м цикле явно относятся к EC–TFEME/EC–TFEMEE.|
|Fan05|Прежние CFx/POxFy и 5–10 нм для SEI исчезли, но ответ стал общим. LiF не назван; причинная цепочка high-F SEI → плотный Li не обоснована выбранным предложением. Явный XPS/high-F текст и dense layer относятся к CEI, при этом рисунок содержит отдельный LiF-rich SEI. Полного исправления не установлено.|
|Fan10|Снова нет total cathode/anode masses для >680 Вт·ч/кг. Значение и ограничение после 125 циклов сохранены; пропуск основы нормировки остаётся.|
|Satoh03|Снова нет численного TFEME 1.1508×10³ кг/м³ при 25°C, хотя оно есть в E3; приведён только EME 0.8472×10³ кг/м³. Дополнительно trifluorination передано как «трифторметилирование»: термин изменён.|

**Два целевых дефекта исправлены в этом прогоне; три вопроса полностью не закрыты.**
Это описательные результаты пяти выбранных известных проблем, не scientific
accuracy/generalization score. Остальные утверждения не получают автоматического
подтверждения. Fan05 и Satoh03 остались без veto конечного checker; Fan10 снова
получил missing_energy_mass_basis. Отсутствие veto не является проверкой полноты.

Tests run:

- 37 passed: семь новых pilot budget/transport/closure controls + прежние 30
  instruction/reader controls. Ruff трёх новых Python файлов прошёл. App не
  менялся; прежние 403 tests/mypy205 здесь не выдаются за повторно выполненные.
- До OAuth выполнена byte-exact регенерация каждого candidate; фактически
  отправленные пять requests равны frozen bytes. Parsed answers совпали с
  исходным message.content, все пять finish_reason=stop. Returned model во всех:
  `GigaChat-2-Max:2.0.30.01`; max_tokens1200/timeout120s.
- Пять новых exclusive attempt slots и receipts проверены, все закрыты. Все
  старые source/native/PDF bindings сохранены. External-network denials0,
  DB/retrieval calls0. Реальные model POST5/OAuth5. Scope closure immutable.
- Шесть exact raw→actual-native source observations, пять source addresses;
  не шесть независимых научных подтверждений. Отдельная автоматическая сверка:
  пять native requests, manifests/bindings/closures/JUnit, HTML5 sections/6rows/
  25 native links. Browser layout и свежие PDF/visual checks не выполнялись.
- Usage из actual native: prompt54523 + completion836 = **55359 tokens**;
  precached_prompt_tokens1169 отдельно, стоимость не установлена.

Limitations:

- Это direct provider pilot на уже допущенном замороженном контексте, не новый
  end-to-end API/retrieval результат. Все пять provider_answered, что не означает
  пять правильных ответов. Новых отказов/технических output errors не было.
- Вопросы выбраны по известным ошибкам, открыты разработчику; сравнение post-hoc
  implementation assistant, не независимая экспертная оценка. Один historical
  baseline и один новый sample, влияние времени/случайности не контролируется.
  Нельзя приписывать общепроектное или статистически доказанное улучшение.
- Часть доказательств содержит mixed caption/prose/table layers и PDF ranges.
  Они не переклассифицировались; точная страница внутри диапазона не придумана.
  Supplementary не получены и не проверялись. Полная scientific validity открыта.

Verdict:

Общие инструкции помогли в двух целевых случаях, но не обеспечили роль/полноту
в остальных. Одной инструкции недостаточно. Следующий отдельный шаг — явные
source-bound обязательные поля ответа и проверка принадлежности каждого
утверждения; не новая серия вызовов и не default rollout. Общий план75% и
независимая оценка остаются без изменения.

- [Сравнительная таблица: старые и новые ответы, цитаты](../output/answer_instruction_pilot_20261110/review_v01/review.html)
- [Машинный отчёт](../output/answer_instruction_pilot_20261110/review_v01/report.json)
- [Автоматическая сверка](../output/answer_instruction_pilot_20261110/verification_v01/result.json)
- [Закрытый лимит](../output/answer_instruction_pilot_20261110/closed_v01.json)
- [Протокол до вызовов](records/answer_instruction_pilot_2026-11-10_v0.1.md)
