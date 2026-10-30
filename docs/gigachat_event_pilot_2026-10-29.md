# GigaChat experimental-event pilot: three bounded cases

29 October 2026, Asia/Yekaterinburg. The user authorized the proposed offline
schema/citation preparation and subsequent three-case GigaChat pilot. This is
direct experimental extraction from curated exact excerpts, not an ASGI
`/answer` run. Production prompts/schema/runtime, retrieval, DB/index, immutable
PDFs and all historical model slots/results were unchanged.

Changed:

- Added `scripts/gigachat_event_proposal.py`: a separate strict event-selection
  schema, exact source-statement catalog and lexical duration atoms. Models select
  catalog IDs; code restores raw quotes and value/unit strings with exact offsets.
  Target and at most two other events propose sample, operation, duration,
  conditions, completion criterion and kind. Missing/uncertain fields require
  empty IDs. Local source integrity is not scientific event assignment.
- Added `scripts/run_gigachat_event_pilot.py`: freezes all three native requests,
  code/tests/protocol/source bindings and archived source before transport;
  reserves append-only global SHA slots before OAuth; saves raw replies before
  parsing. No automatic retry/fallback, purchases, scope upgrades or account reads.
- Cases: explicit dispersion-cell hold, Kayumov equilibrium criterion without
  numeric time, HCl protonation with neighboring H2O2 cleaning time. The model
  received exact questions/catalogs/atoms, without preliminary reference answers,
  scientific annotations or previous model outputs.
- The existing TLS-verified GigaChat transport was reused with current
  `GigaChat-2-Max`, personal scope, 1200 output tokens and 120 seconds per HTTP
  request. Exactly three OAuth exchanges and three model POSTs occurred through
  normal execution escalation for the known sandbox socket restriction.
- Protocol: `docs/records/gigachat_event_pilot_protocol_v0.1.md`. Frozen study,
  sources, native bodies, raw replies and slot/result records:
  `output/gigachat_event_pilot_20261029/`.

Tests run:

- **17 preflight tests passed**: schema/source integrity, exact values/units,
  request-local catalogs, unknown/duplicate IDs, status/ID contradictions,
  context membership, native incomplete/filter outcomes, duplicate JSON keys,
  catalog drift, unauthorized sends, slot reservation before transport, consumed
  failures and prevention of a second send. Fake transport only. JUnit:
  `output/gigachat_event_pilot_tests_20261029_v02.xml`.
- After the observed contract defect, **7 additional offline regression tests
  passed** for the separately versioned diagnostic correction. JUnit:
  `output/event_diagnostic_schema_v02_tests_20261029_v01.xml`. These are 24 distinct
  tests, not a count including repeated runs or the overlapping earlier 13 tests.
- Ruff passed for the extraction module, driver, correction helper, their tests
  and final postflight script. Strict mypy passed individually for the extraction
  module and correction helper; driver-wide typing is not claimed.
- Offline replay reproduced all three original rejection reasons without
  transport or DB use. Guarded postflight transport calls were zero. Verified
  current frozen input/snapshot/prepared/live manifests, exact native request
  identity, original PDF bindings and global registry/result equality.
- Final searchable HTML:
  `output/gigachat_event_pilot_20261029/review_v02/review.html`. Three case cards,
  full original requests/native replies/catalogs/pages/diagnostics and all three
  selected works in the eight TAC columns. Static QA verified three TAC rows and
  six existing original-PDF links; credential scan found zero matches. Missing
  metadata/uncollected fields remain explicit. No browser rendering is claimed.
- The initial postflight HTML remains `review_v01`; `review_v02` adds the tested
  correction helper and postflight code bindings. Native v0.1 responses and their
  classifications were not overwritten or repaired.

Actual v0.1 outcomes:

| Case | Native finish | First local rejection | Accepted output |
| --- | --- | --- | --- |
| Dispersion cell / explicit 2 hours | `stop` | Empty diagnostic | No |
| Equilibrium criterion / missing numeric dwell | `stop` | `not_found` with nonempty selected IDs | No |
| Protonation / neighboring preparation duration | `stop` | Empty diagnostic | No |

All three native JSON bodies had the declared structural fields. There were no
filtered or truncated replies. The transport does not expose successful native
HTTP metadata, so this report does not fabricate HTTP 200/502 results. Returned
model: `GigaChat-2-Max:2.0.30.01`.

## Contract defect identified in this implementation

The v0.1 native JSON schema declared `diagnostic` as an unrestricted string,
while the local parser required a non-whitespace value. This is an implementation
inconsistency in this pilot, **not a model JSON-schema violation**. Empty
diagnostics caused the first rejection in two cases. The original schema,
validator, raw responses, first rejection reasons and consumed slots are frozen
and preserved. Those outputs are not reclassified as accepted.

A separate offline helper `scripts/event_diagnostic_schema_v02.py` prepares
diagnostic `minLength=1` and a non-whitespace pattern, plus an explicit instruction.
Three native candidate bodies and their metadata are in
`output/gigachat_event_pilot_20261029/offline_schema_v02/`. Question and source
catalog are unchanged; the old parser remains unchanged. Regression checks reject
empty/whitespace/wrong-type diagnostics and check the exact limited schema/prompt
change. **These requests were not sent, their slots were not reserved, and
provider support for the added schema constraints is not live-tested.**

The remaining status/ID constraint in the criterion case is a genuine violation
of the requested local selection contract: four fields (`sample`, `operation`,
`conditions`, `completion_criterion`) say `not_found` while selecting `S2`. Its
diagnostic is nonempty; the empty-diagnostic defect does not explain that failure.
No status or ID was normalized after the fact.

## Raw scientific observations, not accepted event outputs

- The dispersion target selected `D1`, exactly `2 часа` from its hold statement.
  There was no invented number. Its kind is `preparation`, the hold event is
  repeated, and sample identity is not established by its selected cell/hold
  statement. This is partial evidence selection, not accepted event extraction.
- The criterion target has empty duration IDs / `not_found`, so it invented no
  numeric dwell time. Its criterion and other fields contradict their selected
  IDs, preventing a coherent accepted event.
- The protonation target uses `S2` and empty duration IDs / `not_found`. The two
  hours of H2O2 cleaning remain in another preparation event rather than becoming
  the HCl protonation time. However, another event labeled `drying` selects both
  `1 ч` and `2 недели`, merging drying with subsequent storage. This source-exact
  but wrong-stage combination demonstrates why exact quotations alone are
  insufficient for scientific admission.

These observations inspect preserved raw selections from rejected responses;
they are not a repaired result, model accuracy or an automatic scientific verdict.

Provider-reported usage:

| Case | Input tokens | Output tokens | Total |
| --- | ---: | ---: | ---: |
| Dispersion hold | 474 | 628 | 1102 |
| Criterion | 425 | 262 | 687 |
| Protonation | 472 | 687 | 1159 |
| Sum as reported | 1371 | 1577 | 2948 |

Native request sizes were 6206, 5809 and 6820 bytes. No response reached its
1200-output-token limit. Token usage is copied from the provider, not measured
as full prompt size or interpreted as monetary cost/context compression.

Limitations:

Three exposed development excerpts with assistant-authored expectations, no
independent scientific annotation, reviewer or accuracy estimate. The catalog
has finite lexical duration coverage. Exact selected IDs and shared source
contexts cannot establish sample, method, experimental stage, causal sequence or
measurement applicability. At most two other events cannot establish complete
extraction of every operation in a paragraph. Neither successful JSON decoding
nor raw partial observations establish reliability. The schema defect consumed
two requests before useful accepted-output evaluation; no replacement budget was
assumed. Runtime ORM/cache and earlier provider-filter limitations remain open.

Verdict:

The authorized three-case pilot is complete: **zero accepted v0.1 outputs**.
Two first rejections are attributable to the implementation's diagnostic schema
gap; one to inconsistent field selections. A separate offline correction is
prepared and tested, while raw stage-assignment issues remain visible. The
experiment does not establish scientific extraction readiness. All three new
slots and all older live budgets are closed; do not resend or activate `/answer`
integration without a separately declared scope.
