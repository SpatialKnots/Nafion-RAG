# Records stage24: explicit material and environment roles

21 October 2026. ARIADNE, `records_material_roles_v0.1`. Separate offline
source-label proposals over the frozen stage23 relation audit. **Zero new model
calls.** This does not establish scientific accuracy or admit experimental facts.

## Scope and preservation

All 37 table candidate versions remain visible over all 42 source slots: four
stage20 versions, ten stage21 versions, and 23 stage22 versions. They address
36 distinct numeric positions, including the deliberate sample-1 revisit.
The four unresolved shared-block positions and two printed dashes remain visible
without invented candidates or zero values. Non-table stage20 cases are outside
this declared overlay scope; their artifacts remain in the frozen input bindings.

The stage23 report is copied byte for byte to `parent_report.json`. Every
candidate equals its original saved native artifact; original fields, notes,
checks, scientific/review states, source coordinates, history and diagnostics
remain intact. The new schema is standalone, with no database migration or
change to RecordCandidate, extraction, OCR, retrieval or old execution modules.

The exporter verifies 687 frozen input bindings, old source/code/run/output
hashes and original PDF identities. The table relation map is regenerated from
frozen stage19 geometry and must equal the parent map before any role projection.
Two separate exports are byte-identical, including their manifests.

## Explicit role policy

[Versioned protocol](records/material_roles_protocol_v0.1.md).

Each candidate projection contains five roles. Populated roles are explicitly
`source_label_proposal`; unknown roles have no asserted bindings. Every role's
scientific_support and the projection's scientific_admission remain not_evaluated.

- `plasticiser_components`: selected printed component code/order or the complete
  same-group heading, supported by the plasticiser column and row/group context.
- `plasticiser_composition`: selected exact row ratio under that header, in a
  recognized mixture group with the printed fraction basis. No ratio parsing,
  summation, normalization or conversion is performed.
- `plasticiser_basis`: selected literal mass-fraction wording for the column;
  the neighbouring W mass-percent column cannot substitute.
- `membrane_composition`: unknown in this policy.
- `measurement_environment`: unknown in this policy.

Classification follows actual source occurrences, not the legacy field name or
the model's notes. Each binding retains its source field, exact selected text and
coordinates, separate reference span and exact supporting context spans. A pure
solvent code supplies a component label, never an inferred fraction of one.
Missing fields stay missing despite available source cells. Unrecognized source
selections are retained unassigned with diagnostics rather than forced into a role.

The full heading `Смеси SL/EC/G2` is allowed as an explicitly documented boundary
variant of its component reference `SL/EC/G2`. All three such native selections
retain their complete text and offsets. The three old stage23 different-coordinate
findings remain in the unchanged parent report; this new rule neither removes
those findings nor rewrites the native candidates.

## Observed outcomes

| Role | Source-label proposals | Unknown | Interpretation |
| --- | ---: | ---: | --- |
| Plasticiser components | 37 | 0 | 33 medium selections and four older medium_composition selections |
| Plasticiser composition | 31 | 6 | Four selected pure codes supply no numeric ratio; two selections were missing |
| Plasticiser basis | 37 | 0 | Selected printed wording, without conversion |
| Membrane composition | 0 | 37 | No final membrane composition inferred |
| Measurement environment | 0 | 37 | No environment inferred from plasticiser or preparation/method text |

There are 105 preserved legacy-selection bindings: 102 exact source labels and
three complete-group-heading variants. Six original legacy selections remain
missing: four stage20 medium fields and two stage21 medium_composition fields.
There are no unassigned selections in this particular frozen run; constructed
negative cases verify that unsupported selections remain visible and unassigned.
These counts are not scientific precision, recall, independent measurements or
proof of chemically correct component interpretation.

The searchable read-only HTML contains 42 slot rows, 37 candidate articles and
185 role rows. Each article exposes the old fields, full parent audit, new typed
projection and diagnostics. Two exact source contexts and original PDF page links
remain available. Static checks found 116 working local artifact/PDF links.
Browser acceptance is not claimed.

## Validation

Changed:

- Added `app/records/material_roles.py`: strict five-role projection schema,
  conservative source-coordinate policy, candidate fingerprints, explicit missing
  and unassigned selections, and rejection of unsupported scientific states.
- Added `app/records/material_roles_export.py` and
  `scripts/records_material_roles.py`: parent verification, deterministic separate
  JSON/schema/HTML export, complete parent byte copy and frozen manifests.
- Added 37 constructed counterexample tests and the versioned protocol.
  Existing records, native outputs, prior code and original PDFs are preserved.

Tests run:

- New targeted tests: **37 passed**, 6.14 seconds. Cases include pure code versus
  ratio, field-name swaps, complete-heading/basis boundaries, identical ratios in
  other rows, component order, mass percent, partial basis, unrelated method and
  preparation atmosphere, misleading model notes, missing selections, unsupported
  source layouts, source/candidate drift, strict-schema contradictions, parent
  history/manifest failures, exclusive output and byte-identical export.
- `ruff check app scripts tests`: passed.
- `mypy app`: passed, 128 source files.
- Full regression suite: **1700 passed**, one Starlette/httpx deprecation warning,
  144.28 seconds. Run outside sandbox with a dedicated stage24 temporary directory;
  JUnit results are preserved locally.
- Repeated real offline exports match byte for byte; strict projections/schema,
  all 37 original native candidates, exact source spans, parent bytes, frozen
  hashes, all source slots, old boundary diagnostics and static HTML links verify.

Limitations:

- Development-exposed article, geometry, source cues and policy. No independent
  gold or scientific precision/recall; no chemical lookup or scientific admission.
- The policy handles only the three existing legacy material fields and the
  declared table context. It does not extract membrane composition, measurement
  environment or new conditions from the surrounding article.
- General method text does not establish per-result applicability. Preparation
  atmosphere does not establish atmosphere during conductivity measurement; the
  old method source still has an explicitly incomplete sentence boundary.
- Source-label roles do not prove specimen identity, final membrane composition,
  component chemistry, mixture arithmetic or whole-article completeness.
- No production/review-store write, mandatory per-case decision, writable
  resolution form, new inference or repair of shared cells/dashes occurs.
- Static HTML checks do not establish browser interaction acceptance.

Verdict:

The bounded role-distinction stage is complete: legacy fields are preserved and
their printed plasticiser roles are explicit in a separate versioned artifact.
Membrane and measurement-environment roles remain unknown. Next bounded work is
source-supported separation of preparation, conditioning and measurement
conditions, preserving ambiguous scope and incomplete source boundaries. A
separate independent scientific evaluation remains necessary; current records
must not be silently admitted or treated as independently validated facts.

## Local artifacts

`output/records_stage24_20261021/`:

- `run_v01/review.html`: all source slots and candidate versions, searchable.
- `run_v01/report.json`: typed projections and summary.
- `run_v01/parent_report.json`: unchanged stage23 report, including sources,
  candidate history, raw selections and old diagnostics.
- `run_v01/role_schema.json`, `run_v01/manifest.json`: strict contract and hashes.
- `run_repeat_v01/`: byte-identical second export.
- `postflight_v01.json`: real frozen-data/source/identity/static-HTML checks.
- `pytest_target_v01.xml`, `pytest_full_v01.xml`: targeted and full test results.
- `baseline_final_v01/`: source-only reproducibility snapshot.
- `final_qa_v01.json`: final snapshot, frozen-parent and regression verification.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_material_roles --output-dir output/records_stage24_20261021/run_v01
```

Output directories are exclusive. This offline command does not call a model.
Earlier source snapshots, responses and budgets remain separate.
