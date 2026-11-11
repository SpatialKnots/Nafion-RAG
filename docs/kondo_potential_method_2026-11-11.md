# ARIADNE: метод оценки потенциала и относительный ноль Kondo02

Changed:

Пользователь «ДАвай дальше» продолжил Kondo02. До app edits выполнен свежий
actual DB read-only/RR/rollback capture полных пулов разрешённых статей: все30
прежних top5 результатов/role metadata совпали с parent Nambu identity.
Полная оригинальная PDF5 свежо отрендерена Poppler и визуально просмотрена.
Methods-фрагмент был вне исходного top5. Узкая роль potential-method/zero для
одного запрошенного иона сохраняет неизменённый объект существующего полного
пула статьи; top5, filters, scores, вопрос и число lookup прежние. Retention
не устанавливает scientific ownership и сам по себе не допускает ответ.

Новый potential_method.py +quantitative_facts/source_reference ветки. Конечная
grammar связывает подготовку электролита/соль/добавку, явную дозу mmol dm−3,
трёхэлектродную CV, рабочий/reference/counter electrodes, среднюю точку пиков,
предположение о постоянстве редокс-потенциала пары, определение Emetal,
соотношение μ=FEmetal+constant для того же электролита, выбранный ноль и
относительные значения. Все шесть μ, пять E (включая preparation), металлы,
редокс-пары/добавка, соль, дозы и повторные basis/ratio должны согласоваться.
Source aliases/прибор/ratio/reference salt берутся из raw, не из QA ID/ответа.

Направления явно разделены: CV измеряет редокс-потенциал Fc/Fc+ относительно
Li reference electrode; ELi определяется как потенциал Li-электрода относительно
Fc/Fc+. Постоянство redox potential — явное предположение источника, не
доказанный общий закон. Относительный ноль задан для LiFSI/DME (1/10 by mol).
Ни абсолютный ноль, ни численное μ, ни новые коэффициенты не рассчитываются.
Формула сохраняет положительный F и constant в записи источника. Наименование
ферроцена не добавляется автоматически там, где bound Methods supplies only Fc.

Доза добавки берётся из явной записи1 mmol dm−3. Parenthetical shorthand mm/mM
ограничен поддерживаемыми литеральными формами и должен совпадать в preparation
и measurement; неизвестные/противоречивые сокращения (например M) отказывают.
Это не глобальная расшифровка шрифта или конверсия единиц. Температура CV остаётся
неизвестной;25°C из следующего Charge–Discharge абзаца в CV не переносится.

Пять raw-bound method/preparation/definition/relation/zero facts, полный F1
либо отказ. Числа/текст/условия/сырой тип источника заново пересчитываются при
выборе, точные raw offsets/SHA сохранены. Existing required-fields guard
not_evaluated, scientific ownership false. App changes: два существующих файла
и новый module. Нет новых glyph/resources/config, prompt/question/DB/PDF/index,
UI/threshold/API schema изменений. Ranking изменён узко и явно.

Tests run:

- Итоговый affected702passed,51 новый тест; focused_v02 —130passed до
  дополнительного unit-shorthand контроля, включённого в702. Один прежний
  Starlette/httpx warning. Audit hook запрещал внешнюю сеть, network_denials0.
  ASGI проверки вне sandbox с синтетическим транспортом/БД.
- Полный mypy app216 файлов passed. Финальный Ruff8 Python-файлов passed.
- Проверены неправильные μ/E/metal/reference direction, redox пары/добавка,
  убранное предположение, midpoint/oxidation-only, неверный знак формулы,
  разные электролиты, абсолютные вместо относительных значений, ratio/basis,
  dose/units/shorthand, ambiguous preparation, unknown query conditions,
  prior/hypothetical/negative/bibliographic scope и record/raw drift.
- Четыре actual experimental API SYNTHETIC исхода: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502; read-only/rollback,
  guard not_evaluated. Это не ответы реальной модели.
- All30 actual-service comparison_v01:19→20 ready-unsent, только Kondo02;
  остальные29 full retrieval/service results и19 ready traces/native точны.
  Дополнительно три synthetic service исхода нового случая.
- Ablation: ranking-only без контракта и contract-only на старом top5
  сохраняют отказ; вместе ready-unsent. Ручной diagnostic packet не использован.
- 81 исторический actual-service сценарий сохраняет full results, пять native
  inputs точны. Регрессия на открытых development данных, не независимость.
- Свежая actual API preparation с настоящим поиском/registry, read-only/rollback:
  trace/native exact, registry diagnostics0/network denials0;12158bytes,
  SHA008dc46352b38c1fd1e11df6fd9fd0c0b4d9a3d7aeb91fbf0ee9564d72d094df.
  Реальные model/OAuth/newslots0, остановка до внешнего transport.
- Exporter заново проверил32 raw-anchor observations, пять facts/два направления
  reference/assumption/dose/formula/relative zero, полную свежую PDF5 extraction
  и support против выбранного raw, неизменный PDF SHA, исходные объекты pool/
  same top5 и оба UI adapters. HTML содержит30 сравнительных строк и raw цитаты
  preparation/method отдельно.

Сохранённые ошибки и исправления:

Первый focused_v01:127passed/2failed. Previously reported перед preparation
не блокировался, хотя тот же prefix перед Evaluation блокировался; локальный
guard применён и к preparation. Второй провал был test fixture: synthetic F1
ссылался на E1, а сервис после evidence selection использовал E2. Правильный
GenerationOutputError дал502. Тест теперь читает единственную фактическую
citation_id из native prompt; неверная цитата сохранена отдельным502 контролем.
App/tests source snapshots и diagnosis сохранены в attempt_v01, JUnit сохранён.

После130passed отдельный constructed adverse probe показал ложный допуск,
когда оба shorthand заменены на M при неизменной явной mmol dm−3 дозе. Exact
source/probe/original module сохранены в unit_probe_v01. Grammar сокращений
сужена до поддерживаемых mm/mM с явной длинной единицей, добавлен отрицательный
контроль, итог702passed. Первые Ruff замечания касались порядка импортов app/
fresh driver; исправлены до окончательных сравнений/подготовки. Никакой
первоначальный провал не назван успешным научным ответом.

Limitations:

Конечная source-method grammar на открытых development примерах. Нельзя
считать её независимой проверкой электрохимической методики, универсальности
redox standard, термодинамического вывода или общей scientific accuracy.
Код требует одну непротиворечивую preparation/procedure/reference convention;
иные методы, зарядовые нотации, units/формулировки могут оставаться unsupported.
Numeric μ не вычисляется, ratio не переводится в молярность/долю; unsupported
shorthand не исправляется автоматически. Реальные ответы модели/F-ID behavior,
natural transfer, browser layout, полный suite, wheel/deployment не проверены.

Verdict:

Kondo02 готов к отправке с исходной методикой, сохранённым предположением и
относительным нулём.20/30 — готовые входы, не20 научно правильных ответов.
Остаются10 отказов:3 context,5 explanation,2 limits. Старые19 готовых входов
сохранены, реальных новых вызовов нет, live scopes закрыты/план качества75%
прежний. Следующий context case — Nambu09: раздельные составы/концентрации
испытаний coin cells и измерения проводимости.

[Отчёт](../output/kondo_potential_method_20261111/review_v01/review.html) ·
[Проверка](../output/kondo_potential_method_20261111/review_v01/report.json) ·
[Сравнение30](../output/kondo_potential_method_20261111/comparison_v01/result.json) ·
[Свежая API подготовка](../output/kondo_potential_method_20261111/fresh_api_v01/Kondo_02/result.json)
