# Records stage51: полная запись результата DSC dispatch

27 октября 2026 года, Asia/Yekaterinburg.
`dsc_live_dispatch_v0.2`, `dsc_live_result_v0.1`.
Выполнен пункт 2 follow-up после аудита готовности к API.
[Протокол](records/dsc_live_result_protocol_v0.1.md),
[executor stage50](records_stage50_dsc_executor_2026-10-27.md).

Changed:

- `dispatch_frozen` подключён к локальной записи/проверке результата после
  сохранения raw bytes и двух transport receipt copies. Return value остаётся
  transport receipt; полная интерпретация записывается в отдельный `result.json`.
  Успешный transport snapshot по-прежнему означает только
  `response_received_unvalidated`, а не научно принятый ответ.
- До резервирования копируется точный frozen `contract.json`. Сохраняются
  request, attempt, raw response/error, transport, response metadata, result и
  manifest. Schema-valid `reply.json` не равен source-valid результату;
  `resolved.json` появляется только после source/artifact checks.
- Native response ID, returned model declaration, usage со вложенными counters,
  service tier, status, provider error и incomplete details сохраняются как
  наблюдаемые значения. Header request ID отделён от response ID. Метаданные
  сохраняются и при невалидном/неполном ответе или JSON HTTP error body.
  Missing значения остаются null с диагностикой; нулевой usage не теряется.
- Raw bytes проходят exclusive write, flush/fsync до parsing. Сохраняются
  доступные partial bytes от IncompleteRead. Echoed literal credentials
  редактируются с явным flag и observed/stored hashes; изменённый body не
  получает source-valid acceptance. Стоимость не вычисляется: actual_cost_usd=null.
- Ошибки разделены по metadata JSON/completion/reply schema/source/artifact
  integrity/credential redaction. Transport/schema/source failure не становится
  successful abstention. На ошибках outcome/evaluation=null. Полные/частичные
  предложения и abstention допустимы только после прежних frozen проверок;
  scientific_acceptance остаётся not_evaluated.
- После проверки повторно сверяются сохранённые bytes, request/contract,
  reservation/receipt copies, source/input bindings и executor code hash.
  Обнаруженный drift блокирует acceptance без repair. Все исходные ключи result
  template сохранены; versioned additions явно описаны в новом протоколе.
- Manifest хеширует все output files, кроме самого себя. Result и manifest
  зеркалируются в registry до последней записи output manifest. Отсутствие
  manifest означает незавершённую запись. Ошибка записи распространяется явно;
  резервирование единственной попытки не отменяется.

Tests run:

- Первый новый suite: **23 passed**. После добавления совместимости с result
  template, nonfinite JSON rejection и partial HTTP retention — финальный
  affected suite **119 passed**, failures=0/errors=0. В JUnit подтверждены
  **25 cases** нового `test_dsc_live_result.py`; это часть 119, не отдельная
  дополнительная сумма. Артефакт: `output/dsc_result_affected_20261027_01.xml`.
- Проверены complete/partial/abstention, actual returned alias distinction,
  nested/unknown/zero/missing usage, request ID vs response ID, все artifact
  hashes и registry mirrors; raw-before-inspection ordering, malformed/non-UTF8/
  duplicate/nonfinite JSON, incomplete envelope, provider refusal, invalid schema,
  foreign/invented citations, HTTP JSON errors, credential redaction, partial
  HTTP bytes, post-transport source/raw/request drift и recording write failures.
- Прежние 18 executor cases и затронутые DSC experiment/admission/context/native
  backend tests вошли в 119. Transport mocks и constructed credentials/ответы;
  реальный provider run этим не заявляется.
- Ruff `app tests scripts`: passed. Mypy `app`: **177 source files**, no issues.
- Captured stage49 воспроизведён в
  `output/dsc_result_parent_replay_20261027_01`: **20/20 файлов byte-identical**.
  Request остаётся 8712 bytes; source packet, schema/model/settings/budget и
  прежние scientific guards не менялись. Старые experiment outputs не дополнялись
  synthetic ответами.
- Replay network evidence: completed=true,
  blocked_socket_or_dns_attempts=[]; model_calls=0, network_ready=false.
  Это CPython audit guard, не OS firewall. Реального
  `data/experiments/dsc_live_attempts` после проверок нет; production slot не
  резервировался. Исходный `data/terms_pipeline_config.json` этой работой не менялся.

Limitations:

- Реальных API/model/provider calls, ответа, usage, цены или provider compatibility
  verification нет. Полный application suite не запускался.
- Source/schema integrity не доказывает научную entailment/accuracy; independent
  gold отсутствует. Даже valid abstention не доказывает отсутствия сведений в статье.
- Transport receipt — отдельный исторический snapshot. Его null model/usage не
  заменяются задним числом; наблюдаемые поля находятся в metadata/result.
- Неожиданное прерывание или storage failure может оставить неполную запись
  без manifest. Reservation сохраняется; автоматического resend/recovery нет.
  Сохраняются ограничения registry одного checkout, удаления/rollback и
  непроверенного hard power-loss/network filesystem из stage50.
- Следующий шаг — оставшийся финальный preflight и отдельное разрешение реальной
  API-попытки. Новых sending CLI/production route не добавлено; запрет API активен.

Verdict: пункт 2 выполнен и проверен offline. Полный result recording подключён к
executor; реальный API-тест не запускался, единственная попытка не израсходована.
