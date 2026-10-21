# Records stage22: remaining numeric table slots

21 October 2026. ARIADNE development. Algorithm
`records_table_remaining_v0.1`; unchanged source-cell algorithm
`records_table_cells_v0.1` and reply `records_multi_fixed_reply_v0.1`.

## Declared scope

Continue the immutable stage21 ledger for Kayumov Table 2. This is a fixed
source-cell development task, not whole-article extraction or independent
scientific evaluation. All 42 logical source positions remain represented:
36 numeric source proposals, two explicit dashes, four shared-block unresolved
positions for rows 12–13. Thirteen distinct numeric positions already carry
proposals from previous stages; the stage21 revisit does not add a source cell.

The new target set is exactly the other 23 numeric positions, ordered by source
row/column. No already covered, dash, shared or unsupported position is targeted.

| Case | Declared source positions |
| --- | --- |
| remaining_04 | Sample 8 at 30°C / −40°C; sample 9 at 30°C |
| remaining_05 | Sample 9 at −40°C; sample 10 at 30°C / −40°C |
| remaining_06 | Sample 11 at 30°C / −40°C; sample 14 at 30°C |
| remaining_07 | Sample 14 at −40°C; samples 15 and 16 at 30°C |
| remaining_08 | Sample 16 at −40°C; sample 17 at 30°C / −40°C |
| remaining_09 | Sample 18 at 30°C / −40°C; sample 19 at 30°C |
| remaining_10 | Sample 19 at −40°C; sample 20 at 30°C / −40°C |
| remaining_11 | Sample 21 at 30°C / −40°C |

## Parent/source integrity and preparation

Before target preparation, all four stage21 native responses were replayed and
compared with exact records, source regions, unresolved spans and cell bindings.
Replayed record identities were reconciled against the parent proposal ledger;
every inherited source field was checked. Parent artifacts and frozen parent
code remain unchanged. The new runner is separate because editing stage21-bound
code would invalidate its frozen manifests.

Every request reuses exactly the two stage21 regions: R1 is the entire protected
table and surrounding source text on PDF p.6 (page offsets 718:2768, 2050
characters); R2 is the complete selected method block on p.3 (389:1146, 757
characters). Source order, headers and footnotes are preserved. The R2 sentence
continues outside its block; omitted text is not reconstructed. No new source
selection, paragraph repair, numeric conversion, unit conversion or output-schema
change is performed.

Target metadata supplies stable cell identity plus sample-label and column-header
token addresses; it does not supply numeric answers or reference records. The
unchanged prompt and validator require the actual value/sample/temperature/unit
coordinates for the targeted cell. Identical lexemes at another location cannot
substitute. A present method must cite same-article R2 with both R1/R2 in its
conditions-measurement linkage; applicability is still a scientific question.

Two independent preparations match byte for byte. The frozen stage22 manifest
has 602 inherited/new input/code/artifact bindings. Its unsent registry includes
all 62 source pages. Guards passed on combined decoded source/task text and
actual user-message JSON for all eight cases. The seven three-target requests
are 31737 bytes each; the final two-target request is 31452 bytes.

[Protocol](records/table_remaining_protocol_v0.1.md): a new maximum of eight
sequential native Responses calls / 65536 output tokens. Same `gpt-6-astra`
development alias and fixed HTTPS transport, medium reasoning, 8192 output
tokens/call, 180 seconds/call, 100000-byte request ceiling, store=false,
stream=false, truncation disabled, default tier. No retries, alternate inputs,
output repair or automatic resumption. First failure stops remaining cases.

## Live results and replay

All eight declared native calls completed: seven cases returned three proposals
each, and the final case returned two. All 23 emitted candidates passed exact
source restoration and target row/column/value/unit binding. No target was omitted;
all eight replies claimed complete coverage of their own declared target set.
No retry, alternate request, schema repair or budget increase occurred.

The additive ledger now accounts for **13 previously covered + 23 newly covered =
36 covered numeric source positions**, with zero remaining numeric targets under
the declared geometric rule. All 42 positions remain present: the four shared
positions for rows 12–13 are still unresolved, and the two dashes remain dashes.
No scientific recall or whole-article completeness follows from this accounting.

All 23 new candidates have exact same-article R2 method evidence and the required
R1/R2 linkage provenance. All 23 meet the unchanged technical field/link presence
prerequisites. They still have `review_state=needs_review`,
`li_ion_confirmation=not_reviewed`, scientific admission `not_evaluated`.
Technical checks yielded 322 pass and 184 unknown, with no fail; these are not
precision/recall or chemical-correctness metrics. Earlier incomplete candidates
remain unchanged rather than being silently backfilled.

Printed values are preserved literally, including sample 14's `6.3 × 10–4`
under the −40°C column. No apparent source peculiarity is corrected, normalized
or accepted scientifically by the coordinate validator.

Known native usage across all eight responses: 78380 input tokens, 35551 output
tokens, 113931 total tokens. Output remained within the declared 65536-token
ceiling. No invoice/cost claim is made. The model alias and returned metadata are
preserved; reproducibility here means frozen inputs plus exact native-response
replay, not a guarantee of identical future inference.

All eight native responses were replayed twice offline. Exact records, source
regions, unresolved spans and cell bindings matched saved outputs. Every old root
ledger field/summary and every old per-slot field/candidate identity remained
unchanged. The final history and per-target outcomes reconcile with saved native
outputs; numeric conservation is 36 = 13 + 23 + 0. All 602 frozen source/code/
parent/request bindings verify after the run.

Static HTML checks passed: eight case rows, 42 ledger rows, exact expandable
source quotes, and 18 existing local/PDF links. Browser acceptance is not claimed.

## Validation

Changed:

- Added `app/records/table_remaining.py` and CLI
  `scripts/records_table_remaining.py` for parent replay/reconciliation, the
  exact 23-target partition, guarded calls and additive ledger accounting.
- Added separate `stage22_proposals` and `stage22_outcomes` per slot and a
  `stage22_summary` / `continuation_version`. The old ledger fields and summary
  remain historical evidence. HTML explicitly displays the current stage summary
  while preserving old details; it does not rewrite the stored parent summary.
- Existing reply contracts, scientific checks, ingestion, extraction, source
  PDFs, database schemas, review store and earlier execution code are unchanged.

Tests run:

- 39 new constructed counterexample tests passed in 49.58 seconds: prior/revisit
  accounting, parent replay/ledger mismatch, repeated identities, source drift,
  resealed metadata policy changes, disjoint/exhaustive target partition, ordering,
  final two-target case, early/late fail-stop, omitted targets, false completeness,
  native response retention, immutable outputs and exact parent-field preservation.
- `ruff check app scripts tests`: passed.
- `mypy app`: passed, 124 source files.
- Full regression suite: **1632 passed**, one existing Starlette/httpx deprecation
  warning, 253.08 seconds. Run outside sandbox, with a dedicated disposable
  stage22 temporary directory; JUnit results are preserved locally.
- Earlier test-only fixture errors were corrected before inference: the SourcePage
  field is `page`, and deliberately corrupted fixtures require an overwrite helper
  rather than production `write_json`, which intentionally creates files exclusively.
  The final 39-test run passed after those corrections. No production guard was
  relaxed to accommodate a fixture.
- Parent raw replay/reconciliation, all frozen bindings, target partition, two
  byte-identical preparations and request/page guards passed before inference.
- All eight native responses replayed twice exactly after inference; parent-field
  and candidate-identity preservation, 42-slot inventory, numeric conservation,
  per-target outcomes, source/code/run hashes and static HTML checks passed.

Limitations:

- This is one development-exposed table; source positions do not establish
  independent experiments, scientific precision/recall or time savings.
- Rows 12–13 remain shared/unresolved; dashes remain dashes. They are not zeros,
  silently inferred row assignments or counted numeric outcomes.
- A complete stored PDF block need not be a complete paragraph. Method association
  and printed plasticiser-composition interpretation remain proposals; neither
  literal coordinates nor required-field presence prove chemical correctness.
- Model completeness claims apply only to individual declared target sets.
  Scientific admission remains `not_evaluated`, candidates remain unreviewed.
- Static HTML/source/path checks do not establish browser acceptance. No XLSX,
  database/review-store write or mass run of all 352 article contexts is performed.

Verdict:

The bounded stage22 run is complete: all 23 remaining numeric target positions
now have literal source-bound candidate proposals. The ledger's 36 numeric
positions are accounted for, without declaring shared cells, dashes, chemical
interpretation or experimental identity resolved. Independent scientific quality
evaluation and source-supported review of sample/composition/method associations
remain the next work; current candidates are not automatically admitted facts.
The eight-call budget is consumed and must not be resumed or rerun as inference.

## Local artifacts and reproduction boundary

`output/records_stage22_20261021/`:

- `parent_audit_v01.json`: parent replay/accounting and declared cell IDs.
- `prepared_v01/`, `prepared_repeat_v01/`: frozen target/source/request/registry
  inputs, ledger, plan and manifests.
- `preflight_v01.json`: byte equality, old-field preservation and all request guards.
- `pytest_new_v03.xml`: final successful new counterexample run.
- `pytest_full_v01.xml`, `validation_v01.json`: full-suite result and observed
  validation commands/outcomes.
- `live_v01/`: exclusive native-response and candidate output directory.
- `live_v01/ledger.html`: all 42 source positions, old/new histories and outcomes.
- `live_v01/review.html`: all eight cases, exact sources, raw replies and checks.
- `postflight_v01.json`: exact double replay, values/methods, technical diagnostics,
  preserved history, conservation, HTML links and actual usage totals.
- `baseline_final_v01/`: source-only snapshot; private corpus/PDFs, databases,
  credentials, generated outputs and model weights are excluded.
- `final_qa_v01.json`: final snapshot/current-source/frozen-code checks and tests.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_table_remaining prepare --parent-prepared output/records_stage21_20261021/prepared_v01 --parent-run output/records_stage21_20261021/live_v01 --output-dir output/records_stage22_20261021/prepared_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_table_remaining run --prepared output/records_stage22_20261021/prepared_v01 --output-dir output/records_stage22_20261021/live_v01
```

These commands record the performed run; output directories are exclusive and
the live budget must not be replayed as new inference. Offline native-response
replay is the reproducibility check, not a new model call.
