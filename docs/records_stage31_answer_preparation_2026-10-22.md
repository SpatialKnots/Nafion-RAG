# Stage31: explicit answer preparation in API and UI

22 October 2026. Version `answer_preparation_v0.1`.
[Prospective integration protocol](records/answer_preparation_protocol_v0.1.md),
[stage30 qualifier guard](records_stage30_query_qualifiers_2026-10-22.md),
[stage29 context comparison](records_stage29_query_packet_2026-10-22.md).

Changed:

- Added POST `/answer/prepare` and GET/POST `/ui/answer/prepare`, with links from
  the home and answer pages. The new JSON explicitly declares its version,
  blockers, qualifier assessment, raw evidence, source provenance and no-generation
  status. Existing `/answer` request/output, provider, gate, selection and scoring
  are unchanged. The preparation route never falls through to generation.
- Actual `answer_question` performs retrieval/selection with the existing observer.
  A provider without transport or credentials raises a dedicated boundary before
  generation. Only that boundary is caught. Existing insufficiency returns and
  failures are preserved. Each request starts a fresh PostgreSQL repeatable-read,
  read-only transaction with autoflush disabled; session closure rolls back.
- Reused existing source collection, exact page alignment and complete-page checks.
  Every Evidence field/text is retained, including blocked/derived/unresolved data.
  Complete registered pages, unproven registry, failed old/qualifier gates and a
  100000-byte canonical question/evidence bundle ceiling are explicit blockers.
  Nothing is clipped. `network_ready` remains false even when necessary checks pass;
  this endpoint constructs no external model request.
- Read author/year metadata from the same live request transaction. Preserve raw
  fields and exact mapping of recognized surname/name fields. Missing, unsupported
  or partially unresolved authors stay unknown. No body/reference/title guessing or
  retroactive repair of stage30's missing metadata is performed.
- UI shows human-readable blockers and per-article qualifier states, full expandable
  evidence and diagnostics, original PDF links and valid raw-chunk context links.
  Derived evidence receives no fabricated raw-chunk URL. User/source strings are
  escaped. Collection, method, top-k and library scope are preserved; GET can
  inherit the existing library cookie. There is no automatic send/generate action.
- Added frozen preparation/API smoke/offline export CLI. Implementation, requests,
  protocol, tests, inherited sources and eight local cache files were frozen before
  the real requests. No policy, question, alias or selection tuning followed them.

## Real local integration observations

Four POSTs ran through the actual ASGI `/answer/prepare` route against the local
PostgreSQL/corpus/index, using the verified offline BGE cache. These are exposed
development questions inherited from stage29, not independent scientific labels.
The smoke saves native HTTP JSON and renders it through the production UI result
renderer. It does not call the separate old `/answer` route.

| Question ID | Original gate allowance | Necessary qualifier allowance | New preparation status |
| --- | --- | --- | --- |
| conductivity_protocol | yes | yes | blocked: complete pages retained |
| dsc_protocol | yes | no | blocked: qualifiers and complete pages |
| preparation_atmosphere | no | no | blocked: old rejection, qualifiers, complete pages |
| absent_material | yes | no | blocked: qualifiers and complete pages |

All **19 selected Evidence objects** match stage29 exactly, in all four queries.
The old allowance count is **3**, qualifier allowance count **1**; **0 checks_passed**
and **0 network_ready** because all contexts retain complete pages. A necessary
mention allowance is not scientific sufficiency. The absence of a selected literal
material does not prove corpus-wide absence; unknown metadata is not article mismatch.

All recorded article-metadata entries selected in this smoke have unresolved
authors and a missing year. Positive author-field mapping is covered by constructed
tests, not demonstrated by a populated real bibliographic record in this run.
The mode reports the gap and does not fill it from source body/reference guesses.
Source-supported automatic metadata completion remains separate work.

No original PDF, source text, database row, model weight or index generation was
modified. There were **zero new generative API calls** and no external model request
was built. Existing local BGE query embeddings did run; their call count was not
independently instrumented. The existing default model-cache failure from stage29
was not repeated: this smoke uses process-local offline/cache settings and verifies
the eight previously recorded cache hashes. Historical index-time weight identity
remains an inherited limitation.

Tests run:

- Targeted software/API/UI regression: **83 passed**, one existing Starlette/httpx
  deprecation warning; `pytest_target_v04.xml`. Covers actual stop-before-provider
  behavior, no-generation even on necessary-check success, all blockers, raw author
  mapping/unknowns, HTTP validation/error statuses, escaped full source text, library
  filtering/cookies/empty input, form choices, old route compatibility, frozen
  input drift and deterministic exclusive export.
- Full regression: **2017 passed**, one existing Starlette/httpx warning,
  no failures/errors/skips, in **352.58 seconds**; `pytest_full_v01.xml`.
  The successful full run used dedicated output/temp/cache directories outside
  the sandbox after the earlier TestClient stall.
- `ruff check app scripts tests`: passed. `mypy app`: passed, **143 source files**.
  Initial import/type diagnostics and a constructed Python-versus-native-JSON
  comparison error were fixed before freezing. The first sandbox HTTP test attempt
  stalled after service tests and was interrupted; no successful result is assigned
  to it. Outside-sandbox HTTP runs completed, including the final 83-test run.
- Four real API responses returned HTTP 200 with explicit blocked diagnostics;
  no generated claims or scientific records were created. Native requests,
  responses, UI fragments and source/code hashes are preserved separately.
- Repeated offline report/HTML/manifest exports are verified separately by local
  postflight QA. Browser rendering/interaction is not established by TestClient or
  static HTML inspection; the prior local-file restriction is not bypassed.
- Postflight verifies byte-identical exports, **840** preparation bindings,
  **854** live bindings and **857** per-review bindings. All native response/UI
  fragments and **19 evidence / 193240 raw characters** match saved originals;
  **35** registered complete-page occurrences and **105** exact evidence-mention
  spans are checked. These repeated occurrences are not distinct experiments.
- Static review includes all four cards, one search input, no forms and **37**
  existing local artifact/PDF links. Exact configured-credential scan across
  **22** artifact files finds zero matches; credentials were not printed.

Limitations:

- Preparation is a new explicit production capability; it does not globally replace
  or guard the existing `/answer` generation route. New callers must choose the
  preparation route. No generation-enabled preparation flag exists.
- The stage30 grammar/catalogue remains finite and unchanged. Mentions may be
  negated, hypothetical, cited work or unrelated within an article. Measurement
  existence, sample/condition linkage, origin and scientific entailment are not
  established. Scientific precision/recall remain null.
- Recorded metadata is not independently validated. Unsupported author shapes may
  cause conservative unknowns. There is no new external metadata lookup or manual
  per-Term task. New live metadata is not a replacement for old frozen evidence.
- Source registry collection and exact alignment reuse the existing experimental
  helpers. Source integrity errors remain visible; no fallback repairs layers,
  PDF paths or chunks. The contract checks raw selected evidence for full pages;
  it does not implement or authorize a compact model request.
- The bundle ceiling applies to canonical question/evidence bytes, not the larger
  local response containing full provenance, token usage or cost. No compression,
  answer-quality improvement, clean install, other-machine restore, independent
  scientific pilot or browser acceptance is claimed. Retrieval still requires its
  configured index and local model cache; the normal runtime may need first-use
  embedding-model installation outside this offline smoke.

Verdict:

The explicit preparation API/UI is implemented and exercised on real local data.
Missing qualifiers, unknown metadata, old refusals and complete-page retention are
now visible before generation in that mode. All four observed contexts correctly
retain their declared technical blockers; this is not scientific acceptance.
The next bounded development should prepare source-supported block contexts with
conditions, negation and unresolved boundaries preserved, then compare them under
a new frozen protocol. Do not relax the full-page prohibition or silently trim
current evidence to obtain a pass.

## Use and local artifacts

After starting the application, open `/ui/answer/prepare`. API example:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer/prepare `
  -ContentType application/json `
  -Body '{"question":"What conductivity was reported for membranes containing Mars regolith?","method":"hybrid_cross_lingual","top_k":5}'
```

Local root: `output/records_stage31_20261022/`.

- `prepared_v01/`: pre-smoke requests, previous contexts, cache and inherited hashes.
- `live_v01/`: native request/response/UI-fragment triplets for all four questions,
  complete report and manifest. The UI fragments retain live application's HTTP
  links; they are not standalone local-PDF review pages.
- `review_v01/review.html`, `report.json`, `manifest.json`: searchable offline
  review with local original-PDF links for all four native results.
- `review_repeat_v01/`: second offline export.
- `postflight_v01.py`, `postflight_v01.json`: native JSON/UI/source/offset/cache/
  baseline/hash/link/credential verification.
- `pytest_target_v02.xml`, `pytest_target_v03.xml`: earlier completed diagnostics;
  `pytest_target_v04.xml`: successful final targeted run. The interrupted initial
  sandbox attempt is not a successful JUnit result.
- `pytest_full_v01.xml`: full-regression result, separate from scientific evaluation.
- `baseline_final_v01/`, `final_qa_v01.json`: source/dependency snapshot and final QA,
  excluding private corpus, database, model weights, output artifacts and credentials.

Offline re-export to a fresh directory performs no retrieval/API calls:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.answer_preparation export --prepared output/records_stage31_20261022/prepared_v01 --captured output/records_stage31_20261022/live_v01 --output-dir output/records_stage31_new_review
```

The clone alone lacks private predecessor/run/corpus artifacts. A new real smoke
requires PostgreSQL, the existing index and matching cache; new live retrieval is
not promised byte-identical. Existing frozen directories are never overwritten.
