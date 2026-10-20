# Stage08: conservative source context compaction

20 October 2026. Offline development replay, algorithm
`source_page_compaction_v0.1`. This stage completes the conservative prepass and
transmission guard; question-specific sentence windows remain unimplemented.

## Changed

Added `app/evaluation/context_compaction.py`. The optional offline prepass aligns
selected chunks with their registered pages using exact text and whitespace-only
separators. It removes proven duplicate page occurrences within one question,
preserving article, layer ID/type, page, text and original-PDF hash identities.
It proposes exclusion after explicit standalone reference headings or for a
narrow consecutive numbered-reference grammar. Unknown/ambiguous bibliography
and unproven alignment remain with diagnostics. Reference exclusion is an
algorithm proposal, not human confirmation or independent scientific truth.

Each retained page/prefix is an exact contiguous source slice. Output records
half-open Unicode character coordinates in both the chunk and page layer, exact
fragment hash, original PDF path/hash, article, layer, page, and old/new citation
IDs. No synthesized replacement text, punctuation correction, formula repair or
sentence truncation is performed. Development IDs `C1`, etc. are separate from
the historical stage07 `E1`, etc.; old answers are never rebound to them.

Added an optional registered-page guard to the development Responses bridge. It
checks the actual user message after the existing whitespace formatter and fails
before transmission or attempt-directory creation if any complete page remains.
An explicitly enabled empty registry fails closed. Default provider behavior and
the frozen stage07 requests remain unchanged. This literal scope guard does not
establish scientific adequacy or prevent every possible disclosure; callers
must supply the complete source registry. It is not enabled in production.

Added `scripts/compare_answer_context.py` and a
[declared offline protocol](records/context_compaction_protocol_v0.1.md). The
script freezes input/code hashes before compaction, validates stage07 manifests,
exact chunk/page checksums, source slices and current original PDF hashes, then
recomputes the existing adequacy diagnostic on candidate context. It constructs
local candidate requests only: no `generate`, transport, API key, database or
retrieval operation is used. Selection never receives old answers, expected DOIs
or answerability labels. Search scoring, ingestion/OCR/chunking, database schema,
model defaults and scientific metrics were not changed.

## Observed replay

Inputs are the same four exposed development questions and selected evidence
from [stage07](records_stage07_end_to_end_2026-10-20.md), not new held-out cases.
Baseline corpus fingerprint remains an input identifier
`18c9df4032897aaf576ad0e07beb4045fc39561ebf340c72e1abff4bca15b1ac`;
no fresh database snapshot or end-to-end retrieval was performed here.

| Frozen case | Context characters before → after | Reduction | Candidate adequacy | Complete pages still found in formatted request |
| --- | ---: | ---: | --- | ---: |
| EC/SL conductivity, Russian | 52,669 → 37,355 | 29.08% | adequate | 8 |
| Mixing temperature/swelling, Russian | 36,517 → 30,081 | 17.62% | adequate | 8 |
| Nafion/water thermodynamics, English | 34,132 → 27,686 | 18.89% | adequate | 8 |
| Negative regolith query | 63,911 → 61,485 | 3.80% | insufficient_distinctive_term_coverage | 9 |

Across all four cases: 187,229 → 156,607 characters, **16.36% reduction**.
Across the three positive cases: 123,318 → 95,122, **22.86% reduction**.
These are sums of `len(Evidence.text)`, not token or billing savings. Corresponding
candidate serialized request byte counts for positives are 46,811 / 37,453 /
40,285, versus baseline 61,763 / 43,661 / 49,283. The negative had no baseline
request because its original gate rejected it; its local candidate is explicitly
not submitted. More citation items result from splitting chunks into page slices;
the change in item count is not improved retrieval coverage.

Five exact repeated page occurrences were omitted. Two explicit reference
suffixes were proposed for exclusion, one in a positive case and one in the
negative. All 35 retained slices match both frozen chunk and registered page
coordinates. Original conditions, captions, table rows, footnotes and damaged
characters within retained slices remain unchanged. This is an exact-copy
property, not proof that every relevant condition in the corpus was retrieved.

The dissertation bibliography pages in the water query did **not** satisfy the
narrow whole-page grammar; ambiguous/incomplete numbered blocks were retained.
One duplicated bibliography page occurrence was removed. This remaining noise
is explicitly visible in the report; no rule was retuned to hide this outcome.
Chernyuk formula damage remains unchanged.

All four candidate messages still contain complete page text. The new scope
guard therefore rejects all four. The negative also retains its adequacy refusal.
**Zero new GPT calls, zero new model answers, no measured token usage or answer
accuracy comparison.** Shorter context alone does not satisfy the stage07
no-complete-page condition, and arbitrary clipping was not used to evade it.

## Tests run

The initial default pytest temporary/cache directories were inaccessible, including an escalated
attempt. Tests were rerun with fresh workspace temporary directories and cache
disabled. A sandboxed full-suite attempt stopped progressing on the existing
upload API test and was interrupted; the full suite was rerun outside the sandbox.
These infrastructure attempts are not passing test results.

- Targeted compaction/trace/generation: **69 passed**, 1.81 s. Includes 22 new
  synthetic cases for exact source coordinates; conditions/table/caption/footnote
  preservation; ambiguous references; absent/wrong/partial/duplicate page mappings;
  derived source fallback; independent article/layer/layer-ID/PDF identities;
  scope rejection before network/directory creation; empty registry; and shorter
  exact-slice preparation without registry paths in the request.
- Ruff `app tests scripts`: passed. Mypy: no issues in 103 app source files.
- Full regression: **1,189 passed**, 72.24 s; one existing Starlette/httpx
  deprecation warning. This software result is separate from scientific accuracy.
- Offline final replay `replay_v02`: four cases, 35 exact slices, fifteen frozen
  input/protocol files and eight code/config files verified; eleven current
  original PDF hashes verified before/after. No unaligned chunk fallback occurred.
- Static HTML: four question rows, twenty existing original-PDF links, searchable
  full before/after text, full original source registry, source coordinates and
  omission/adequacy/scope diagnostics. Browser visual/click checks were not run.
- Eleven final replay artifacts scanned for the exact configured credential:
  zero matches; the credential was not printed or used for inference.

## Artifacts and replay

Private outputs are excluded from Git:

- `output/records_stage08_20261020/replay_v02/review.html`
- `output/records_stage08_20261020/replay_v02/report.json`
- `input_manifest.json`, `credential_qa.json`, four per-question comparisons and
  four `candidate_request_not_sent.json` files under the same directory.

The earlier `replay_v01` remains as an intermediate output. Final `replay_v02`
adds explicit source-layer/PDF identity checks for duplicate removal, full source
registry display and post-replay PDF checks. Both runs have zero inference and
the same character totals; the final manifest identifies the actual final code.

From the private working copy, replay to a fresh directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.compare_answer_context --baseline data/experiments/records/pilot/stage07_20261020 --output output/records_stage08_new
```

Existing outputs are refused. A clone has code/protocol/synthetic tests but lacks
the private stage07 source packets, PDFs and raw requests.

## Limitations

Conservative offline prepass only. Bibliography detection is incomplete and may
make mistaken proposals; complete source is retained for auditing. Adjacent pages
become separate exact citation items; preserving a table's scientific relation
across pages is not evaluated. No sentence-window selector, fresh retrieval/DB
audit, production activation, browser QA, held-out evaluation, independent
entailment review, new GPT answer or measured token/cost saving. Scope guard is
optional and relies on complete correct source registration.

## Verdict

Exact duplicate reduction, source coordinate tracing and fail-closed development
scope checks are implemented and replayed. The candidate context is smaller but
not admitted for transmission under the no-complete-page rule. Next development
stage: separately versioned sentence/section windows with explicit preservation
and diagnostics for measurement conditions, table headers, captions and footnotes;
then a newly frozen bounded answer comparison and independent new questions.
