# Current GigaChat /answer smoke protocol v0.1

29 October 2026, Asia/Yekaterinburg. The user authorized execution of the
previously proposed new frozen test of the current `/answer` path, including one
GigaChat model request. This authorization does not reopen either old DSC slot.

## Scope and budget

Use the actual in-process ASGI POST `/answer`, current `Settings`, production
retrieval, evidence selection, adequacy gate, GigaChat factory/adapter, response
parser and citation validation. Freeze this exposed development question before
the outcome: «Каким методом измеряли проводимость мембран и как выполняли
уравновешивание образцов перед измерением?» Use the configured collection,
retrieval method and top-k; answer style `claims`, language `auto`.

Maximum: one model POST, one OAuth exchange, no automatic retry, fallback,
purchase or scope upgrade. Require `GIGACHAT_API_PERS`, `GigaChat-2-Max`, current
1200 output-token ceiling and 120-second timeout per HTTP request. These are
token/time limits, not a verified monetary cap. No models/balance API reads.

Use a PostgreSQL repeatable-read, read-only transaction for each preparation
and live request. Embedding inference uses the existing local cache, with model
downloads disabled. No ingestion, PDF, DB, index or runtime-default changes.

## Freeze and transport observation

Preparation stops at the production transport boundary with an explicit local
exception. Its OAuth token is a local placeholder; no OAuth success is claimed.
Save the exact native JSON body serialized by the current adapter, ranked
retrieval, final evidence, metadata, source pages/layers/PDF hashes and article
metadata. Freeze code, cache and index file hashes and a separate output manifest.

Live retrieval, evidence, source registry and exact model request bytes must match
preparation. Input/code/source drift blocks dispatch. Atomically reserve a
checkout-wide append-only slot by request SHA256 before OAuth. A failed or
interrupted attempt consumes the slot; a new output path does not reset it.

Instrument the actual factory-created provider's `_post` only to capture request,
response and timing. Use its original HTTPS transport, TLS, proxy/redirect policy
and native parsing. Save response bytes durably before the production parser.
Do not persist OAuth bodies, credentials or tokens. Redaction, if needed, must be
explicit and block integrity acceptance. The adapter does not expose response
headers; absent header request IDs remain unknown.

## Evaluation and limits

Record native HTTP status/body from the ASGI route, returned model declaration,
usage, transport time, errors, final claims and citation IDs. Gate rejection is
not a provider abstention. Transport/schema/citation failures remain failures;
do not repair the answer or change the prompt after seeing it. Offline replay
of captured bytes may verify determinism without another network call.

This tests the existing raw-chunk runtime. Complete-page occurrences, normalized
whitespace, bibliographic noise and adequacy limitations must be shown explicitly.
The older compact-packet no-complete-page admission policy is not an acceptance
claim for this raw runtime test; no compact candidate is substituted into it.
Source-ID validity does not establish claim entailment. Scientific acceptance
and independent accuracy remain `not_evaluated`. Record assistant source review
separately as exposed-case diagnostics, with exact supporting text and caveats.

Deliver a separate searchable HTML review with expandable full request, response,
evidence, diagnostics and links to original PDFs. Include all selected articles
in a TAC table: Title, Authors, Journal, Year, Abstract, Conclusions, Terms, original
file link. Preserve recorded metadata and explicitly mark uncollected or
unimplemented fields. No XLSX and no compulsory user classification.

Context-compression instrumentation remains deferred; existing byte-size evidence
for this one frozen request is not a new general compression feature.

## Prospective infrastructure continuation after the sandbox failure

The first dispatch (`live_v01`) returned HTTP 503 at OAuth, before any model
request: model attempts 0, OAuth attempts 1. A separate credential-free socket
probe established sandbox `WinError 10013`; the same verified-TLS probe outside
the sandbox succeeded. Preserve that result and its slot. The original one-OAuth
attempt budget ended with that failure; do not relabel it as successful.

Before further dispatch, freeze fresh code and input bindings plus the failed
result/manifest. Permit exactly one separately recorded infrastructure continuation
outside the sandbox, with the same native model request bytes and one new OAuth
exchange. This continues the user's authorized total budget of one model request;
it does not authorize a second model request. Record two OAuth attempts across
both runs, one failed in the sandbox, and distinguish this continuation from
automatic transport retries (zero within either run).

Require the old output manifest, request identity and ledger result to agree,
old model attempts = 0 and the exact recorded OAuth/URLError HTTP 503 diagnostic.
Reserve one immutable child slot `infrastructure_recovery_v01` under the original
request slot. Never delete/reset the original slot. An existing child blocks
another continuation, even if the child failed or was interrupted. Any earlier
model attempt forbids this continuation. All original runtime/source/parser rules
remain in force; no prompt tuning or answer repair is allowed.

## Prospective infrastructure continuation after the sandbox failure

The first dispatch (`live_v01`) returned HTTP 503 at OAuth, before any model
request: model attempts 0, OAuth attempts 1. A separate credential-free socket
probe established sandbox `WinError 10013`; the same verified-TLS probe outside
the sandbox succeeded. Preserve that result and its slot. The original one-OAuth
attempt budget ended with that failure; do not relabel it as successful.

Before further dispatch, freeze fresh code and input bindings plus the failed
result/manifest. Permit exactly one separately recorded infrastructure continuation
outside the sandbox, with the same native model request bytes and one new OAuth
exchange. This continues the user's authorized total budget of one model request;
it does not authorize a second model request. Record two OAuth attempts across
both runs, one failed in the sandbox, and distinguish this continuation from
automatic transport retries (zero within either run).

Require the old output manifest, request identity and ledger result to agree,
old model attempts = 0 and the exact recorded OAuth/URLError HTTP 503 diagnostic.
Reserve one immutable child slot `infrastructure_recovery_v01` under the original
request slot. Never delete/reset the original slot. An existing child blocks
another continuation, even if the child failed or was interrupted. Any earlier
model attempt forbids this continuation. All original runtime/source/parser rules
remain in force; no prompt tuning or answer repair is allowed.
