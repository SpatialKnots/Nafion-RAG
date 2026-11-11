# Общие инструкции генерации: экспериментальный режим

10 ноября 2026. Выполнен первый пункт: общие правила формирования научного
ответа в отдельном режиме. Вопросы и переводы не переписывались. Новые запросы
не отправлялись модели; улучшение качества ответов пока не измерено.

Changed:

- Новый `app/generation/answer_instruction_experiment.py`:
  `scientific_answer_instruction_experiment_v0.1`, класс
  `ExperimentalScientificAnswerProvider`. Явное создание класса добавляет один
  фиксированный префикс инструкции к обычному GigaChat user prompt.
- Общие правила: сохранять отрицание и степень уверенности источника; различать
  наблюдение, идентификацию, интерпретацию и гипотезу; связывать свойство с тем
  объектом/ролью/работой, которому оно принадлежит; сохранять существенный состав
  смеси, условия, единицы и основу нормировки; отвечать на все части исходного
  вопроса и сравнения. Не угадывать химические названия, недостающие условия или
  функции компонентов. Обязательные неподтверждённые части ведут к прежнему
  `answerable=false, claims=[]`; необязательные детали не становятся новыми
  требованиями. В эксперименте запрещены пересчёт единиц и вычисление новых
  величин; сравнение уже приведённых значений не заменяется новым измерением.
- В тексте правил нет авторов, годов, QA ID, эталонных ответов или заданных
  числовых результатов. SEI/CEI служат общим примером разных ролей, не готовым
  ответом на конкретный вопрос. Это разработка на уже открытых случаях.
- Конкретный factory по-прежнему создаёт `GigaChatAnswerProvider`. Config/API/UI
  не включают эксперимент. Exact quote/fact selection contracts получают
  побайтно прежний запрос. Разбор ответа, проверки, transport, отсутствие retry,
  system prompt, схема, модель, max_tokens и retrieval остаются у базового класса.
- Старые 204 app Python файла и один app YAML совпали с родительскими хешами;
  новый app файл один. Existing finite support audit не подключался автоматически.

Tests run:

- **403 passed**, 0 failed/errors, один прежний Starlette/httpx deprecation
  warning. Из них 30 новых: 24 provider/request/contract tests и 6 reader tests;
  373 существующих generation/GigaChat/fidelity/support/selection regressions.
- Обе формы ответа (claims/mini_review), три language modes, другой model/max_tokens,
  недоверенные тексты, empty evidence, четыре bounded selection contracts,
  native abstention/invalid JSON/inconsistent answer/filtered response/transport
  failure проверены на synthetic transport. Проверена прежняя factory. Это не
  тесты научного поведения реальной LLM.
- Ruff пяти новых Python файлов прошёл. Полный mypy app: **205 source files**.
- Из всех 60 сохранённых записей подготовлены **52 пары** baseline/candidate;
  восемь empty-evidence записей не создают запрос. В каждой паре отличается
  только фиксированная инструкция. Входы, порядок источников, system message,
  response schema, модель, language и output budget сохранены.
- **30** baseline запросов с сохранённым actual-native provenance воспроизведены
  побайтно. Это 30 записей, включая cached повторения, а не 30 независимых
  наблюдений. Для остальных baseline preparations историческая эквивалентность
  не заявляется. Проверены **171 raw-text occurrence** в prompts, не 171
  независимое научное подтверждение.
- Отдельная автоматическая сверка повторно проверила manifests/bindings, обе
  формы вопросов, пары prompts, raw sources, прежние actual native и JUnit.
  Новые model/OAuth/DB/retrieval/slots: **0**; external-network denials: **0**.

Сохранённые неуспешные этапы:

- Первый sandbox прогон показал две setup errors и завис при локальном ASGI;
  остановлены только идентифицированные PID 8040/2592. Успешным не считается.
- Второй прогон: 395 passed, две setup errors из-за отсутствующей родительской
  папки `--basetemp`; исходный `tests_v02.xml` сохранён. После создания папки
  финальный `tests_v03.xml`: 403 passed. Самостоятельные 6 reader tests также
  прошли, но не прибавляются повторно к финальным 403.
- Первая preparation остановилась: whitelisted original question не содержит
  историческую добавку «По статье …», которую сервис ранее включил в отправленный
  вопрос. v0.1 runner/freeze/incomplete preparation сохранены. Отдельный reader
  v0.2 сохраняет original/delivered question раздельно и извлекает добавку только
  из actual native. Требуется exact suffix исходного вопроса и реконструкция
  полного запроса. Ни новая добавка, ни ответ, ни gold в вопрос не подставляются.
  App instruction не менялась; SHA256
  `d1095764ae98b630b06d2c97c86258c3983accad00757bb5e58c55173b5756a3`.

Limitations:

- Подготовленные prompts не отправлены. Нет новых ответов, научных оценок,
  показателя отказов, расхода tokens/стоимости или доказательства улучшения.
- Инструкция является просьбой модели; её выполнение не гарантировано. Общие
  semantic ownership, completeness и factual correctness не становятся
  реализованными детерминированными проверками благодаря этому тексту.
- Существующие cases открыты разработчику. Обобщение на проект/новую литературу
  требует новых вопросов и независимых эталонов. Full repository suite, свежие
  PDF/visual/browser checks и deployment здесь не выполнялись.

Verdict:

Первый пункт выполнен и проверен offline. Эксперимент включается только явным
созданием нового provider; основной режим проекта не изменился. Следующее
измерение — отдельный ограниченный запуск на фиксированных источниках, затем
проверка на новых вопросах. Новая live-сессия не открыта; прежние бюджеты закрыты.

- [Инструкция и экспериментальный provider](../app/generation/answer_instruction_experiment.py)
- [Парная preparation: 60 записей](../output/answer_instruction_experiment_20261110/preparation_v02/report.json)
- [Автоматическая сверка](../output/answer_instruction_experiment_20261110/verification_v01/result.json)
- [Финальный JUnit](../output/answer_instruction_experiment_preflight_20261110/tests_v03.xml)
- [Исходный протокол](records/answer_instruction_experiment_2026-11-10_v0.1.md)
- [Исправление reader](records/answer_instruction_experiment_reader_2026-11-10_v0.2.md)
