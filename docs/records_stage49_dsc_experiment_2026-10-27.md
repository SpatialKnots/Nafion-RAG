# Records stage49: frozen-контракт DSC-эксперимента

27 октября 2026 года, Asia/Yekaterinburg. `dsc_frozen_experiment_v0.1`.
[Протокол](records/dsc_experiment_protocol_v0.1.md),
[source admission stage48](records_stage48_dsc_admission_2026-10-27.md).

Changed:

- Выполнен **пункт 3** pre-API плана: локально зафиксированы исходный вопрос,
  неизменённый source packet, system prompt, полный Responses request, reply
  schema, параметры модели, operational budget, критерии проверки и result format.
  Настоящий запрос не отправлялся; credentials не запрашивались.
- Новый native envelope построен по существующим локальным Responses conventions.
  Model alias `gpt-6-astra`, reasoning `medium`, max_output_tokens **4096**,
  timeout **180 s** взяты из прежнего protocol-association development backend.
  Это исторические настройки репозитория, не подтверждение текущей доступности,
  поддержки новой схемы, конкретного model snapshot или стоимости у провайдера.
- Бюджет нового будущего эксперимента: **одна transport attempt**, retries **0**,
  fallback models **0**. Slot должен резервироваться до transport и оставаться
  израсходованным после timeout/error. Ledger scope — request SHA256 между output
  directories, чтобы копия папки не сбрасывала budget. Live executor/ledger здесь
  не реализован; это обязательство контракта следующего пункта.
- Сохранены store=false, stream=false, truncation=disabled, default service tier.
  Existing ceiling 100000 bytes проверен для всего provider envelope, а не только
  source wire. Input-token estimate и monetary cap/price estimate не выдуманы:
  соответствующие значения unknown/null. Ограничение request/output counts не
  объявляется долларовым лимитом.

## Замороженный запрос

Фактический request — **8712 UTF-8 bytes**. SHA256:
`2487a45c01426b2b174ec2dcbf93d912058545c8e8d578b4011cf87f8e7d6093`.
Исходный wire остаётся **4346 bytes**, SHA256:
`11a3dd6570f293260c3be339b5e3e5f80b45b4cfbfb20fe5a11e7549a7822f57`.
Contract SHA256, записанный в result template:
`a13dd76aa7afe86c001e9e6e95177b70070f90c21647d33b21da8a337784d0df`.

Request содержит system prompt, ровно исходный wire и strict JSON reply schema.
В prompt отделены B1–B4 identity contexts от M1 methods evidence. Context quotes,
Unicode signs/units/newlines и полный source scope не изменены. Local paths и
полная source-page registry остаются локальными. Повторно проверены source
admission, точная реконструкция stage47/48, source/full-section/interval-union
guards, literal/decoded complete-page guards и размер полного envelope.
Это локальная проверка request contract, не server-side validation.

## Ответ и критерии

Модель должна учесть шесть topics ровно по одному разу: instrument, sample_handling,
measurement_environment, flow_rate, temperature_range, temperature_programme.
Каждый field — present/not_found_in_context/ambiguous/unsupported с diagnostic.
Present fields ссылаются на уникальные точные M1 quotes; bibliography и чужие
citation IDs не подставляют условия измерения. Non-present fields не утверждают
values/evidence. Answer/partial/abstention proposal должны соответствовать числу
present fields; отказ не превращается в источник отсутствия данных.

Автоматически проверяются completed single-message envelope, JSON schema,
уникальность/полнота topics, consistent abstention, M1 citation role, уникальные
exact source substrings и восстановление absolute page/layer/PDF offsets.
Числа/units не преобразуются; sample-specific методика не назначается. Free
diagnostics и принадлежность выбранной цитаты конкретному topic остаются
непроверенными научными предложениями. Structural/source integrity и coverage
proposals **не являются** научной entailment/accuracy оценкой. Независимого gold нет.

## Результаты, raw data и ошибки

`result_template.json` явно **not_executed**: transport_attempts=0, delivery
not_attempted; request_id, returned_model, usage, response hash, elapsed time и
actual_cost неизвестны/null. Реальных или synthetic response/reply/resolved files
в артефакте этого эксперимента нет.

Контракт определяет будущие request/attempt/raw response-or-error/metadata/result/
manifest artifacts, сохранение raw bytes до parsing, provider request ID и actual
returned model/usage/service tier/elapsed time. Ошибки сохраняются с типом и stage,
credentials в error evidence должны редактироваться. Missing usage остаётся unknown.
Нельзя превращать transport/schema/source failure в успешную abstention или
неявно повторять вызов. Исполнение этих transport-правил относится к пункту 4.

Реализован отдельный `inspect-response` для **предоставленных offline response
files**. Он не отправляет запрос и не расходует/сбрасывает будущий call budget.
Origin — offline_supplied_response; original transport attempts неизвестны,
model_calls_by_this_tool=0. Exact raw bytes сохраняются прежде parsing, включая
non-UTF8 failures; actual observed envelope metadata/usage остаются verbatim.
Схема/цитаты с ошибкой дают offline_response_invalid с явным error, а не abstention.
Этот режим проверен на constructed fixtures; provider run этим не заявляется.

## Tests run

- Новый test file: **24 passed**. Финальный affected suite по experiment,
  admission и существующему native OpenAI backend: **57 passed**;
  `output/commit_check_20261026/dsc_experiment_v02.xml`. Прогоны пересекаются,
  не складываются. Native transport tests используют mocks, не настоящий API.
- Проверены model/prompt/source/schema/settings drift, actual envelope byte
  ceiling, complete/partial/abstention, missing/duplicate topics, inconsistent
  outcomes, non-present evidence, чужие/bibliographic citation IDs, invented/
  ambiguous/duplicate/whitespace quotes, duplicate JSON keys и incomplete native
  envelopes. Source offsets, observed usage, raw non-UTF8 error bytes, overwrite,
  frozen-directory protection, contract/budget drift и HTML escaping проверены.
- Ruff `app tests scripts`: passed. Mypy `app`: **176 source files**, no issues.
  Две начальные typing diagnostics исправлены до final prepare; научные правила
  или outcomes для этого не менялись.
- Postflight: **1407 bindings**, **1377 unchanged parent bindings**, пять source
  regions, шесть reply topics, exact request/schema/system prompt/template hashes.
  Все **11 admission files** byte-identical; два экспорта — **20/20 одинаковых файлов**.
- Prepare/run/два exports: четыре network-evidence files, completed=true,
  connect/DNS/sendto attempts отсутствуют; postflight также запрещает их.
  Это CPython audit guard, не OS/native-network firewall.
- Chrome 156 offline: четыре contract sections, budget/model, полный request и
  schema, unexecuted template, search/reset и все links прошли. В сохранённом
  packet — пять contexts, TAC один документ / восемь колонок. PDF click открыл
  physical page 4. JS errors и remote HTTP requests отсутствуют. Budget/request/
  template screenshots просмотрены.

## Артефакты

`output/records_stage49_20261027/`: `prepared_v01`, `run_v01`, `review_v01`,
`review_repeat_v01`, browser/postflight/network evidence и screenshots.
В final review: contract.json, request.json, reply_schema.json, system_prompt.txt,
result_template.json, report.json и manifest.json. `admission/` хранит неизменённый
stage48 и вложенный stage47 packet/TAC с явными unimplemented fields. Старые
вопросы, PDFs, source metadata, Terms workflow, runtime/provider/defaults не менялись.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.dsc_experiment --network-evidence output/stage49_new_network.json export --source output/records_stage49_20261027/run_v01 --output-dir output/stage49_new_review
```

Использовать новые output/evidence paths. Code/source/runtime drift останавливает
replay; installed direct-dependency snapshot не является portable/transitive lockfile.
Private PDF и generated artifacts в Git не входят.

Limitations: нет live provider/model/schema/pricing verification, реального usage,
ответа модели, независимой научной оценки, полного application suite, sending
executor или durable live-attempt ledger. API/model/retrieval/embedding/DB calls
не выполнялись. Schema/source-valid proposal не означает научную корректность.

Verdict: пункт 3 выполнен offline. Contract ready; network_ready=false. Пункт 4 —
отдельный bounded live smoke с этим точным запросом и durable attempt/result
recording после явного снятия пользовательского запрета API.
