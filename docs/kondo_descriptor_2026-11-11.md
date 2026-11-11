# ARIADNE: определение дескриптора Kondo01

Changed:

Пользователь «Да, давай продолжим далее» продолжил работу с13 оставшимися
отказами. Следующим взят Kondo01 из группы context: нужное определение уже
содержится в выбранной первой странице, дополнительный retrieval не требуется.

В quantitative_facts добавлено конечное семейство descriptor_definition.
Используется существующий raw-bound/F1 путь количественного дескриптора;
новые факты явно помечены source_reported_definition с операциями reported
descriptor/thermodynamic definition/stability interpretation. Это определение
и авторская корреляция, а не численное экспериментальное измерение. Unit=null,
numeric_value=null, scientific_ownership_verified=false; отдельный claim_kind
сохраняет это различие в provenance. Старые версии/контракты не переписаны.

Три факта связывают название параметра, термодинамическое определение и
направление интерпретации устойчивости. Конечная локальная grammar требует
chemical potential, partial molar Gibbs free energy, thermodynamic stability,
higher(lower)→unstable(stable) в solvation environment и явно сформулированную
сильную корреляцию с интеркаляцией в графит. Все пять упоминаний иона и три
обозначения потенциала должны соответствовать единственному иону вопроса.
Никаких QA IDs, авторов, ответных значений или фиксированного Li+ в grammar.

Полная оригинальная PDF1 свежо отрендерена Poppler и визуально просмотрена.
Исходные Greek micro sign/разрывы строк/переносы обрабатываются только прежней
NFKC/dehyphenation/whitespace нормализацией с сохранением точных raw адресов.
Новые glyph aliases, единицы, пересчёты или исправление raw не понадобились.
Серверный текст сохраняет авторское определение и сильную корреляцию, не
переносит из соседних абзацев порог/SEI механизм/универсальность. Более высокому
потенциалу сопоставляется неустойчивый, более низкому — устойчивый ион в
сольватационном окружении, как сформулировано в источнике.

Только полный F1 либо отказ, затем повторный расчёт всех полей/текста из raw.
При изменённом ионе/символе, другом типе энергии, перевёрнутой зависимости,
prior/hypothetical/negative/reference-list scope и неизвестных условиях вопроса
новый контракт не допускает ответ. Прежние required-concept/relation veto
сохранены. Из app изменён только quantitative_facts.py; новых app modules,
resources/config, retrieval/ranking, вопросов, prompt, DB/PDF/index/UI,
threshold и внешней схемы API изменений нет.

Tests run:

- Focused107passed; итоговый затронутый набор607passed,37 новых проверок.
  Один прежний Starlette/httpx warning. Audit hook запрещал внешнюю сеть,
  network_denials0. ASGI проверки выполнены вне песочницы из-за ранее
  наблюдавшихся зависаний в ней, с синтетическим транспортом/БД.
- Полный mypy app214 файлов passed; финальный Ruff5 Python-файлов passed.
- Проверены generic Na+/K+ селекторы, смешение ионов/символов, Gibbs/Helmholtz
  и partial/total, корреляция/causation, направление устойчивости, отрицательный/
  старый/гипотетический источник, дополнительные условия/единицы вопроса,
  metadata scope, raw/record/rendering drift и переносы/µ→μ с точными адресами.
- Три actual experimental API SYNTHETIC исхода: F1→200/answered,
  abstention→200/insufficient, unbound prose→502, read-only/rollback.
  Existing required-fields guard not_evaluated. Это не реальные ответы модели.
- Финальный all30 actual-service comparison_v02:17→18 ready-unsent, новый
  только Kondo01; остальные29 full results/retrieval и17 старых ready native
  точны. Дополнительно три synthetic service исхода нового случая.
- 81 исторический actual-service сценарий и пять native inputs точны;
  regression_v01. Это регрессия на прежних development данных.
- Свежая actual API preparation read-only/rollback: trace/native exact,
  registry diagnostics0/network denials0,7085bytes,
  SHAe196047973ec8b1db389606cfdac1eb3dc11c580d375af9cfd564e7a88b4c203.
  Реальные model/OAuth/newslots0, остановка до внешнего transport.
- Exporter заново проверил17 raw-anchor observations, все три определения и
  направление higher/lower, полную свежую PDF1 extraction/каждый support против
  выбранного raw и неизменный PDF SHA, оба UI adapters. HTML содержит30 строк.

Сохранённые остановки/исправления harness:

Первый Ruff указал порядок импортов fresh driver, исправлен до его исполнения.
Первый all30 comparison_v01 остановился на реконструкции старого Peng07:
загруженный source snapshot вычислял resource path через свой output __file__,
поэтому не находил старый catalogue; рабочий app module проходил тот же вопрос.
Исходный driver/failure сохранены в before_baseline_loader_fix_v01, частичный
comparison_v01 не переписан. Loader устанавливает исходный app __file__ перед
исполнением неизменного snapshot, сохраняя закреплённые catalogue hashes.

Диагностический импорт без -B создал дополнительный .pyc в frozen directory;
следующий запуск остановился на проверке manifest до сравнения. Все изначально
связанные файлы сохранили SHA. Служебный bytecode с SHA перенесён в отдельный
probe_bytecode_v01, оригинальный frozen manifest снова совпал без переписывания.
Финальный запуск с -B/comparison_v02 воспроизвёл все30 baseline cases и завершил
сравнение. Проблемы harness не объявлены научными отказами или app regressions.
App после тестов/первой подготовки нового определения не менялось.

Limitations:

Конечное source-definition семейство по открытым development примерам,
не независимая научная проверка или общий entailment checker. Определение и
корреляция воспроизводят источник, не доказывают истинность/причинность или
универсальность. Другие формулировки/ионы с иной зарядовой нотацией/неизвестные
условия могут оставаться неподдержанными. Натуральный перенос, реальные ответы
модели/F-ID compliance, scientific accuracy, browser layout, полный suite,
wheel и deployment не проверены. Числа готовности не являются научной accuracy.

Verdict:

Kondo01 готов к отправке с полным определением и сохранённым направлением
интерпретации. Всего18/30 ready-unsent; остаются12 отказов:5 context,
5 explanation,2 limits. Все прежние17 готовых входов сохранены. Реальные
вызовы модели/OAuth отсутствуют, старые scopes закрыты, план качества75% прежний.
Следующий прямой контекстный случай — Nambu01, идентичность трёх эфиров и
степени фторирования; он в этом шаге не изменён.

[Отчёт](../output/kondo_descriptor_20261111/review_v01/review.html) ·
[Проверка](../output/kondo_descriptor_20261111/review_v01/report.json) ·
[Сравнение30](../output/kondo_descriptor_20261111/comparison_v02/result.json) ·
[Свежая API подготовка](../output/kondo_descriptor_20261111/fresh_api_v01/Kondo_01/result.json)
