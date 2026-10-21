# Records stage19: complete-scope bounded context planning

21 October 2026. Offline continuation of records stage18; S05/S07–S08 preparation.
[Protocol](records/article_windows_protocol_v0.1.md).

## Changed

Added `app/records/article_windows.py`, its HTML renderer,
`scripts/records_article_windows.py` and 26 constructed regression cases. The
planner operates on the complete frozen stage18 article tasks rather than top-k
retrieval or only the four earlier oracle fragments. Existing ingestion,
selected text, OCR, chunks, retrieval, record schemas, output formats, scientific
metrics, review store and production generation defaults remain unchanged.

The wrapper verifies stage18 input/code/output hashes, unchanged source-only
bundles, source inventory/page declarations, original/selected PDF hashes and
actual original-PDF page counts. Existing registered-block, layout, closed ruled
table v0.2 and graphics readers are reused without modification. The mapping is
accepted only when its ordered whole blocks reproduce the exact saved page
text. Every block is assigned to exactly one core unit or to a deferred page.
Bibliography, methods, headers, no-keyword text and failures remain in scope.

Protected groups enclose their full contiguous source-order interval, including
intervening text and declared context blocks. Overlapping group intervals merge.
Each core unit receives one complete neighboring block on either side, expanded
to keep every intersecting protected group whole. No cell/row/footnote is cut to
meet the development ceiling of 6000 Unicode characters. This new offline policy
is explicit in the protocol and manifest; it is not a token limit or a production
or scientific threshold.

Unprotected caption, numeric-layout, note and damaged-text risks defer the
entire page. A geometric table boundary cannot mask damaged scientific notation.
Paragraph completeness, cross-page conditions and table-cell semantics remain
unknown even when a context is exact and short. Raster/vector registrations
retain source hashes, coordinates, text-line overlaps and unknown scientific
roles. The planner neither repairs source text nor infers graphical values.

Plain contexts and a JSON user-message fixture are checked with the existing
complete-page guard. A second pass checks every bounded proposal against all
62 registered pages, including other documents. JSON escaping cannot make a
complete plain page eligible. The final provider request is not built in this
stage and will require its own guard check, including any token-map rendering.
`bounded_context_proposal` does not mean scientific adequacy or approved
transmission. All dispatch and extraction states remain unrun/offline.

Existing full/span-fixed model replies permit only one measurement per request.
Using that limit to claim exhaustive extraction from an entire article/table
would conceal a potential omission. This stage completes the offline planning
step declared at the end of stage18; it does not pass whole-article sources
through that one-record API or claim that model extraction has been completed.

## Real input scope and results

Frozen input: `output/records_stage18_20261021/run_v01/`.
Historical source fingerprint:
`f133dcf1d95bf94d38f0d1cf49da24ca55082a42a8867e51f6f343fd84811a94`.
The scope remains development-exposed: Kayumov 2021, Sanginov 2021 with its
proposed supplement and Istomina 2021. No corpus/scope eligibility is promoted.

| Denominator/result | Observed count |
| --- | ---: |
| Article tasks / source PDFs | 3 / 4 |
| Original PDF pages retained | 62 |
| Registered and accounted text blocks | 1112 / 1112 |
| Pages deferred for unresolved structural risk | 34 |
| Pages with explicit context proposals | 28 |
| Core units on those pages | 354 |
| Distinct proposed context slices | 353 |
| Bounded source-only context bundles | 352 |
| Deferred complete-page context | 1 |
| Protected layout/table proposals | 14 |
| Registered raster occurrences | 107 |
| New model/API calls | 0 |

One pair of core units has the same surrounding slice; they remain two accounted
cores within one context, not two measurements. Neighbor overlap is never
counted as independent data. The sole deferred context is 1127 characters and
contains a full source page: the page guard blocks it even though it is below
the size ceiling. No actual proposed context exceeded 6000 characters.

Deferred-page reasons overlap: 20 pages have unresolved caption boundaries,
16 numeric-layout/header/row/footnote risks, eight damaged/private-use text
risks and two unprotected-note risks. These are heuristic diagnostics, not
34 scientifically ineligible pages or measured recall loss. Likewise, 107
raster occurrences do not mean 107 lost measurements. No-hit and deferred
cases are retained with their complete source text and graphics diagnostics.

Both complete exports match byte-for-byte across all 355 artifact files per
export. All 352 generated context bundles contain unchanged exact selected-text
slices with original page text, path/hash, article, page and layer identities;
they contain zero candidate records. The source type absent from the historical
source schema stays explicitly unavailable rather than being inferred from its
original/ocr layer label.

Outputs:

- [Searchable all-page/context HTML](../output/records_stage19_20261021/run_v01/review.html).
- `output/records_stage19_20261021/run_v01/report.json`, `contexts/` and
  `manifest.json`; independently repeated files in `repeat_v01/`.
- `postflight.py` and `postflight_v01.json` preserve exact coverage/hash/HTML QA.
- Three read-only source renders, `render_qa.py` and `visual_notes_v01.json`
  retain the assistant's layout inspection separately from scientific review.
- The initial `probe_v01/` remains an explicitly earlier development artifact;
  final outputs add paragraph/cell uncertainty and a full-scope page-guard pass.
  No earlier output was overwritten or silently repaired.

## Visual source-layout inspection

Original PDFs were rendered read-only with Poppler and three full-page PNGs
were actually inspected. These are assistant observations, not independent
annotations:

- Kayumov PDF p.6: Table 2, sample rows through 21 and both star footnotes are
  retained in the text group. Physical table order differs from PDF text order;
  vertically shared cells around rows 12–13 prevent assuming one text cell per
  sample. Exact source retention is not scientific table reconstruction. No
  value, missing cell or footnote was corrected.
- Sanginov PDF p.3: the page begins with a continuation/word fragment from the
  previous page. An interior context can include that fragment plus a section
  heading and following paragraph. Complete PDF blocks do not prove complete
  paragraphs; the new output states this explicitly and does not grant admission.
- Istomina PDF p.5: Figure 3 contains plotted points/axes. The whole page remains
  deferred for unresolved caption boundaries; no conductivity points were
  inferred from pixels, OCR or nearby text.

Browser visual/click acceptance of the HTML was not attempted. Static HTML
verification is separate; no HTTP workaround was introduced for the earlier
file-URL restriction.

## Tests run

- Final targeted suite: **26 passed**, **13.21 seconds**. Constructed cases
  cover exact single-core block accounting, interleaved/overlapping protected
  groups, neighboring-context expansion, unresolved/damaged source retention,
  full-page rejection despite JSON newline escaping, another complete source
  page inside a context, oversized context retention without clipping, wrong
  source identities/ranges, malformed mappings, empty PDF-page links, changed
  source/artifact inputs, path traversal and input drift during planning.
  Real constructed PDFs exercise two identical offline exports and source-only
  bundles. HTML source escaping and overwrite refusal also pass.
  JUnit: `pytest_target_v03.xml` under the stage19 output root.
- Full regression outside sandbox: **1530 passed**, one existing Starlette/httpx
  deprecation warning, **226.76 seconds**. JUnit: `pytest_full_v01.xml`.
  The outside-sandbox route reuses the established workaround for HTTP tests
  stalled in previous sandbox runs; no passing result is invented for those runs.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 118 source files.
  Initial local lint/type errors were corrected before the final runs. Earlier
  targeted runs had 23 cases before the three additional counterexamples.
- Actual exports and postflight verified all input/PDF/code/output hashes, 62
  page rows and local PDF/page link targets, all 62 exact full-page texts and 353
  exact context quotes in parsed HTML, complete 1112-block accounting, core-unit
  partitions, uncut protected intervals and page-guard checks across the complete
  source scope. Scientific rates remain null. No model result is fabricated.

## Reproduction

Use fresh destinations from the repository root:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_article_windows --scope output/records_stage18_20261021/run_v01 --output-dir output/records_article_windows_new
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/unit/test_record_article_windows.py -q -p no:cacheprovider --basetemp=output/records_article_windows_test_tmp
```

The saved stage18 packet, its historical source inputs and PDF paths must exist
and match hashes. Corpus, screening and generated outputs remain private/local
and are absent from a clean clone. Basetemp must be a dedicated disposable test
directory under the source root; pytest clears it. Failed planning can leave a
partial fresh output directory, but it has no successful final manifest.

## Limitations

This is complete-scope input planning, not full-article extraction, independent
scientific evaluation or model comparison. The 34 deferred pages, unresolved
paragraph/page dependencies, graphical information and table-cell semantics
remain open. No precision/recall, inferred scientific measurements or human-time
savings are available. The independent cohort target of 10–15 suitable works,
reference/split, full corpus recovery and offline inference remain unclosed.

## Verdict

The declared offline bounded-context planning stage is complete and reproducible.
All 62 pages and 1112 source blocks remain accounted for, with explicit deferred
states rather than hidden omissions. Extraction and scientific acceptance remain
open. The next bounded engineering stage is a separately versioned multi-record
reply/coverage contract and offline validation, then a frozen, budgeted model run
on appropriate contexts; whole-article recall cannot be claimed from the current
one-record adapter or from these 352 exact input slices alone.
