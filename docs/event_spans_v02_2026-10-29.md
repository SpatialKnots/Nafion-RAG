# Exact-span experimental-event contract v0.2: offline preparation

29 October 2026, Asia/Yekaterinburg. The user authorized the proposed next stage:
prepare a new event-extraction contract and offline checks on the twelve real
excerpts. This stage does not authorize or perform a new live pilot. All earlier
GigaChat request slots and budgets remain closed. Production `/answer`, model,
prompts/schema, retrieval, DB/index, immutable PDFs and historical failures are
unchanged.

Changed:

- Added `scripts/event_spans_v02.py`, a separately versioned extraction-contract
  candidate. Each event selects one operation fragment and separate exact spans
  for sample, method, duration, conditions, completion criterion, result and
  exclusion. Multiple events can belong to one question. The old two-other-event
  ceiling is not carried into this candidate. Event relations cite distinct
  existing event IDs and exact bridge fragments; values are not propagated.
- A neutral lexical catalog supplies raw tokens and character offsets. Inclusive
  token indices restore exact raw source substrings, including internal line
  breaks, hyphenation, soft hyphens and nonbreaking spaces. This is a new address
  sidecar only; no stored text, OCR, extraction or chunking behavior changes.
- Native JSON schema and local structural models now share nonblank diagnostic
  and status/selection definitions. Present fields require nonempty spans;
  missing/uncertain fields require empty spans. Duration proposals distinguish
  exact, range, bounds, approximation and unresolved interpretation; the original
  source phrase, including any bound, is retained. Interpretation is not verified
  merely by selecting a span.
- Local source-integrity checks supplement the schema: catalog identity, strict
  integer address representation, valid forward intervals, ordered unique
  nonoverlapping selections, unique event/target IDs and existing relation
  endpoints. These relational constraints are not all expressible in the emitted
  native schema. Filtered/incomplete/malformed replies fail without repair.
- Added `scripts/event_span_checks_v02.py` and
  `docs/records/event_span_fixtures_v0.2.json`. All twelve previously exposed
  excerpts have **assistant-authored constructed fixtures**, with 32 events,
  seven example event relations and 42 sparse required/forbidden field checks.
  They are preliminary development annotations, authored together with the
  fixtures, not model answers, independent gold or an extraction-quality result.
  Original preliminary notes and unresolved issues remain visible.
- Added `scripts/run_event_spans_v02.py` to verify sources and prepare twelve
  unsent native request candidates. Requests contain only the original question,
  neutral raw source catalog, system instruction and schema: no fixture outputs,
  expected labels or prior model replies. Candidates use current GigaChat-2-Max
  and the existing 1200 output-token setting. No credentials/settings are loaded,
  transport invoked or request slot reserved by this runner.
- Added `scripts/check_event_span_schema_v02.py` for a separate local JSON-schema
  preflight. This uses the already installed `jsonschema`, without installation
  or a provider call. The preparation/protocol is
  `docs/records/event_spans_v0.2_protocol.md`.

Tests run:

- **128 affected tests passed: 71 new controls plus 57 prior controls.** JUnit:
  `output/event_spans_v02_regression_20261029_v01.xml`. Used a checked, previously
  absent project-local `--basetemp`, with the optional pytest cache disabled.
  The new-only run separately passed the same 71 tests; it is not added again
  to the distinct test count.
- Controls cover exact restoration, OCR-like breaks/Unicode/units, lower-bound
  preservation, every field's status/span contradictions, blank diagnostics,
  bad/duplicate IDs, invalid/overlapping spans and relations, strict address
  types, malformed/filtered/truncated output, catalog/reference/restored-output
  drift, request-local schemas, input immutability and annotation leakage.
- Twelve positive constructed fixtures passed the local parser and their sparse
  checks: 30 required bindings matched and 12 forbidden bindings were not
  proposed in aligned events. This checks the contract/comparator against the
  authored examples, not model performance. Unaligned, ambiguous or compound
  operation anchors are explicitly unscored; unannotated operations are not
  negatives. The seven fixture relations are structurally validated only.
- A deliberate drying/storage control remains locally source-exact and formally
  valid when both `1 ч` and `2 недели` are attached to drying. The sparse comparator
  reports the forbidden storage binding using its explicit annotation. No claim
  of automatic semantic detection without annotation is made.
- Local `jsonschema` 4.23.0 preflight validated all twelve emitted schemas and
  positive constructed fixtures, plus twelve structural/source-integrity
  controls. Eight invalid controls fail the native schema; four pass the schema
  but fail documented local integrity checks: reversed intervals, duplicate
  event IDs, unknown target IDs and an integral float address representation.
  The wrong-stage control also passes the native schema, demonstrating the
  scientific limit. Results:
  `output/event_spans_v02_20261029/schema_check_v01/report.json`.
- Ruff passed for the contract module, comparator, preparation runner, schema
  preflight script and new tests. Strict mypy with `--explicit-package-bases
  --follow-imports=silent` passed for the contract/comparator, two source files.
  Driver-wide typing is not claimed. An initial mypy invocation lacked explicit
  package bases and reported duplicate module names; no source relaxation was
  needed. The archived one-off fixture builder retains an unused `copy` import
  reported by its initial Ruff invocation; builder-wide lint success is not
  claimed. Its original code and build bindings remain preserved.
- The preparation runner completed with socket operations prohibited. All eight
  selected full pages matched fresh PyMuPDF extraction from all five original
  PDFs. PDF identities, quote/page hashes, exact excerpt offsets, prior frozen
  bindings and old review manifests verified. No model/OAuth/DB operation or new
  slot reservation occurred. Python/PyMuPDF versions, request sizes, code/test/
  protocol/source snapshots and hashes are recorded in the report/manifests.
- Final searchable HTML:
  `output/event_spans_v02_20261029/review_v02/review.html`. Includes all twelve
  questions, quotes, full registered pages, exact token catalogs, constructed
  events/checks/open notes, full unsent native requests and all five works in the
  eight TAC columns. Static QA verified twelve case cards, five TAC rows and
  seventeen existing original-PDF links. Missing/uncollected metadata remains
  explicit. Browser rendering and search execution were not tested.
- `review_v01` is preserved before runner line wrapping and addition of the
  integral-float source-integrity control. `review_v02` retains the same source
  fixtures, field checks and unsent request bodies. Historical v0.1 event-pilot
  responses were not reparsed as this schema or reclassified as accepted.

Limitations:

This stage implements the contract/parser, prepares requests and tests constructed
examples. It does not execute semantic model extraction or establish improved
GigaChat behavior. Provider support for the emitted schema's unions/constraints
is untested. Offline JSON-schema validation is not a provider-support claim.
The ability to finish the larger event representation under 1200 output tokens
is untested; no live budget increase is implied.

Source-exact fragments cannot establish scientific ownership, atomicity, sample
identity, applicability, negation interpretation, method, completeness or
answerability. Bound/type classifications are proposals. The sparse comparator
uses known exact operation anchors and selected field checks; it does not evaluate
target semantics, semantic event relations or alternative valid paraphrased
anchors. Reference fixtures and expected checks share authorship and exposed
sources. No independent annotator, held-out set, scientific acceptance or
accuracy estimate exists. A future independent evaluation must remain separate
from the automatic Terms/user workflow.

Earlier provider filtering, failed raw responses and runtime ORM/cache
limitations remain unresolved. The twelve request candidates are unsent and
unreserved; neither this stage nor the user's instruction to perform it permits
automatically reopening old live budgets.

Verdict:

The authorized offline contract stage is complete. Exact fragments can represent
distinct operations within a sentence and preserve bounds, sample distinctions,
temperature exceptions and exclusions in the constructed development controls.
Model extraction quality and independent scientific acceptance remain open.
The artifacts are ready for review and a separately scoped future pilot;
`/answer` is unchanged.
