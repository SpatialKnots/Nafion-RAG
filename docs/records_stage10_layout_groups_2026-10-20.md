# Stage10: protected layout group proposals

20 October 2026. Development algorithm `source_layout_groups_v0.1`.
[Declared protocol](records/layout_groups_protocol_v0.1.md). Offline replay of
the same four exposed stage07 cases, with unchanged stage08/09 defaults.

## Changed

Added `app/evaluation/layout_groups.py` and opt-in `--layout-groups` in the offline
comparison script. The existing selector accepts exact protected block ranges
only in this explicit mode; default output remains unchanged. Geometry must match
registered source identity/text, cover the page exactly and have finite positive
rectangles. A partial-block protection override is rejected with diagnostics.

Separate caption blocks are distinguished from line-wrapped references inside
prose. A standalone caption needs a block-start label, number and punctuation.
An inline reference proposal requires an unfinished preceding sentence and no
standalone caption punctuation. The whole referring block remains protected.
Unknown styles and captions merged ambiguously with prose retain old protection.

For a separate caption, propose an enclosure between complete same-column prose
paragraphs above/below it. Prose requires 25 alphabetic words and terminal sentence
punctuation; explicit notes and damaged blocks cannot become barriers. Column
overlap must reach half the narrower paragraph width. Keep every intervening block
and both bounding paragraphs; reject crossing rectangles with 3 PDF-point tolerance,
intervening prose, open boundaries and explicit continued captions. Footnote-prefix
recognition is deliberately limited and remains an algorithmic proposal.

Protected groups retain complete member blocks regardless of query rank, plus the
existing anchor/condition/neighbor selection. Structural risks are checked on the
remaining unprotected text. Unresolved captions, numerical layouts and formula
damage still retain the whole prepass fragment. Source output itself is never
masked, repaired, clipped, reordered, reconstructed as table cells, or interpreted
from images. New ranges retain exact article/chunk/page/layer/PDF provenance and
original citation identity. No production, database, PDF, OCR, chunking, retrieval
scoring, model default or scientific metric changed.

## Observed result

Five proposal occurrences: four enclosures for **two unique figures** repeated
across the positive questions, and one inline-reference paragraph in the negative
case. **No real table group was resolved in this replay.** Twenty-two open
enclosures and fourteen unresolved caption styles remain across per-case page
registrations. The synthetic table tests are software counterexamples, not evidence
of successful real-corpus table extraction or independent boundary accuracy.

| Frozen case | Stage09 → stage10 characters | Adequacy | Complete pages still detected |
| --- | ---: | --- | ---: |
| EC/SL conductivity, Russian | 35,026 → 34,994 | adequate | 6 |
| Mixing temperature/swelling, Russian | 27,662 → 27,630 | adequate | 5 |
| Nafion/water thermodynamics, English | 24,329 → 24,329 | adequate | 6 |
| Negative regolith query | 61,485 → 61,210 | insufficient_distinctive_term_coverage | 9 |

Positive context changed by only **64 characters**, 87,017 → 86,953 (about 0.074%).
Across all cases: 148,502 → 148,163, a 339-character reduction. This is **not a
material context compression improvement**. Relative to the original stage07
positives, reduction is 29.49%; nearly all of that was already achieved in earlier
stages. Character/byte counts are not token, cost, speed or answer-quality measures.

Forty-two output slices remain exact: nineteen selected windows and twenty-three
broad fallbacks, versus fourteen/twenty-eight in stage09. For pages actually
narrowed, 150 blocks are retained and 96 omitted; fallback pages are not included
in those block counts. All 35 page/block registrations and 906 registered blocks
remain available. Increasing window processing does not prove better recall.

Existing adequacy decisions remain three adequate and one insufficient. All four
candidate requests still fail the complete-page guard. **Zero new GPT calls or
answers; no new usage, scientific accuracy, entailment or completeness measurement.**
The frozen corpus fingerprint is only a baseline identifier, not a fresh DB audit:
`18c9df4032897aaf576ad0e07beb4045fc39561ebf340c72e1abff4bca15b1ac`.

## Visual and coverage postflight

Rendered three unique proposal pages with Poppler at 120 dpi and inspected the
PNG overlays: two figure groups and one inline-reference paragraph. Group/member
rectangles align with the displayed text/captions and adjacent paragraphs. This
is coding-agent visual QA, not independent gold or scientific acceptance. Source
PDFs were read only and their checksums remained unchanged. No new PDF was written.

One enclosed figure contains a 1202×725 embedded image. Its body is not present as
registered text blocks, even though its caption and enclosing geometry are found.
Visual conditions visible in the render are therefore not supplied as source text.
No OCR, image interpretation or transcription was performed. Another figure has
textual chemical labels but its bonds/visual geometry are not serialized. A geometric
enclosure must not be described as extracting all data inside a figure.

A separate **postflight diagnostic**, not a tuned selector/acceptance metric,
calculates the union of retained nonwhitespace source positions per page. Two new
partial-page occurrences refer to the same page and retain **3,302/3,327 = 99.25%**
of its nonwhitespace text. Thus a reduced literal full-page match count does not
establish meaningful source-scope reduction. The 95% flag is declared only in this
postflight diagnostic; it changes neither the frozen selector nor existing gate.
Original requests, report and protocol are preserved without repair.

## Tests run

- Targeted layout/windows/compaction/trace/generation: **133 passed**, 2.51 s.
  Twenty-four new synthetic cases cover caption/numeric-row/long-note/context
  retention, exact ranges, EN/RU labels, open/crossing/invalid geometry, incomplete
  captions, explicit continuations, damaged formulas inside/outside groups, inline
  versus merged caption ambiguity and rejected partial-block overrides.
- Full regression: **1,253 passed**, 89.84 s; one existing Starlette/httpx warning.
  Ran outside the sandbox with a fresh workspace temporary directory, following
  the previously observed sandbox API-test hang.
- Ruff `app tests scripts`: passed. Mypy: no issues in 105 app source files.
- Stage08 and stage09 compatibility replays: both complete `report.json` files
  are **byte-identical** to their prior final outputs. Separate compatibility
  directories preserve those checks without overwriting earlier stages.
- Frozen stage10 replay: 42 chunk/page slices, 27 input/protocol/PDF files,
  ten code/config files, geometry/layout registry hashes and eleven original/
  selected PDF file hashes verified. No geometry mismatch was repaired silently.
- Main static HTML: four question rows and twenty existing original-PDF links;
  full before/prepass/block-only/after text, group proposals, bounding boxes,
  unresolved boundaries and scope/adequacy diagnostics. Supplemental HTML includes
  all three inspected overlays and full source-coverage data. Browser QA not run.

## Artifacts and replay

Private outputs under `output/records_stage10_20261020/replay_v01/`:

- `layout_review.html` — supplemental visual/coverage review, links to the full
  searchable `review.html`.
- `report.json`, `input_manifest.json`; per-case source comparisons, geometry and
  layout registries and candidate requests marked not sent.
- `diagnostics/` — original PNG renders, overlays, render manifest, coverage data
  and coding-agent visual notes. Render-time pending status remains in the original
  manifest; the subsequent `visual_qa.json` records completed image inspection.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.compare_answer_context --layout-groups --baseline data/experiments/records/pilot/stage07_20261020 --output output/records_stage10_new
```

Existing output directories are refused. Source/algorithm replay is reusable;
the local postflight rendering helpers and private PDFs are not in a clean clone.

## Limitations

Only exposed development questions, two unique figure enclosures and one inline
reference proposal; no successfully resolved real table, independent annotation,
cross-page closure, general note recognition, figure OCR, cell/axis reconstruction,
new end-to-end retrieval, production activation, model answer or billing measure.
Nearly complete page text remains possible. Geometry and source-ID integrity alone
do not prove semantic support or coverage of visual scientific conditions.

## Verdict

Implemented and tested source-bound protected layout proposals, with visual QA and
unchanged older algorithms. The practical compression target is **not achieved**
by this iteration. Do not count header removal as meaningful narrowing or a figure
enclosure as image-data extraction. Next priority: explicit source-completeness
diagnostics for embedded graphics and real table boundaries/continuations before
another bounded GPT comparison; preserve unresolved cases rather than force a
smaller accepted context.
