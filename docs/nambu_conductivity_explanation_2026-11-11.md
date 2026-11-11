# ARIADNE: объяснение проводимости, Nambu07

Changed:

Пользователь «Давай дальше» продолжил Nambu07. Новый conductivity_explanation.py
и узкая ветка quantitative_facts используют существующий выбранный parent
PDF2/3. Retrieval/ranking и сохранение evidence не менялись.

Четыре source-bound facts сохраняют: порядок EFEE > FETFEE > ETFEE для
растворов LiPF6,1 mol dm−3 при reference temperature25°C; способность
частичного фторирования повышать образование hydrogen bonds (can increase)
и приведённое авторами объяснение electron-pair acceptability; возможное
усиление сольватации PF6− и ионной диссоциации (may result); возможную
anion-attracting роль fluoromethyl group CH2F- (may serve).

Анион PF6− не подменяется катионом лития. Возможное объяснение не объявлено
доказанным единственным механизмом. Численная степень диссоциации,
абсолютная проводимость, transport numbers и независимое структурное
подтверждение не добавлены.25°C относится к заданию концентрации, а не к
утверждению, что весь температурный порядок измерен только при25°C.

Один contiguous block/parent, уникальный полный кандидат, согласованные
salt/solvents/ranking и literal metal-prefix/anion binding. Последнее —
конечная проверка записи, не общая проверка химической формулы или валентности.
Полный вопрос должен совпасть с finite шаблоном после single-surname/year
prefix; нет общего снятия causal/why/negative veto. Исключения status guard
ограничены тремя exact can/may clauses распознанного блока. Прежний guard
currentness/reference/negation и service concept/relation veto сохранены.
Коды/концентрация/температура/порядок берутся из источника. F1 либо отказ;
raw offsets/SHA/type/fields и русский серверный текст пересчитываются.
Scientific ownership false, arithmetic null, required-fields guard not_evaluated.

Три U+00B9 интерпретированы как минусы: две mol dm−3 единицы в методическом
frame и заряд PF6−. Свежий полный Poppler PDF2 визуально просмотрен. Новый
reviewed_conductivity_explanation_glyph_aliases_v01.json ограничен одним
точным parent/article/chunk/page/type/full raw SHA, PDF text offsets/font/
bbox/font-program SHA. Это визуальная интерпретация агента, не автоматическая
семантика шрифта или независимая экспертная приёмка. Семь прежних каталогов,
original raw и PDF прежние; package-data дополнен одной строкой.

Tests run:

- Первоначальные54focused:53passed/1failed. Ошибочное ожидание отказа для
  FETFEE > EFEE > ETFEE: запрошенная пара FETFEE > ETFEE остаётся истинной.
  Исходный тест/код/диагноз сохранены в test_expectation_v01, JUnit focused_v01.
  Проверка неправильного порядка заменена дублированным элементом; добавлен
  positive control другого допустимого порядка. Приложение не менялось.
  focused_v02:55passed. Первоначальные cache permission warnings сохранены;
  финальные проверки используют отдельный cache_dir.
- affected_v01:1240passed; после typing-only исправления affected_v02:
  1240passed,55новых. Один прежний Starlette/httpx warning, network denials0.
  ASGI synthetic tests вне sandbox, audit hook запрещает внешнюю сеть.
- Initial mypy дал1arg-type diagnostic: условное выражение view выводится
  как SourceView, новый parse принимает ReviewedGlyphView. В этой ветке view
  всегда создаётся через новый ReviewedGlyphView constructor. Явный typing.cast
  возвращает тот же объект; AST после удаления cast/import точно равен
  исходному. Исходный module/readers/diagnostic сохранены в typing_attempt_v01.
  Финальный полный mypy app225 файлов passed; Ruff7 Python-файлов passed.
- Проверены can/may→does/must/cannot, anion→cation/positive charge/wrong anion,
  hydrogen→covalent bonds, acceptability→donability, CH2F→CF3, salt/concentration
  units, wrong/repeated ranking, wrong solvent membership, prior/hypothetical/
  negative/reference scope, cross-parent/subsection, incomplete/ambiguous source,
  raw/record/catalogue drift и дополнительные требования к вопросу.
- Четыре actual experimental API SYNTHETIC контроля: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502. Отдельно три
  synthetic service исхода; не ответы реальной модели.
- Финальный comparison_v02: все30 frozen actual-service before/after,
  28→29ready-unsent, только Nambu07. Retrieval всех30, остальные29 полных
  результатов и28 прежних native точны. Preliminary comparison_v01 до cast
  сохранён:30caseJSON/29native побайтно совпадают с finalv02; manifests не
  переписывались, исторический source hash сопоставлен со snapshot.
- Два81-case historical replays,162 service executions/five native exact;
  финальный regression_v02 выполнен после cast. Development-exposed regression,
  не независимая научная оценка.
- fresh_api_v01/Nambu_07: настоящий поиск/registry/actual experimental API,
  read-only/RR/rollback, trace/native exact, registry diagnostics0, network
  denials0. Native11444bytes,
  SHAb8c59e3fc9e9f2487a2949f5e50bc4f1fc465a0e3038d9a3b6863a81169e2fbb.
  Остановка до transport; реальные model/OAuth/newslots0.
- Exporter проверил45raw-anchor observations,4facts/order/conditions/modal
  clauses/anion charge/group,3positioned glyphs/font programs, полный PDF2
  против raw/support, неизменный PDF SHA, оба существующих UI adapters.
  HTML30case rows/4details/6local links; bindings/manifests сохранены.

Limitations:

Конечная source grammar на открытом development источнике; не общий causal/
chemical validator и не независимое подтверждение авторского механизма.
Новые статьи, реальные F-ID ответы, scientific accuracy, browser layout,
полный repository suite, wheel и deployment не проверены. Retrieval/ranking/
questions/prompt/thresholds/UI/DB/PDF/index/API schema прежние. Автоматического
glyph repair нет. Старые live scopes закрыты, новых нет; план75% прежний.

Verdict:

Nambu07 подготовлен с сохранением анионной роли и can/may.29/30ready-unsent;
остаётся Nambu08, explanation family. Следующий отдельный этап — Nambu08.
Независимая оценка остаётся открытой.

Отчёт: output/nambu_conductivity_explanation_20261111/review_v01/review.html.
