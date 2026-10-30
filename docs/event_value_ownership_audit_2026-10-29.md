# Offline source-region diagnostics for operation/value ownership

29 October 2026, Asia/Yekaterinburg. The user authorized continuing with offline
operation/value ownership checking after the v0.2 live pilot exposed cleaning
values assigned to protonation and drying. This stage adds a separate diagnostic
sidecar. It does not implement general semantic ownership validation or runtime
admission. No new model/OAuth/DB operations or slot reservations occurred.

Changed:

- Added `scripts/event_value_ownership_audit.py`. The algorithm consumes raw
  source and exact validated proposal spans, without questions, case IDs,
  assistant reference labels or the model's declared event kind. A finite RU/EN
  vocabulary recognizes operation lexemes. Exact statement/local-region anchors
  make different-source-operation selections visible without selecting a nearest
  operation or transferring values through a relation.
- A mapped recognition view joins line-end word hyphens and soft hyphens for
  matching only. Output anchors restore exact original character offsets and
  quotes. Stored extraction, OCR, original PDFs and historical splitters remain
  unchanged. The inherited finite statement splitter is reused as-is.
- Explicit sequence markers can separate operations. Coordinated operations are
  split only when separate duration expressions occur before/after the connector;
  a shared trailing value remains unresolved. Unknown or multiple operation
  lexemes, recognized abbreviation-boundary ambiguity, shared/referential and
  negated/conditional scopes stay visible and unresolved. Participial material
  modifiers such as `очищенной мембраны` are not a new cleaning operation in the
  supported patterns. This remains a finite vocabulary, not full grammar parsing.
- Duration/conditions selections receive locality diagnostics. A value in a
  different explicitly recognized region yields
  `different_explicit_operation_regions`; a value in the same local region yields
  `same_local_region_unverified`. Neither establishes a scientific owner.
  Missing fields receive `no_selected_value_not_evaluated`, not a validated
  absence. Every row retains `owner_established=false`.
- A separate finite duration-cue check records bounds, ranges and approximation
  cues, including adjacent cues outside the model-selected span. It preserves
  original units/values, leaves strict/unrecognized/distributed meanings
  unresolved, and cannot prove an exact requested value from a bare number.
  Model classifications and raw outputs are not repaired.
- Added `scripts/run_event_value_ownership_audit.py` and the protocol
  `docs/records/event_value_ownership_audit_protocol_v0.1.md`. The offline runner
  keeps twelve constructed fixtures separate from three saved real model replies,
  replays the original native bytes, validates source/page anchors, verifies
  fresh PDF text and freezes a separate source/code/test/protocol snapshot.
  Socket operations are forbidden; provider transport is patched to fail if
  invoked. Production `/answer`, prompts/schema, prior parsers and scientific
  annotations remain unchanged.

Observed results, separated by input origin:

| Input group | Proposals | Same local region, unverified | Unresolved operation/scope | Different explicit operation regions | Missing selected field, unevaluated |
| --- | ---: | ---: | ---: | ---: | ---: |
| Assistant-constructed fixtures | 12 | 15 | 10 | 0 | 39 |
| Saved live proposals | 3 | 4 | 0 | 3 | 1 |

Counts refer to duration/conditions selections, not events, answers or accuracy.
There are 64 fixture field rows and eight actual model field rows. Their counts
are not pooled. All eight selected original PDF pages/five source works are
included; there are no newly generated model answers.

The three source-region signals in the saved protonation case are:

- Target protonation `E1`: selected `2 ч` belongs to the separately recognized
  source region describing H2O2 cleaning, before the protonation region.
- Drying `E2`: selected `2 ч` comes from that same cleaning region.
- Drying `E2`: selected `при 60–80°C` also comes from cleaning, rather than its
  own drying region. The source separately reports drying at 60°C for one hour.

The diagnostic engine obtains these regions without reading the frozen reference
owners/checks or trusting model kind. It additionally reports two
`declared_relation_cue_not_found_in_finite_scope` duration readings for the model's
`at_least` labels on `2 ч`. This is a finite cue diagnostic, not a general proof
that every possible linguistic expression of a lower bound was excluded.

The dispersion hold's duration/working temperature and the criterion case's
selected conditions remain local and unverified. The engine does not fix the
incorrect `storage` kind, resolve the cell/material identity or clean the
criterion's interleaved formula/layout text. The ten unresolved constructed
field rows expose coverage limits, including unrecognized operations, mixed
contexts and abbreviation-boundary ambiguity. Zero different-region signals in
the final constructed set is not an independently measured false-positive rate.

Tests run:

- **180 affected tests passed: 40 new ownership controls plus 140 prior controls.**
  Final JUnit: `output/event_value_ownership_regression_20261029_v04.xml`.
  Constructed controls cover cross-sentence borrowing, distinct stages in one
  sentence, identical numbers/different operations, repeated operation classes,
  shared trailing values, references, negation/conditionals, unknown operations,
  broad operation spans, explicit sequence markers, participial modifiers,
  abbreviation boundaries, raw OCR-like word breaks/Unicode/units, duration
  cues, missing fields, source/proposal drift and input immutability. Changing
  only model kind leaves ownership diagnostics unchanged.
- Initial new-only tests exposed an overly broad cleaning stem matching
  `очищенной`; the matcher was narrowed and modifier controls added. The first
  full run had 14 fixture setup errors because the task's parent temporary
  directory had not been created. That directory was created; no sandbox
  override or weakened assertion was needed. A subsequent abbreviation guard
  initially treated a sentence-final hour unit `ч.` as ambiguous and failed two
  existing controls; the finite abbreviation list was narrowed without changing
  those assertions. Earlier JUnit files are preserved rather than counted as
  successful runs. The final run used a checked new project-local `--basetemp`
  and disabled the optional pytest cache.
- Ruff passed for the audit module, runner and new tests. Strict mypy with
  explicit package bases/silent imports passed for the audit module, one source
  file. Runner-wide typing is not claimed.
- Executed final audit on all twelve frozen constructed fixtures and three
  saved live proposals with socket operations prohibited. The provider guard
  recorded zero transport calls. Native replay reproduced all three complete
  original restored outputs; their formal parser verdicts remain unchanged.
  Original schema/prompt/reference files, raw bytes, prior output manifests and
  source bindings were preserved.
- All eight selected full pages matched fresh PyMuPDF extraction from immutable
  originals. PDF hashes, quote/page hashes, exact excerpt offsets and every
  constructed/live selection's computed full-page operation/value anchor were
  verified. Python/PyMuPDF versions are in the final JSON report.
- Final searchable HTML:
  `output/event_value_ownership_20261029/review_v02/review.html`. Includes all
  twelve cases, three separately identified actual model sections, the raw
  proposals, diagnostics, full source pages and all five works in the eight TAC
  columns. Static QA verified twelve case cards, five TAC rows, three model
  sections and seventeen existing original-PDF links. Missing metadata and old
  open notes remain explicit. Browser rendering/search execution were not tested.
- `review_v01` preserves the initial two false different-region diagnostics on
  the known cleaning excerpt: the inherited splitter broke at `мас.`, separating
  the cleaning noun from its duration/temperature and exposing a later mixing
  lexeme. Final `review_v02` marks the recognized abbreviation boundary unresolved
  instead of merging/repairing the source. That correction was developed on an
  exposed example; it is not independent generalization evidence. The old
  report, source snapshot, native replies and annotations remain untouched.

Limitations:

This is a bounded deterministic source-region audit, not a semantic ownership
solver. Lexical regions and even explicit sequence markers cannot establish
scientific assignment, sample identity, method, event completeness, causal
relations or question coverage. The finite vocabulary/splitter/cue rules can
miss phrasing, nominal versus asserted operations, abbreviations, distributed
bounds, shared conditions and valid cross-sentence references. Unresolved cases
are retained; no confidence score, universal safety claim or automatic admission
is provided. The same-region state deliberately confirms no scientific owner.

All twelve source cases and three model replies were already exposed. Rules were
developed against those observations and constructed tests. There is no independent
annotator, held-out evaluation, reviewer or accuracy estimate. Independent quality
evaluation remains separate from the automatic Terms/user workflow. Historical
provider filtering and ORM/cache limitations remain open; live budgets/slots are
still closed and no remaining offline candidate is newly authorized for sending.

Verdict:

The authorized offline diagnostic stage is complete. It reproduces three known
cross-operation source signals and two unsupported finite-scope bound readings
without reference labels, while retaining ambiguous/local cases as unverified.
Semantic ownership validation and independent evaluation remain open.
`/answer` is unchanged; new API/OAuth/DB operations and slot reservations: zero.
