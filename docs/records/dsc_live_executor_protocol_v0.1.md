# DSC live dispatch and one-attempt reservation v0.1

27 October 2026. Implements item 1 of the API-readiness follow-up: a separate
executor and persistent attempt accounting. Implementation does not authorize a
provider call. The existing user API prohibition remains active.

`app.records.dsc_live.dispatch_frozen` is an explicitly called Python function;
there is no sending CLI, API route, startup hook or production integration. Its
`api_calls_authorized` argument defaults to false and accepts only literal true,
representing the caller's attestation of explicit current user permission. Source
eligibility is never treated as permission. Credentials must be provided by the
caller; this code does not look them up. Tests use constructed credentials and
mock transport only.

The executor loads the existing captured stage49 through its unchanged validator.
It verifies frozen source/code/runtime bindings, reconstructs admission and request
guards, and sends the exact saved request bytes through the existing fixed-endpoint
transport. Model, schema, timeout, output ceiling and one-attempt/no-retry/no-fallback
budget are unchanged. Old artifacts, including historical authorization/executor
flags, remain immutable snapshots. The new executor records a separate attestation
and execution identity; it does not rewrite stage49's flags or scientific state.

The registry is fixed at
`data/experiments/dsc_live_attempts/<request_sha256>/` relative to the installed
checkout's code, never cwd or output. The public executor offers no alternate
ledger path. An atomic exclusive directory creation selects one process across
different output directories. A new `attempt.json` is written exclusively,
flushed and fsynced before transport. The output also receives exact request bytes
and a synced copy of the attempt before transport. No refund, stale-lock cleanup,
retry, fallback or automatic recovery exists. Existing directories, including empty,
partial or malformed reservations, fail closed. Once directory creation succeeds,
any later write failure, timeout, transport error, unexpected exception or process
interruption leaves the slot consumed, even if delivery cannot be established.

Expected HTTP/URL/OS/HTTP-protocol transport errors produce explicit typed error
receipts; other exceptions propagate. Raw response bytes or credential-redacted
error bytes are saved and fsynced before any parsing. Transport receipts are
saved separately in output and registry. A receipt-write failure propagates;
the reservation remains. Successful transport is only
`response_received_unvalidated`. No response schema/source interpretation, model
identity extraction, token usage accounting, monetary calculation, scientific
acceptance or completed live-experiment result is asserted by this item.

The registry is local to one checkout on its local filesystem. It is not a global
provider idempotency guarantee, a distributed lock, or protection against deliberate
registry deletion, rollback, filesystem corruption, restored backups or independent
repository copies. Preserve the registry when moving/restoring the checkout.
`fsync` uses the OS/filesystem's durability guarantees; hard power-loss behavior is
not experimentally verified. Filesystem atomicity/durability must not be assumed
for an untested network share. Never delete a reservation to retry an uncertain
delivery. The slot is an operational count limit, not a monetary billing cap.

Before any future authorized send, implement/verify the remaining live-result
recording and final preflight, including provider compatibility and actual model/
usage/error metadata. Existing offline `inspect-response` remains available for
separate validation of saved bytes. No extra API/status probe is authorized here.
