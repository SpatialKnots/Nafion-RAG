# Offline requested-information diagnostic, 29 October 2026

Changed:

- Added `scripts/requested_information_audit.py`, a pure offline duration-expression
  diagnostic, and `scripts/run_requested_information_audit.py`, a reader of frozen
  development outputs. Neither is imported into the production answer chain.
- The finite Russian/English query grammar recognizes explicit duration requests.
  The diagnostic records exact raw question/claim spans and returns one of:
  `outside_finite_duration_query_scope`, `no_duration_expression_detected`, or
  `duration_expression_present_unverified`. It never emits an answerable flag,
  scientific pass, confidence score, forced abstention or rewritten answer.
- For saved native replies, the runner first applies the current strict GigaChat
  parser and citation validator. Rejected outputs, valid model abstentions and
  valid answers remain separate layers. A provider `blacklist` finish reason is
  retained alongside its exact parser error and historical HTTP result.
- Evidence-side time expressions are displayed separately with citation/article/
  chunk/page identity and offsets into the unchanged full evidence text. A time
  elsewhere in a cited chunk cannot establish a measurement dwell duration.
- Production prompts, schemas, validation, scoring, models, API/UI behavior, DB,
  embeddings/index and original PDFs were unchanged. Old manifests, responses and
  consumed slots remain intact. No additional API or OAuth calls were made.

Tests run:

- **34 constructed unit tests passed**, JUnit:
  `output/requested_information_audit_tests_20261029_v01.xml`.
  Covers exact offsets, numeric/common word-number durations, decimal commas,
  ranges, line breaks, RU/EN queries, irrelevant years/IDs/temperature/frequency,
  qualitative questions, no cross-claim assembly, invalid inputs and explicit
  finite-grammar misses. Adversaries include negation, preparation versus
  measurement, other specimens/articles and hypothetical timings: all lexical
  duration matches stay unverified.
- Ruff passed on the two new scripts and unit test. Strict mypy passed on the
  pure diagnostic module (one source file); no claim of runner-wide mypy checking.
- Read and re-parsed **eight frozen native results**, without transport or DB
  connections. Guarded transport and DB connection call counts were zero; socket
  events were forbidden. Verified prepared/live manifests, exact request hashes,
  append-only registry result identity and original-PDF hashes. Production parser
  acceptance/rejection agreed with all eight saved public HTTP outcomes.

| Historical layer | Count | Offline finding |
| --- | ---: | --- |
| Valid answer to an explicit duration query | 2 | Both lack a recognized duration expression; scientific coverage remains unevaluated |
| Other valid scientific answer | 2 | Outside this finite query scope |
| Valid model abstention | 1 | Kept separate; not semantically certified by this audit |
| Rejected output | 3 | Two inconsistent answerable/claims replies and one provider blacklist; not scientific abstentions |

- Final artifact:
  `output/requested_information_audit_20261029/review_v02/review.html`, with eight
  case cards, six source documents in the agreed eight TAC columns, full
  expandable requests/native replies/evidence/source-page registry and six
  existing original-PDF links. Static HTML checks passed; browser rendering and
  interactive search execution were not tested. Missing metadata and uncollected
  Conclusions/Terms remain explicit.
- The initial `review_v01` was generated before correcting import ordering and
  adding explicit zero-call transport/DB assertions to the runner. Its snapshot
  is retained as historical output. `review_v02` binds the corrected scripts and
  protocol; outputs are not silently overwritten.

Limitations:

This is a lexical diagnostic, **not a semantic coverage validator**. The two
flagged answers are already exposed development failures reviewed by the
assistant; detecting their missing expression is not an accuracy estimate.
Numeric values can be negated, hypothetical, borrowed from another sample or
about a different experiment. Conversely, valid expressions outside the finite
grammar (for example Russian `полчаса` or unsupported languages) can be missed.
The tests explicitly preserve that limitation rather than silently call those
answers wrong. Source-wide absence, original article identity from unknown
metadata, numerical agreement and scientific entailment are not established.

The qualitative control remains a provider-filtered result: the exact reason
`blacklist` is observable, its trigger is unknown. No filter bypass was attempted.
The long-lived-server ORM/cache limitation remains open. No new live slots exist.

Verdict:

The offline diagnostic makes the repeated missing-duration symptom visible while
demonstrating why checking for a number is insufficient for runtime acceptance.
It is ready for development inspection and remains disconnected from `/answer`.

## Boundary for a future semantic coverage implementation

The next implementation must describe each requested fact separately, including
quantity, sample, article, method, experimental stage and conditions where stated.
It must distinguish a requested numerical value from a qualitative method or
completion criterion. Unsupported query interpretation must remain unresolved.

For each proposed answer, bind the reported value/unit and experimental context
to exact supplied source spans, citation ID, article/chunk/page identity and
registered text layer/PDF hash. Offsets must identify the unmodified input; a
separate normalized view cannot replace the source. A time and a measurement
mentioned in the same chunk are not automatically related. Preparation/drying/
soaking times require an explicit source link before becoming measurement times.

Represent sample/article/stage mismatches, negation, hypotheses, conflicting
values, missing conditions and unparsed requirements as unresolved diagnostics.
Multi-part questions need per-requirement coverage; a nearby supported claim
cannot stand in for an unanswered requirement. Partial answers and valid
abstentions require an explicit product policy before changing runtime behavior.
No new production output contract is introduced by these design notes.

Evaluate any future semantic method on a separately frozen, independently
annotated set, keeping the present exposed cases as regressions. Independent
evaluation must stay separate from the automatic user workflow; do not require
the user to approve each article/Term/query. Do not claim reliability from parser
tests or use the finite lexical diagnostic alone to admit or reject scientific
answers. Additional model use, runtime policy/schema changes and live evaluation
need their own declared implementation scope and evidence.
