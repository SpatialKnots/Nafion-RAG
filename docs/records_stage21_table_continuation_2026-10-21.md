# Records stage21: targeted table continuation and same-article method evidence

21 October 2026. ARIADNE development stage. Algorithm versions:
`records_table_cells_v0.1`, `records_table_continuation_v0.1`.
Reply contract remains `records_multi_fixed_reply_v0.1`.

## Scope and source accounting

The frozen stage20 Kayumov Table 2 context is preserved verbatim: PDF p.6,
stored page offsets 718:2768, 2050 characters. Every request retains the entire
protected table, headers, footnotes and preceding source prose. No protected
table is split into selected rows, and native source order is not repaired.

The new source-coordinate ledger accounts for 21 row labels × 2 conductivity
columns = 42 logical slots:

| Source state | Slots | Meaning |
| --- | ---: | --- |
| Numeric source proposal | 36 | Unambiguous by the declared geometric rule, not independently annotated measurements |
| Explicit dash | 2 | Samples 2 and 15 at −40°C; no conversion to numeric zero |
| Unresolved shared block | 4 | Both columns for samples 12–13; shared physical values are not assigned to the nearest row |

Column bands derive from printed sigma-header centers. Single-row blocks require
positive vertical overlap with the row label. Blocks containing multiple row
labels remain unresolved for all affected row/column slots. Source line offsets,
text hashes, boxes, sample/header/unit/value evidence and stable cell identities
are retained. Unsupported syntax, missing/multiple candidates and unproven
geometry cannot silently become numeric cells.

The four old table proposals are rebound from stage20 raw token coordinates to
their actual source cells, not by string equality. Previous candidate IDs and
all stage20 artifacts are retained. The denominator describes source accounting;
it does not establish independent experimental identity or scientific recall.

## Additional method source and declared targets

R2 is a new explicitly selected complete PDF text block on p.3, offsets
389:1146, 757 characters. Its opening describes transverse membrane conductivity
measurement by impedance spectroscopy. It ends mid-sentence at `достижения`;
the continuation is printed in the other column. Registered source order places
formula fragments after this block. No continuation/formula/conditions are
reconstructed. This development selection does not activate the deferred
stage19 whole-page context.

Original p.3 and p.6 renders were visually inspected. The method block does not
contain a protected table/caption/footnote boundary. Any present method must cite
same-article R2 and supply both R1 and R2 in its conditions-measurement linkage.
These are structural provenance checks, not proof that the generic method
applies to a particular table result.

The first nine previously unproposed numeric cells in row/column order form
three cases of three targets:

1. Sample 3 at −40°C, sample 4 at 30°C and −40°C.
2. Sample 5 at 30°C and −40°C, sample 6 at 30°C.
3. Sample 6 at −40°C, sample 7 at 30°C and −40°C.
4. Deliberate revisit: sample 1 at 30°C with the additional method context.

Targets sent to the model contain cell identities, sample-label token addresses
and column-header token addresses. Expected numeric answers, parsed values or
reference records are not supplied. All other table cells remain in source text
but outside the declared target scope. A repeated cell cannot increase unique
coverage. Exact row/column/value/unit coordinate binding rejects an identical
lexeme selected from another location.

## Frozen inference protocol

[Protocol](records/table_continuation_protocol_v0.1.md). New stage21 budget:
at most four sequential native Responses calls, `gpt-6-astra`, medium reasoning,
8192 output tokens per call / 32768 maximum across calls, 180 seconds per call,
100000 serialized request bytes, no retries or output repair. `store=false`,
`stream=false`, truncation disabled, default service tier. First failure stops
remaining cases and retains raw response/diagnostics.

Prepared inputs and a separate repeated preparation are byte-identical.
537 input/code/artifact bindings include parent source/PDF bytes, previous raw
outputs, the exact ledger, new code/tests/protocol and all request bytes. The full
62-page registry guards the combined decoded source/task and actual user JSON.
Requests are 31737 bytes for each three-target case and 31167 for the revisit.
Source context lengths are 2050 + 757 characters; no complete PDF page is sent.

## Live results

All four declared native calls completed. Every emitted candidate passed exact
source restoration and target row/column/value/unit binding; no retry or output
repair occurred. Model coverage claims refer only to the declared targets.

| Case | Proposals | Missing targets | Coverage claim |
| --- | ---: | ---: | --- |
| remaining_01 | 3 | 0 | claimed_complete_in_context |
| remaining_02 | 3 | 0 | claimed_complete_in_context |
| remaining_03 | 3 | 0 | claimed_complete_in_context |
| method_revisit | 1 | 0 | claimed_complete_in_context |

Nine previously unproposed numeric cells now have candidates. The deliberate
revisit is one additional candidate for an already covered cell, never a new
covered cell: **4 previous + 9 new = 13 covered numeric source slots**, with
**23 numeric slots remaining**. Four shared-block slots and two dashes remain
separate and unchanged. This is not table-wide completeness or scientific recall.

All ten new candidates propose a method with exact R2 evidence and both source
regions in their conditions-measurement linkage. Eight meet the unchanged
technical completeness prerequisites. Two retain missing `medium_composition`
(sample 3 and the sample-1 revisit). These are field-presence/linkage results,
not proof of composition interpretation, method applicability or scientific
correctness. All ten remain `needs_review`, `li_ion_confirmation=not_reviewed`,
and scientific admission is `not_evaluated`.

Technical checks: 138 pass, 2 fail, 80 unknown; these counts are not accuracy.
Known native usage across all four responses: 39050 input tokens, 16260 output
tokens, 55310 total tokens. Output stayed within the 32768-token stage ceiling.
No cost/invoice claim is made.

All four native responses were replayed twice offline. Exact records, regions,
unresolved spans and cell bindings matched saved outputs. Every old ledger field
and all 42 slot identities remained unchanged. Numeric-slot conservation holds:
36 = 13 covered + 23 remaining. All 537 frozen bindings still verify, including
parent PDFs/code/previous responses; no stage20 candidate was overwritten.

Both local HTML files were checked statically: four case rows, 42 ledger rows,
exact source quotes, and ten existing PDF/local links. Browser acceptance is not
claimed.

## Validation

Changed:

- Added source-cell accounting and exact-coordinate binding in
  `app/records/table_cells.py`.
- Added separate frozen continuation preparation/runner and local ledger HTML in
  `app/records/table_continuation.py`, with CLI `scripts/records_table_continue.py`.
- Existing single/multi reply contracts, ingestion, extraction, database schemas,
  scientific scoring and review-store context remain unchanged.

Tests run:

- 34 new constructed counterexample tests passed in 8.30 seconds: identical
  lexemes at wrong coordinates, row/column swaps, shared blocks, dashes, unknown
  syntax, missing/multiple cells, source drift, method evidence, full-page guards,
  duplicate targets/proposals, false completeness, fail-stop and revisit accounting.
- Full suite: **1593 passed**, one existing Starlette/httpx deprecation warning,
  227.21 seconds. Run outside sandbox, with a disposable stage21 basetemp.
- `ruff check app scripts tests`: passed.
- `mypy app`: passed, 123 source files.
- The first targeted run exposed an error-review issue: intentionally corrupted
  source was passed to the old source-preview renderer. Stage21 now retains the
  error report and withholds source preview when frozen integrity fails. The
  targeted suite above was rerun successfully before inference.
- Two independent preparations matched byte for byte; full source/page/request
  checks passed before inference. Original source renders were inspected.
- Native offline replay, parent/PDF/code/request/run hashes, all-slot conservation,
  old-field preservation and static HTML checks passed after all calls.

Limitations:

- One development-exposed table and one same-article method block; no independent
  gold, precision/recall estimate, time-savings estimate or multi-article pilot.
- Generic method joining is a proposed association. The method block has an
  explicit incomplete sentence boundary. Full paragraphs/experimental independence
  are not established by complete PDF blocks or source-cell coordinates.
- Shared rows 12–13 remain unresolved; dashes remain dashes. Untargeted values are
  not negative outcomes or silently accepted measurements.
- Technical completeness and model coverage claims are not scientific admission.
  No review-store revisions or production facts are written by this runner.
- HTML source text, row counts and local paths are checked statically; browser
  acceptance is not claimed. No XLSX is generated.

Verdict:

The bounded stage21 development run is complete and reproducible: nine new
source cells, one deliberate revisit, verified cross-region method provenance,
and separately versioned raw outputs/ledger/review. Scientific acceptance and
table-wide extraction remain open. Next bounded work is the 23 remaining numeric
slots under a new frozen target budget; shared-cell ownership and independent
quality evaluation must remain separate unresolved questions. Do not rerun this
consumed four-call budget or revise these native outputs after the fact.

## Local artifacts

`output/records_stage21_20261021/`:

- `prepared_v01/`, `prepared_repeat_v01/`: frozen plan, exact sources/requests,
  source ledger, method diagnostics, full page registry and manifests.
- `preflight_v01.json`: byte-identical preparation, guard results and target list.
- `validation_v01.json`: observed test/check commands and outcomes.
- `method_page.png`: read-only original p.3 render.
- `live_v01/`: native responses and target/candidate diagnostics as produced.
- `live_v01/ledger.html`: all 42 source slots, old/new proposals and outcomes.
- `live_v01/review.html`: all four cases, exact source, fields, raw replies/checks.
- `postflight_v01.json`: twice-replayed records, literal values, methods, usage,
  technical checks, conservation and static HTML results.
- `baseline_final_v01/`: source-only reproducibility snapshot; corpus, PDFs,
  databases, secrets, weights and generated outputs are excluded.
- `final_qa_v01.json`: final snapshot/source/code hash verification and test results.

Commands:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_table_continue prepare --previous output/records_stage20_20261021/live_v01 --windows output/records_stage19_20261021/run_v01 --output-dir output/records_stage21_20261021/prepared_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_table_continue run --prepared output/records_stage21_20261021/prepared_v01 --output-dir output/records_stage21_20261021/live_v01
```

Output paths are exclusive: these commands document the performed preparation/run,
not instructions to overwrite or repeat the consumed live budget.
