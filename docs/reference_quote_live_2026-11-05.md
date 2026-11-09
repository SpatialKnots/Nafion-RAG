# Q01/Q05: две разрешённые живые попытки — 2026-11-05

Changed:

- Пользователь ответил «Давай, да» на конкретное предложение по одной новой
  попытке Q01/Q05,1200 output tokens/120s/no retry/fallback. Разрешение отдельно
  сохранено в `output/reference_quote_live_20261105/approval_v01.json`;
  [scope](records/reference_quote_live_scope_2026-11-05_v0.1.md).
- **Реально выполнены2 model POST attempts и2 OAuth attempts**, по одному каждого
  на случай, последовательно в fresh processes через наблюдаемый ASGI `/answer`,
  read-only DB/rollback. Модель обоих ответов — GigaChat-2-Max:2.0.30.01.
  Ни повторов, fallback, continuation, изменения prompt/gate/runtime/index/
  schema/thresholds/units, ни новых вопросов в этой работе не было.
- Перед отправкой сверены первоначальные manifests/native bytes/runtime/model/
  index/source bindings. Исходные zero-budget preparations неизменны; новые
  authorized copies отдельно привязали approval/scope/driver/tests/current inputs.
  Ровно два ранее документированных drift допускаются после точного сопоставления
  с сохранённым source snapshot: stdout ensure_ascii Q01 и local author_words
  rename для mypy. Старые hashes/guards не переписывались.
- Gold/intake/post-hoc review reads в inference workers запрещены. Code snapshot
  разрешён только для точной проверки известного input drift. В inference вошли
  исходные вопросы и цитаты найденных источников, не пользовательский эталон.
- Native requests, native responses, API errors, traces, pages, timing/usage
  сохранены. **Оба новых global slots и оставшаяся allowance закрыты**:
  `scope_close_v01.json`; resend_authorized=false. Старые budgets также закрыты.

## Фактический исход

| Случай | Native response | Результат API | Посимвольное сравнение с разрешёнными строками |
|---|---|---|---|
| Q01 | answerable=true,1 claim,stop | **HTTP502**, `Bounded answer must select unique exact source-backed statements` | Одно изменение: `«AB` (U+00AB/U+0041/U+0042) заменено одним U+ABAB. Остальная строка совпадает, citation E1 верен. |
| Q05 | answerable=true,2 claims,stop | **HTTP502**, та же локальная проверка | В method claim `«D` (U+00AB/U+0044) заменено одним U+0ABD. **Table claim совпадает целиком**, обе citation IDs верны. |

**Успешных ответов API0/2.** Эти строки не восстановлены, не нормализованы и не
опубликованы как успешный ответ. API ошибки отделены от raw непринятых claims
провайдера в [таблице «эталон / программа / различия»](../output/reference_quote_live_20261105/review_v02/review.html).
Native данные — реальные ответы, не прежние SYNTHETIC selections.

В трёх native claims последовательности цифровых поверхностей совпали с
разрешёнными строками. Два текстовых расхождения ограничены указанными заменами;
таблица232 characters совпала точно. Это **строковая диагностика**, не scientific
accuracy/semantic ownership/независимая экспертная приёмка. Не утверждается, что
получен полноценный научный пересказ на русском языке.

Модель предоставила правильные source IDs и все три запрошенные quotation roles,
но не обеспечила точное соответствие длинным Unicode enum strings. HTTP502
сформирован локальным валидатором после получения native body, не заявляется
HTTP502 от внешнего сервера. Provider сообщил stop и408/615 output tokens;
length stop не наблюдался. Точный механизм Unicode-искажения (модель/экранирование/
сериализация) не установлен; исходный native content сохранён.

## Использование и время

- Q01: input789/output408/total1197, precached_prompt_tokens3.
- Q05: input991/output615/total1606, precached_prompt_tokens3.
- **Итого по provider usage: input1780/output1023/total2803**.
  Денежная стоимость неизвестна; billing из этих данных не выводился.
- OAuth0.79s/0.55s; model request9.61s/16.02s; total observed service24.53s/37.69s.
  Это два наблюдения с локальным retrieval, не latency benchmark.
- Фактические native bytes совпали с approved bodies:
  Q01 SHA256821446de48ea4256d654923a4679eb3ed2cfa60ada9d97bfb1606139c14fc2eb,
  Q05 SHA256f264b28d85dbbad9800811149dc44deb38e781b45bb748a603b4a34c4c218d63.

Tests run:

- **31 distinct tests passed**:18 новых approval/budget controls,6 новых
  Unicode/character/citation diagnostics controls и7 прежних one-call durability/
  manifest/request-boundary controls. Реального transport в unit tests нет.
  JUnit: `output/reference_quote_live_20261105/tests_final_v01.xml`.
- Два фактических **offline ASGI replays** воспроизвели полные HTTP502 status/body
  и точные native request bytes, используя исходные сохранённые provider bodies.
  Новых model/OAuth/DB calls в review0. Первоначальный reviewer уже выполнил эти
  две симуляции, но остановился на неправильных ключах adapter перед HTML;
  failed source snapshot сохранён, исправленный review_v02 снова воспроизвёл2
  случая. Это **не** дополнительные live attempts.
- Проверены manifests,44 review bindings, actual→approved trace/source/native
  equality, два global result/closed records,2 PDF hashes и3 свежие selected
  pages. Исходный gold SHA2568b5450878bf9791635767f800616c38e8f1d9108852563171b8af8d1a3677332
  неизменен. [Verification](../output/reference_quote_live_20261105/verification_v01.json).
- Static HTML:2 cases,2 scoped TAC works, восемь основных колонок,10 существующих
  PDF/page links, expandable raw content/diagnostics и поиск. Ответы/эталоны
  показаны без исправлений. Browser execution не проводился.
- Ruff четырёх новых Python-файлов прошёл; `git diff --check` прошёл с CRLF
  warnings. App/runtime в этом этапе не менялись; ранее пройденные262 tests и
  mypy app не объявлены новым run этого этапа.
- Первый unit run:18 passed/7 fixture setup errors из-за отсутствующего parent
  каталога workspace basetemp. Каталог создан до следующего run;25 passed, затем
  финальные31 passed. Старый JUnit сохранён. Первый reviewer adapter KeyError
  исправлен только в новом script; live outputs не менялись. Starlette/httpx
  deprecation warning сохранён. Один ad-hoc verification command дал SyntaxError,
  исправленная read-only проверка завершилась успешно; реального transport там нет.

Limitations:

- n=2 exposed development, не blind независимый test. General scientific accuracy
  не назначена. Наличие корректных цифровых поверхностей не является semantic
  оценкой полноты/условий/материала.
- Точный source-copy contract оказался хрупким в реальном provider response:
  native string enum не обеспечил побайтового соответствия. Локальный отказ
  работает как задано, но пользователь не получает успешного ответа.
- Scientific synthesis, Q03 claim-level εког/ΔH validation и Q03 missing p2
  остаются открыты. Cache/ORM/concurrency/browser/new visual PDF/full suite и
  deployment не проверялись; независимая оценка всё ещё открыта.

Verdict:

Разрешённый живой тест завершён, без повторов. Источники и обязательные роли
вернулись, но **оба API ответа отклонены из-за Unicode-несоответствия цитат**.
Следующий отдельно версионированный **офлайн** фикс: модель выбирает короткие
ASCII selection IDs, сервер строго проверяет IDs/citations/completeness и сам
подставляет неизменённые заранее привязанные source quotes. Не следует ослаблять
exact-source checks или молча «чинить» реальные ответы. Этот фикс пока не
реализован; новая live проверка потребует нового scope/разрешения. Все бюджеты
закрыты. План качества остаётся75% работ, не scientific accuracy.
