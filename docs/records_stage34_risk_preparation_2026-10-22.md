# Stage34: preparation UI with context-risk audit

22 October 2026. Version `answer_preparation_risks_v0.1`.
[Prospective protocol](records/risk_preparation_protocol_v0.1.md),
[stage33 risk audit](records_stage33_context_risks_2026-10-22.md),
[stage32 block preparation](records_stage32_block_context_2026-10-22.md).

Changed:

- Added POST `/answer/prepare/blocks/risks` and GET/POST
  `/ui/answer/prepare/blocks/risks`, discoverable from preparation forms. The new
  API returns the complete unchanged block preparation plus its stage33 audit in
  a versioned envelope. It accepts the existing validated question/search options,
  not client PDF paths, plans, evidence or admission overrides.
- Added readable page/window tables, exact expandable source text, original-PDF
  links, geometric/trigger relation counts, full source registries and unresolved
  diagnostics. Each page explicitly shows aggregate diagnostic-window coverage.
  Empty/no-anchor/unproven-mapping states remain visible. No source text is clipped.
- Added per-audit page/window search and expandable unchanged parent preparation.
  Text, questions, titles and error messages are escaped. Known failures keep
  diagnostic HTTP statuses; unexpected failures propagate. No per-case scientific
  resolution forms or generation action is introduced.
- Preserved form options, explicit library scope and the library cookie. Navigation
  links explicitly carry the selected library ID, so a different cookie cannot
  silently change the scope when opening the audit.
- Existing `/answer`, `/answer/prepare` and `/answer/prepare/blocks` JSON contracts,
  extraction/OCR, chunking, retrieval scores, qualifiers and source guards remain
  unchanged. Only preparation-form navigation was added to the older UI. The new
  mode never constructs an external model request and always reports
  `network_ready=false`.

## Frozen real integration

The four unchanged stage32 questions ran through the actual new ASGI API, with
read-only PostgreSQL source verification/retrieval and the existing hash-bound
offline BGE query-embedding cache. Code, protocol, tests, cache and predecessor
artifacts were frozen before each batch. These were four API requests per batch;
production-renderer fragments were saved from their native responses. This is not
a claim of four browser-driven form submissions.

The final batch preserves **all four complete preparations exactly against
stage32** and **all four complete audits exactly against stage33**. It contains
the same **19 Evidence objects / 193240 raw characters**, **35 page occurrences**
and **527 diagnostic windows**. Missing metadata remains unknown. All original
blocking reasons, old refusals, byte ceilings and page-union checks remain intact.

| Question | Diagnostic windows | Preparation equals stage32 | Audit equals stage33 | Network-ready |
| --- | ---: | --- | --- | --- |
| conductivity_protocol | 150 | Yes | Yes | No |
| dsc_protocol | 0 | Yes | Yes | No |
| preparation_atmosphere | 165 | Yes | Yes | No |
| absent_material | 212 | Yes | Yes | No |

The audit remains diagnostic: 1549 image/vector occurrences and 90 trigger records
are not accepted measurements or independent error labels. Geometric disjointness
does not prove irrelevance. Diagnostic-window unions still cover 22 page
occurrences; the unchanged parent candidate retains its separate three-page union
finding. The UI makes these distinctions visible and does not upgrade any refusal.

There were **eight actual ASGI API requests across two four-question batches**,
and **zero generative API calls**. Existing local query embeddings ran; their call
count is not independently instrumented. Original PDFs, selected text layers,
database content, model weights and index generation were not changed.

The first batch completed successfully before a navigation issue was found:
the new audit link omitted an explicit library ID. The first source snapshot,
prepared plan and complete native outputs are preserved separately. After fixing
the link and adding two cross-page scope tests, a new plan was frozen and the same
four requests repeated. No scientific rule, request, threshold or scope was tuned
to outcomes. Native requests, responses and renderer fragments are byte-identical
between batches; the correction affects form navigation. The first full regression
was interrupted for this repair and is not reported as a pass.

Tests run:

- Final targeted regression: **157 passed**, one existing Starlette/httpx warning;
  `pytest_target_v03.xml`. Covers old preparation/block/audit behavior, validated
  options, exact native PDF geometry, generation-factory exclusion, source identity
  failures, empty/unproven states, text escaping, error statuses, explicit library
  navigation over a different cookie, frozen input/code drift and exclusive exports.
- Full regression: **2134 passed**, one existing Starlette/httpx warning, no
  failures/errors/skips, **205.68 seconds**; `pytest_full_v02.xml`. Full/API tests
  ran outside the sandbox because of its prior TestClient restriction. Ruff
  passed; mypy passed for **150 source files**.
- All four native API JSON results, production UI fragments and audit replays
  match. **527** exact window quotes are present in the production renderer;
  **90** trigger records match their registered source spans. The two independent
  exports are byte-identical for HTML, report and manifest.
- Frozen bindings verify: **910** final preparation, **924** final live capture
  and **927** per review. The stage33 **558-file** archive and the pre-navigation-
  fix **563-file** archive verify. The first live run verifies **928** bindings
  through two explicit historical source mappings for its changed form/test files.
  Original manifests are unchanged; private-data drift never uses archive fallback.
- Static review contains four question cards, four scoped audit/search controls,
  35 page sections, 527 window rows, no forms and **142 existing local links**.
  Exact configured-credential scanning across **38** prepared/live/review files
  finds zero matches; keys were not printed. These are static/TestClient checks,
  not browser or scientific acceptance.
- Initial targeted checks passed 25 and then 155 tests before the navigation
  correction; their artifacts remain saved. An initial mypy re-export diagnostic
  was corrected before the first frozen API batch by importing the version from
  its defining module. It did not alter runtime behavior or scientific policy.

Limitations:

- The four questions were already exposed development inputs. Source integrity,
  unchanged payloads and software regressions do not establish scientific
  precision/recall, complete paragraphs, table semantics, cross-page relations or
  per-result method/condition association. Scientific quality remains unmeasured.
- No browser rendering, interactive search acceptance, independent pilot, clean
  installation or other-machine restore is claimed. Static/TestClient checks do
  not establish those. The earlier local-file browser restriction was not bypassed.
- The existing `/answer` remains a separate generation path. This preparation UI
  does not add new inference providers or modify admission for other routes.
- Frozen replay needs private predecessor outputs, PDFs, cache/index identities
  and verified source snapshots. Changed historical source binds explicitly to
  archived bytes; private-data drift cannot use that fallback.

Verdict:

The risk audit is now available in the preparation workflow without changing
selection or scientific admission. Every observed packet remains blocked. Next
bounded task: source-supported author/year metadata diagnostics from article front
matter, preserving unknown/ambiguous cases and exact source provenance; no guesses
from reference lists or automatic scientific confirmation.

## Use and artifacts

After application startup, open `/ui/answer/prepare/blocks/risks`, enter a question
and run preparation. The original preparation/block forms link to this mode.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer/prepare/blocks/risks `
  -ContentType application/json `
  -Body '{"question":"How was conductivity measured?","method":"hybrid_cross_lingual","top_k":5}'
```

Local root: `output/records_stage34_20261022/`.

- `prepared_v01/`, `live_v01/`: first successful API batch, before the navigation fix.
- `baseline_before_scope_fix_v01/`: preserved 563-file source/dependency snapshot.
- `prepared_v02/`, `live_v02/`: final freeze and final native request/response/UI sets.
- `review_v01/`, `review_repeat_v01/`: separate full report/HTML/manifest exports.
- `postflight_v01.py` / `postflight_v01.json`: native/source/span/link/binding checks.
- `pytest_target_v03.xml`: final targeted regression evidence.
- `pytest_full_v02.xml`: final successful full regression.
- `baseline_final_v01/`: final source/dependency snapshot, excluding private
  corpus, database, generated outputs, weights and credentials.
- `final_qa_v01.py` / `final_qa_v01.json`: final source, test, link and binding QA.

Offline export to a fresh directory, without retrieval or API requests:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.risk_preparation export --prepared output/records_stage34_20261022/prepared_v02 --captured output/records_stage34_20261022/live_v02 --output-dir output/records_stage34_new_review
```

Use `prepare` and `run` subcommands for a new frozen integration. Defaults point
to stage32 native results, stage33 audit/source snapshot and the stage29 verified
offline cache manifest. A fresh live run is not promised identical on changed data.
