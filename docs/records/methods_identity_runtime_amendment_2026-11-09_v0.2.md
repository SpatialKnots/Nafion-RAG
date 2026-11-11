# Methods identity runtime: adverse-probe amendment v0.2

The original v0.1 protocol/freeze remains unchanged. The final opt-in policy
becomes `ordered_methods_identity_v0.2`; disabled remains default. This is a new
version, not a rewritten successful v0.1 measurement.

Initial new-policy probe_v01: 71 passed, six service/HTTP cases deselected.
Additional adverse probe_v02: six failed, 73 passed, six deselected. Three new
artificial substitutions (`a different electrolyte makes`, `another electrolyte
makes`, `a different cell system makes`) were wrongly admitted. The existing
local status guard covered another sample/material/experiment but not these
subjects. v0.2 extends this path's local guard to electrolyte/cell/system and
checks the complete target-to-CE interval, not only the immediate CE prefix.
The global source grammar and historical audit module remain unchanged.

Three other failures were test-fixture errors: two default/English legacy-path
checks failed to replace the provider and reached OAuth DNS. The Python audit
guard denied both socket.getaddrinfo events for ngw.devices.sberbank.ru before
DNS/connection; two denials retained in probe_v02.scope.json. No OAuth exchange,
model POST, live budget or slot occurred. The fixture now supplies a synthetic
abstaining provider. The third passed no max_claims to ExtractiveAnswerProvider;
the corrected fixture uses an Extractive subclass with explicit max_claims and
synthetic abstention, preserving the actual isinstance branch.

The failing app/test sources are preserved under adverse_v01 with hashes. Also
retain the original unsuccessful multi-file apply_patch (context mismatch; no
partial patch applied), first Ruff's two import diagnostics and full-app mypy's
one optional-context type error. These were corrected without scientific changes.
A raw-source terminal print hit cp1251 UnicodeEncodeError; a separate ASCII-escaped
view succeeded, without modifying original text.

Final checks must rerun the affected scope, both policy-off and v0.2-on frozen
channels, actual synthetic service/ASGI cases, native request and visual review.
Known-case regression and constructed controls are not independent evaluation.

Integration assessment: probe_v03 hung on sandbox ASGI after two direct failures;
only verified Python PIDs 22552/16344 were stopped. Same code outside sandbox in
probe_v04 completed: 5 failed / 80 passed, network denials zero. These five failures
were the fixture's incorrect assumption that the new service path was active:
the complete real Abstract already yields all three existing fact recipes, so
the original fallback-only selector correctly retained the one-parent legacy
bundle. The native/direct graph tests had passed, but did not prove service
activation. This is evidence against claiming a new answer/refusal gain on Lin.

Final v0.2 selector explicitly opts in to the stronger graph contract only for
a structurally selected three-parent packet with Methods and Conclusion. It can
replace a complete old bundle on that selected input; the disabled default and
unrelated complete bundles remain unchanged. An attempted graph that fails
abstains before the provider rather than silently falling back. Existing English,
Extractive and explicit-marker paths remain available outside this opt-in packet.
This is an auditability/citation change for the exposed real packet, not proof
that its pre-change product answer was refused. No retrieval/context expansion
or general ownership gain is claimed.

probe_v05 completed: 4 failed / 83 passed, network denials zero. The active direct
complete path reached the legacy generic quote checker, which cannot represent
a definition-only parent or final multi-source citations (Empty procedure quote
selection). Only the new fully recomputed Methods graph now omits that redundant
legacy one-quotation/one-citation check; F-ID completeness, exact recomputation,
server rendering and final citation membership checks remain. Old paths retain
their checks. Three ASGI assertions still exercised disabled settings because
/answer calls app.main.get_settings directly, rather than via Depends; the test
now patches that actual lookup in addition to the session dependency. No app
route/settings behavior was changed to accommodate the fixture.

First affected run tests_v01: 27 failed / 856 passed, external-network denials
zero. All new-policy tests passed; 27 old tests used a pre-existing SimpleNamespace
settings fixture without the new optional setting. Runtime now treats a missing
attribute as the same disabled default, preserving those existing callers and
fixtures; historical tests were not rewritten. Final affected run must pass.
