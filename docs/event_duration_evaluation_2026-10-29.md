# Offline operation-duration evaluation infrastructure

29 October 2026, Asia/Yekaterinburg. Continued development after the real-excerpt
dependency check and the rejected event-extraction pilot. This stage adds a
reproducible comparison against explicit source annotations. It does not add a
semantic extractor or alter `/answer`, the provider, prompts, schemas, retrieval,
database, indices, original PDFs or any closed live-call budget.

Changed:

- Added `scripts/event_duration_evaluation.py`: validates exact catalogs,
  text hashes, operation anchors, unique operation IDs, explicit duration owners
  and the complete annotated/unannotated atom partition. Reference contradictions
  fail visibly. An operation may own multiple atoms; different operation owners
  remain separate even within the same source statement.
- Added `docs/records/event_duration_reference_v0.1.json`: three exposed pilot
  excerpts, six operation anchors and four duration-owner annotations. Labels
  were authored by the assistant after inspecting the sources and model replies;
  they are post-hoc preliminary interpretation, not independent gold. Two
  annotated target operations have no numeric duration in the selected excerpt.
  This does not establish absence elsewhere in the article or corpus.
- The evaluator reproduces the unchanged original parser decision separately
  from raw-duration-field comparison. It never fills a diagnostic, changes a
  status/ID or repairs rejected output. Unknown/invalid selections are unscored;
  known but unannotated atoms are not treated as negatives. Filtered, incomplete,
  malformed or structurally invalid replies cannot receive duration comparison.
- Added `scripts/run_event_duration_evaluation.py`: prohibits socket operations,
  verifies frozen pilot inputs/manifests and original PDF identities, compares
  exact excerpts/full pages, reproduces the historical rejection reasons, and
  writes a separate report plus source snapshot and output manifest. The
  reference builder and its bindings are archived in
  `output/event_duration_evaluation_20261029/build_reference_v01.py` and
  `build_manifest_v01.json`.
- Final HTML: `output/event_duration_evaluation_20261029/review_v01/review.html`.
  Includes all three questions, exact excerpts, raw native replies, catalogs,
  preliminary annotations, original rejections, full registered pages and all
  three source works in the agreed eight TAC columns. Missing/uncollected
  metadata remains explicit. Search is included; local PDF links retain pages.

Tests run:

- **57 affected tests passed: 33 new evaluator controls plus 24 existing
  event-pilot/schema controls.** Final JUnit:
  `output/event_duration_evaluation_regression_20261029_v03.xml`.
  Controls cover different operations in one statement, multiple durations of
  one operation, missing/uncertain values, unannotated atoms, wrong-operation
  values, repeated selections, raw inspection without promoting rejected output,
  exact input immutability, invalid references/catalogs/IDs/order/contexts and
  filtered/incomplete/malformed JSON.
- Initial new-only run passed 33 tests with a pytest cache permission warning.
  Two broader attempts each passed 54 tests but had three fixture setup errors
  because the system pytest temporary directory was inaccessible. One of these
  attempts ran with execution escalation; it still could not read that directory.
  Both failed attempts are preserved in the `v01` and `v02` regression JUnit files.
  The final run used a verified, previously absent stage-local `--basetemp` and
  disabled the optional cache provider. No test assertion was weakened and no
  temporary directory outside the project was deleted.
- Ruff passed for the evaluator, runner, tests and archived reference builder.
  Strict mypy with silent imported modules passed for the evaluator module,
  one source file; runner-wide typing is not claimed.
- Offline runner completed on all three saved native replies and reproduced all
  three original parser errors verbatim. Fresh PyMuPDF text extraction matched
  all three selected original PDF pages; original PDF hashes, excerpt offsets
  and quote/page hashes matched. Python/PyMuPDF versions are in `report.json`.
- Static HTML QA checked three case cards, three TAC rows and six existing
  original-PDF links. Browser rendering and execution of the search field were
  not tested. Socket operations were prohibited during the runner; new model,
  OAuth and database operations were not performed.

Observed comparison with these preliminary annotations:

- The three raw target duration fields agree with the limited reference: `2 часа`
  for the dispersion-cell hold, no selected numeric duration for equilibrium
  waiting, and no selected numeric duration for HCl protonation. This is only
  a field comparison. **All three original event outputs remain rejected.**
- One other-event record selects both `D2 = 1 ч` (air drying) and
  `D3 = 2 недели` (storage over P2O5). The evaluator reports two annotated operation
  owners despite the values sharing `S3`. It does not infer those owners itself.
- The dispersion case repeats `D1` in the target and another event. This is
  reported as a repeated selection, not independently declared a scientific
  error: identity and duplicate-event semantics have not been evaluated.
- The criterion case retains four status/ID contradictions in its raw fields;
  the two other cases retain the original blank-diagnostic rejection. Raw field
  agreement does not erase any of these failures or validate event kind/sample.

Limitations:

This is evaluation infrastructure using explicit assistant-authored labels, not
an automatic operation assignment method, independent accuracy result or runtime
admission gate. The same three responses were already inspected; no held-out
evaluation or independent reviewer participated. Numeric equality, shared
statements and exact source quotations cannot establish sample identity, method,
conditions, operation identity, causal links or question coverage. Units/bounds
interpretation, complete event extraction and requested-information semantics
beyond the supplied target-operation label remain unevaluated. The inherited
duration inventory is finite. Runtime ORM/cache limitations and the earlier
provider-filter trigger remain unresolved. All live budgets remain closed.

Verdict:

The offline comparison stage is complete and exposes the already observed
drying/storage combination reproducibly without changing historical outcomes.
A separate semantic extraction method and independent source annotation/evaluation
remain necessary before scientific acceptance or integration into `/answer`.
