# DSC dispatch result recording v0.1

27 October 2026. Implements item 2 of the API-readiness follow-up, building on
the [one-attempt executor](dsc_live_executor_protocol_v0.1.md). It does not grant
permission to send a provider request; the existing user API prohibition remains.

## Integration and versions

`dispatch_frozen` now invokes a private result recorder after saving raw bytes
and the immutable transport receipts. The dispatch version becomes
`dsc_live_dispatch_v0.2`; the new result/manifest version is
`dsc_live_result_v0.1`. Its return value remains the transport receipt. The full
interpretation is stored separately in `result.json`; a successful transport
receipt still means only `response_received_unvalidated` at that earlier stage.
There is no new sending CLI, route, retry, fallback or attempt-reset operation.

Captured stage49, its validator, source admission, request bytes, response schema,
method/sample semantics and scientific thresholds remain unchanged. Before
reserving the attempt the executor also saves the exact frozen `contract.json`.
The attempt records its own executor code hash and all validated source bindings.

## Bytes, observed metadata and errors

Raw response/error bytes are saved with exclusive writes, flush and fsync before
JSON, completion, reply-schema or source interpretation. The v0.2 receipt adds
the observed response hash, stored-byte policy and a credential-redaction flag.
Ordinary responses are byte-exact. Literal supplied credentials are redacted
if echoed in a response/error body; this transformation is explicit, with both
observed and stored hashes recorded. A transformed body cannot become an
accepted source-valid result. HTTP/URL/timeout error messages are also redacted.
No credential value is added to attempt records.

`response_metadata.json` retains observed envelope values for response ID, actual
returned model declaration, usage (including nested and unknown counters), service
tier, response status, provider error and incomplete details. Header request ID
is retained separately; it is not inferred from the response ID. Metadata is
retained even when completion/schema/source validation fails, or when a JSON HTTP
error body contains it. Missing values stay null with missing-field diagnostics;
observed zero counters are preserved. Returned metadata is evidence of the
provider's declaration, not independent model-identity or billing verification.
No token estimate, price or monetary cap is invented; actual_cost_usd stays null.

Expected response failures are recorded with exception type, stage and explicit
error text. Stages distinguish metadata JSON, native completion, reply schema,
source integrity, post-transport artifact integrity and credential redaction.
Available partial bytes from IncompleteRead are retained. Non-finite numeric JSON
constants in metadata are rejected without altering the frozen parser.
Transport errors remain transport errors, even when their bodies resemble valid
replies. Incomplete native responses and provider refusals cannot become successful
scientific abstentions. Output write failures and unexpected exceptions propagate;
expected artifact-read failures are recorded as artifact-integrity errors. The
consumed reservation remains and no automatic retry is possible.

## Replies and interpretation

The existing frozen parser enforces complete six-topic accounting, consistent
answer/partial/abstention proposals and exact unique M1 citations. Its resolver
restores registered region/article/PDF/page/layer identities and absolute offsets.
`reply.json` is saved only after reply-schema validation; it may still be an
unsupported source proposal. `resolved.json` is saved only after source and
artifact checks, without credential transformation. Free diagnostic text and
topic entailment remain scientifically unreviewed.

`result.json` distinguishes `integrity_valid`, `response_invalid`,
`transport_error` and `artifact_integrity_error`. Outcome/evaluation are null on
failure; only a fully valid proposal may carry answer_proposal, partial_proposal
or abstention. A valid abstention is not proof that the article lacks information.
Scientific acceptance is always not_evaluated; there is no independent gold or
accuracy claim. Transport elapsed time and local recording time have separate
explicit scopes.

All original result-template keys remain represented; the new version adds
checks, observed/stored hashes, scoped timing and the complete errors list. The
singular error field contains the first recorded error. response_sha256 is null
for a transport failure; response_or_error_sha256 always identifies saved bytes.

## Integrity and completion

After interpretation, verify saved raw bytes, request, contract, both attempt and
transport receipt copies, frozen input/source bindings and executor code hashes.
Detected drift prevents acceptance and remains a diagnostic; no source repair is
performed. A detected discrepancy does not refund the attempt.

The output manifest hashes every completed output file except itself, including
request, contract, attempt, raw bytes, receipt, metadata, result and any reply or
resolved proposal. It also records input/code bindings and final status. The
registry receives identical result bytes and the output manifest as
`result_manifest.json`. Write the output `manifest.json` last as the recording
completeness marker. Missing manifest means incomplete recording, regardless of
earlier receipt/result files. Storage failures are not disguised as successful
abstentions and never enable a resend.

This is recording of one dispatch, not a recovery/resend tool. Existing offline
`inspect-response` remains separate and never spends or resets the future slot.
Registry deletion/rollback, distributed execution and power-loss guarantees retain
the limitations from the executor protocol. A completed failure manifest means
that failure evidence was recorded, not that the scientific experiment passed.
