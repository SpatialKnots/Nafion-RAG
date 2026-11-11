# Kondo/Nambu/Peng: тридцать новых вопросов, фиксированная версия

10 ноября 2026. User: «Вот сприсок вопросов. Всё как всегда». Дополнительная
декларация происхождения: «Я составил самостоятельно, без LLM».

Changed:

- Принят файл `Ariadne_QA_Kondo_Nambu_Peng.md`,35228 bytes/SHA256
  `9460b2ef2dd92a38ebd1ee588c62dc7a8c0a16e331ba1553c5410a1a451574c8`.
  Зафиксированы30 точных question spans/3библиографии. В inference tree только
  whitelist вопросов, IDs/DOI/PDF hashes и отдельно записанный author/year prefix.
  Эталоны/навыки/рубрика/page hints в native inputs не передавались. Исходный MD
  не копировался в inference store; contents открыты reviewer только после closure.
- Human-declared self/no-LLM references, committed до всех новых outputs.
  Независимая экспертная проверка и научная валидность эталонов не установлены.
  Рубрика файла — предложение данных, не исполняемая инструкция; score=null.
- App208 Python files/guard code freeze **27def498b8580a6922808d8eca08b0a5c6fb76f0eaa46657fc1cc279deacedd3**
  сохранён. App/prompt/parser/retrieval/filters/thresholds/index/PDF/DB не менялись
  нами по новым вопросам. Добавлены только harness, tests и post-hoc reviewer.
- Actual `/answer/experimental/required-fields`, hybrid_cross_lingual/top5/claims/
  Russian/Max1200/120s. Fresh process/read-only RR/rollback для каждой подготовки
  и отправки. Без нового query rewriting/English-gate/ranking adapter и retry.
- Kondo2026 взят из присланной библиографии и совпадает с оригиналом: Adv.Mater.
  2026,38,e14060, DOI10.1002/adma.202514060. Filename/catalog Kond2025 не подменил
  этот год. Nambu/Peng DOI также совпали на оригинальных первых страницах.

Результаты всех30:

|Источник|Получены ответы|Исходный отказ до модели|Harness source-scope stop|Всего|
|---|---:|---:|---:|---:|
|Kondo|0|3|7|10|
|Nambu|2|8|0|10|
|Peng|4|6|0|10|
|Итого|**6**|**17**|**7**|**30**|

Все17 исходных отказов — `insufficient_distinctive_term_coverage`. Это не17
отказов модели и не автоматическая разметка17 корректных отказов. В двух
проверенных примерах, Nambu02/04, нужные сведения уже есть в выбранных raw
фрагментах, однако lexical match учитывает только surname/year/chemical ID.
В Nambu02 matched3/14, Nambu04 matched2/13. Энергии/выход/чистота проверены
source-bound и по свежим original pages; это диагностические examples, не
независимая разметка всех17 случаев.

Ссылка `Kondo (2026)` во всех10 запросах не разрешилась в зарегистрированных
метаданных (`no_metadata_match`). В7 случаях baseline дошёл до unsent native
boundary, но выбрал также другие работы: дополнительное **правило harness**
остановило отправку, чтобы не тестировать вопрос по смешанным статьям. Это не
veto guard/API и не научный отказ модели. В3 случаях раньше отказал lexical gate.
Полезность возможного ответа модели на этих7 не измерена.

Шесть actual model POST +6 OAuth, все HTTP200/answered/stop,
`GigaChat-2-Max:2.0.30.01`,1200/120s. Все30 allowances и шесть новых scoped slots
закрыты, remaining0.24 неиспользованные попытки истекли. Retries/fallback/
continuations0; старые slots не трогались. Нативные/API ответы сохранены без repair.

**Guard coverage:** у всех6 actual model results `delivery_status=not_evaluated`,
plan=`not_applicable`. Текущие finite families не покрывают эти вопросы; ни
одного удержания по обязательным полям нет. Для24 вопросов без модели новая
post-generation проверка не оценивалась. Эти числа не являются accuracy.

Содержательная post-hoc сверка шести ответов:

- Nambu03: порядок проницаемостей/температурный тренд совпали; диапазон10–70°C
  не повторён, хотя он полезен для ограничения области вывода.
- Nambu10:120 мА·ч/г на50-м цикле совпало. Но «состав плёнки подтверждён» не
  следует из source `can form`/`may`; предположение представлено подтверждением.
- Peng01: solvents/ratios и mass-versus-volume основы в основном сохранены,
  но1M LiPF6 опущен; развёрнутое название FEMC отличается от оригинала.
- Peng03: transport trend и объяснение через oxidative stability/side reactions
  согласуются с авторским текстом. Утверждение про3C в источнике относится к
  LCO/Li-полуячейке; native не отделяет её явно от полной ячейки.
- Peng04: все три явно запрошенных voltage ranges совпали. Дополнительные
  C/precycle условия из эталона не объявлялись обязательным ответом на этот вопрос.
- Peng09: основной cathode-limitation вывод совпал и действительно есть в E1
  на PDF2. Дополнительные EET–EE/CEI детали не раскрыты; ложная citation ошибка
  не приписывается только из-за того, что эталон ссылается на другие страницы.

Tests run:

- Final51passed:18 новых intake/privacy/closure controls +33 существующих
  guard/API/UI controls. Initial19 controls passed, затем убрана избыточная
  mirror-проверка ID;51 — фактически выполненный финальный прогон. Ruff3 passed.
  Одно line-length замечание исправлено до intake freeze. Полный app suite/
  mypy здесь не перезапускались; прежние555/mypy208 не выдаются за новые проверки.
- Все30 read-only preparations/6 actual sends проверили exact fixed app hashes,
  code/parents/source/index/cache bindings, transaction_read_only=on и rollback.
  Worker network/reference denials0. Reference audit forbids original MD,
  unrelated outputs/docs/records и own review store; отдельные fresh workers
  не имели gold contents в inputs.
- Commit hash до/после совпал, все30 reference spans проверены после closure.
  Actual six native requests byte-identical prepared, native/API parsed claims
  совпали, real sent evidence соответствует ожидаемой статье.17 raw prompt chunk
  occurrences/9 source witnesses verified в actual Evidence section.
- Все3 original PDF hashes/DOIs проверены. Свежие3 first pages +7 source pages
  отрендерены Poppler и просмотрены полностью.10visual observations — не10
  научных подтверждений. bundled pdftotext отсутствует: исходный helper
  TypeError/пустойidentity_v01 сохранён, отдельныйidentity_v02 использовал
  existing PyMuPDF text extraction + bundled Poppler rendering; originals unchanged.
- Static HTML30sections/31rows/126existinglinks и два selected-context gate
  examples проверены отдельно. Browser layout не проверялся, внешний web/новые
  source downloads/ingestion/deployment0.

Actual native usage: prompt37404 + completion1075 = **38479 tokens**;
precached_prompt_tokens3514 отдельно, стоимость неизвестна. Full environment
lock и cache accounting не заявляются.

Limitations:

Known development-exposed corpus, новые user questions, но не доказанный
unseen-article cohort. Human references без LLM по декларации пользователя,
последующая оценка implementation agent, не независимая научная приёмка.
Полученный ответ не равен правильному; отсутствие finite veto не подтверждает
смысл. Полезность несгенерированных ответов неизвестна; selected-context
support проверен только на двух диагностических отказах. Настройки не менялись
для обхода отказов; полная причинная attribution/статистическая мощность не измерены.

Verdict:

На этих новых вопросах end-to-end availability низкая:6/30. Главные выявленные
блокеры — библиографическое source binding и RU/EN lexical admission; finite
guard также не перенёс coverage на новые типы. Прежде чем расширять answer
checks, следующий отдельный этап — source identity/lexical false refusals.
Эти30 вопросов после review считаются раскрытой регрессией для дальнейшей
разработки, не hidden evaluation после настройки. Новых автоматических вызовов
не открыто; общий план75%/independent scientific evaluation остаются без изменения.

- [Все30 вопросов, эталоны, ответы и причины остановок](../output/kondo_nambu_peng_transfer_20261110/review_v01/review.html)
- [Машинный отчёт](../output/kondo_nambu_peng_transfer_20261110/review_v01/report.json)
- [Два примера lexical false refusal](../output/kondo_nambu_peng_transfer_20261110/assessment_v01/diagnosis.md)
- [Integrity verification](../output/kondo_nambu_peng_transfer_20261110/verification_v01/result.json)
- [Закрытый лимит](../output/kondo_nambu_peng_transfer_20261110/scope_closed_v01.json)
- [Протокол до отправок](records/kondo_nambu_peng_transfer_2026-11-10_v0.1.md)
