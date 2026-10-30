# GigaChat DSC smoke protocol v0.1

Frozen prospectively on 28 October 2026 (Asia/Yekaterinburg), before model outcomes.
The user requested trying GigaChat and supplied local credentials after being
instructed to verify Freemium. This authorizes this bounded GigaChat experiment;
it does not authorize OpenAI dispatch or a provider change in production.

## Inputs and request

- Parent: `output/records_stage49_20261027/run_v01`. Reconstruct its unchanged
  source admission, source/code/runtime bindings and full-page/byte guards.
- Same exact question, B1–B4 identity anchors, complete M1 methods span, system
  prompt, six DSC topics and Pydantic Reply schema. Do not clip or repair sources.
- Separate frozen request: `GigaChat-2-Max`, `/v1/chat/completions`, non-streaming,
  `max_tokens=4096`, timeout 180 seconds; `response_format` uses GigaChat's
  `type=json_schema`, `schema`, `strict=true` syntax. Provider-default sampling.
  OpenAI reasoning/store/truncation/service-tier fields are not claimed equivalent.
- No alternate model, retry, fallback, schema repair, changed prompt or regenerated
  answer within this experiment. Provider schema compatibility is unverified until
  the actual response. Errors remain outcomes, not successful abstentions.

## Authorization and transport

Load only `GIGACHAT_CREDENTIALS`, `GIGACHAT_SCOPE`, and optionally
`GIGACHAT_CA_BUNDLE_FILE` from environment or the checkout `.env`. The Scope must
be `GIGACHAT_API_PERS`. Never persist the OAuth response or access token. Use
verified TLS (system trust plus optional application CA), fixed official endpoints,
no proxy, redirects or automatic retries. No dependencies need installation.

One OAuth exchange, then GET models and GET balance. Require the exact model in
the returned list and a positive explicit Max package balance before generation.
The legacy documented aliases `GigaChat-Max` and `GigaChat-2-Max` identify the
accepted Max balance entries. Unknown balance shapes, access errors or missing
models block generation, with no automatic fallback. Balance is not independent
confirmation of tariff, monetary cost, or sufficient tokens for this request.
No token purchase, billing upgrade or pay-as-you-go Scope is performed.

Reserve one model attempt using exclusive mkdir under the checkout-bound
`data/experiments/gigachat_dsc_attempts/<request_sha256>/`, flush/fsync attempt
evidence before sending. Errors/timeouts/interruption after reservation do not
refund it. Read-only/auth failures before reservation do not consume a model slot;
they are recorded in separate exclusive outputs. Local file copies or changing
the output directory do not reset the model budget. This is not a distributed
lock or provider-side idempotency guarantee; preserve the registry during recovery.

## Artifacts and evaluation

Exclusive output directories contain exact request/contract, account responses,
raw model response or error before parsing, observed model/usage/request ID,
typed staged errors, elapsed time, source-resolved proposals when valid, hashes,
and escaped HTML review. Authentication error bodies are intentionally not saved
because they may carry tokens. Literal credential echoes are redacted with
acceptance blocked if that changes a model response. Monetary cost stays unknown.

Require a single `finish_reason=stop` assistant text choice. Reject function
calls, incomplete/refused/malformed responses, duplicate JSON keys and nonfinite
JSON. Preserve raw GigaChat bytes; an explicitly derived in-memory adapter
envelope calls the unchanged DSC validator. It is not a provider Responses reply.
Every present field must use a unique exact M1 quote with preserved PDF/page/layer
and offsets. Preserve unsupported/ambiguous fields. Check all six topics and
consistent complete/partial/abstention outcome. Recheck source/code bindings and
stored request/response after transport. HTML links the separately copied complete
historical TAC review (all parent documents), without changing its metadata.

Integrity is not scientific entailment or independent accuracy. This is one
exposed development question, not a benchmark or production integration. Original
PDFs, DB, retrieval, embeddings, OCR, Terms and previous artifacts remain unchanged.

## Official documentation consulted

- https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/gigachat-api
- https://developers.sber.ru/docs/ru/gigachat/guides/structured-output
- https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/get-balance
- https://developers.sber.ru/docs/ru/gigachat/certificates
- https://developers.sber.ru/docs/ru/gigachat/tariffs/individual-tariffs

## Verification before live sending

Run offline tests for request/source preservation, source drift, wrong Scope or
missing key/permission, incomplete/invalid/foreign citations, full/partial/refused
outcomes, secrets/HTTP/TLS failures, registry persistence and output integrity.
Transport callbacks are constructed fixtures, not real provider responses.
Run affected DSC tests and Ruff/mypy. Freeze a new prepared directory after checks;
never change prepared files to bypass stale bindings.
