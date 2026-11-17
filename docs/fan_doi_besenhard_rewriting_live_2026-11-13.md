# ARIADNE: реальный rewriting 30 вопросов, 13 ноября 2026

Changed:

Пользователь `Запускай` разрешил ранее предъявленный scope:30 rewriting POST,
30 OAuth, по одной попытке, GigaChat-2-Max/1200 output tokens/120s per HTTP,
без retries/fallback/continuations. Authorization записан отдельно и привязан
к исходному freeze/scope SHA. Генерация ответов в это разрешение не входила.
Приложение, defaults, научные правила, словарь, prompt/parser/adapter v0.2,
PDF/БД/индекс и исходный baseline не менялись во время прогона.

Выполнены ровно30 actual rewriting POST и30 OAuth, по1/1 на каждый случай,
без повторов. Все30 returned models: `GigaChat-2-Max:2.0.30.01`, finish_reason
`stop`. Raw request/response сохранены; каждый request совпадает с frozen bytes,
response SHA совпадает с observed/stored digest без redaction. Все30 scope-local
attempt slots и общий rewriting allowance закрыты; остаток0.

Формальные проверки прошли27/30. B2/B3 отклонены: Li заменено словом lithium;
B8: Mg заменено magnesium. Это нарушение frozen literal-identifier contract,
а не установленная химическая ошибка перевода. Guards не ослаблялись; raw
переводы не исправлялись и повторно не отправлялись.

После закрытия scope выполнен exposed-agent смысловой review всех30 исходных
вопросов и реальных переводов/keywords. Приняты26. Дополнительно консервативно
отклонён F6: исходник явно спрашивает изменение объёмного и межфазного
сопротивлений, перевод сравнивает сами сопротивления и использует volumetric
resistance. Эквивалентность не признана гарантированной; это явное решение
знакомого с набором агента, не независимая экспертная аттестация. F6 не исправлялся.
Странная punctuation/title-derived wording вспомогательных keywords сохранена;
нормализация выполнялась только прежним v0.2 parser с явными diagnostics.

Decisions и actual canonical plans зафиксированы в plans_freeze_v01. Затем
выполнены26 фактических API preparations через прежний experimental required-fields
маршрут в свежих процессах/read-only repeatable-read/rollback. Четыре отклонённых
перевода сохранены как skipped/rewrite_rejected без answer-provider вызова.
Все26 принятых переводов дошли до frozen native answer boundary, все выбрали
нужную статью. Итоговые answer questions остались исходными prefixed русскими.
Ответов модели на вопросы нет; placeholders не считаются OAuth/API результатами.

| Статья | Baseline ready-unsent | После rewriting ready-unsent |
| --- | ---: | ---: |
| Fan | 2 | 9 |
| Doi | 4 | 10 |
| Besenhard | 0 | 7 |
| Всего | 6 | 26 |

Это плюс20 подготовленных запросов, а не плюс20 правильных ответов. Все шесть
прежних допущенных случаев сохранены. Шесть исходных native bodies/baseline
outputs не переписывались. Новых answer native requests26,988995bytes суммарно,
максимальный68668bytes; каждый ниже100000-byte ceiling, без clipping.

Reported rewrite usage:10183prompt+2581completion=12764total tokens.
Precached5031 входят в prompt count, не добавляются к total. Стоимость неизвестна.
Прямой HTTP status/header capture адаптер не предоставляет; successful native
results не выдаются за отдельно записанный HTTP200 envelope.

Tests run:

- Новый preparation-only execution wrapper исправляет проверенный probe-ом
  конфликт read guard: временные constants baseline модуля меняли разрешённые
  пути к исходным hash bindings. Wrapper сохраняет original freeze/prepared roots
  до активации; private/assessment запреты сохранены. Исходный frozen runner,
  переводы, thresholds и scientific behavior не изменены. Probe сохранён как
  preparation_guard_probe_v01.json; extension source/bindings — execution_prepare_v01.
-5 focused synthetic regression controls passed: воспроизведение исходной
  блокировки, допустимость stable hash reads и сохранение запретов эталонов/
  private/assessment. Scoped Ruff wrapper/review/test passed. Прежние59 tests
  относятся к предыдущей итерации и заново здесь не запускались.
-30 actual native rewrite responses заново разобраны без сети:27 canonical
  plans exact,3 исходных rejection reasons exact. Проверены30 request SHA,
  response SHA/usage/model, ledger/result/closure и exact frozen questions.
-26 actual answer preparations/plan bindings/readonly contracts проверены;
  исходные baseline manifests неизменны.362 union input bindings verified,
  включая неизменные app/resources, актуальный docs glossary, source/code/PDF/
  model/index inputs. Answer digests уникальны.
-23 уникальные выбранные PDF-страницы свежо извлечены,122 source-page
  observations и3 PDF hashes точны; raw page text/quote spans совпали.
  Статический HTML содержит30 cases и115 существующих local links.
- Final verification связывает158 actual input/output/authorization/closure/
  ledger/manifest paths. Подтверждены ровно30 attempt slots, все случаи закрыты,
  остаток0, answer_authorization=false. Network/reference denials0.

Limitations:

Новых answer model calls0. Нет ответов/научных баллов/общей accuracy. Допуск26/30
не доказывает точность будущих ответов. Смысловой review выполнен exposed
implementation agent; независимая scientific acceptance не установлена.
Ни source-level independence, ни полностью autonomous meaning validation
не заявлены. Full suite/mypy/browser/PDF visual QA/deployment не запускались.
Реальные outputs и четыре исходных отказа сохранены без ремонта/пересылки.

Verdict:

Разрешённый rewriting scope завершён и закрыт. На этом наборе метод повысил
готовность к отправке с6до26. Все26 concrete answer requests готовы, но их live
scope пока не разрешён. Prospective максимум26 answer POST+26 OAuth, по1/1,
GigaChat-2-Max/1200/120s, без retry/fallback/continuation, стоимость неизвестна.
Отдельное разрешение требуется по п.5 прежнего separate-set protocol;
оно не выводится из разрешения на rewriting. Все старые allowances закрыты.
План75% без изменений, scientific accuracy null.

Финальный review:
`output/fan_doi_besenhard_rewriting_20261113/live_review_v01/review.html`.
Машинные итоги и конкретные answer request SHA: `report.json` и
`prospective_answer_scope.json` рядом с HTML. Контроль закрытия:
`final_verification_v01/summary.json` в том же output каталоге.
