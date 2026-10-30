# ARIADNE: три пользовательских вопроса — замороженная подготовка

30 октября 2026, Asia/Yekaterinburg. Продолжение пункта 4 плана качества
ответов. Пользователь предоставил три вопроса после сообщения о подготовке
новых вопросов. Все тексты, включая «пре переходе», сохранены дословно в
`docs/records/user_questions_2026-10-30_v0.1.json`.

Changed:

- Добавлен отдельный runner `scripts/user_questions_20261030.py`, который
  использует текущий настоящий ASGI `/answer`, read-only БД, локальные embeddings/
  index и остановку на provider transport boundary. Settings остаются
  GigaChat-2-Max / literature / hybrid_cross_lingual / top-k 5 / claims / auto,
  max_tokens 1200 / timeout 120 s per HTTP. Нет нового текста модели или
  фиктивных научных ответов.
- Для каждого вопроса использован отдельный свежий процесс. Прежняя проблема
  cache/ORM длительно работающего процесса не исправлена и этой изоляцией не
  считается проверенной.
- Сохранены actual retrieval/evidence/source/metadata traces, точные native
  request bytes/hash, public API request и gate result, code/PDF/index/cache
  bindings. Preparation contracts явно разрешают **0** live attempts и
  reservations. Вызовы OAuth/model — **0**.
- Вопросы имеют пользовательское происхождение, но не являются независимо
  размеченным gold. Темы H/Li swelling и максимума проводимости смесей уже
  представлены в прежних regression/cross-lingual datasets; отдельные источники
  методик тоже экспонированы. Сверены 148 прежних query records. Exact wording
  matches и тематическое пересечение учитываются отдельно; новая формулировка
  не объявляется доказательством unseen-source independence.
- Критерии вопроса записаны до новых прогонов: paired H/Li values при сопоставимых
  средах/условиях; смесь с composition/basis/σ/unit/temperature и явным comparison
  set; раздельные протоколы литирования, без переноса очистки/протонирования в
  lithium exchange. Это prospective requirements, не ожидаемые численные ответы.
  Independent reference answers/annotations пока не представлены.

Фактический результат подготовки:

| Вопрос | Результат текущей системы | Native request |
| --- | --- | --- |
| Изменение набухания H → Li | Provider boundary достигнута, request не отправлен | 55341 bytes; SHA 05786a7433a756f0a0aab5d930eaf746523995d85f7d9c8ad38ce5d18da5f8e4 |
| Лучшая смесь для ионной проводимости Li-Nafion | Provider boundary достигнута, request не отправлен | 40073 bytes; SHA 4cc40b85628d9e94ef3015e914a1d62fb619c1f635a194a1fde54e9fcc8e4137 |
| Методики литирования Nafion | **HTTP 200 / insufficient_evidence**, до provider | request отсутствует, 0 bytes |

В третьем случае `evidence_adequacy.reason=insufficient_distinctive_term_coverage`:
matched только `nafion`, coverage/top_coverage=0.25; distinctive terms —
`существуют`, `методики`, `литирования`, `nafion`. Это результат текущего gate,
не доказательство отсутствия методик в корпусе.

**Отдельный assistant preflight source hint:** выбранный E1 диссертации охватывает
с.49–51 и содержит описание литирования ионным обменом в водном LiOH, с явными
параметрами стадии. Две exact page anchors source hints совпали с извлечённым
текстом. Это показывает, что буквальное coverage и наличие релевантного текста
различаются; не является независимым ответом на вопрос о всех методиках.
Gate/status/trace сохранены без исправления, переписывания вопроса или обхода
порогов. Третий вопрос не включён в предлагаемый live dispatch.

Raw-chunk prompts первых двух вопросов содержат полные source pages; это
раскрыто в review. Они не получили compact-packet/scientific admission.
Размер каждого ниже отдельно объявленного experiment ceiling 100000 bytes;
контексты не обрезались и лимит ради успеха не повышался.

Дальнейший конкретный live scope подготовлен, **но пока не разрешён**:

- Только q1_swelling_forms и q2_best_mixture, не более одного model POST и одного
  OAuth exchange на вопрос: максимум **2 + 2**, без retry/fallback.
- Тот же frozen native input/model/limits и новая отдельная append-only
  authorization/dispatch запись после явного разрешения пользователя.
- Driver `scripts/run_user_questions_20261030_live.py` проверяет report/prepared
  hashes, точные eligible IDs и глобальный SHA slot; повторный dispatch запрещён.
  Blocked q3 и неизвестные worker outcomes не превращаются в нулевые попытки
  или разрешение продолжить. Неизвестный outcome останавливает batch.
- Предыдущие zero-authorization preparation contracts и все старые закрытые
  budgets/slots не переписываются. Ожидаемая денежная стоимость не измерена;
  token/output/HTTP limits указаны, новых usage ещё нет.

Tests run:

- **105 tests passed**, JUnit `output/user_questions_preflight_20261030_v02.xml`:
  12 новых preparation/authorization/isolation controls и прежние smoke/provider
  controls. Проверены verbatim questions, отсутствие вымышленного gold,
  восстановление helper scope после ошибки, gate/oversize блокировки, нулевая
  preparation authorization, отказ до чтения файлов без live approval,
  запрет третьего вопроса, fresh workers, no repeat, сохранение unknown outcome
  и redaction diagnostic secrets. Все transport outcomes в tests — fake.
- Более ранний узкий прогон: 5 passed; входит в 105 и не суммируется.
- Ruff пяти новых runner/test files и отдельного QA script passed.
  `git diff --check` passed с существующими LF/CRLF warnings. Нового mypy/full-suite
  success не заявляется; product app code в этой итерации не менялся.
- Три read-only ASGI preparations вне sandbox завершились. Проверены hashes
  оригиналов и **23 уникальные страницы / 5 works** со свежим PDF text extraction.
  Review/QA работают без DB/provider/network. Зафиксированные request SHAs пока
  отсутствуют в global live ledger, `live_dispatch.json` отсутствует.
- Static HTML QA: три вопроса дословно, **5 TAC rows**, восемь agreed columns,
  **18** существующих file links, search markup/handler, полные exact source
  fragments. Missing metadata/Abstract/Conclusions/Terms явно сохранены.
  Browser rendering и исполнение поиска этого отчёта не проверены.
- Initial sandbox preparation первого вопроса зависла в ASGI TestClient:
  сохранился только api_request.json. PID 20232/1832 идентифицированы вне sandbox
  и остановлены; точная причина не установлена. `preparation_v01` сохранён,
  успешные fresh processes — `preparation_v02`. Реальных provider calls в обоих
  вариантах нет. Прежняя Starlette/httpx deprecation warning остаётся видимой.
- Исправлены initial reviewer import-spacing/driver line-length lint diagnostics.
  До успешных preparations сверено и исправлено имя historical query ID в
  notes; сами пользовательские вопросы не менялись. Summaries ошибок находятся
  отдельно и не выдаются за полные raw terminal logs.

Артефакты:

- [Финальный review подготовки](../output/user_questions_20261030/review_v02/review.html).
- `output/user_questions_20261030/preparation_v02/<case>/prepared/`: точные
  контракты, bytes/trace/source/gate results. `review_v01` сохранён.
- `review_v02/report.json` и `source_snapshot/`: все три случая, eligibility,
  source hints, исходный код и input/output hashes.
- `qa_v01.py/json`, `development_failures.json`: QA и summaries.
- Протокол подготовки и будущего ограниченного scope — отдельные файлы в
  `docs/records/`; ни один из них сам по себе не является разрешением live calls.

Limitations:

**Новых ответов GigaChat ещё нет.** Ни success rate, ни scientific accuracy,
ни полнота methodological/mixture coverage не измерены. Релевантный LiOH-фрагмент
не исправляет software rejection и не заменяет независимый эталон всех методик.
Темы/источники уже частично знакомы системе/ассистенту; пользовательские вопросы
не объявляются независимой source annotation. Источники/прежние budgets сохранены.

Verdict:

Три вопроса зафиксированы и проведены до границы текущего runtime допуска.
Два готовы только к отдельно разрешённым новым вызовам; третий завершился
исходным отказом gate. **Прогресс четырёхпунктного плана остаётся 75% (3/4)**:
пункт 4 начат, но научная оценка и новые model results ещё не выполнены.
