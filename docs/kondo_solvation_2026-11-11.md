# ARIADNE: сольватация, концентрация и μ в Kondo03

Changed:

Пользователь продолжил предложенный Kondo03. Нужные утверждения уже находились
в выбранном raw PDF2; retrieval/ranking не менялись. Новый solvation_trends.py
и ветка quantitative_facts связывают preparation scope, два направления
изменения μ, Raman-корреляцию и итоговое авторское объяснение из одного полного
parent. Четыре facts, полный F1 либо отказ; русский текст формирует сервер.

В bound source более слабая сольватирующая способность растворителя и более
высокая концентрация соли, включая локализованное высококонцентрированное
состояние, повышают μLi⁺; это соответствует дестабилизации Li⁺. Raman-связь
с более выраженным спариванием Li⁺/FSI⁻ сохраняет linear correlation,
suggesting и commonly related. В отдельной author-summary записи остаются
взаимодействие катиона с анионом, координационное число/степень спаривания и
основность аниона по Льюису. Отдельное направление эффекта основности или
численный коэффициент не выводится. Не добавлены SEI mechanism, graphite
thresholds, энергии из промежуточных списков, новые численные зависимости.

Согласуются все шесть μ-symbol occurrences, три катиона, два аниона, обе
записи соли и номера рисунка. Связь соли ограничена литеральным совпадением
monovalent cation/anion codes; это не общая проверка стехиометрии/структуры.
Требуется preparation→trend→correlation в одной секции одного raw parent.
Неполные/дублированные/противоречивые записи, неизвестные условия, general
why/proof/negative/universal вопросы отказывают. Все raw offsets/SHA/type
сохранены, поля и серверный текст заново пересчитываются при F1 selection.
Ownership false, arithmetic null, guard not_evaluated.

Полные оригинальные PDF2/3 свежо отрендерены Poppler и визуально просмотрены,
включая Fig2 и caption. Прежних NFKC/dehyphenation/whitespace правил достаточно;
новых glyph aliases/resources/package-data/config нет. Пики/точки/fit Raman
не переизмерялись; текст источника не считается независимым causal proof.

Tests run:

- Focused60passed с первой попытки; affected948passed (60 новых), один прежний
  Starlette/httpx warning, network denials0. ASGI synthetic checks вне sandbox.
- Полный mypy app220 файлов passed; финальный Ruff6 Python-файлов passed.
- Проверены обратные направления, стабилизация вместо дестабилизации,
  исключённый localized state, чужие μ/ion/anion/salt/figure, correlation→proof,
  commonly→universal, basicity→acidity/only factor, prior/hypothetical/negative/
  bibliographic scopes, cross-section/cross-parent assembly, record/raw drift,
  неизвестные дополнительные требования и consistent generic source codes.
- Четыре actual experimental API SYNTHETIC контроля: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502; read-only/
  rollback, guard not_evaluated. Дополнительно три synthetic service исхода.
- All30 actual-service comparison_v01:23→24 ready-unsent, новый Kondo03;
  все30 retrieval traces и остальные29 full results прежние,23 prior native
  exact. Это готовность входов, не24 научно верных ответа модели.
- 81 historical actual-service сценарий сохраняет full results, пять native
  inputs exact. Открытые development данные, не независимая оценка.
- Свежая actual API preparation с настоящим поиском/registry: read-only/
  rollback, trace/native exact, registry diagnostics0, network denials0;
  9608bytes, SHAb2990420941f6573efba7eb03008b88b12e35a24097fb718bd4e94b24892f6f0.
  Остановка до transport; реальные model/OAuth/newslots0.
- Exporter проверил41 raw-anchor observations,4facts/directions/status,
  полный PDF2 против raw/support, свежую PDF3 extraction, неизменный PDF SHA
  через frozen bindings и оба UI adapters. HTML30 case rows/4fact details.

Первый source-only probe отказал: PDF text содержит FSI−vibration без пробела.
Исходный module и diagnosis сохранены в spacing_probe_v01. Pattern допускает
ноль или более whitespace после заряда перед literal vibration, raw не
переписывается. Начальные Ruff formatting/E501 исправлены до запуска driver/
exporter. Провалов тестов в этой итерации не было.

Limitations:

Конечная source grammar по открытым development источникам, не общий semantic/
causal validator и не независимое принятие Raman-интерпретации. Новые статьи/
реальные F-ID ответы/независимая scientific accuracy/browser layout/полный
repository suite/wheel/deployment не проверены. Retrieval/ranking/вопросы/
prompt/thresholds/UI/DB/PDF/index/resources/config/API schema прежние.
Старые live scopes закрыты; новых нет.

Verdict:

Kondo03 подготовлен с сохранёнными направлениями и статусом корреляции.
24/30 ready-unsent; шесть отказов:4explanation,2limits. Следующий отдельный
этап — Kondo07, контрпример универсальности концентрации LiFSI. Общий causal
допуск не включён. Независимая оценка открыта; план75% прежний.

Отчёт: output/kondo_solvation_20261111/review_v01/review.html.
