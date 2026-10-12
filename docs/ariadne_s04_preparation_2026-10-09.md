# ARIADNE: development cases and S04 preparation

Date: 9 October 2026. Continues [S03/S05](ariadne_s03_s05_execution_2026-10-09.md) and [the development plan](ariadne_development_plan_2026-10-09.md).

## Changed

- Added `source_regions_from_pages` and `source-pages` CLI. Exports separate full-page regions in declared order; rejects empty/non-positive/duplicate page scopes before source reads. Batch failure propagates and no partial bundle is written. Existing single-page CLI output and record schema remain unchanged.
- Added `app/records/review.py` and `review-packet` CLI. Produces an offline Markdown worksheet with observations, missingness, linkage proposals, exact citations/page offsets, source hashes and blank reviewer decisions. It does not implement a decision store, scientific acceptance, independent annotation, or interactive review UI.
- Escapes table markup while keeping exact source quotes in adaptive fenced blocks. Identical evidence spans are referenced consistently; distinct occurrences retain distinct provenance.
- Exported 29 source pages: Sanginov 14, Istomina 14, Sanginov supplement identity page 1. Inspected selected methods/results/reference passages and relevant rendered PDF pages.
- Prepared three manually specified scalar candidates from Sanginov Table 2, with all selected mandatory observations backed by exact source evidence. Footnote d's 20 °C overrides the generic 25 °C column heading. Candidates remain `needs_review`; conditioning history is explicitly ambiguous.
- Prepared a context-only Istomina prior-work case to review reference origin and prevent transferring the present article's Ni/Z-350M method to the conductivity range cited from Sanginov.
- Created [development cases, grouping proposal and annotation protocol](records/li_nafion_development_cases_2026-10-09.md), plus private candidate/context manifests and review worksheets.

No production migration, PDF edit, extraction/OCR/chunking change, retrieval change, bulk facts refresh or automatic commit was performed.

## Tests run

- Batch-source targeted suite: **17 passed in 1.27 s**, including 5 new batch invariants.
- Combined record suites after worksheet implementation: **47 passed in 1.87 s**, including 3 new worksheet checks. Tests cover markup escaping/exact quote preservation, blank decisions, deterministic output and empty context not becoming automatic negative gold.
- Full regression: **658 passed, 1 warning in 7.60 s**.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 81 source files**.
- Three Table 2 proposals: **live evidence validation succeeded**, 4 regions, 3 records; all required observations/linkage proposals present, scientific admission `not_evaluated`.
- Istomina prior-work context: **live evidence validation succeeded**, 3 regions, 0 candidates.
- Source exports and both new candidate/context manifests completed successfully. `git diff --check` reported no whitespace errors in the inspected tracked paths.

The existing Starlette/httpx deprecation warning remains. Live DB checks and the full pytest suite used approved processes outside sandbox because local TCP/async/temp-file restrictions were previously established. No test or scientific metric was inferred from successful artifact creation.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m app.records.cli source-pages `
  --article-id aec95165-f993-4576-9dba-0ec4bb8ecee1 --pages 3 8 11 12 `
  --selection-basis manual_development `
  --selection-note 'Declared development methods/table/conclusion scope; not gold.' `
  --output data/experiments/records/sources/new_methods_table_export.json
.\.venv\Scripts\python.exe -m app.records.cli validate `
  data/experiments/records/development/sanginov2021_table2_candidates_v01.json --live
.\.venv\Scripts\python.exe -m app.records.cli review-packet `
  data/experiments/records/development/sanginov2021_table2_candidates_v01.json `
  --output data/experiments/records/development/new_table2_review.md
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_record_contract.py tests/unit/test_record_sources.py `
  -p no:cacheprovider --basetemp D:/Nafion-RAG/tmp/records_next_review_tests
```

New files are written exclusively; existing outputs are not overwritten. The private manual annotation recipes are preserved beside their artifacts. They intentionally fail if a declared literal fragment is absent/non-unique or if output already exists. They are source-specific development recipes, not production extraction rules.

## Limitations

Three agent-authored manual proposals are not three scientifically accepted records and do not estimate extractor accuracy. No model extraction, automatic table interpretation, numeric conversion, record evaluator, human decision persistence, or user-time experiment was added. The candidate-filled worksheet is review/adjudication material; it must not be presented as blinded gold annotation.

Sample descriptors are row-level, not physical specimen UUIDs. Initial plasticiser fractions are not independent measurements of in-membrane composition. Conditioning/thermal history and general-method-to-point linkage still require scientific review. The source text's apparent `pure PC` in the EC/SL methods passage was observed in both stored text and rendered PDF; it was not silently corrected to SL or used to change component identity.

The related-work family is proposed only. Supplement identity and cited-range repetition are evidenced, but a full corpus duplicate/grouping audit and independent split remain open. Newly modified code fingerprints differ from the historical S03 manifests; those files remain historical captures and were not overwritten. New manifests describe current code; no new sealed source/wheel snapshot was built.

## Verdict

S04 preparation has started: source-backed development cases, a review worksheet generator and an annotation protocol are available. Scientific review, independent gold and corpus split remain open. S05 now supports multi-page context without losing page identity. S11 interactive UI and S12 comparative export remain unimplemented.

Next development task: inspect local model/runtime availability and prepare S06 smoke using these development contexts, while the human review and blinded annotation decisions are pending. Scientific acceptance must not be inferred from completeness or live integrity success.
