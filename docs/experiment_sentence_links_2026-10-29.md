# Offline dependencies between statements of one experiment

29 October 2026, Asia/Yekaterinburg. Implements the requested offline adjacent
context experiment. No API/OAuth/DB, retrieval, embedding or production changes.

Changed:

- Added `scripts/experiment_sentence_links.py` and runner
  `scripts/run_experiment_sentence_links.py`. A separate graph records exact
  parent/child statements, explicit bridge cues, original-page anchors and
  blocking diagnostics. Previous quantity/context audits and answer statuses
  remain byte-for-byte unchanged in their sidecar inputs.
- Finite templates cover a single preceding measurement operation followed by
  `before this measurement` / `for the same measurement` / `перед этим измерением`,
  and an impedance-instrument statement followed by recorded spectra. Mere
  adjacency or a shared sample label does not create a dependency.
- Preparation/drying/soaking, competing or mixed sample/property/method cues,
  negation, hypothesis/conditionals, other-work references, paragraph breaks and
  nonunique exact page anchors block the proposal. A reference to a measurement
  cannot itself become an asserted antecedent for a chain. No intervening unit
  is skipped and no transitive inference is performed.
- Proposal states stay unverified. No durations, temperatures, sample identities
  or scientific validity are inherited. Temporal `before` is recorded only when
  explicitly present; generic `for the same measurement` does not establish it.
- Sentence boundaries and semicolon-clause boundaries are reported separately.
  A new finite punctuation splitter fixes semicolons after instrument numbers
  within this sidecar; the earlier frozen splitter and production extraction
  remain unchanged. Saved source text and its offsets are never normalized.
- Frozen protocol and constructed expectations:
  `docs/records/experiment_sentence_links_protocol_v0.1.md` and
  `docs/records/experiment_sentence_links_cases_v0.1.json`.

Tests run:

- **113 tests passed**: 32 new dependency/anchor regressions plus 81 earlier
  quantity/context tests. Final JUnit:
  `output/experiment_sentence_links_tests_20261029_v04.xml`.
- Ruff passed on both new scripts and tests. Strict mypy passed on the pure
  dependency module, one source file; runner-wide typing is not claimed.
- The 21 exposed constructed cases have five declared positive templates and
  sixteen negatives. Observed versus declared link counts: zero mismatches,
  zero proposals on the declared negative cases, zero missed declared links.
  Fourteen attempts were blocked; two cases had no recognized template attempt.
  Those are assistant-authored software expectations, not independent scientific
  annotation, held-out accuracy, recall or a reliability estimate.
- Additional tests verify exact raw statement/bridge/page offsets, ambiguous or
  wrong layer/article quotes, cross-chunk isolation, no baseline mutation,
  criterion versus duration, unresolved sample identity, conditional statements
  and rejection of noun mentions/references as asserted parent operations.
- Verified the frozen parent manifest/bindings, source snapshots, original PDF
  hashes and historic requests/results/attempt records through the parent chain.
  Every returned raw bridge, statement and page anchor was checked against its
  exact registered input. Socket operations were forbidden; runner imports no
  database modules and makes no transport calls.
- Final searchable HTML and JSON:
  `output/experiment_sentence_links_20261029/review_v02/`. Includes eight cases,
  full graph/blocked diagnostics, prior answers and audits, native replies,
  requests, evidence/source registries, all six documents in the eight TAC
  columns, copied bound source snapshot and manifest. Static QA verified eight
  case cards, six TAC rows and 28 existing PDF/page links. Missing/uncollected
  fields remain explicit. Browser rendering/search execution was not tested.
- Earlier failed test logs and `review_v01` remain separate. Initial tests caught
  a semicolon-after-number boundary problem and an unsupported reference variant;
  both were fixed before the final 113-test run. No old artifact was overwritten.

Observed source behavior:

The eight frozen cases yield eleven repeated dependency proposals, all connecting
semicolon clauses. They represent **one unique physical source dependency** by
exact parent/child page anchors: Kayumov page 3, the impedance instrument clause
followed by the spectra-recording/equilibrium-criterion clause. Repetition across
selected chunks and questions does not create independent observations.

No full-stop sentence dependency was established on these real inputs. Such
templates work in the constructed fixtures only; real cross-sentence coverage
therefore remains unvalidated. All eleven proposals leave sample identity
unestablished. The earlier 112 source-candidate context statuses remain unresolved;
the graph does not upgrade them to scientific acceptance.

For the exact-duration questions, the linked child still describes unchanged
spectra as the equilibrium criterion. There is no promotion of the nearby
preparation periods into measurement dwell time and no duration inferred from
thermal equilibrium. The provider-filtered qualitative control retains its
original `blacklist`/HTTP 502; source linkage cannot supply the absent model answer.

The runner also reports the fraction of all punctuation units without a proposed
dependency (about 99.1%). These chunks contain introductions, equations and other
irrelevant units. That fraction is an inventory/grammar-coverage diagnostic,
**not semantic uncertainty, scientific recall or answer accuracy**. For these
proposals, unresolved sample identity is explicit in every case. General
scientific uncertainty cannot be quantified from this exposed set.

Limitations:

Finite adjacent templates do not implement general coreference, event extraction
or scientific entailment. Abbreviations, tables, captions, intervening sentences,
implicit subjects, sample equivalence and more complex syntax remain unsupported.
Coarse cue guards may block valid relations. The impedance/spectra template is a
domain-specific proposal and still needs independent assessment; it does not
establish that every spectrum belongs to the requested measurement.

No independent annotator or model reviewer participated. Constructed expectations
and reused exposed sources cannot establish general error rates. The long-lived
runtime ORM/cache limitation and provider blacklist trigger remain unresolved.
All consumed model slots and budgets remain closed.

Verdict:

The offline sidecar now represents explicit adjacent dependencies and their
source anchors, with counterexample checks and visible coverage limits. It is
suitable for development inspection. Real evidence validates only the narrow
semicolon-clause proposal; full cross-sentence scientific linkage is not
demonstrated. Do not install this as an `/answer` gate or silently remove existing
uncertainties. A broader independently annotated relation set and a justified
semantic method remain prerequisites for runtime decisions.
