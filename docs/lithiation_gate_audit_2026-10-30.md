# ARIADNE: отказ q3 и контрпримеры лексического исправления

Changed:

Добавлен отдельный offline-аудит `lithiation_gate_audit_v0.1`. Он воспроизводит
проверку достаточности на трёх сохранённых evidence lists и сравнивает три
локальных предложения с исходной эвристикой. Код приложения, retrieval,
словарь, пороги, схемы и provider prompts не менялись. Процессные варианты
всегда восстанавливают исходные matcher dictionaries, включая выход по ошибке.

Причина исходного отказа q3 локализована точнее:

- Distinctive terms: `существуют`, `методики`, `литирования`, `nafion`.
  Совпадает только `nafion`, coverage/top_coverage=0.25.
- Сохранённый E1, диссертация Чернюк с.49–51, содержит на с.51 точный текст
  «проводили литирование ионным обменом». Номинатив `литирование` не содержит
  подстроку `литирования`. Научное описание не исчезло из этого evidence;
  конкретная словоформа не совпала в lexical gate.
- Вопрос также содержит общую формулировку «существуют методики»; оба слова
  входят в знаменатель. Это диагностика токенов, не утверждение, что их можно
  безопасно удалить из всех вопросов.

Результаты на том же фиксированном evidence:

| Вариант | q3 lexical admission | Проблема на отдельных искусственных контролях |
| --- | --- | --- |
| Исходный | false, 0.25 | Уже допускает точное «Nafion. Литирования не проводили.» |
| Только литирования→литирование | true, 0.50 | Допускает «Литирование не проводили», заголовок, будущее действие и операцию над другим материалом |
| Только исключить существуют/методики | true, 0.50 | Хватает одного Nafion: при двух distinctive terms достаточно одного совпадения |
| Оба предложения | true | Наследует эти ограничения |

Для q1/q2 все поля gate diagnostics остались одинаковыми во всех вариантах.
Это проверка сохранённых evidence lists, не новый retrieval/selection replay:
общая функция term matcher участвует также в выборе evidence, и влияние на
новое ранжирование здесь не измерено. Три исходных gate metadata воспроизведены
полностью; исходный API-отказ q3 и реальные ответы q1/q2 сохранены.

Десять искусственных контролей и их intent labels составлены ассистентом.
Labels не передаются в gate и не являются независимым gold. Исходный matcher
уже принимает отрицание с точной поверхностью запроса; проблема шире новой
словоформы. Поэтому оба минимальных shortcuts **не перенесены в runtime**.
Процент lexical admission нельзя интерпретировать как scientific accuracy.

Tests run:

- **66 passed**: 14 новых diagnostic/counterexample tests и 52 прежних generation /
  user-question preparation/live-scope controls. Проверены отсутствие evidence,
  сохранение registered DMF identity veto и восстановление словарей после ошибки.
  JUnit: `output/lithiation_gate_audit_20261030/tests_v03.xml`.
- Ruff трёх новых файлов прошёл; mypy отдельного diagnostic module прошёл.
  Полный suite и runner mypy не запускались.
- Все три frozen adequacy metadata точно совпали с текущей исходной функцией.
  23 страницы пяти PDF совпали со свежим извлечением; original/layer SHA256 и
  точные source occurrences/offsets проверены. Это text QA, не новый визуальный
  просмотр PDF и не научная разметка.
- Static HTML QA: пять TAC works, восемь основных колонок, пять существующих
  original PDF links; полный evidence и diagnostic раскрываются. Проверены 35
  текущих bindings и 293 прежних live-review bindings — прежняя история цела.
  Browser execution не проверен.
- Новых model/OAuth/DB операций, native requests и slot reservations: **0**.

Разработка и сохранённые ошибки:

- Начальный inline Python probe не выполнился из-за shell quoting SyntaxError;
  заменён модулем, вызовов провайдера не было.
- Первый test run: 4 failed / 10 passed. Тест ошибочно предполагал, что
  аббревиатура `ДМФА` зарегистрирована в required-concept catalogue; там есть
  `DMF` и полные русские формы, но этой аббревиатуры нет. Контроль исправлен на
  поддерживаемый `DMF`; приложение и catalogue не менялись. Отсутствующая
  аббревиатура остаётся отдельным ограничением. Первый JUnit сохранён.
- Default pytest cache был недоступен в sandbox; последующие прогоны отключают
  cacheprovider и используют отдельный project-local basetemp.
- Первый reader ошибочно ожидал map вместо фактического списка articles.json;
  исправлен reader, исходный файл сохранён. Затем не был создан source_snapshot
  directory; partial review_v01 сохранён.
- review_v02 завершился с тремя TAC works q3. Финальный review_v03 включает
  все пять работ целевого вопроса и двух контролей; scope correction явно внесён
  в протокол, старые report/protocol/code snapshots сохранены.
  Summaries: `output/lithiation_gate_audit_20261030/development_failures.json`;
  это не полные raw terminal logs.

Артефакты:

- [Финальная HTML-таблица](../output/lithiation_gate_audit_20261030/review_v03/review.html).
- [Протокол](records/lithiation_gate_audit_protocol_v0.1.md).
- `scripts/lithiation_gate_audit.py`: source-text probes и отдельные controls.
- `scripts/run_lithiation_gate_audit.py`: frozen metadata/source replay и HTML.
- `tests/unit/test_lithiation_gate_audit.py`: контрпримеры и isolation controls.
- `output/lithiation_gate_audit_20261030/review_v03/`: report, source snapshots,
  manifest; отдельные `qa.py/json` и три JUnit в корне стадии.

Limitations:

Аудит не распознаёт научного владельца операции, не устанавливает её выполнение
и не доказывает полноту каталога методов. Он показывает, почему два предложенных
лексических изменения недостаточны. Успех 66 software tests не равен качеству
научных ответов. Независимых эталонов по-прежнему нет.

Следующий дизайн должен отдельно проверять: описание операции над нужным
материалом; статус performed/negative/future; принадлежность реагента и условий
этой операции; границу между найденным примером и полным каталогом методик.
До такой проверки нельзя объявлять lexical admission научным подтверждением.
Исторические model outputs, PDF, бюджеты и закрытые slots сохранены.

Verdict:

Лексический механизм отказа воспроизведён; unsafe workaround отклонён на
контрпримерах. Рабочий gate пока сохраняет исходное поведение. Пункт4 независимой
научной оценки остаётся открытым. **Прогресс плана: 75%.**
