# Пункт 4: естественный пропуск coulombic role

9 ноября 2026, Asia/Yekaterinburg.

Changed:

По разрешению пользователя выполнен следующий офлайн-шаг: аудит реальных
пропусков source grammars и минимальное расширение одного семейства.
Сначала зафиксированы corpus/runtime/controls, затем изменено распознавание.

Выбран composition/cycling, одна роль — coulombic efficiency. В заключении
Lin2020 имеется явная конструкция `coulombic efficiency of the Li||Cu
half-cells maintain ... or so after charging and discharging for ... times
under ... current density and ... lithium deposition amount per cycle`.
Она содержит в одной фразе ячейку Li||Cu, приблизительную CE98%,200 циклов,
ток1 mA cm−2 и осаждение1 mAh cm−2 за цикл. Все значения извлекаются из raw
источника; эти числа/авторы/IDs/страницы не входят в runtime grammar.

Это один естественный passage PDF7, повторённый в трёх перекрывающихся chunks
(PDF6–7,7,7–8). Повторы не являются независимыми положительными примерами.
SourceView сохраняет точные offsets и raw quote с исходной лигатурой eﬃciency.
Ранее recipe давала `missing_or_ambiguous_source_pattern`; теперь выдаёт
привязанный к источнику CE fact. Эффективность не смешивается с capacity retention.
Статус остаётся `source_reported_approximate`, scientific ownership=false,
температура измерения и состав электролита в этой фразе явно неизвестны.

Изменены четыре существующих app файла; новых app модулей нет:

- `source_paraphrases.py`: отдельная `natural_coulombic_source_v0.1`, строгая
  непрерывная конструкция с полным набором полей, существующий prefix guard;
  предыдущая `source_paraphrases_v0.2` Q02/Q04 остаётся прежней;
- `fact_recipes.py`: общий сбор старых/новых CE кандидатов и явная ambiguity
  при разных passages; условия и единицы не берутся из соседней операции;
- `fact_types.py`: необязательная версия grammar в Rendering; при её отсутствии
  прежний `data()` остаётся байт-совместимым по сериализованным значениям;
- `answer_facts.py`: версия добавляется только в новый внутренний record как
  `source_grammar.version` и проверяется при серверном пересчёте.

F-ID, exact citation/source binding, recomputation, sample/operation/unit/status
checks и explicit unknowns сохранены. Retrieval/gate/context budget, selectors,
public top-level fields, PDF/DB/index/schema не менялись. Старые outputs и
пользовательские uncommitted файлы не откатывались, commit не создавался.

Ключевая граница: это улучшение извлечения роли, не новый production-ответ.
Существующий composition contract требует abstract и не собирает F3 из
Conclusion автоматически. Он не расширялся и не обходился. Conclusion
сам по себе не получает полный family admission; это проверено отдельно.

Аудит и Tests run:

- Frozen corpus:619 chunks/33 works. Предварительный cue intake дал280
  наблюдений слов в11 работах; ни один такой hit автоматически не назван фактом
  или ошибкой. После исправления scanner зафиксированы212 пар chunk/recipe
  по шести ролям. Q05 проверяется с явно объявленными exposed selectors,
  не как автоматическое понимание любых образцов в других работах.
- Полных recipe observations до/после:18→21. Изменились ровно три bindings
  одного CE passage; остальные209 observations неизменны. Не размеченные
  recipe refusals не являются установленными false refusals.
- Отдельно зафиксированы10 естественных development windows: три новых CE
  bindings, три прежних CE bindings, четыре неполных/неподдержанных контекста.
  Labels предварительные, assistant-authored, корпус раскрыт; это не independent gold.
  Например, capacity clause того же Conclusion не задаёт число циклов, а
  Laporta Conclusion не содержит полной количественной preparation chain.
- Отдельные19 constructed controls:2 positives (другие числа/whitespace)
  и17 negatives (отрицание, будущее, чужая работа/образец, неправильные units,
  операция, химический регистр, отрицательное число, отсутствующая
  приблизительность/циклы, разрыв фразы). Все ожидаемые outcomes получены.
- Начальный pre-edit run:5 failed/24 passed/11 deselected — три новых real
  bindings и два constructed positives не распознавались. JUnit/log сохранены.
- Финальный affected run: **713 passed** (673 предыдущих +40 новых),
  failures/errors/skips0, external-network guard denials0. Проверены field values,
  raw addresses, unknowns/status, mixed/contradictory passages, F-ID/citation,
  numeric/operation/unknown/version/summary tampering и сохранение admission.
  Starlette/httpx deprecation warning сохранён.
- Три записанных81-run service preparations: freeze_v01, канонический freeze_v02
  и compare_v01, всего243 actual frozen-channel service executions. Все пять
  current и76 old full results, а также пять actual native bodies прежние.
  Старые76 не активируют новую CE grammar и не подтверждают её научный смысл.
- Отдельно собран component packet из двух неизменённых реальных raw parents:
  composition/capacity из Abstract и CE из Conclusion. Это явная компонентная
  сборка, не production evidence selection/admission. Настоящий provider
  сформировал native body на подменённой transport boundary, без отправки:
 7616 bytes, SHA256 `73d6556dcbfe41051a595e3a18721f5faf5a2fc5d62540ee39c8cdb065c756bc`.
  Все три decoded F records и source quotes соответствуют source-bound fields.
  Синтетическая complete F-ID provider reply и серверный renderer проверены
  unit test; это не новый результат реальной модели.
- Контрольные источники:4 PDFs/9 свежих страниц,6 узких CE raw-span observations
  точно найдены на свежих страницах. Весь corpus:33 original PDF SHA проверены.
  В HTML включены5 прежних вопросов,10 natural windows,19 constructed controls,
  полный before/after audit и TAC33/eight columns с существующими PDF links.
- Ruff девяти app/test/driver файлов и полный mypy app192 passed.

Сохранённые подготовительные ошибки:

1. Pre-edit freeze_v01 имел опечатку в cue efficiency; half-cells alternative
   всё же находила выбранный passage. Reader исправлен до app edits, отдельно
   сохранён канонический freeze_v02. Оба runtime/service snapshots остались.
2. Первый mypy выявил неверно выведенный тип списка кандидатов; добавлена
   аннотация. Первый Ruff выявил три неиспользованных импорта; удалены.
   Ни одно научное правило по этим diagnostics не менялось.
3. Sandbox controls_after_v01 с TestClient остановился после частичного вывода,
   final JUnit не создан и pass не присвоен. Host CIM установил PID20704/14776,
   остановлены только эти процессы. Контрольный100-test run без HTTP и полный
  713-test run вне sandbox завершились. Причина hang не установлена.
4. Первый review_v01 остановился на Python tuple/list сравнении свежих source
   addresses с JSON. Canonical bytes controls_v01.json до/после были идентичны.
   Review reader теперь сравнивает точные canonical bytes; исходные controls,
   outcomes и runtime не менялись. Финальный review_v02, старый log сохранён.

Limitations:

Один новый уникальный real CE passage в ранее раскрытой работе, не перенос
на новую независимую литературу и не general entailment/ownership validator.
Остальные194/191 неполные observations до/после — результаты parser,
а не научные отрицательные примеры или доказательство отсутствия сведений.
Finite guards могут пропускать сложные отношения или давать лишние отказы.

Нет новых полных production answers: прежние пять запросов не изменились.
Component assembly не подключена как обход abstract/author/coverage checks.
Реальных model/OAuth calls и новых slots0; контекст/native пяти прежний,
поэтому fresh DB/rollback preparation не выполнялась. Browser/PDF visual QA,
full suite, cache-ORM/concurrency/deployment и независимая научная оценка
в этой итерации не выполнены. Все прежние live scopes закрыты.

Verdict:

По реальному corpus audit найден и устранён конкретный grammar miss одной
роли. Сохранены прежние сценарии и строгий полный family admission. Общий
scope пункта4 и scientific evaluation остаются открытыми; прежний75% прогресс
проекта не пересчитывается по этим controls.

Следующий содержательный шаг — отдельный source-role assembly protocol:
при каких явных условиях composition/capacity/CE можно собирать из разных
разделов одной работы, проверяя cells/электролит/операции и сохраняющуюся
неоднозначность. Это предложение, не реализованное расширение или разрешение
новых live calls. Также нужны реальные примеры из других работ для проверки
переноса, с раздельными development/hidden evaluation наборами.

- [HTML-обзор](../output/natural_source_grammar_20261109/review_v02/review.html)
- [Полный report](../output/natural_source_grammar_20261109/review_v02/report.json)
- [HTML QA](../output/natural_source_grammar_20261109/review_v02/qa.json)
- [Протокол до edits](records/natural_source_grammar_protocol_2026-11-09_v0.1.md)
- [Предыдущая итерация](source_paraphrases_2026-11-09.md)
