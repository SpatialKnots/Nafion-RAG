# ARIADNE: ограничение растворимости, Nambu08

Changed:

Пользователь «Давай дальше» продолжил последний отказ Nambu08: почему в
сравнении проводимости нет1M LiPF6 в нефторированном DEE. Новый
solubility_limit.py и узкая ветка quantitative_facts используют существующий
выбранный parent PDF1/2. Retrieval/ranking/evidence preservation не менялись.

Три source-bound facts связывают:

- DEE с исходными именами1,2-diethoxyethane/ethylene glycol diethyl ether.
  Используется точный identification frame аннотации; приведённое там
  сравнение viscosity/permittivity не объявляется причиной отсутствия1M DEE.
- Методический conductivity frame: растворы LiPF6 в FETFEE/EFEE/ETFEE,
  1mol dm−3, концентрация указана при25°C, Figure3(a).
- В том же методическом блоке растворимость LiPF6 в DEE «much less than»
  1mol dm−3. Это качественное ограничение относительно выбранной концентрации,
  не точная измеренная растворимость и не нулевая растворимость/проводимость.

Ответ связывает отсутствие DEE в этом сравнении с явным ограничением
растворимости; это сопоставление приведённых условий, не заключение из
отсутствия найденных сведений. Не выдуманы неудачная попытка приготовления,
температура измерения растворимости, точная растворимость или механизм.
25°C остаётся reference temperature концентрации и не присваивается
solubility fact. Кривые Figure3 не оцифровывались.

Один полный raw parent с уникальными identification/comparison frames,
согласованные salt/base aliases, три различных включённых растворителя,
DEE вне их списка; identification sample принадлежит списку. Точное имя
1,2-diethoxyethane — конечная nomenclature binding, не общий structure toolkit.
Положительная концентрация/порог сравнения совпадают с вопросом через Decimal;
M соответствует mol dm−3 при том же численном значении, без пересчёта.
Строчное m не принимается как M. Полный вопрос обязан совпасть с finite
шаблоном после проверенного single-surname/year prefix. Не снимаются общие
why/negative/status/concept/relation veto; новых modal exceptions нет.

F1 selection пересчитывает original raw/SHA/type/offsets/условия/русский текст;
arithmetic null, scientific ownership false, required-fields guard
not_evaluated. Сохранены unknown fields exact_solubility,
solubility_measurement_temperature, preparation_attempt, conductivity_value.

Повторно используются две exact-source glyph operations прежнего conductivity
catalogue: U+00B9→minus в двух mol dm−3 единицах данного parent. Полные свежие
Poppler PDF1/2 визуально просмотрены; positioned offsets/font/bbox/font-program
SHA перепроверены. Новых glyph interpretations/aliases/resources/package-data
нет. Все восемь прежних каталогов, raw/PDF/pyproject/config прежние.

Tests run:

- focused_v01:58passed; affected_v01:1298passed,58новых, с первой попытки.
  Один прежний Starlette/httpx warning; network denials0. Локальные ASGI
  controls вне sandbox; audit hook запрещает внешнюю сеть.
- Полный mypy app226 файлов passed; Ruff6 Python-файлов passed. Только import
  formatting исправлен до запусков; новых pytest/type failures не было.
- Проверены wrong/zero concentration, threshold mismatch, less/equal/greater
  versus much less, salt/base alias/identity/name inconsistency, включение DEE
  в список, repeated solvent, wrong units, missing/ambiguous/cross-parent/
  spliced/reversed frames, prior/hypothetical/negative/reference scope,
  неизвестные дополнительные требования/температура/точное значение/failed
  preparation и raw/record/catalogue drift. Другие aliases/values/temperature/
  figure numbers проходят, если все source bindings согласованы.
- Четыре actual experimental API SYNTHETIC контроля: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502. Ещё три synthetic
  service исхода. Это не реальные ответы модели.
- comparison_v01:30 frozen actual-service before/after,29→30ready-unsent,
  только Nambu08. Retrieval всех30, остальные29 полных результатов и29
  прежних native побайтно точны. Все30 случаев теперь development-exposed;
  готовность не означает scientific accuracy или отсутствие других дефектов.
- regression_v01:81 historical actual-service сценарий/five native exact.
  Это regression safety на открытых данных, не независимая научная оценка.
- fresh_api_v01/Nambu_08: настоящий поиск/registry/actual experimental API,
  read-only/RR/rollback, trace/native exact, registry diagnostics0, network
  denials0. Native6421bytes,
  SHAecfd3f5abe6c0854c80c76dfa7044d4819dbe0e0406f6256b1e59c092519d08d.
  Остановка до transport; реальные model/OAuth/newslots0.
- Exporter независимо проверил18raw-anchor observations/3facts/name/salt/
  comparator/concentration/reference temperature/unknowns, две positioned
  glyph operations/font programs, полные PDF1/2 против raw/support,
  неизменный PDF SHA и оба существующих UI adapters.
  HTML30case rows/3details/7local links, bindings/manifests сохранены.

Limitations:

Конечная source grammar на открытых development вопросах/источниках, не общий
causal/chemical validator и не independent acceptance.30/30 означает готовность
этих входов; это не30 модельных ответов и не30 правильных ответов. Новые статьи,
реальное поведение F-ID selection, scientific accuracy, browser layout,
полный repository suite, wheel и deployment не проверены. Retrieval/ranking/
questions/prompt/thresholds/UI/DB/PDF/index/API schema прежние. Все старые live
scopes закрыты, новых нет; план75% и независимая оценка прежние.

Verdict:

Nambu08 подготовлен с сохранением качественного solubility limit и
температурных границ. В этой development серии remaining pre-model refusals0,
ready-unsent30/30. Следующий отдельный этап — сводный offline audit/freeze
серии; новые live измерения или независимые задачи требуют отдельного scope.

Отчёт: output/nambu_solubility_limit_20261111/review_v01/review.html.
