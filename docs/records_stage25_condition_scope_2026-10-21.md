# Records stage25: preparation, conditioning and measurement scope

21 October 2026. ARIADNE, `records_condition_scope_v0.1`. Offline source-scope
proposals over frozen stage24 material roles and stage23 relation history.
**Zero new model calls.** No independent scientific accuracy or admission claim.

## Problem and resulting behavior

In 31 saved candidates, the legacy conditioning field selects
`в режиме охлаждения с шагом\n10°C` from a sentence explicitly describing
conductivity measurement. Treating the field name as proof of pre-measurement
conditioning would change the source meaning. The source's argon/dry-box sentence
describes electrode preparation and cell assembly; it does not establish the
environment during conductivity measurement. The final method sentence ends at
`достижения`, without specifying what was attained or establishing equilibrium.

The new standalone projection assigns only literal source-scope proposals. It
retains original fields and selections, separates complete clauses from unsupported
and clipped text, and keeps per-result applicability unknown. The old method,
conditioning and preparation observations are never rewritten or filled.

## Frozen scope and source policy

[Versioned protocol](records/condition_scope_protocol_v0.1.md).

All 37 table candidate versions and all 42 source slots remain visible. They
refer to 36 distinct numeric positions, including a deliberate revisit. Four
shared-block unresolved positions and two printed dashes remain unresolved, with
no invented candidate or zero. This remains a bounded table/source-method audit,
not extraction of every condition from the article or the three-paper corpus.

Before export, 697 frozen input bindings verify, including original PDFs, prior
code/source/run outputs and native candidate artifacts. Table geometry is
regenerated, and every stage24 role projection and its summary are recomputed
and compared exactly. Both prior reports are copied byte for byte. All original
candidate objects equal their saved native artifacts. Prior checks, missing
values, material roles, review/scientific states and diagnostics stay intact.

The bounded Russian cue policy recognizes source clauses for conductivity
measurement, electrode/cell preparation, explicit before-measurement holding,
symmetric-cell setup and impedance instrumentation. It preserves exact text and
offsets, including hyphenation and newlines. Decimal punctuation does not split
the first method sentence. Unknown, reported or explicitly negated cue forms do
not become recognized scope proposals. This is a development policy, not a
general scientific sentence parser or independently validated semantic model.

Five source events are retained from the registered method block:

| Source event | State | Use |
| --- | --- | --- |
| Conductivity measurement, temperature range, cooling step and thermostat | complete_clause_proposal | Method/cooling fragments may propose measurement_protocol |
| Parenthetical explanation of the temperature range | unsupported_clause | Source retained; no selected condition invented |
| Symmetric cells, titanium electrodes and specimen disks | complete_clause_proposal | Setup opportunity retained; no candidate condition inherited |
| Electrode preparation and cell assembly in dry box/argon | complete_clause_proposal | Preparation scope opportunity only; no measurement atmosphere inferred |
| Impedance instrument, frequency range and clipped attainment phrase | incomplete_source | Tail retained; no equilibrium completion or waiting duration inferred |

The complete first sentence can support its literal source scope despite the
incomplete final sentence of the same region. The old paragraph-completeness,
source-order and page-layout diagnostics remain explicit in source_events.json.
No following block is joined, and no missing text is reconstructed.

Each projection accounts for temperature, method, preparation and conditioning
exactly once, either as a selected occurrence or the original missing state.
Field names and model notes cannot establish scope. Exact bound conductivity
header substrings propose measurement_temperature; another column, a general
method range or a stability tolerance cannot substitute. A method or cooling
selection within the complete conductivity clause proposes measurement_protocol.
Preparation atmosphere requires its own preparation clause. Explicit conditioning
requires a before-measurement cue; none is proposed from cooling alone.

Selections crossing multiple clauses remain ambiguous. Those intersecting the
clipped tail remain incomplete_source. Other unsupported fragments remain
unassigned with exact evidence. Proposed scopes retain event IDs and exact source
contexts; the strict schema rejects lost contexts, duplicate/lost fields,
unsupported scientific states and contradictory boundary states.

## Observed outcomes

| Preserved source field | New source-scope outcome | Count |
| --- | --- | ---: |
| temperature | measurement_temperature | 37 |
| method | measurement_protocol | 33 |
| conditioning | measurement_protocol, preserving the original field name/text | 31 |
| preparation | unassigned: selected title adjective `пластифицированной` is not a procedure | 4 |
| preparation | original missing selection retained | 33 |
| conditioning | original missing selection retained | 6 |
| method | original missing selection retained | 4 |

There are 101 scoped proposals, four unassigned selections and 43 missing legacy
selections. No candidate receives a preparation-procedure or conditioning-procedure
binding in this frozen result. The source has a preparation opportunity, but no
such selected native field; it is not filled automatically. Constructed tests
exercise both preparation and explicit conditioning bindings without treating
those test phrases as experimental evidence.

All 37 projections retain measurement_environment=unknown and
equilibration_completion=unknown. Every scoped selection has
applicability=not_evaluated; scientific_admission remains not_evaluated. Shared
source sentences reused by multiple candidates are not independent observations.
The counts are inventory diagnostics, not scientific precision or recall.

## Validation

Changed:

- Added `app/records/condition_scope.py`: strict source-event/selection/projection
  schemas, bounded literal clause scopes, exact table-temperature binding,
  explicit missing/unassigned/ambiguous/incomplete states and conservative claims.
- Added `app/records/condition_scope_export.py` and
  `scripts/records_condition_scope.py`: verified parent import, exact stage24
  replay, preserved reports and deterministic searchable HTML/JSON/schema export.
- Added 53 constructed tests and the versioned protocol. Old scientific modules,
  candidate schemas, native outputs, database/review store, ingestion, OCR,
  retrieval, units and original PDFs remain unchanged.

Tests run:

- Final targeted suite: **53 passed**, 5.81 seconds. It covers cooling versus
  conditioning, field-name/confirmation-note swaps, preparation atmosphere,
  explicit before-measurement holding, unsupported fragments, wrong temperature
  column, decimal boundaries, clipped tails, multi-clause ambiguity, negation,
  reported/unknown cues, missing fields, source/candidate drift, strict contract
  failures, lost context, native/parent identity and repeated exclusive exports.
- `ruff check app scripts tests`: passed.
- `mypy app`: passed, 130 source files.
- Final full regression: **1753 passed**, one existing Starlette/httpx deprecation
  warning, 132.55 seconds. Run outside sandbox with a dedicated stage25 temporary
  directory; the final JUnit result is preserved separately from earlier runs.
- Real final exports are byte-identical. Both parent copies, all 37 native
  candidates, exact source/event/selection contexts and old diagnostics verify.
- Static HTML checks found 42 slot rows, 37 candidate articles, 105 selected-field
  rows and 118 existing local PDF/artifact links. Full source quotes are exact;
  there is search and no writable resolution form. Browser acceptance not claimed.

The first targeted run exposed a fixture construction error: a newly populated
synthetic observation retained its missing status. The helper was corrected;
the failed JUnit output is preserved. Later structural checks added three tests
for context loss/out-of-context selection and contradictory event boundaries.
The final authoritative exports are run_v02 and run_repeat_v02. The earlier
run_v01 and first full suite belong to the pre-hardening revision and are kept
separately, not used as final-code validation.

Limitations:

- Development-exposed single article/source block and literal Russian cues.
  No independent gold, scientific precision/recall, semantic entailment score,
  specimen identity, chemistry validation or whole-article completeness.
- The bounded sentence policy does not cover arbitrary abbreviations, punctuation,
  lowercase sentence starts or all scientific languages/layouts. Unsupported
  contexts remain diagnostic rather than guessed.
- Source scope is not proof that a general method/procedure applies to each
  numeric table result. Preparation atmosphere is not measurement atmosphere.
- The clipped method sentence cannot establish what was attained, equilibration
  completion, waiting duration or a repaired continuation.
- No new extraction/model call, production/review-store write, compulsory per-case
  decision or repair of original missing/shared values occurs.
- Static HTML verification does not establish browser interaction acceptance.

Verdict:

The bounded source-scope stage is complete. Cooling is explicitly distinguished
from pre-measurement conditioning; preparation context cannot become a measurement
environment; clipped text stays incomplete. Existing records and material roles
are preserved as historical proposals. Next work is a separately frozen test of
rule transfer on other article contexts, with explicit abstentions and no assumed
generalization. Independent scientific evaluation remains a separate requirement.

## Local artifacts

`output/records_stage25_20261021/`:

- `run_v02/review.html`, `report.json`: all source slots and candidate projections.
- `run_v02/source_events.json`, `scope_schema.json`, `manifest.json`: source scope,
  exact boundary diagnostics, strict schema and frozen hashes.
- `run_v02/parent_report.json`, `material_roles_report.json`: exact prior reports.
- `run_repeat_v02/`: byte-identical final repeat.
- `postflight_v02.json`: final source/native/history/static-HTML checks.
- `pytest_target_v03.xml`, `pytest_full_v02.xml`: final-code regression results.
- `baseline_final_v01/`, `final_qa_v01.json`: source snapshot and final verification.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_condition_scope --output-dir output/records_stage25_20261021/run_v02
```

Output directories are exclusive. The command is offline and does not call a model.
