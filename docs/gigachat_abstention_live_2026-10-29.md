# GigaChat: live verification of two abstention cases, 29 October 2026

Verdict: **both requests returned HTTP 200 and structurally consistent JSON,
but the expected abstention was observed in only one of the two cases**.
The lunar-regolith control returned `answerable=false, claims=[]`. The exact
dwell-duration query returned `answerable=true` with a thermal-equilibrium
criterion rather than the requested exact duration. HTTP success is not a
successful scientific answer to that question.

Changed:

- Added a separate prospective
  [two-case protocol](records/gigachat_abstention_live_protocol_v0.1.md), fresh
  preparations, study contract, archived source and result/review artifacts.
  The user explicitly authorized executing the proposed two-case live test.
- Reused the unchanged current production ASGI `/answer`, retrieval, selection,
  adequacy gate, factory-created GigaChat adapter, native transport/schema/parser
  and local validation. No production code was changed in this live-test stage.
- Each preparation and send used a fresh Python process to preserve the stated
  workaround for the previously observed read-only ORM/cache lifecycle issue.
  DB transactions remained repeatable-read/read-only and query embeddings used
  the existing offline cache. No cache setting, DB/PDF/index or ingestion changes.

## Frozen comparison and budget

The questions are the unchanged `missing_hold_duration` and `unsupported_regolith`
cases from the four-question batch. Fresh API parameters, ranked/final traces,
source registries and article metadata matched that batch byte-for-byte. Native
bodies matched the independently saved offline candidates after the instruction
change. No old evidence was manually substituted into automatic retrieval.

| Case | Request bytes | Native request SHA256 |
| --- | ---: | --- |
| missing_hold_duration | 71620 | e8b98230b891c6753bd07b8d05de2321adff2a0fa90925bde0ea92eb63c0fd20 |
| unsupported_regolith | 43005 | 8c20f8e9d8e0cce88acf23600753d92849779489d3a50496de46f44c418f3e0f |

Actual budget use: **two model POSTs and two OAuth exchanges**, one per case,
zero automatic retries/fallbacks, no account reads, purchase or scope upgrade.
Both sends ran outside the known sandbox socket restriction. Each used personal
scope `GIGACHAT_API_PERS`, `GigaChat-2-Max`, maximum 1200 output tokens, 120 seconds
per HTTP request and default sampling. Both native choices ended with `stop`;
declared returned model: `GigaChat-2-Max:2.0.30.01`.

## Actual outcomes and assistant source review

### Exact dwell duration

The public result is HTTP 200 / `answered`. Native `answerable=true` has one
claim citing exact ID `E3`:

> Перед измерением проводимости образцы выдерживались при каждой температуре
> в течение времени, необходимого для достижения термического равновесия,
> о чём судили по неизменности спектров.

E3 resolves to Каюмов 2021, selected original-layer pages 2–3. The original page 3
supports measurement after thermal equilibrium judged by unchanged spectra.
However, the question explicitly requests an **exact dwell duration**. The
response supplies no duration and does not state that the requested exact time
is unavailable. A related supported criterion has replaced the requested answer,
and the model has still declared the question answerable.

The response does not invent a numerical dwell time. The source's 24-hour solvent
mixture conditioning and two-day membrane soaking belong to preparation, not a
per-temperature measurement dwell. Exact source windows with page/layer/offsets
and PDF hashes are preserved. The unmet expectation is task/answerability
coverage, not another JSON/citation syntax error. Absence is assessed only in
selected evidence, not asserted for the whole article or corpus.

Usage: **12403 prompt / 87 completion / 12490 total** tokens.

### Lunar-regolith control

The native response is exactly `{"answerable": false, "claims": []}`.
The public result is HTTP 200 / `insufficient_evidence`, with null answer and
empty claims/citations. This is the expected format and model abstention on
the selected evidence. It replaces neither the old raw response nor its failure.

The selected texts have no literal regolith/lunar material cue; no conductivity
value for the requested hypothetical combination is supplied. This is not
independent gold or proof of corpus-wide absence.

Usage: **8523 prompt / 18 completion / 8541 total** tokens.

## Tests run

- Two real ASGI `/answer` calls: **two HTTP 200** results; native format consistent
  in both; expected abstention observed in **one**. These are case outcomes,
  not a 50% scientific accuracy or general refusal-success estimate.
- Offline ASGI replay used saved ranked retrieval and native bytes. It reproduced
  both exact HTTP statuses and full public bodies. Native transport was replaced
  only with explicit local placeholders/saved response bytes; real model calls
  during replay: **0**. DB connections were explicitly forbidden during replay.
- Current source/cache/index/PDF and study bindings verified; **186 source files**
  archived. Fresh/live native request bytes match. Both new append-only request
  slots match their saved results; old negative-case output manifests and slots
  are unchanged. The previous batch's HTTP 502 failures remain historical failures.
- All **9 selected evidence occurrences / 5 documents** are retained in the final
  review, including metadata gaps and uncollected Conclusions/Terms.
  Static HTML QA: **2 case cards**, **5 TAC rows**, **8 existing original-PDF/page
  links**, expandable full request/response/evidence/diagnostics and search.
- Exact configured-credential scan: **0 matches**. No OAuth body/token was
  persisted. Offline replay network denials: `[]`.
- Ruff of the case driver and postflight script: passed. `git diff --check`:
  passed. Existing Starlette/httpx deprecation warning remains. No production
  code changed here; the 168-case affected suite and mypy success belong to the
  preceding instruction-fix stage and were not rerun or counted as new tests.

Aggregate observed usage: **20926 prompt / 105 completion / 21031 total** tokens.
Precached prompt counts remain separate provider observations; no token-cost
conversion or verified monetary spending cap is claimed. Monetary cost remains
unknown. Per-request timing and raw provider usage are in the saved results.

## Artifacts and limitations

- Study contract: `output/gigachat_abstention_live_20261029/study_contract_v01.json`.
- Fresh inputs and real raw/API results:
  `output/gigachat_abstention_live_20261029/cases/<case_id>/prepared/` and `live/`.
- Source archive: `output/gigachat_abstention_live_20261029/source_snapshot_v01/`.
- Driver: `output/gigachat_abstention_live_20261029/run_case_v01.py`.
- Offline replay: `output/gigachat_abstention_live_20261029/postflight_v01.py`.
- Final searchable HTML and detailed QA:
  `output/gigachat_abstention_live_20261029/review_v01/review.html` and `report.json`.
- Both new SHA256 slots under `data/experiments/gigachat_answer_runtime_attempts/`
  are consumed. **The two-call authorization is exhausted.** Changing output
  paths or reusing old offline readiness flags must not reopen them.

Two repeated exposed cases with default sampling cannot establish independent
scientific acceptance, general accuracy, causal attribution or reliable refusal
behavior. The old boolean/claims inconsistency did not recur in this run; that
does not prove it cannot recur. A structurally valid contextual claim still failed
the exact requested-value task. Process isolation, full-page context exposure,
extraction noise and broader cache/session behavior remain limitations. Static
HTML and in-process ASGI are not browser UI acceptance. Compression is deferred.

Next step: strengthen answerability relative to the specific requested quantity:
a supported neighboring fact or equilibrium criterion does not establish an
unreported exact duration. Add offline coverage regressions and preserve source
traceability and strict validation. Do not claim the parser should infer missing
scientific relationships, hard-code these two questions, repair old outputs or
launch more model calls without a new bounded authorization.
