# ARIADNE: субъект раздела и явная ссылка на подрисунок

Changed:

Добавлен отдельный `lithiation_subject_context_v0.1`, получающий только raw text.
Он не меняет предыдущий operation analyzer и не подключён к `/answer`.
Вопросы, IDs и reference labels алгоритму не передаются.

Реализованы два вида source-linked предложений:

1. Ближайший предшествующий numbered single-line heading с явным Nafion и
   единственной формой membrane/dispersion. Новый numbered heading закрывает
   старый scope, включая заголовок без материала. Неявный fallback к более
   раннему заголовку запрещён.
2. Явная ссылка на уникальную предшествующую подпись рисунка и точный подрисунок.
   Номер и буквенная метка должны совпасть; латинские/кириллические метки не
   отождествляются. Подрисунок должен описывать литирование и форму материала,
   parent caption — явно называть Nafion. Слова общего названия схемы исключены
   из распознавания операции конкретного подрисунка.

Защита границ:

- другой материал, неизвестный явно названный объект операции/мембраны,
  composite/analogue и смешение membrane/dispersion не дают перенести субъект;
- новый раздел между подписью и операцией закрывает ссылку;
- переход then/затем/«на втором этапе» не наследует материал от общего заголовка
  без новой явной ссылки; «другой этап» блокирует перенос;
- прежние ограничения статуса, отрицания, будущего, вопросов, смешанных операций
  и общих условий сохранены;
- выводятся все попытки, положительные и blocked, с точными spans заголовка,
  parent caption, подрисунка, ссылки, операции и промежуточного текста;
- численные условия не переносятся и не перепривязываются. Выполнение,
  material owner, value owner и полнота каталога методик не объявляются
  установленными даже у `context_subject_candidate_unverified`.

Фактические результаты:

- Исходные 36 operation/field results сохранены точно: 14 source rows и22
  искусственных текста предыдущего этапа. Добавлены14 отдельных искусственных
  context controls, всего36 constructed texts. Все labels составлены ассистентом,
  не являются независимыми эталонами и не входят в analyzer input.
- На source rows:14 blocked/unresolved attempts и **две структурные proposals**.
  Это не научная accuracy или доказательство выполнения опыта.
- **Исходный q3 E1, диссертация с.51:** общий heading остаётся blocked из-за
  смешанного контекста мембран/дисперсии и перехода этапа. Отдельная цепочка
  «см. рисунок2.1б» → подпись «Схема подготовки мембран Nafion» → подрисунок
  «литирование мембраны (б)» → «проводили литирование» даёт explicit-reference
  candidate. Никакого обхода исходного gate или реального model call не было.
- **Post-hoc с.52:** heading2.2.1 «Литирование водно-спиртовой дисперсии Nafion»
  даёт отдельный candidate к последующему «Литирование проводили…». Это не
  original q3 input. Membrane и dispersion не объединены.
- Все24 отобранных context excerpts имеют уникальные точные совпадения в
  зарегистрированных PDF page texts. Их page offsets и ссылки сохранены.
  Для остальных потенциальных случаев reader сохраняет missing/ambiguous,
  не заменяя exact match нормализованным совпадением.
- Четыре численных/реагентных поля в q3 и все остальные baseline поля/owner
  states не изменились. Из схемы не заимствована температура: прежнее расхождение
  текста60–80°C и рисунка60–65°C сохранено, structural subject link его не решает.
- Среди constructed attempts:32 blocked/unresolved, пять прежних local targets
  без нового переноса и три context candidates. Это counts конкретных exposed
  controls, не precision/recall или independent acceptance.

Tests run:

- **132 passed:**43 новых context tests +89 прежних operation/lexical/ownership
  tests. JUnit: `output/lithiation_subject_context_20261030/tests_v04.xml`.
- Проверены RU/EN заголовки, неизвестный объект/новый раздел, смена формы,
  переход этапа, неправильный/отсутствующий/дублированный подрисунок, смешение
  кириллических и латинских labels, смена материала в bridge, отделение parent
  title от panel action, raw spans, отсутствие памяти между вызовами,
  неизменность условий и исходного analyzer.
- Ruff трёх новых файлов и mypy diagnostic module прошли. Runner mypy/full
  suite/browser execution не запускались.
- Свежим извлечением сверены24 страницы пяти исходных PDF. Рекурсивная проверка
  source spans и24 уникальных page anchors прошла. Сверены49 текущих bindings
  и293 старых live-review bindings; все три исходных gate metadata неизменны.
- Static HTML QA: пять TAC works, восемь основных колонок,29 существующих
  PDF/page links; полный source, попытки, baseline и диагностические причины
  раскрываются отдельно.
- Новых model/OAuth/DB операций, native requests и slots: **0**.

Разработка:

Первый Ruff исправил import ordering теста; первый mypy выявил пять сообщений
о выведенном heterogeneous heading type — добавлена явная типизация списка.
Первый source run остановился на `ValueError: Invalid normalized-view span`:
двоеточие после первой panel label ошибочно использовалось как её начало.
Теперь separator допустим только до первой метки, иначе первая часть остаётся
unresolved; добавлен regression test. На том сбое output directory ещё не был
создан. Затем review_v01 успешно завершился; дополнительные guards неизвестного
материала в bridge/caption сохранены в финальном review_v02. Предыдущие source
snapshots/manifests оставлены. Overlapping test runs36/129/130 не суммируются с132.
Summaries, не полные raw logs: `output/lithiation_subject_context_20261030/development_notes.json`.

Артефакты:

- [Финальный HTML](../output/lithiation_subject_context_20261030/review_v02/review.html).
- [Протокол](records/lithiation_subject_context_protocol_v0.1.md) и
  [14 новых controls](records/lithiation_subject_context_controls_v0.1.json).
- `scripts/lithiation_subject_context_audit.py`: source-only analyzer.
- `scripts/run_lithiation_subject_context_audit.py`: binding/page/field replay,
  source-linked HTML и snapshots.
- `tests/unit/test_lithiation_subject_context_audit.py`:43 новых tests.
- `output/lithiation_subject_context_20261030/review_v02/`: report, manifest,
  snapshots; отдельные qa.py/json, JUnit и summaries в корне стадии.

Limitations:

Это конечные structural templates и material-conflict cues, не общая химическая
entity recognition или coreference. Не все формы/заголовки/неявные ссылки
распознаются. Полученные две связи остаются unverified proposals. Независимой
научной разметки, подтверждённого владельца условий, исчерпывающего каталога
и научной приёмки нет. Рабочий q3 по-прежнему отклоняется до модели.

Verdict:

Запрошенная привязка реализована и воспроизведена на реальном q3: explicit
figure reference теперь даёт отдельную проверяемую subject proposal, вместо
объединения всех mentions в разделе. Положительные и заблокированные пути
сохранены с exact evidence; source/answer/runtime история не переписана.
**Прогресс четырёхпунктного плана остаётся75%:** independent scientific
evaluation не завершена, новые live calls автоматически не разрешены.
