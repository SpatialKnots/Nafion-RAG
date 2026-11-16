# ARIADNE: current answer pipeline in the web interface

2026-11-16, Asia/Yekaterinburg. Local implementation and verification.

User requested the complete current answer path in the frontend after confirming
that the main form did not activate the 13 November rewriting experiment.

Scope: a named current pipeline, question rewriting with the existing GigaChat
transport and v0.2 validation, request-local ranking/selection/adequacy, existing
requirement-guided answer provider and required-fields delivery guard, readable
source presentation, and separate native/guard diagnostics. Main-page entry points
will select this pipeline explicitly. Existing API contracts and archived experiments
remain available; no changes to PDFs, DB schema, extraction, index or thresholds.

The experiment used manual post-rewrite meaning review and frozen, source-verified
titles. Automated web rewriting cannot be claimed equivalent to that human review.
Use existing TAC title extraction on hash-checked original front pages where a
single explicit article reference resolves; unavailable title context stays unknown.
Preserve the original question for generation and original material/relation vetoes.
Reject invalid rewrites without repair, fallback or repeated model calls.

Validation planned: synthetic HTTP/UI pipeline tests with intercepted model
transport, parity with archived rewriting validators/adapters, concurrency controls,
focused regressions, Ruff/mypy, and local read-only HTTP page checks. No live
model/OAuth calls are authorized for implementation verification. Existing closed
experiment budgets are never reused.

UI submission will disclose at most one rewrite and one answer call, no automatic
retry, diagnostic limits, source coverage uncertainty and lack of independent
scientific acceptance. A failed/withheld answer must preserve the available rewrite
and native diagnostics.

Changed:

- Added `/answer/current`, `/ui/answer/current` and its async result route, with
  versioned `current_answer_web_v0.1` diagnostics. Main-page form now uses this
  path explicitly, with top-5 / claims / Russian defaults matching the trials.
  Baseline API/UI and experimental required-fields endpoints remain available.
- Ported v0.2 request/parser/validation into `app/generation/query_rewriting.py`.
  Existing experimental scripts remain unchanged. Nullable verified-title context
  is an explicit extension for general questions or unresolved title extraction;
  it is recorded as unavailable, never fabricated from a filename.
- Ranking query is an explicit parameter through retrieval. The service adds the
  English topical query to evidence selection and uses the same translated
  adequacy with original material/relation vetoes. No process-wide monkeypatches.
- Reused the general TAC title algorithm on hash-checked original PDF front pages.
  Three actual works resolve to the same title contexts as the archived trial.
- Reused `RequirementGuidedAnswerProvider` and `RequiredFieldsGuardProvider`.
  Native transport bodies, parsed native result, guard review, selected raw
  sources/layers, retrieval metadata and PDF links are exposed separately.
  OAuth tokens and authorization headers are not collected or exposed.
- Current requests use read-only repeatable-read transactions with rollback.
  Their vector-index ORM cache is disabled: the archived process cache retains
  session-owned rows, and rollback made a second real request raise
  `DetachedInstanceError`. This workaround is scoped to the new path; global
  cache repair remains separate. Index weights/scoring/thresholds are unchanged.
- Corrected two pre-existing positive reuse-test fixtures to reside under their
  isolated `ROOT/output`. The production path guard and negative escape test
  are unchanged. The original full-run failures remain in verification logs.

Tests run:

- Full regression `tmp/current_answer_web_full_v01.xml`: **6151 passed, 2 failed**,
  no skips, one existing Starlette/httpx deprecation warning, 778.67 s. Both failures
  are the pre-existing reuse fixture's output-root mismatch described below.
  After the test-only correction, `tmp/current_answer_fix_v01.xml`: **34 passed**,
  including all three reuse tests and all 31 new pipeline tests. A clean full-suite
  rerun is not claimed; the running full suite had already imported the old test
  definitions when the isolated fix was verified.
  Final `pytest --lf`, `tmp/current_answer_web_lastfailed_v01.xml`: **2 passed**
  in 0.43 s; both previously failing cases re-executed after the full run ended.
- 309 focused tests passed before the final two additional controls; 34 later
  tests passed, including all 31 new pipeline tests and three reuse controls.
  Synthetic HTTP/UI checks cover both model stages, missing evidence, failed
  rewriting, provider abstention/error, guard withholding/native retention,
  scoped library, original question, citation links and credential non-disclosure.
  Concurrency control exercises 12 independent requests without global patches.
- All 30 archived rewrite responses match the old v0.2 parser exactly: 27
  structurally valid, three rejected. The later manual F6 meaning rejection is
  deliberately not misrepresented as an automatic parser rejection.
- Actual local read-only replay of all 26 historically accepted cases through
  the new current pipeline: **26/26 exact** native rewriting requests, native
  answer requests, retrieval, evidence, preparation metadata, title contexts,
  delivered answers, guard reviews and delivery statuses. Saved model outputs
  are supplied only after answer-request byte equality. Report:
  `output/current_answer_web_20261116/replay_v03/summary.json`.
  Real model/OAuth calls: **0/0**. No historical ledgers/allowances reused.
- Full app mypy: 231 source files passed. Ruff for app/changed tests/new verifier
  passed. `git diff --check` passed (existing Windows line-ending notices only).
- Restarted the local server and read both main/current pages: HTTP200, current
  submit route, call disclosure and top-5 default verified. No live question POST.
- `output/current_answer_web_20261116/version.json` binds 256 app/resource/TAC/
  verification source files and base commit `270263e`; implementation remains
  in the working tree, with pre-existing user modifications preserved.

Diagnostics retained:

- Sandbox TestClient run produced no output and was interrupted. The explicit
  outside-sandbox offline run completed. Initial 28pass/1fail was a synthetic
  question outside the existing energy grammar; test question corrected, grammar
  unchanged. The next 70pass/1fail was the old dashboard route assertion, updated
  to the deliberately changed form route.
- First source-title probe used `.text` instead of the existing TACSpan `.quote`;
  corrected before successful three-PDF checks and 26-case replay. An actual
  PDF-span/checksum regression test now covers this path.
- Replay v01 stopped at an exporter envelope key mismatch. Replay v02 exposed
  the ORM cache lifetime defect and an inappropriate presentation projection for
  retrieval equality. V03 uses request-local index loading and raw retrieval
  dataclasses; archived outputs were never rewritten to obtain equality.

Limitations:

- A fresh live rewrite/answer has not been run. Support for the archived provider
  contract is historical; current returned model version, usage, price and actual
  latency are unknown. Each user submission can make up to two model POSTs and
  two fresh OAuth exchanges; no automatic retry/fallback/continuation.
- F6 was rejected manually in the trial, while its rewrite is structurally valid.
  The automatic web path does not reproduce that human semantic filter. Three
  literal-ID rejections remain strict. No new semantic correctness claim.
- Exact replay preserves the old answers and their known scientific failures;
  it does not fix missing source paragraphs, quantity ownership, PDF glyphs or
  all finite-grammar false holds. The deferred improvement queue remains pending.
- No independent scientific evaluation, new accuracy, complete offline inference,
  deployment or visual-browser verification is claimed. The HTTP/UI tests and
  live GET checks verify wiring, not visual layout or new live answer quality.
- Disabling the current path's ORM cache may increase local retrieval overhead;
  performance has not been benchmarked. The baseline cache defect remains open.

Verdict:

The current web path is connected and locally running. Archived accepted-case
behavior is reproduced exactly offline, with manual meaning-review limitations
explicit. Integration does not change the historical 75% overall project-plan
estimate or establish independent scientific acceptance.
