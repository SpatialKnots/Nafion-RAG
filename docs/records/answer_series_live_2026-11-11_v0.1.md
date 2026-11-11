# ARIADNE: new bounded live trial after consolidated freeze

Authorization: user `давай`, immediately after the completed offline audit and
the proposed separately scoped real-model trial. This opens one new pass over
the same 30 development-exposed questions; it does not reopen any older scope.

Runtime application: commit c5a72d3dd5068fc05819d7612d76c51f6aed9810;
source freeze 8a3740426404b02e4a99a8da2387d67935745f32395992b9e1c443438199a287.
Original questions and explicit article prefixes remain unchanged. All app code,
glyph catalogues, prompt, admission, ranking, units, source content, schema and
thresholds remain frozen throughout preparation and dispatch.

Use the existing /answer/experimental/required-fields route, collection
literature, hybrid_cross_lingual, top5, claims, Russian, GigaChat-2-Max,
1200 output tokens and 120 seconds per HTTP operation. Maximum30 model POSTs
and30 OAuth exchanges, at most1/1 per eligible question. No automatic retries,
fallbacks, rewrites, continuations, model changes or further scope extension.
Monetary cost is unknown; do not infer it from token usage.

Prepare all30 in fresh processes using actual read-only/repeatable-read DB
transactions with rollback. Stop before actual transport, verify the full trace,
source registry, original PDFs, exact native bytes against the audited inputs,
article scope and100000-byte ceiling. Seal all concrete hashes before sending.
No clipping or alternate preparation after seeing model results. A preparation
failure stops the batch before model calls and requires a separately recorded
diagnostic attempt; it never authorizes a hidden resend.

New scope-local exclusive attempt slots. Fresh worker per send. Verify the
same trace/source metadata/request before dispatch. Preserve native response,
API status/body, model version/finish reason/usage, guard review, timing and any
errors separately. Provider/API failures consume the corresponding allowance.
HTTP503 or an internal/unknown worker failure stops further dispatch; unused
allowance expires at closure. Known HTTP502 validation failures are recorded,
without retry, while the remaining cases may continue. Close all30 allowances,
including unsent; a reserved unknown outcome is never labelled zero attempts.

References and historical assessments do not enter inference. All questions
and source grammars have already been exposed to development; this is a runtime
and contract-compliance trial, not a new blinded/independent evaluation. Review
only after closure. Report actual availability, source-fact selections,
abstentions, validation/transport errors, guard coverage and qualitative source
issues separately. No scientific accuracy score or expert acceptance is implied.
The answer-quality plan remains75%. No deployment or publication is authorized.
