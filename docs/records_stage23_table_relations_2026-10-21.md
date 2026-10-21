# Records stage23: table relation evidence audit

21 October 2026. ARIADNE, `records_table_relations_v0.1`. Offline source-coordinate
and literal-cue audit; **zero new model calls**. This is not independent scientific
annotation, accuracy evaluation or scientific acceptance.

## Scope and reproducibility

All 37 table candidate versions are retained: four from stage20, ten from stage21
(including the deliberate revisit), and 23 from stage22. They address 36 distinct
numeric source positions. All 42 logical slots remain visible, including four
shared-block unresolved positions and two dashes. The three non-table stage20
cases are outside this declared audit scope; their artifacts are still hash-bound.

The 13 table native responses were replayed and compared with exact saved reply,
records, source regions, unresolved spans and cell bindings. The complete replayed
identity set reconciles with all three ledger histories. The base cell ledger was
regenerated from the frozen stage19 source geometry, and every source field was
compared. Each earlier per-slot field/candidate identity and each previous check
was preserved. Earlier source/code/PDF/run manifests and new audit code/test/
protocol hashes verify. No old module or candidate was changed to run this audit.

Two separate exports are byte-identical, including their manifests. Exact source
quotes and original PDF page links are retained. Static HTML verification found
42 slot rows, 37 candidate versions and 113 existing local/PDF links. Browser
acceptance is not claimed.

## What is checked

[Versioned protocol](records/table_relations_protocol_v0.1.md).

- Sample/value source coordinates remain bound to the ledger cell.
- The literal `пластификатора` header defines the proposed composition column;
  `(масс. доли)` is a separate source basis, not the neighbouring mass-percent
  column. Each row composition uses source block, header interval and y overlap.
- A literal table section heading proposes component order for the row group.
  Unknown/tied headings and shared blocks remain unsupported; no abbreviation,
  chemical identity or numeric pure-solvent fraction is inferred.
- Actual raw token selections are compared with those source locations.
  Identical ratios elsewhere do not substitute. Field citations are checked for
  sample, composition, plasticiser header, basis and mixture-group endpoints.
- Method selection requires same-article/different-page source and the literal
  impedance-spectroscopy cue. Its per-result applicability remains unknown, and
  the selected method block's incomplete sentence boundary stays explicit.
- Each linkage role's own evidence is checked for its actual selected endpoints.
  Coordinate coverage is not a scientific-support verdict.

## Observed outcomes

| Check | Observed result | Interpretation |
| --- | --- | --- |
| Sample/value cell | 37 coordinate matches each | Literal source positions, not independent experiment identities |
| Row composition selection | 35 exact matches; 2 not proposed | Missing fields remain missing, even with a possible source cell |
| Medium/component label | 30 exact matches; 3 boundary differences; 4 not proposed | Printed plasticiser group/code only; semantic field mapping not established |
| Composition basis | 37 coordinate matches | Printed mass-fraction wording retained; no conversion |
| Composition field citation chain | 35 covered; 2 not proposed | Required source endpoints occur in that field's citations |
| Method literal cue | 33 present; 4 not proposed | Generic same-article method source, not proof of applicability |
| Each of three linkage roles | 37 endpoint-covering proposals each | Quoted endpoint coverage only |
| Plasticiser/medium semantics | 37 unknown | No external environment/final membrane interpretation admitted |
| Per-result method applicability | 37 unknown | No scientific acceptance introduced |

Aggregate diagnostic counts are 176 coordinate matches, 146 endpoint-covering
results, 33 literal method cues, 12 not-proposed findings, 74 scientific unknowns
and three different-coordinate findings. These totals are **not** precision,
recall or a chemical-correctness score. A candidate contributes multiple findings.

The three boundary differences are all in stage22 `remaining_10`: sample 19 at
−40°C and sample 20 at both temperatures. The actual raw medium span is the
complete heading `Смеси SL/EC/G2`, page offsets 2427:2441. The audit's tighter
component reference is `SL/EC/G2`, 2433:2441. Both identify the same printed group;
the difference is span width, not evidence of a wrong row or a scientific error.
Native selections are retained verbatim. No automatic prefix removal, record
rewrite or post-hoc output repair was performed.

The sample-1/30°C revisit has two candidate versions. Five fields differ:
`conditioning`, `medium`, `medium_composition`, `method`, `preparation`.
For example, stage20 selects the printed `SL` code as medium_composition, while
the stage21 revisit selects it as medium and leaves medium_composition missing.
The revisit also receives the separate method region and selects its method/
cooling text. These are different proposals with different available contexts;
they are not automatically conflicting facts, independent measurements or a
reason to replace the old version with the new one.

## Validation

Changed:

- Added `app/records/table_relations.py`: geometric/literal source expectations,
  exact-occurrence diagnostics, role-specific citation coverage and history
  comparison. Scientific support remains not_evaluated for every finding.
- Added `app/records/table_relations_export.py` and
  `scripts/records_table_relations.py`: frozen native-history reconciliation and
  separate searchable HTML/JSON export for all candidate versions and source slots.
- Existing schemas, native outputs, readiness/check policies, database/review store,
  ingestion, extraction, numeric values/units and stage20–22 code are unchanged.

Tests run:

- 31 new constructed counterexample tests passed in 1.97 seconds. They cover
  identical ratios at other coordinates, reversed component-group order,
  mass-percent versus fraction basis, partial/broad spans, missing/ambiguous
  source cues, unknown section barriers, shared blocks, missing fields, unrelated
  method text, wrong article/page, incomplete role citations, source drift,
  manifest failure/history loss, context differences and HTML escaping.
- `ruff check app scripts tests`: passed.
- `mypy app`: passed, 126 source files.
- Full regression suite: **1663 passed**, one existing Starlette/httpx deprecation
  warning, 241.95 seconds. Run outside sandbox, with a dedicated disposable
  stage23 temporary directory; JUnit results are preserved locally.
- All 13 native table batches replayed exactly; old slot fields/history and all
  37 candidate versions reconcile. Original PDF and frozen source/code/run hashes
  verify. Both audit exports match byte for byte; static HTML/source/link checks pass.

Limitations:

- Development-exposed source, rules and expected cues; no independent gold,
  scientific precision/recall, chemistry validation or human time-savings estimate.
- Matching the plasticiser column does not establish an external measurement
  medium, final membrane composition or exact specimen identity. All such semantic
  mappings remain unknown. A pure-solvent code is not a supplied numeric ratio.
- Matching a general method phrase and its cited endpoints does not establish
  per-result applicability; the selected source block remains mid-sentence.
- Full/partial span boundary diagnostics are not automatic error labels. Unknown
  source layouts remain unresolved; shared cells and dashes are not repaired.
- No scientific admission, writable resolution form, compulsory per-case user
  decision, new model inference or production/review-store write occurs.
- Static HTML checks do not establish browser acceptance or whole-article coverage.

Verdict:

The offline relation audit is complete and deterministic. It preserves all 37
candidate versions, verifies literal source/citation coverage, exposes the three
harmless group-span boundary differences and the revisit's field-role differences,
and retains scientific unknowns. Next development work is an explicit versioned
field-role distinction between printed plasticiser composition and measurement
environment, with separate independent quality evaluation. Current records must
not be silently reinterpreted or admitted as facts.

## Local artifacts

`output/records_stage23_20261021/`:

- `run_v01/report.json`, `run_v01/review.html`, `run_v01/manifest.json`:
  all 42 source slots, all 37 unchanged candidates/checks/raw selections, source
  context proposals, new diagnostics, history comparison and frozen input/code hashes.
- `run_repeat_v01/`: byte-identical independent export.
- `postflight_v01.json`: native replay/identity/source validation, exact rule
  outcomes, literal boundary interpretation, history difference and HTML checks.
- `pytest_unit_v01.xml`: 31 new counterexample test results.
- `pytest_full_v01.xml`: successful full regression result.
- `baseline_final_v01/`: source-only reproducibility snapshot; private corpus/PDFs,
  databases, credentials, model weights and generated outputs are excluded.
- `final_qa_v01.json`: final snapshot/current-source/frozen-code and regression checks.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_table_relations --output-dir output/records_stage23_20261021/run_v01
```

Output directories are exclusive. This is an offline export and never calls a
model. Original stage20–22 inference budgets remain consumed and unchanged.
