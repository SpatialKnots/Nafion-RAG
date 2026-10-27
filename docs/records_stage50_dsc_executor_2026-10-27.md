# Records stage50: DSC executor and persistent one-attempt registry

27 октября 2026 года, Asia/Yekaterinburg.
`dsc_live_dispatch_v0.1`. Выполнен пункт 1 follow-up после аудита готовности к API.
[Протокол](records/dsc_live_executor_protocol_v0.1.md).

Changed:

- Добавлен отдельный `app.records.dsc_live.dispatch_frozen`. Он использует
  существующий fixed-endpoint transport и точные bytes captured stage49 после
  прежних source/code/runtime/byte/full-page проверок. Старые файлы и frozen
  hashes не менялись. Нет sending CLI, startup hook или production route.
- Отправка требует `api_calls_authorized=True` как явного подтверждения вызывающей
  стороной текущего разрешения пользователя. По умолчанию вызов запрещён; source
  admission не становится разрешением. Ключ передаётся явно, не извлекается из
  окружения. Пользовательский запрет API в этой работе не снимался.
- Общий registry закреплён за checkout:
  `data/experiments/dsc_live_attempts/<request_sha256>/`. Он не зависит от cwd или
  output и не имеет публичной настройки альтернативного пути. Атомарный mkdir
  выбирает один процесс, exclusive attempt file проходит flush/fsync до transport.
  До отправки также сохраняются точные request bytes и synced output attempt copy.
- После создания reservation directory нет refund или stale-lock cleanup.
  Timeout/HTTP error, прерывание, ошибка записи и пустая/повреждённая reservation
  сохраняют расход единственной попытки. Повторный output/export не сбрасывает
  бюджет. Retries/fallback отсутствуют.
- Минимальное transport recording сохраняет raw response либо error bytes,
  тип/stage ошибки, request ID и elapsed time; literal credential redacted в
  error body/message. Raw bytes сохраняются до parsing. Успешный transport имеет
  только `response_received_unvalidated`; interpretation не выполняется,
  model/usage/cost остаются unknown. Полный result recording из пункта 2 этим
  результатом не объявляется выполненным.

Tests run:

- Новый test file: **18 passed**. Final affected suite: **94 passed**, включая
  DSC live/experiment/admission/context и existing OpenAI backend. Прогоны
  пересекаются и не суммируются. JUnit:
  `output/dsc_live_affected_20261027_01.xml`.
- Проверены отсутствие разрешения/ключа, durable reservation до callback,
  точные request bytes, copied frozen export, 4 competing threads с единственным
  transport callback, 4 независимых процесса с единственной reservation,
  повторный процесс, timeout/URL/HTTP errors, отсутствие retries, credential
  redaction, storage failures до/после transport, KeyboardInterrupt, source drift,
  output protection, malformed reservation и привязка registry к code path.
  Transport mock; credentials, ответы и ошибки — constructed fixtures.
- Ruff `app tests scripts`: passed. Mypy `app`: **177 source files**, no issues.
- Existing stage49 export воспроизведён в
  `output/dsc_live_parent_replay_20261027_01`: **20/20 файлов byte-identical**.
  Request остаётся 8712 bytes, одна будущая попытка, retries/fallback 0.
- Offline replay network evidence: completed=true,
  blocked_socket_or_dns_attempts=[]; `model_calls=0`, `network_ready=false`.
  Guard охватывает CPython audit events, не является OS firewall.
- Реального `data/experiments/dsc_live_attempts` после проверок нет: production
  slot не резервировался. Все тестовые registries изолированы во временных папках.
  Исходный untracked `data/terms_pipeline_config.json` не изменялся этой работой.

Limitations:

- API/model/provider calls не выполнялись. Нет реального ответа, usage, pricing,
  provider compatibility или научной приёмки. Полный application suite не запускался.
- Это registry одного checkout на локальном filesystem, не distributed lock или
  provider idempotency. Удаление/rollback registry, отдельная копия репозитория,
  повреждение filesystem и восстановление старого backup выходят за гарантии.
  Сохранять registry при переносе/recovery. Hard power-loss и network shares
  экспериментально не проверялись; fsync зависит от OS/filesystem.
- Неожиданное прерывание может оставить только reservation с неизвестной
  доставкой. Это явное fail-closed состояние; повторный вызов запрещён.
- Полный live result/manifest/returned-model/usage parsing из пункта 2,
  финальный preflight и разрешение фактической отправки остаются отдельно.

Verdict: пункт 1 выполнен и проверен offline. Executor и общий журнал готовы как
отдельный компонент; реальный API-тест не запускался и не разрешён этой работой.
