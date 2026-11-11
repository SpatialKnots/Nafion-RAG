# ARIADNE: контекст и начальная CE Peng07

Changed:

По просьбе «Давай далее» устранены две причины отказа Peng07. Нужное сравнение
было вне старого top5; после его естественного сохранения нужен отдельный
контракт принадлежности начальной CE и сравнительного максимума полуячейке.

До app edits выполнен свежий read-only/RR/rollback capture полного пула
разрешённых статей для всех30 вопросов. Все30 старых top5 результатов и role
metadata воспроизведены точно. Это существующий пул `_source_reference_chunks`,
не вручную дополненный diagnostic packet. В source_reference добавлена узкая
роль: один явный идентификатор полуячейки + запрос лучших результатов/начальной
CE; body cue той же полуячейки/highest initial CE/best cycle performance/among
several cases. Роль резервирует неизменённый объект из существующего пула перед
top5. Фильтры, оценки, исходный вопрос, top_k и число DB lookup не меняются.
Это retention cue, не научная проверка или самостоятельный допуск ответа.

В quantitative_facts добавлена конечная грамматика: ближайшая соответствующая
half-cell frame, источник явно сообщает highest initial CE и best cycle
performance among several cases. Два факта связывают электролит, процент CE,
unit%, сравнительный ранг и область сравнения с точными raw offsets/SHA.
Approximation относится только к CE; не переносится на факт циклирования.
Модель выбирает весь F1 либо отказывается; числа/русский текст выводит сервер
после повторного расчёта record из raw. Никаких QA IDs, ответных значений,
названий электролитов, авторских правил или предположений о материале в grammar.

Полная страница PDF5 свежо отрендерена Poppler и просмотрена визуально. Авторы
относят максимум начальной CE и best cycle performance к EET в MCMB/Li; CE
напечатана с приблизительностью. Серверный synthetic-selection текст сохраняет
приблизительно95.3% и ограничение сравниваемыми в статье электролитами/этой
полуячейкой. Он не переносит катодный/full-cell ranking и не подтверждает
следующее за исходной фразой предложенное SEI объяснение.

Старый Peng catalogue уже содержит позиционное наблюдение этого знака~ на
PDF5. Новый отдельный `reviewed_best_ce_glyph_aliases_v01.json`, SHA3ab2492d…,
привязывает тот же физический знак к двум полным raw parents, в том числе
новому естественно выбранному перекрывающемуся chunk. Две операции, одно
наблюдение, полные raw identity/SHA +PDF offset/font/bbox/font-program SHA.
Runtime использует прежний internal trusted catalogue API. Старые каталоги,
raw store и PDF неизменны. Никакого общего исправления U+0003 нет. Новый
resource включён в package-data; app patch ограничен двумя существующими
файлами quantitative_facts/source_reference, новым resource и одной config строкой.

Tests run:

- Финальный affected570passed,41 новый тест; один прежний Starlette/httpx
  warning. Focused77passed до семи дополнительных отрицательных контролей;
  обе версии affected_v01/v02 по570passed сохранены. Внешняя сеть запрещена
  audit hook, network_denials0; реальные provider/OAuth/newslots0.
- Финальный полный mypy app214 файлов passed; Ruff7 Python-файлов passed.
- Проверены неверные cell/full-cell, промежуточный другой owner, prior/hypothesis/
  negative/reference-list scope, неполный сравнительный ранг, неизвестные условия
  вопроса, процент/approximation, конфликтующие кандидаты и record drift.
  Для нового raw — подмена chunk/article/page/type/full text и недоступный/
  изменённый catalogue; источник не получает чужую расшифровку.
- Три actual experimental API SYNTHETIC проверки: F1→200/answered,
  abstention→200/insufficient, unbound prose→502; read-only/rollback.
  Required-fields guard not_evaluated; научная ownership false.
- Два all30 actual-service сравнения16→17, новый только Peng07. В финальном
  comparison_v02 остальные29 полных retrieval/service результатов и16 готовых
  traces/native совпали с parent. Дополнительно три synthetic service исхода.
- Ablation на фактическом полном capture: один ranking без нового контракта
  сохраняет отказ; один контракт на старом top5 тоже; вместе ready-unsent.
- Два81-case actual-service прогона сохраняют старые full results и пять
  native inputs; финальный regression_v02.
- Две свежие actual API подготовки с настоящим поиском/registry, read-only/
  rollback; trace/native exact/registry diagnostics0/network denials0.
  Финальная fresh_api_v02:4848bytes,
  SHAb2077a57d0703d063c153e9746f8ac041afdb5417ccfb6747559f24880c3a802.
  Реальных model/OAuth/slots0, остановка до внешнего transport.
- Exporter проверил15 raw-anchor observations, обе glyph операции по исходному
  page5 offset/font bytes, полную свежую page5 extraction против выбранного raw,
  PDF SHA, неизменённые объекты полного пула/top5 и оба UI adapters.
  HTML включает30 сравнительных строк и точный raw-фрагмент.

Промежуточные результаты:

Первый DB capture в sandbox остановился с localhost PostgreSQL Permission
denied10013 до соединения/транзакции; driver/failure сохранены в capture_v01.
Вне sandbox capture_v02 успешно воспроизвёл все30 прежних результатов.
Первая проверка нового ranking нашла raw context, но контракт ещё отказал:
approximation glyph не был привязан к новому exact raw parent. Snapshot/probe
сохранён в attempt_v01; добавлен отдельный catalogue, старый не изменён.
Первый Ruff обнаружил порядок импортов нового comparison driver; исправлен
до выполнения драйвера. После успешного affected_v01/fresh_api_v01 при ревью
структуры условий обнаружено, что CE approximation был также записан в
conditions факта циклирования. Исходники сохранены в before_condition_scope_v01;
условия разделены, добавлены assertions, повторены570/81/30 и свежая API.
Оригинальные сравнения/нативные inputs не переписаны; финальные версииv02.

Limitations:

Конечная грамматика на открытых development данных. Retention cue сам по себе
не устанавливает принадлежность/полноту/научную истинность сравнения. Поддержан
явный авторский максимум среди рассмотренных вариантов, не универсальный
оптимум; механистический вывод SEI не оценивается. Точная source-specific
расшифровка одного знака — агентский визуальный разбор, не независимая экспертная
приёмка; новые raw не исправляются автоматически. Проценты вне допустимой
формы, неизвестные conditions и иные формулировки conservative refuse.
Реальные ответы модели/F-ID compliance, scientific accuracy, перенос на новые
статьи, browser layout, полный test suite, wheel и deployment не измерены.

Verdict:

Peng07 готов к отправке с контекстом MCMB/Li и явно сохранённой приблизительностью.
Готовность17/30; остальные13 отказов относятся к другим исходным группам.
Все восемь исходных количественных случаев теперь готовы-unsent. Это не17
научно правильных ответов и не независимая оценка. DB/PDF/index/question/prompt/
threshold/UI изменений нет; ranking изменён узко и явно. Старые live scopes
закрыты; реальных новых вызовов нет, план качества75% прежний.

[Отчёт](../output/peng_best_ce_20261111/review_v01/review.html) ·
[Проверка](../output/peng_best_ce_20261111/review_v01/report.json) ·
[Сравнение30](../output/peng_best_ce_20261111/comparison_v02/result.json) ·
[Свежая API подготовка](../output/peng_best_ce_20261111/fresh_api_v02/Peng_07/result.json)
