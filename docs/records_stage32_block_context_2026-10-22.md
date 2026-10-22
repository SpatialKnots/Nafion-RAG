# Stage32: whole-block query contexts and aggregate page coverage

22 October 2026. Version `query_block_context_v0.1`.
[Prospective protocol](records/block_context_protocol_v0.1.md),
[stage31 baseline](records_stage31_answer_preparation_2026-10-22.md).

Changed:

- Added explicit POST `/answer/prepare/blocks` and GET/POST
  `/ui/answer/prepare/blocks`, discoverable from the preparation page. The input
  remains the server-side question/search request; clients cannot supply PDF paths,
  mappings or source plans. Old `/answer` and `/answer/prepare` behavior/contracts
  remain separate. The full current preparation is preserved under `baseline`.
- Reused exact selected-PDF block registration, existing protected layout/table
  proposals and the stage19 whole-core-plus-neighbor planner. No arbitrary text
  cuts, fuzzy alignment, new retrieval scores, top-two block cap or source repair.
  The existing 6000-character context limit diagnoses rather than truncates.
- Within articles with a literal supported query mention, retain whole blocks with
  query anchors, finite condition/method cues, negation/reported-work/modality guards
  or unresolved sentence boundaries. All source events, unsupported clauses and
  boundary states remain visible. Other blocks stay explicitly accounted for in
  the unchanged baseline; they are not classified as irrelevant.
- Candidate citations have explicit B IDs, exact source regions/offsets/hashes,
  seed IDs and inherited metadata with its basis stated. These are proposals,
  not stored chunks, scientific classifications or accepted measurements. Source
  geometry/layout/visual uncertainty defers the page without deleting its text.
- Added aggregate interval-union coverage in addition to literal full-page text
  matching. Several overlapping windows cannot bypass the page rule by reconstructing
  its text collectively. Candidate qualifiers, old refusals and byte ceilings are
  checked separately. Generation remains disabled and `network_ready=false` always.
- Added explicit historical-source verification. A changed historical code binding
  can point only to matching bytes in the verified stage31 source snapshot, with
  original path/hash retained in a mapping. Private PDFs, indices, cache and other
  non-source inputs cannot use this fallback. Original manifests remain immutable.
  Current code is frozen separately. A typing-only cast in the source snapshot
  helper fixes its imported mypy diagnostic; its pin/output behavior is unchanged.

## Frozen real API observations

Four unchanged exposed development questions ran through the actual new ASGI API,
with read-only PostgreSQL retrieval and the existing verified offline BGE cache.
Code/tests/protocol/input bindings were frozen before the real run. No selection
rule, alias, ceiling or question was tuned after observing these results.

All **19 baseline Evidence objects / 193240 raw characters** match stage31 exactly.
The scope contains **35 page occurrences / 863 registered block occurrences**;
these counts include repetitions across questions, not distinct pages or experiments.

| Query | Proposed contexts | Candidate bytes | Aggregate result |
| --- | ---: | ---: | --- |
| conductivity_protocol | 0 | 438 | No supported candidate; source pages unresolved |
| dsc_protocol | 0 | 338 | No supported candidate; old/candidate qualifiers and source pages fail |
| preparation_atmosphere | 105 | 101433 | Old refusal preserved; qualifiers, page coverage, source pages and byte ceiling fail |
| absent_material | 0 | 323 | No supported candidate; old/candidate qualifiers and source pages fail |

The three empty candidates contain only wire metadata; their small byte counts are
not compression successes. The 105 proposals occur in the already-refused atmosphere
question. All are individually `bounded_context_proposal`; none establishes question
answerability or scientific sufficiency. Their repeated windows contain **24060
characters**, not a count of unique retained source characters. The one nonempty
candidate exceeds the frozen **100000-byte** ceiling by **1433 bytes**; it is retained
locally without clipping or a post-hoc ceiling increase. Combined candidate-wire
bytes are **102532**, which is not a token-cost metric or an approved request size.

**30/35 page occurrences are deferred.** Block accounting retains **688 deferred**,
**105 included** and **70 unselected** occurrences, totaling all 863. Unselected
and deferred text remains in baseline/source registries. Nonexclusive page diagnostics:

| Diagnostic | Page occurrences |
| --- | ---: |
| Uninterpreted non-text assets | 27 |
| Unresolved numeric layout/headers/rows/footnotes | 18 |
| Unresolved caption/table/figure boundaries | 13 |
| Damaged/private-use formula text | 12 |
| Unprotected note/footnote boundary | 5 |
| Visual registry diagnostics | 2 |

These are finite algorithm diagnostics, not independent scientific error labels.
Whole-page deferral is conservative: a drawing may be outside the eventual relevant
paragraph. Its presence does not prove a question depends on that drawing; the
current rule does not establish a safe local exclusion either.

Literal complete-page matching finds **zero** full pages inside the candidate
concatenations, but interval unions expose **three** fully covered source pages.
The new aggregate check blocks them. Splitting source text into overlapping windows
therefore does not make these packets eligible. **0/4 pass all technical checks;
0/4 are network-ready.** Old insufficiency/qualifier rejections are not upgraded.

No generated answer, scientific record or measurement is created. There are **zero
new generative API calls**; existing local query embeddings did run, with their
call count not independently instrumented. Original PDFs, database content, index
generation and cached weights were not changed. Missing author/year metadata from
stage31 remains unknown; no source-body/reference guesses fill it.

Tests run:

- Final targeted software/API regression: **85 passed**, one existing Starlette/
  httpx warning; `pytest_target_v03.xml`. Includes exact native test-PDF geometry,
  complete block/neighbor/protected-group closure, JSON round-trip, source drift,
  negative/unknown tails, old refusal, literal and assembled page guards, oversize
  retention, immutable inputs, private-input archive rejection, escaped UI/library
  scope and exclusive deterministic native-result exports.
- Full regression: **2062 passed**, one existing Starlette/httpx warning, no
  failures/errors/skips, **234.50 seconds**; `pytest_full_v02.xml`. Tests ran outside
  the sandbox due the earlier TestClient restriction. `ruff check app scripts tests`
  passed; `mypy app` passed, **146 source files**.
- Initial import/type diagnostics were fixed before the real comparison. Preliminary
  `prepared_v01` was superseded before any real request by `prepared_v02` after
  adding tuple/list JSON compatibility for archived protected groups. The initial
  full regression was deliberately interrupted for that software correction; it
  is not assigned a passing result. Earlier successful targeted runs remain saved.
- All four native JSON responses and production UI fragments replay exactly. The
  complete block builder also replays from saved JSON plans without retrieval,
  proving the representation compatibility. **105** proposal regions, **95** query
  anchor mentions and **6848** source event/context/cue/guard spans resolve to exact
  page text. These are technical span checks, not semantic support metrics.
- **869** preparation, **883** live and **886** per-review bindings verify. Two
  offline exports are byte-identical across report, HTML and manifest. The stage31
  **545-file** archive verifies; two historical source-path mappings are explicit.
  Strict historical runners may reject the changed current code; the new archive
  reader verifies saved historical bytes rather than silently accepting drift.
- Static review: all four query cards, one search input, no forms, **37** existing
  local artifact/PDF links. Exact configured-credential scan across **22** final
  prepared/live/review artifact files finds zero matches; keys were not printed.
  Static/TestClient checks do not establish browser rendering, and the prior
  local-file restriction was not bypassed.

Limitations:

- Exact PDF blocks and geometric table groups do not establish complete paragraphs,
  table-cell semantics, cross-page relations, sample identity or per-result method/
  condition applicability. Scientific precision/recall remain null. The same
  exposed queries are integration observations, not independent scientific gold.
- Finite query/condition aliases, page-wide source guards and retention of unknown
  boundaries can over-select or over-defer. No unsupported clause is forced into
  a category. Protected geometry does not repair damaged scientific notation.
- The current visual deferral applies to the page; local relevance of an asset is
  not established. The 105 overlapping windows repeat source text and can disclose
  complete pages collectively. No savings, answer-quality improvement or general
  applicability is claimed from the raw size difference.
- Existing `/answer` remains a separate generation path. The block preparation
  mode performs no model request in any state. A positive constructed necessary-
  check case is not permission for inference. No clean install, other-machine
  restore, browser acceptance, independent pilot or new provider support is claimed.

Verdict:

The source-block API/UI and bounded comparison are complete. Every selected source
is retained locally; whole-block proposals and their unresolved state are explicit.
The aggregate page-coverage check closes a real gap missed by literal matching in
this run. The observed packets remain blocked, so this stage does not enable paid
analysis of them. Next bounded work should localize layout/visual risk to selected
blocks and their protected context under a new frozen protocol, preserving unknown
and excluded evidence. Do not simply remove visual diagnostics, lower closure,
increase the byte ceiling or discard missing metadata to produce a pass.

## Use and artifacts

After application startup, open `/ui/answer/prepare/blocks`. API example:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer/prepare/blocks `
  -ContentType application/json `
  -Body '{"question":"How was conductivity measured?","method":"hybrid_cross_lingual","top_k":5}'
```

Local root: `output/records_stage32_20261022/`.

- `prepared_v01/`: preserved superseded preflight, never executed against the corpus.
- `prepared_v02/`: final pre-comparison code/input/archive/cache/request bindings.
- `live_v01/`: four native request/response/UI-fragment sets, complete report and
  manifest. UI fragments retain live HTTP links, not standalone local-PDF links.
- `review_v01/review.html`, `report.json`, `manifest.json`: all four query results
  with local original-PDF links; `review_repeat_v01/`: identical second export.
- `postflight_v01.py`, `postflight_v01.json`: native/JSON-plan/source-span/coverage/
  historical-source/hash/link/credential QA.
- `pytest_target_v03.xml`, `pytest_full_v02.xml`: final successful regression.
- `baseline_final_v01/`, `final_qa_v01.json`: source/dependency snapshot and final QA,
  excluding private corpus, database, model weights, outputs and credentials.

Offline export, without retrieval or API calls, to a fresh directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.block_preparation export --prepared output/records_stage32_20261022/prepared_v02 --captured output/records_stage32_20261022/live_v01 --output-dir output/records_stage32_new_review
```

The clone alone lacks private predecessor/corpus/run artifacts. New live retrieval
is not promised identical, and source/index drift is not repaired. Preserve the
stage31 archive and explicit mapping for the historical code identities.
