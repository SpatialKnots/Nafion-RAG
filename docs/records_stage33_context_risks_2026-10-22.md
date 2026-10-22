# Stage33: diagnostic localization of context risks

22 October 2026. Version `query_context_risks_v0.1`.
[Prospective protocol](records/context_risks_protocol_v0.1.md),
[preserved stage32](records_stage32_block_context_2026-10-22.md).

Changed:

- Added a separate offline context-risk auditor and `scripts.context_risks`
  prepare/run commands. No production API, selection policy, database schema,
  extraction, OCR, retrieval, qualifier, ceiling or generation path changed.
- Replays the preserved stage32 builder exactly, then compares fresh selected-PDF
  registrations with the frozen page plans, including blocks, protected groups
  and all visual assets. All parent results and source files remain immutable.
- Describes the existing whole-core, one-neighbor and transitive protected-group
  closure on deferred pages too. These are diagnostic windows, never candidate
  evidence. No anchor means no fallback window; unproven mapping prevents windows.
- Reports every asset/window geometric relation, including distant objects and
  unknown geometry. Touching edges and degenerate vector paths count as
  intersections; participating protected-group boxes also participate. Scientific
  relevance remains unknown even when bounding boxes do not intersect.
- Retains exact structural-trigger blocks, quotes, offsets and hashes. Trigger
  location does not prove its semantic extent. Aggregate numeric-page diagnostics
  that cannot be reproduced within individual blocks remain explicitly unlocalized.
  All old diagnostics, refusals and page-coverage results remain visible.
- Produces searchable local HTML with all four questions, 35 page tables, full
  expandable context/registry text and original-PDF/native-result links. The full
  machine-readable report and manifest accompany each independent output.

## Frozen observations

The unchanged stage32 scope contains **19 Evidence objects / 193240 raw
characters**, **35 page occurrences** and **863 block occurrences**. These are
development questions already exposed in earlier stages, not independent gold.
No retrieval, query embedding, database operation or generative API call ran.

| Preserved question | Page occurrences | Diagnostic windows | Asset occurrences | Trigger records | Window unions covering pages |
| --- | ---: | ---: | ---: | ---: | ---: |
| conductivity_protocol | 10 | 150 | 1161 | 32 | 6 |
| dsc_protocol | 7 | 0 | 8 | 2 | 0 |
| preparation_atmosphere | 8 | 165 | 115 | 9 | 6 |
| absent_material | 10 | 212 | 265 | 47 | 10 |
| Total | 35 | 527 | 1549 | 90 | 22 |

Asset occurrences comprise **26 raster images and 1523 vector drawings**, including
small paths and repeated pages across queries. They are not 1549 distinct scientific
figures. The finite method/property anchor can retain windows in `absent_material`
while its material requirement is missing; the existing qualifier refusal remains.
The DSC question has no supported literal anchor and receives no generic windows.

There are **49116 asset/window relations**: **1909** intersect selected or protected
geometry, **47207** are geometrically outside it with relevance unknown. These are
repeated pairwise relations, not counts of irrelevant assets or scientific errors.
No relation in this run has the `unknown_geometry` label; the implementation still
preserves that state and tests invalid/unproven geometry. Neither disjointness nor
intersection establishes whether pixels/paths contain necessary scientific data.

The **90 trigger records** comprise 38 damaged/private-use-text, 24 caption,
20 numeric-layout and eight note/footnote detections. A block may carry more than
one detector; these are not independent error labels. Across windows, 191 trigger
relations intersect selected text and 1413 lie outside it with extent unknown.
**29 page occurrences retain unlocalized parent diagnostics.** No diagnostic is
deleted after finding its lexical trigger elsewhere.

Diagnostic-window unions cover **22 page occurrences**. They were never assembled
into a candidate wire packet. The original stage32 result of **three** candidate
page unions is preserved separately and unchanged. Every question retains its old
blocking reasons; **0/4 become network-ready**. `selection_changed`,
`admission_changed`, `scientific_exclusion_proven`, `generation_performed`,
`external_request_constructed` and `network_ready` remain false.

Tests run:

- Final targeted geometry/source/old-planner/API regressions: **133 passed**, one
  existing Starlette/httpx warning; `pytest_target_v03.xml`. Includes distant,
  intersecting, touching, degenerate and invalid geometry; protected enclosure;
  unlocalized numeric aggregates; missing anchors; old refusal; page unions;
  foreign identities; frozen-input drift; source immutability and HTML escaping.
- Ruff passed; mypy passed for **148 source files**.
- Full regression: **2097 passed**, one existing Starlette/httpx warning, no
  failures/errors/skips, **316.27 seconds**; `pytest_full_v02.xml`. Full and API
  regressions ran outside the sandbox because of its prior TestClient restriction.
- Both independent executions produce byte-identical report, HTML and manifest.
  Four JSON audit replays match exactly; **527** context quotes preserve complete
  block/protected closure, and **90** trigger records resolve to exact source text.
  All **19 / 193240** baseline Evidence objects/characters remain in unchanged
  parent results. Verified bindings: **894** final preparation and **897** per review.
  The stage32 **552-file** source archive verifies; no new historical source-path
  fallback was needed (earlier explicit archived bindings remain preserved).
- Static HTML QA finds all four query cards, 35 page tables, one search input,
  no forms and **41 existing local links**. Exact configured-credential scans
  across **10** prepared/review artifact files find zero matches; keys were not
  printed. This does not establish browser rendering or independent scientific
  correctness.
- The initial constructed run exposed two incorrect test expectations: note and
  numeric blocks can themselves be retained for unknown boundaries. The assertions
  now explicitly select the conductivity core window; retention rules were not
  changed to satisfy the test.
- The first frozen corpus execution stopped on `TypeError: unhashable type: 'list'`
  in JSON protected-group ranges, before writing a review. `prepared_v01` is
  preserved as superseded. Added tuple conversion and an explicit protected-group
  JSON round-trip regression; `prepared_v02` freezes the correction. The first full
  regression was interrupted for this repair and is not a successful run. No
  scientific rule, question, threshold or scope changed after this failure.

Limitations:

- PDF blocks do not prove paragraph completeness, per-result condition association,
  table-cell semantics, cross-page relations or scientific adequacy. Bbox relations
  and finite lexical triggers cannot authorize exclusion of distant source data.
  Scientific precision/recall, answer quality and token/cost savings are unmeasured.
- The output intentionally includes deferred and broadly retained windows. Its
  527 windows are not 527 accepted evidence items, measurements or paid requests.
  Metadata missing in stage31 remains unknown. No new provider support is added.
- Standalone HTML has static integrity checks; browser rendering/acceptance is not
  established. The previous local-file browser restriction was not bypassed.
- Clone-only replay lacks the private PDFs, cache/index bindings, predecessor
  artifacts and verified source archive. Input drift fails rather than being repaired.

Verdict:

Local risk observations now have exact block/context geometry and preserved unknown
states. This establishes an inspection surface, not a new scientific admission rule.
The parent preparation remains blocked. Next bounded product step: show this audit
in the preparation UI while preserving the old gate; scientific exclusion criteria
and independent quality evaluation remain separate work.

## Artifacts and replay

Root: `output/records_stage33_20261022/`.

- `prepared_v01/`: superseded preflight; its execution failed before review output.
- `prepared_v02/`: final prospective protocol/code/test/input bindings.
- `review_v01/`: full `report.json`, searchable `review.html`, `manifest.json`.
- `review_repeat_v01/`: separate deterministic repeated execution.
- `postflight_v01.py` / `postflight_v01.json`: artifact/source/span/link/binding QA.
- `pytest_target_v03.xml`: final targeted regression evidence.
- `pytest_full_v02.xml`: final successful full regression.
- `baseline_final_v01/`: final source/dependency snapshot, excluding private
  corpus, database, model weights, generated outputs and credentials.
- `final_qa_v01.py` / `final_qa_v01.json`: final source/test/link/binding checks.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.context_risks prepare --output-dir output/records_stage33_new_prepared
.\.venv\Scripts\python.exe -X utf8 -m scripts.context_risks run --prepared output/records_stage33_new_prepared --output-dir output/records_stage33_new_review
```

Use a fresh directory per command. Defaults point to the preserved stage32 live
results and its 552-file source snapshot. The run re-reads immutable selected PDFs
and verifies frozen bindings before and after execution; it performs no retrieval.
