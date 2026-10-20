# Stage11: closed ruled table proposals, corrected v0.2

20 October 2026. Offline development algorithm `source_ruled_tables_v0.2`.
[Final protocol](records/ruled_tables_protocol_v0.2.md); the
[initial v0.1 protocol](records/ruled_tables_protocol_v0.1.md) and rejected run are
preserved. Same four exposed stage07 cases; no new retrieval or model inference.

## Changed

Added `app/evaluation/ruled_tables.py` and explicit `--ruled-tables` in the offline
comparison script. This composes the unchanged stage08 prepass, stage09 lexical/
condition selection and stage10 layout protection with exact registered vector
rules. Default stages08–10 remain available and unchanged in their results.

Read horizontal line/rectangle paths from the selected source PDF only after its
checksum and page text match the registered evidence. Rules must span at least
120 PDF points and be at most one point high. Keep original drawing indices and
coordinates. A table caption needs an opening rule within 16 points; a closing
rule must match both horizontal endpoints within 3 points, before a prose/next-table
barrier. Retain all complete enclosed text blocks; crossing blocks, fewer than two
header/data blocks or fewer than four numeric tokens prevent a table proposal.

Attach explicitly prefixed notes below the closing line in the same horizontal
span, with at most 12 points between blocks. Every body star/dagger marker needs
its note definition. New v0.2 rejection prevents admission when any unclassified
text remains within 12 points below the closing rule or final attached note.
Unknown tails are retained by the existing fallback; their meaning is not guessed.
Continued tables remain unresolved. Whole leading reference paragraphs can be
protected via listed reference verbs; they are not counted as table detections.

Groups preserve whole source blocks and exact article/chunk/page/layer/PDF hashes
and character ranges, including notes that appear earlier than header rows in
stored extraction order. No source-order correction, cell/column assignment,
unit change, OCR, image interpretation, scientific record acceptance, stored text,
retrieval score, database schema or production provider change occurred.

## Rejected v0.1 and correction evidence

The first frozen run proposed three tables. Poppler renders and coding-agent
inspection found the third boundary excluded the final visible row and a letter
note. It is **not** a successful table result. The raw run, requests, overlays,
protocol and exact code/test source snapshot remain under:

- `output/records_stage11_20261020/replay_v01/`
- `output/records_stage11_20261020/rejected_v01_source/`

Two synthetic counterexamples (an extra numeric row and an unsupported letter
note immediately below the purported closing line) were added. Both actually
failed against v0.1 before the fix: **2 failed, 19 deselected**, 1.10 s. They are
development counterexamples informed by this audit, not held-out gold. A separately
declared v0.2 protocol and fresh `replay_v02` preserve the original failure without
repairing its artifacts or silently changing its metrics. No inference followed
the rejected proposal.

## Corrected real-source replay

Two proposed closed tables remain: Sanginov page 12 and Kayumov page 3. Both were
rendered again with block/caption/note overlays and visually inspected in the
corrected run. Kayumov's whole four-line star-note block is included and every
body star-marker arity has a matching definition. The previously partial third
table is now explicitly `table_tail_unresolved`, and its broad source remains.
Three additional leading reference paragraphs are protected separately.

This is a finite structural/source audit, not independent table/row/cell accuracy
or scientific validation of numerical claims. A table may still be retained inside
a broad page when another figure or unresolved structure on that page prevents
narrowing. Finding a table group does not mean the entire request is admissible.

| Frozen case | Stage10 → stage11 characters | Adequacy | Complete pages still found |
| --- | ---: | --- | ---: |
| EC/SL conductivity, Russian | 34,994 → 33,750 | adequate | 5 |
| Mixing temperature/swelling, Russian | 27,630 → 27,630 | adequate | 5 |
| Nafion/water thermodynamics, English | 24,329 → 24,329 | adequate | 6 |
| Negative regolith query | 61,210 → 61,210 | insufficient_distinctive_term_coverage | 9 |

Positive contexts: **86,953 → 85,709 characters**, another 1,244 characters (1.43%)
beyond stage10. The 30.50% reduction relative to stage07 includes all previous
stages; it is not attributable solely to table grouping. All cases total 146,919
characters. These are character counts, not token, cost, speed or answer-quality
measurements. Serialized positive candidate requests are 43,264 / 33,554 / 36,909
bytes; the negative candidate is local-only and was never submitted.

Forty-two output slices are exact: twenty selected windows and twenty-two broad
fallbacks. For narrowed fragments, 167 blocks are retained and 107 omitted; fallback
pages are excluded from those counts. The 35 source registrations expose 906 text
blocks and 51 qualifying horizontal vector rules across per-case pages. Full exact
sources, drawing IDs, member ranges, notes and unresolved cases remain visible.

All four candidates still fail the independent complete-page transmission guard.
The negative also retains its adequacy refusal. **Zero new GPT calls, answers or
measured model usage.** Stage10's graphic-text gaps and nearly complete-page finding
are not solved by vector-rule grouping. The final postflight preserves per-page
source-position coverage; literal scope acceptance would not prove scientific
completeness or meaningful narrowing.

## Tests run

- Corrected targeted tables/layout/windows/compaction/trace/generation:
  **154 passed**, 5.56 s. Twenty-one new table cases cover full header/row/note
  retention, exact ranges, missing/shifted rules, caption and note gaps, crossing
  blocks, missing marker definitions, continuations, figure/reference confusion,
  invalid registries, actual temporary PDF vector-rule extraction/immutability
  and the two reproduced incomplete-tail failures.
- Ruff `app tests scripts`: passed. Mypy: no issues in 106 app source files.
- Final full regression: **1,274 passed**, 112.79 s; one existing Starlette/httpx
  warning. Ran outside the sandbox with a fresh workspace temporary directory.
- Stage08, stage09 and stage10 compatibility replays: all three complete
  `report.json` files are byte-identical to their prior final reports.
- Corrected replay: 42 exact source slices, 27 frozen input/protocol/PDF files,
  eleven code/config files, text/rule/table/layout registry hashes and eleven
  original/selected PDFs verified. A fresh DB state or new retrieval was not read.
- Two corrected table overlays inspected after rendering with Poppler at 120 dpi.
  Original PDFs unchanged. This is coding-agent visual QA, not independent gold.
  The three original v0.1 overlays include the documented rejected result.
- Main static HTML retains all four questions and twenty existing original-PDF
  links, full source and previous-context comparisons, candidate tables, notes,
  rule drawings, scope/adequacy and unresolved diagnostics. The supplemental
  `table_review.html` displays the two corrected table overlays. Browser QA not run.
- Final postflight reverified corrected input/code/PDF/registry/image hashes and
  the archived v0.1 source checksums. Seventy-one artifacts across failed/corrected
  runs were scanned for the exact configured credential: zero matches; no key printed.

## Artifacts and replay

Final private outputs: `output/records_stage11_20261020/replay_v02/`.

- `table_review.html` — corrected table overlays and source-coverage diagnostics;
  links to full searchable `review.html`.
- `report.json`, `input_manifest.json`; per-case geometry, layout, vector-rule,
  table registries, comparisons and candidate requests explicitly not sent.
- `diagnostics/` — final PNGs, rendering/coverage data and subsequent visual notes.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.compare_answer_context --ruled-tables --baseline data/experiments/records/pilot/stage07_20261020 --output output/records_stage11_new
```

Existing directories are refused. Raw failures are preserved, not overwritten.
The clone includes reusable code/protocol/tests but lacks the private corpus,
frozen stage07 inputs and local rendering helpers.

## Limitations

Only two visually checked real table proposals after a revealed development failure.
No independent gold, universal note/letter/superscript recognition, broken-rule or
image-table parsing, cross-page closure, cell reconstruction, scientific numerical
validation, production activation, new model answer, billing measure or browser QA.
Embedded figure content remains outside registered text. Unknown cases remain
unresolved; source tracing and software regression do not imply scientific accuracy.

## Verdict

The next engineering step now covers two real closed table groups with their
source headers/rows/notes and rejects the observed incomplete-tail failure. The
previous algorithms remain reproducible. General table completeness and model
answer acceptance remain open; unresolved graphics and complete-page scope still
prevent a new GPT batch. Next priority: explicit graphic source-gap diagnostics
and additional table continuation/note styles on independent cases.
