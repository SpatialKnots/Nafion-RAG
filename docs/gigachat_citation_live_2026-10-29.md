# GigaChat citation fix: live /answer verification, 29 October 2026

Verdict: **HTTP 200 / answered** on the newly authorized post-fix live request.
Both claims use the exact raw ID `E1`; the unchanged production citation
validator accepts them. This is one successful exposed development case,
not independent scientific acceptance or a general reliability estimate.

Changed:

- Added a separate prospective
  [post-fix protocol](records/gigachat_citation_live_protocol_v0.1.md), frozen
  study contract, source snapshot and new artifacts under
  `output/gigachat_citation_live_20261029/`. Production code was not changed
  during this stage. The previous failed live result and offline fix report
  retain their original identities and outcomes.
- Reused the existing smoke runner and actual in-process ASGI POST `/answer`:
  current local retrieval, selection, gate, factory-created GigaChat adapter,
  verified HTTPS transport, native parser, citation validation and response
  assembly. Preparation/live DB transactions were repeatable-read/read-only;
  cached query embeddings ran offline. No DB/PDF/index/ingestion changes.
- The user authorized the proposed next one-call live check with «давай».
  No previous attempt slot was reset or reused.

Observed request and response:

- Same question: «Каким методом измеряли проводимость мембран и как выполняли
  уравновешивание образцов перед измерением?» Collection `literature`,
  `hybrid_cross_lingual`, top-k 5, style `claims`, language `auto`.
- Fresh `api_request.json`, ranked/final `trace.json`, `sources.json` and
  `articles.json` are byte-identical to the old pre-fix preparation. The five
  selected evidence objects still come from three recorded documents:
  Каюмов 2021, Чернюк 2024 and Guo 2020. No manual evidence substitution.
- Native request is byte-identical to the separately captured offline post-fix
  candidate: **74093 bytes**, SHA256
  `6d16aa501118f63a5a19238d7d33ba5d14e33a134a63d8f5f2fb6e82ed48ce38`.
  The request-local schema enum contains `E1` through `E5`.
- **One model POST, one OAuth exchange**, zero automatic retries/fallbacks,
  no account reads, purchase or scope upgrade. The authorized send ran outside
  the sandbox because its socket restriction had already been established.
  Scope `GIGACHAT_API_PERS`, requested `GigaChat-2-Max`, maximum 1200 output
  tokens and 120 seconds per HTTP request. Declared returned model:
  `GigaChat-2-Max:2.0.30.01`; native finish reason `stop`.
- Usage: **14106 prompt**, **139 completion**, **14245 total** tokens;
  precached prompt tokens separately reported as **3**, not added to the total.
  Model request elapsed **7.206806899979711 seconds**, including response transfer.
  Monetary cost remains unknown; token/time limits are not a spending cap.
- Native schema parsing, production citation checks and ASGI response assembly
  succeeded. Actual returned claims, both with `citation_ids: ["E1"]`:

  1. «Электропроводность мембран измерялась методом импедансной спектроскопии
     в поперечном направлении мембраны.»
  2. «Образцы мембран уравновешивались перед измерением до достижения
     термического равновесия, о чём судили по неизменности спектров.»

Assistant source review, separate from format success:

- Both claims resolve only to E1, recorded title Каюмов 2021, source chunk
  pages 3–4. Exact supporting windows are in its registered original text layer,
  page 3, with source offsets, text-layer identity, PDF path and hashes saved.
- The method window explicitly gives impedance spectroscopy in the transverse
  membrane direction. The equilibrium window states thermal equilibrium judged
  by unchanged spectra. On this exposed case, the assistant assesses both
  paraphrases as source-supported. This is not independent gold or accepted
  scientific accuracy; no percentage accuracy is calculated.
- The answer does not invent an equilibration duration or substitute solvent
  swelling equilibrium. It does not provide a complete numerical protocol:
  temperature/frequency ranges and other source conditions are not all reported.
  The article is identified through E1, not named in claim prose. This is not
  a synthesis of all three retrieved documents or a completeness assessment.
- Formula fragments and line-break/hyphenation noise near the equilibrium
  wording remain visible in the exact source windows; source text was not repaired.

Tests run:

- Actual live ASGI POST `/answer`: **HTTP 200**, two claims, exact ID `E1`.
  The endpoint accepted this native enum request and the observed output conforms.
  This does not establish that every future response will satisfy the constraint.
- Offline ASGI replay used saved ranked retrieval and the original native
  response with local transport placeholders. The current production chain
  reproduced the **same HTTP status and full response body**. Real model requests
  during replay: **0**; DB connections were explicitly forbidden during replay.
- Verified **225** current input hashes, the prepared/live/review manifests and
  **185 archived source files**. The prospective study contract also binds the
  new protocol, freeze script, runtime tests, prior comparison files and offline
  candidate. Final live request equals preparation bytes.
- All five prior smoke output manifests and both parent/continuation ledger
  results were preserved. The new SHA256 slot matches the new live result and
  is consumed; do not resend by changing the output path.
- Static final HTML QA: **3 TAC article rows**, **2 source-review cards**,
  **5 existing original-PDF/page links**. All agreed TAC columns remain present;
  missing metadata and uncollected Conclusions/Terms remain explicit.
- Exact configured-credential scan found **0 matches** in the new artifacts
  examined before final rendering. No OAuth body/token was persisted.
  External network denials in offline replay: `[]`.
- Ruff of the freeze/postflight scripts: passed. Initial postflight lint found
  two long lines; only their formatting was corrected. `git diff --check`: passed.
  No production code changed, so the 155-case affected suite and mypy result
  remain results of the preceding fix stage, not new runs claimed here.

Artifacts:

- `output/gigachat_citation_live_20261029/study_contract_v01.json` — prospective
  authorization/scope/protocol/input comparison bindings.
- `output/gigachat_citation_live_20261029/prepared_v01/` — fresh automatic
  retrieval, source registry, full exact request and generic runtime contract.
- `output/gigachat_citation_live_20261029/source_snapshot_v01/` — archived code.
- `output/gigachat_citation_live_20261029/live_v01/` — unchanged raw model response,
  native ASGI result, usage, timing and reservation details.
- `output/gigachat_citation_live_20261029/review_v02/review.html` — final searchable
  full review with source checks and all selected TAC documents.
- `output/gigachat_citation_live_20261029/review_v02/report.json` — replay/source QA.
- `output/gigachat_citation_live_20261029/freeze_study_v01.py` and
  `postflight_v01.py` — separate freeze and offline replay/QA code.
- Reservation:
  `data/experiments/gigachat_answer_runtime_attempts/6d16aa501118f63a5a19238d7d33ba5d14e33a134a63d8f5f2fb6e82ed48ce38/`.

Limitations:

One known question, default sampling, one pre-fix and one post-fix model response;
no causal isolation, statistical superiority, independent scientific annotation,
broader quality estimate or full-corpus completeness claim. The existing prompt
still includes **10 complete-page occurrences**; this is the raw-chunk runtime,
not context-compaction acceptance. Existing metadata gaps and extraction noise
remain. Native/header response IDs are absent/not exposed and remain unknown.
Static HTML/link checks and in-process ASGI do not constitute browser UI QA.

Next: define a separately budgeted set of new questions, including different
measurement conditions, cross-article comparison and insufficient evidence.
Do not extend the consumed one-call authorization automatically. General
context-compression instrumentation remains deferred.
