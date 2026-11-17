# ARIADNE: rewriting v0.2 подключён к текущим 30 вопросам

Changed:

По указанию пользователя `Подключи метод` добавлен явный профиль
`scripts/fan_doi_besenhard_rewriting_20261113.py`. Он использует существующие
`query_rewriting_v02`/v0.1 adapter и тот же experimental required-fields API,
что и исходная подготовка. Профиль работает в отдельных worker-процессах;
process-global patches прежнего адаптера не включаются в общий сервер.
Приложение, defaults, API schema, PDF/БД/индекс, научная логика, словарь,
пороговые значения и прежние snapshots не изменялись.

Rewriting v0.2 подключён к ранжированию контекста явно указанной статьи,
отбору evidence и проверке достаточности. Переведённый английский вопрос
используется для lexical adequacy, а исходные required-concept/relation vetoes
сохраняются. Финальная генерация получает исходный prefixed русский вопрос
и реальные source fragments; перевод не становится доказательством.

Реализованы команды init, authorize-rewrites, rewrite/rewrite-all, freeze-plans,
prepare. Authorize-rewrites требует отдельного текста фактического разрешения;
init не создаёт разрешение или попытки. Все native requests сохраняются до
отправки. Реальный rewrite sender использует прежний GigaChat transport,
scope-local exclusive ledger, по одному model/OAuth attempt на вопрос, сохранение
raw response/ошибок и закрытие scope. После закрытия требуется exposed-agent
смысловая проверка переводов; недопустимые переводы не исправляются и не
отправляются на генерацию. Это работа агента, не обязательная ручная работа
пользователя. prepare привязывает frozen plan к exact answer-preparation manifest.
Answer-live allowance не создаётся этим rewrite scope.

Зафиксированы30 исходных случаев, полностью идентичных baseline. Вход rewriter
содержит только оригинальный вопрос, locked identifiers и проверенные title/
article/PDF identity. Названия подтверждены уникальными точными spans и свежим
извлечением: Fan PDF1, Doi PDF2 после обложки, Besenhard PDF1. Полный научный title
не подменён коротким DB label. В native нет эталонов, abstract/results или page hints.

Все30 exact rewrite requests готовы, но не отправлены:66116bytes суммарно,
максимальный2301bytes. Предлагаемый scope — не более30 rewrite POST и30 OAuth,
GigaChat-2-Max,1200 output tokens,120s/HTTP, по одной попытке, без retries/
fallback/continuations, стоимость неизвестна. Текущий live allowance0.

Tests run:

-59 focused tests passed: новый профиль, прежние v0.1/v0.2 guards и experimental
  API routes. Новый синтетический API-контроль: исходный русский вопрос получает
  insufficient_evidence; тот же вызов внутри rewriting profile достигает
  синтетического provider; provider получает исходный русский вопрос и исходный
  текст. После выхода profile прежнее поведение восстановлено.
- Подтверждены original material и relation vetoes, отказ при другой article/PDF
  identity, read-guard запрет эталонов/assessment, отказ sender без authorization.
  API-тесты используют fake source/session/provider, без реальных DB/model/OAuth.
- Scoped Ruff двух новых scripts и нового test passed.
- Все30 native bytes пересобраны и сверены;30 вопросов/30 прежних manifests
  неизменны;3 title spans/pages/PDF identities перепроверены;33 local HTML links
  существуют. Свежий worker под actual ReferenceGuard прочитал все30 frozen
  cases с network/reference denials0; authorization отсутствует.

Первая попытка tests:58passed/1setup error, Windows PermissionError на системной
Temp. Повтор с новой workspace basetemp:59passed/one прежний Starlette warning;
JUnit сохранён в output/fan_doi_besenhard_rewriting_20261113_attempts/focused_v02.xml.
Первый read-only exporter остановился на byte mismatch: snapshot JSON сортирует
context keys, тогда как native request сохранил исходный порядок конструктора.
Первоначальный reader сохранён как review_reader_v01_failed.py. Исправлен только
reader: восстановлен известный constructor key order при проверке. Исходные
request bytes/контексты/manifests не переписывались. Финальная exact сверка30
native прошла. Это диагностика сериализации, не научная нормализация.

Limitations:

Реальных rewrite/model/OAuth calls/slots0. Новых переводов и ответов GigaChat нет.
Синтетические API-контроли не являются результатами проверки пользовательских
статей. Пока нельзя утверждать, что допущенных вопросов стало больше шести,
и нельзя выдавать доступность за scientific accuracy. Parser/finite guards не
доказывают смысловую эквивалентность; прежний exposed-agent meaning review
сохранён. Общий сервер не переключался на process-global experimental adapter.
Полный pytest/mypy/browser/layout/scientific acceptance не запускались.

Verdict:

Метод подключён и проверен для отдельного сравнительного прогона этих30
вопросов. Первый baseline6ready/24refusals сохранён. Тридцать конкретных
rewrite inputs готовы к отдельно разрешённой отправке по п.5 existing separate-set
protocol. Все старые allowances закрыты; новое authorization отсутствует.
После реальных переводов/закрытия scope/смысловой проверки будут подготовлены
exact answer requests для отдельного answer scope. План75% без изменений.

Отчёт: output/fan_doi_besenhard_rewriting_20261113/connection_review_v01/review.html.
Конкретный scope: connection_review_v01/prospective_rewrite_scope.json в том же
output каталоге. Input freeze: input_freeze_v01/manifest.json.
