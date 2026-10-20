# Stage09: source-bound block windows

20 October 2026. Offline development algorithm `source_block_windows_v0.1`.
[Declared protocol](records/context_windows_protocol_v0.1.md). Four exposed
stage07 cases, unchanged questions/retrieval/expectations; no model inference.

## Changed

Added `app/evaluation/context_windows.py`. The selector uses complete PDF text
blocks rather than splitting sentences at decimals, abbreviations, initials or
broken line wraps. It reads the registered selected PDF layer, requires its frozen
checksum and exact equality of current plain text and concatenated PDF blocks
with the stored page text, and records character ranges plus block bounding boxes.
Geometry mismatch retains the original prepass fragment with diagnostics; file,
PDF and hash errors propagate. No fuzzy alignment, OCR or formula repair occurs.

The existing stage08 prepass is unchanged. New selection uses the frozen existing
distinctive query terms, up to two highest-match anchor blocks per page (ties in
source order), every condition/measurement/definition heuristic match, and one
neighboring block on each side. Adjacent selected blocks become one exact window;
separated blocks remain distinct evidence. Numerical units, equilibrium,
measurement, sample/weight definitions and uncertainty cues are protected by an
explicit versioned EN/RU regex. This is heuristic selection, not proof of complete
condition recognition or scientific relevance. Omitted blocks remain auditable.

Table/figure captions, dense numerical layouts and damaged/private-use formula
characters retain the whole prepass fragment. Header/row/footnote/figure boundaries
are not guessed. The numeric rule is six or more lines of at most fifty characters
with digits forming at least half the alphanumeric characters. Geometry faults and
nonwhitespace block cuts also retain the full fragment. These fallbacks can keep
complete pages, so the independent transmission guard continues to reject them.
An otherwise valid selection covering a whole page is not arbitrarily shortened.

Each window has a new `W` citation ID, exact source text/hash, half-open Unicode
coordinates in the original chunk and registered page, source article/type, layer
ID/type and original PDF path/hash. Diagnostics link prepass IDs to output IDs;
the original `E` ID remains in the source slice. Invalid prepass coordinates are
not emitted as verified slices. Historical answers are not rebound to new IDs.

Extended `scripts/compare_answer_context.py` with explicit `--block-windows`.
The default remains the stage08 algorithm and output contract. New-mode manifest
additions are explicit: selected-layer PDF hashes and PyMuPDF version. Source files
and geometry registries are frozen before selection. Full prepass, original source,
all block selections/omissions, scope and adequacy diagnostics are visible in the
separate local HTML/JSON. No production provider/default, HTTP/UI route, database,
ingestion/OCR, stored chunk, retrieval scoring or scientific metric changed.

## Observed replay

Private output: `output/records_stage09_20261020/replay_v01/`. Runtime PyMuPDF
1.28.0. Baseline corpus identifier
`18c9df4032897aaf576ad0e07beb4045fc39561ebf340c72e1abff4bca15b1ac` is
verified against the frozen stage07 snapshot; this is not a fresh DB audit.

| Frozen case | Original → stage08 → windows characters | Reduction vs original | Adequacy | Complete pages still found |
| --- | ---: | ---: | --- | ---: |
| EC/SL conductivity, Russian | 52,669 → 37,355 → 35,026 | 33.50% | adequate | 7 |
| Mixing temperature/swelling, Russian | 36,517 → 30,081 → 27,662 | 24.25% | adequate | 6 |
| Nafion/water thermodynamics, English | 34,132 → 27,686 → 24,329 | 28.72% | adequate | 6 |
| Negative regolith query | 63,911 → 61,485 → 61,485 | 3.80% | insufficient_distinctive_term_coverage | 9 |

All cases: **187,229 → 148,502 characters, 20.68% reduction**. The three
positive cases: **123,318 → 87,017, 29.44% reduction** versus stage07 and
8.52% versus stage08. New windows remove another 8,105 characters. These are
context character counts, not token/cost or answer quality measurements.
Candidate serialized bytes for positives are 44,519 / 33,586 / 36,909; stage07
requests were 61,763 / 43,661 / 49,283. No baseline negative request existed.

Thirty-five per-case page registrations cover 906 PDF text blocks; all registered
text/block comparisons passed. Eleven selected PDF files and eleven original
PDF files were verified (the selected files in this scope are the originals).
Forty-two output slices match the original chunk and page coordinates exactly:
fourteen newly selected windows and twenty-eight broad structural fallbacks.
For the pages actually narrowed, 82 blocks were selected and 91 omitted; these
counts do not include blocks inside the broad fallbacks. One prepass fragment
had no lexical/condition window and was excluded with an explicit unknown/absence
diagnostic. More evidence items do not imply more retrieved documents or recall.

Existing adequacy decisions remain three adequate and one insufficient. All four
candidate messages still contain complete page text and fail the independent
scope guard. Ambiguous bibliography remains visible, including selected lexical
matches in reference entries. Source formulas are not repaired. Page-spanning
scientific relations remain unresolved. **Zero new GPT calls, zero new answers,
no measured token usage, entailment, completeness or scientific accuracy.**

## Tests run

- Targeted windows/compaction/trace/generation: **109 passed**, 4.43 s. Forty new
  synthetic cases cover exact disjoint/adjacent source windows and old IDs,
  condition blocks distant from anchors (EN/RU units, percent, uncertainty and
  sample definitions), full retention of tables/captions/numerical layouts/formula
  damage, invalid/missing/overlapping/incomplete/duplicate geometry, invalid
  provenance, deterministic anchor selection, empty terms, whole-page protection,
  and actual temporary PDF block extraction/hash mismatch/immutability.
- Full regression: **1,229 passed**, 81.65 s; one existing Starlette/httpx
  deprecation warning. Executed outside the sandbox using a fresh workspace temp
  directory, following the previous stage's observed sandbox API-test hang.
- Ruff `app tests scripts`: passed. Mypy: no issues in 104 app source files.
- Frozen replay: 27 input/protocol/PDF files and nine code/config files verified;
  geometry registry hashes, all 42 exact source slices and PDF hashes checked again
  after regression. No extraction mismatch or geometry fallback occurred; the
  broad fallbacks above are structural/quality protection.
- Default stage08 replay: complete new `report.json` equals the final stage08
  report, including all scientific/source data and diagnostics. Compatibility
  output is separate: `output/records_stage09_20261020/stage08_compatibility/`.
- Static HTML: four rows, twenty existing original-PDF links, full before/prepass/
  after text, source registries, bbox/character coordinates, all omission reasons,
  unchanged adequacy and full-page guard diagnostics. No browser visual/click QA.
- Fifteen final replay artifacts scanned for the exact configured credential;
  zero matches. No credential was printed or used for inference.

## Local replay

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.compare_answer_context --block-windows --baseline data/experiments/records/pilot/stage07_20261020 --output output/records_stage09_new
```

Existing output directories are refused. `review.html`, `report.json`,
`input_manifest.json`, per-question `comparison.json`, `geometry_registry.json`
and `candidate_request_not_sent.json` are private and excluded from Git. A clone
lacks the private corpus and frozen stage07 source packets; synthetic tests do
not require them. Runtime/library differences can produce an explicit geometry
mismatch and preserve the broad fragment instead of reproducing these windows.

## Limitations

Offline replay of exposed development cases only. The condition regex is not an
exhaustive scientific parser. Query anchors can match irrelevant prose or reference
entries. Complete PDF blocks do not guarantee complete cross-page paragraphs or
scientific relations. Structural protection is broad and still blocks transmission.
No held-out annotation, fresh retrieval/DB snapshot, independent source entailment,
production activation, new model answer, billing measurement or browser QA.

## Verdict

Source-bound block windows and exact-coordinate tracing are implemented, tested
and compared with the unchanged stage08 baseline. The no-complete-page restriction
is still unsatisfied. Next target: use the now-verified block geometry to resolve
table/figure/caption/footnote groups and page continuations, keeping unresolved
cases explicit; then freeze a new bounded answer comparison and new independent
evaluation cases. Do not relax scope or claim scientific acceptance from smaller
context or unchanged adequacy alone.
