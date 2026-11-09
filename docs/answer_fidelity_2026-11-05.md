# Полнота Q02 и научные оговорки Q04 — офлайн-фикс

Changed:

Пользователь согласился исправить оставшиеся проблемы Q02/Q04. Введён конечный
request-local контракт `source_bound_answer_fidelity_v0.2` в новом модуле
`app/generation/answer_fidelity.py`; изменены `gigachat.py` и `service.py`.
До правок сохранены189 bindings исходного runtime и двух тестов в `freeze_v01`.

Для вопросов сравнения модельного однофазного Li₂O с bulk при комнатной
температуре требования извлекаются только из выбранных фрагментов одной работы:
обе абсолютные проводимости/единицы и литературное происхождение bulk значения;
O₂, диапазон температуры получения слоя и время; EIS/симметричная ячейка,
концентрация LiPF₆ и объёмное соотношение EC/DEC. Числа читаются из raw текста,
в алгоритме нет case IDs, авторов, годов, PDF страниц и ожидаемых benchmark значений.
Синтез и комнатная температура сравнения выделены как разные роли.

Для вопросов Li-Nafion EC/SL о смешении/нагревании/охлаждении/структуре контракт
удерживает наблюдение поглощения в обоих циклах, длительность/температуру
выдержки, альтернативы равновесие/медленный синерезис, статус необратимости как
гипотезы, небольшое снижение интенсивности кристаллического рефлекса при
практически сохранённых областях и различие старого сухого/нового аморфного гало.

Для каждого требования сохранены точные citation/article/chunk/raw offsets/SHA.
Prompt содержит обязательные роли и исходные фрагменты. Provider и service
проверяют покрытие конечных шаблонов с нужными citations; известные преувеличения
и пропуски дают `GenerationOutputError` с перечислением причин. Исходный текст
модели не исправляется и не заменяется fallback. Если конечные source patterns
не распознаны, перед внешним вызовом возвращается явный
`answer_fidelity_source_pattern_unresolved`; это диагностический отказ parser,
а не доказательство отсутствия научных данных. Ранее отрицательный adequacy
этим контрактом никогда не становится положительным.

Публичные поля/JSON schema, source types, retrieval, единицы, пороги и исходные
PDF не менялись; добавлено явное versioned metadata `answer_fidelity`.
Вне этих двух семейств новый контракт отсутствует, prompt сохраняется побайтово.
Все прежние live бюджеты закрыты; этот этап не разрешает новых вызовов.

Tests run:

- **350 различных тестов passed,51 новый**. Искусственные примеры используют
  изменённые числа, диапазоны, концентрации, отношения и выдержку; покрыты RU/EN,
  перестановка layer/bulk, неверные числа/ссылки/массовая вместо объёмной основы,
  отрицания, cross-work join/неоднозначность, hypothetical/No source prefixes,
  missing-source отказ до OAuth, полный provider path и abstention. `M` строго
  отделяется от `m`, единицы/масштаб не конвертируются.
- Ruff8 Python файлов и полный mypy `app`187 файлов прошли; `git diff --check`
  без whitespace errors. Полная suite не запускалась.
- Final `review_v03`:162 frozen-channel service executions,81 прежний full trace
  baseline воспроизведён. Все76 старых full traces неизменны, новый контракт там
  не активен; это не проверка научной корректности активного пути. Q01/Q03/Q05
  сохранили полные traces и native bytes. Во всех пяти выбранные источники те же.
- Восемь final фактических offline ASGI сценариев: Q02/Q04 SYNTHETIC complete —
  HTTP200; abstention — HTTP200/insufficient_evidence; старые native outputs,
  поданные как COUNTERFACTUAL на новый контракт, — HTTP502 с fidelity reasons.
  То же подтверждено при обходе provider validator: service самостоятельно
  отклоняет эти строки. Старые реальные успешные API ответы не переклассифицированы.
- Две fresh-process read-only DB/native подготовки `fresh_v02` завершены с
  rollback, их полные traces/native bytes точно совпадают с offline prediction.
  В обеих source/gold/network diagnostics пусты. Max/1200/120s сохранены;
  **реальных model/OAuth/новых slots0**, новые native bodies не отправлены.
- Verifier:244 base-report bindings,33 PDF SHA,10 свежих reference pages/19 raw
  spans и10 source-fidelity anchors совпали. Исходный gold SHA и все прежние live
  manifests сохранены. Static HTML QA:5 sections/33 TAC works/8 columns/63
  существующих PDF ссылок. Browser execution не проверялся.

| Новый unsent request | Bytes | SHA256 |
| --- | ---: | --- |
| Q02 | 20799 | `f66d5d125143c24e1f0d080480bb809bc33c0a01642bd4f9ba69889e893b5611` |
| Q04 | 51844 | `3e20289d07da99bd8af2adf867f5d81de6d60064090c64f48743953a2afda0c4` |

Все неудачи сохранены. Первый control run:35 passed/1 failed из-за singleton
tuple в hold pattern; исправлен до baseline измерения. Первичный source-pattern
preflight на exposed excerpts выполнен до завершения controls; он не является
независимой оценкой. Далее v0.1 слишком широко трактовал `not` в source prefix:
`does not significantly influence` ошибочно блокировало сохранность кристаллов.
`review_v01` сохраняет тот runtime/8 channel-service executions/три unsent native
captures; fresh_v01 Q02 завершён, Q04 сохранил диагностический gate response,
capture driver завершился ошибкой до внешних границ. После отдельной
[поправки v0.2](records/answer_fidelity_amendment_2026-11-05_v0.2.md) позитивное
отрицание влияния имеет отдельный regression, прежние отрицательные controls
сохранены. Ни один старый manifest не переписан.

Initial affected run:348 passed/1 failed — исторический pre-retention baseline
Q04 приобрёл новую fidelity metadata. Только old-baseline context соответствующего
теста теперь изолирует более поздний fidelity layer; текущий branch тестируется
с ним. Старый тест и JUnit сохранены. Следующий reviewer завершил5-case этап,
восемь HTTP controls и первый old-case baseline/after (12 channel executions),
после чего упал на legacy `request` versus `api`. Исправлен только reader;
`review_v02` сохранён. Final `review_v03` прошёл полностью; все23 case/native/HTTP
JSON файла совпали с v02 побайтово. Таким образом, восемь HTTP controls также
выполнились в предыдущем незавершённом reviewer, без внешнего transport.
Starlette/httpx warning и первичные E501 замечания сохранены в tool outputs.

Limitations:

Это конечная проверка текстового покрытия и известных небезопасных формулировок,
**не общая semantic entailment/quantity ownership система**. Поля одной роли
ожидаются в одном claim с нужной ссылкой; правильная перефразировка, разбивка
условий между claims, другой научный формат числа, иной source язык или layout
могут привести к false refusal. Все поддержанные source patterns здесь английские,
answer patterns ограниченно RU/EN. Нераспознанный parser не должен описываться
как отсутствие научных данных. Полнота всех сведений статьи и все возможные
добавленные противоречия не проверены; например, контракт не устанавливает
автоматически все свойства слоя или универсальную причинность.

SYNTHETIC positives показывают работоспособность проверок, но не поведение
GigaChat на новом prompt. Старые референсы и cases уже exposed; независимая
научная приёмка/accuracy не назначена. В частности, корректные основные числа
Q03 в прежнем live не заменяют общую проверку владения величинами. Q01/Q05
по-прежнему выводят исходные английские цитаты. Увеличение native bytes не даёт
измерения стоимости/latency. Browser/PDF visual/full suite/cache-ORM/concurrency/
deployment остаются непроверенными. Никаких новых live slots/авторизации нет.

Verdict:

Офлайн-фикс реализован: прежние Q02/Q04 ошибки теперь дают явный отказ, полные
искусственные ответы проходят. Будущий ответ модели должен выполнить новые
требования, иначе пользователь получит отказ вместо неполного/искажённого текста.
Утверждать, что живые ответы уже стали лучше, до отдельного нового теста нельзя.
Независимая приёмка открыта, план остаётся75% работ; все live бюджеты закрыты.

[Итоговая таблица](../output/answer_fidelity_20261105/review_final_v01/review.html),
[verification](../output/answer_fidelity_20261105/review_final_v01/verification.json),
[предварительный протокол](records/answer_fidelity_protocol_2026-11-05_v0.1.md).
