# GigaChat: four new development questions, 29 October 2026

Verdict: **four model requests completed; two `/answer` responses were accepted
(HTTP 200), two were rejected (HTTP 502)**. The rejected responses both set
`answerable=false` while supplying a nonempty `claims` array. This violates the
existing local consistency rule. The responses were not repaired or counted as
accepted scientific abstentions. These are technical outcomes, not 50% accuracy.

Changed:

- Added versioned questions, prospective assessment rules and separate protocols:
  [cases](records/gigachat_answer_batch_cases_v0.1.json),
  [v0.1 scope](records/gigachat_answer_batch_protocol_v0.1.md),
  [v0.2 process isolation](records/gigachat_answer_batch_protocol_v0.2.md).
  The user explicitly requested continuing testing. Budget was frozen before
  inference: at most four model calls, one per eligible case, no retries/fallback.
- Added `scripts/gigachat_answer_batch.py` and seven safety cases. The wrapper
  scopes each question/protocol in the unchanged smoke helper and runs each case
  in a fresh process. Production prompts, schema, parser, validation, retrieval,
  cache settings, thresholds and model defaults were not changed in this stage.
- Real preparation and live requests used actual in-process ASGI POST `/answer`,
  automatic `hybrid_cross_lingual` retrieval, collection `literature`, top-k 5,
  `claims`/`auto`, offline cached local embeddings and repeatable-read/read-only
  PostgreSQL transactions. No DB/PDF/ingestion/index mutation.

## Observed cases

| Case | Native request bytes | API outcome | Observation |
| --- | ---: | --- | --- |
| measurement_conditions | 57093 | HTTP 200 / answered | Four claims: method/direction, Ti cell, 1 Hz–3 MHz, equilibrium criterion and 20–100 mV |
| equilibrium_comparison | 73686 | HTTP 200 / answered | Two claims separate Kayumov thermal equilibrium from Chernyuk gravimetric constant mass at 25°C; wording/citation caveats below |
| missing_hold_duration | 71313 | HTTP 502 | Raw reply declines an exact dwell time, but `answerable=false` has one claim with E3/E4 |
| unsupported_regolith | 42698 | HTTP 502 | Raw reply declines the hypothetical material's conductivity, but `answerable=false` has one explanatory claim with empty citations |

All four passed the existing local adequacy gate. The negative-regolith query
was allowed despite no literal regolith/lunar cue in the selected source texts.
This demonstrates a limitation of necessary mention/coverage checks; gate
allowance does not establish the requested material/value/condition relationship.
It does not prove that the entire corpus lacks such data.

Native JSON and the typed `_Answer` schema parsed in all four cases. No observed
ID was foreign to its own supplied evidence set. The two failures occurred in
the additional local `answerable`/`claims` semantic check:
`GigaChat answerable and claims are inconsistent`.
The current JSON Schema does not encode that cross-field rule. These responses
therefore do not establish that GigaChat ignored its supplied JSON Schema.

The raw negative replies acknowledge missing information, and neither reports
a requested conductivity or dwell value. Their invalid structure still makes
them runtime failures. The lunar-control explanation is also in English despite
the Russian question; it is preserved as returned.

## Source review, separate from runtime acceptance

All **19 selected evidence occurrences** across **6 recorded documents** are
included in the HTML scope. Recorded metadata is preserved; missing metadata
and Conclusions/Terms not collected by the smoke are explicitly marked.

- Measurement conditions: the four accepted claims match the Kayumov original
  text on registered page 3: transverse impedance measurement, blocking
  Ti/sample/Ti cell, frequency range 1 Hz–3 MHz, unchanged spectra as the thermal
  equilibrium criterion, and external signal amplitude 20–100 mV. E3/E4 overlap
  the same page and are not independent corroboration.
- Comparison: the core distinction is supported by Kayumov's thermal-equilibrium
  context and Chernyuk's gravimetric swelling context at 25°C until constant mass.
  However, the phrase `достигавшегося неизменностью спектров` blurs the criterion
  for recognizing equilibrium with the means of reaching it. The source says
  equilibrium was judged by unchanged spectra. Chernyuk E1 directly supplies the
  gravimetric method; the additional E2 discussion citation does not independently
  establish that method. Broad relevance is not the same as direct support.
- Exact-duration query: the examined Kayumov context supplies an equilibrium
  criterion, not an explicit per-temperature dwell duration. Its 24-hour solvent
  mixture conditioning and two-day membrane soaking refer to preparation and
  must not become a measurement dwell time. The raw reply declines a duration,
  but it is not a valid accepted abstention. Absence is scoped to selected
  fragments, not a claim about the complete article/corpus.
- Lunar control: selected texts contain no literal target-material cue. The raw
  reply declines the requested value instead of borrowing another membrane's
  conductivity, but the local answer contract rejects its explanatory claim.

Exact source windows retain original text, page/layer IDs, offsets, PDF paths
and hashes in the review JSON/HTML. This is assistant-authored review on exposed
development sources, not independent gold, accuracy or scientific acceptance.

## Infrastructure observations

The first same-process preparation is preserved at
`output/gigachat_answer_batch_20261029/`: one ready case, three explicit
`DetachedInstanceError` preparation failures, **zero model/OAuth calls**. Code
inspection found cached ORM rows in `LoadedVectorIndex.rows_by_chunk_id`, while
the smoke rolls back each read-only session. The lifecycle issue was not hidden
as lack of evidence, and production cache logic was not modified.

Before inference, v0.2 froze fresh-process execution with exactly the same four
questions and settings. All four prepared successfully in separate processes at
`output/gigachat_answer_batch_20261029_v02/`. The first preparation's outputs and
188-file source snapshot remain intact. This isolation is an explicit limitation:
repeated requests in a long-lived server under its real session lifecycle are
not established by this batch and need a separate regression investigation.

## Tests run

- Final software suite: **82 passed**, failures/errors/skips = 0: seven batch
  safety cases, seven prior smoke cases and 68 GigaChat runtime cases. JUnit:
  `output/gigachat_batch_tests_20261029_v02.xml`. The initial 79-case run is
  superseded, not added to the final count.
- Covered fixed four-case inventory, question/protocol restoration, explicit
  authorization, skip behavior for gates/preparation errors, immutable parent
  dispatch marker, per-case fresh process command, redacted worker logs, and
  prohibition of a send worker without its parent dispatch marker.
- Actual live ASGI: four model POSTs and four OAuth exchanges, no automatic
  retries, fallback, account reads, purchase or scope upgrade. All native choices
  completed with `stop`; each request used personal scope `GIGACHAT_API_PERS`,
  `GigaChat-2-Max`, at most 1200 output tokens and 120 seconds per HTTP request.
  Sends ran outside the already-known sandbox socket restriction.
- Aggregate native usage: **45071 prompt**, **657 completion**, **45728 total**
  tokens. Precached prompt counts are separate observations and are not added
  to or subtracted from the total. Monetary cost remains unknown.
- Offline ASGI replay reproduced **all four exact HTTP statuses and complete
  response bodies**, including both rejections, using saved ranked retrieval
  and native bytes. Real model calls during replay: **0**; DB connections were
  explicitly forbidden. Replaying a saved response did not alter its claims.
- Verified batch/source/cache/index/preparation bindings, all case/live manifests,
  the **189-file** final source snapshot, each new request/result slot and earlier
  live-smoke parent/continuation slots. No old slot or output was reset.
- Static final HTML QA: **4 case cards**, **6 TAC rows**, **16 existing PDF/page
  links**, full expandable source/request/response/diagnostics and search. Exact
  configured-credential scan: **0 matches**. No OAuth body/token persisted.
  Offline replay network denials: `[]`.
- Ruff `app scripts tests` and the postflight script: passed. `git diff --check`:
  passed. Initial postflight lint found closure-binding and long-line diagnostics;
  they were corrected, and the final offline replay/review was generated separately
  as `review_v02`. An existing Starlette/httpx TestClient deprecation warning remains.
  No new full-suite or mypy success is claimed for this stage.

## Artifacts and budget

- Final batch contract: `output/gigachat_answer_batch_20261029_v02/batch_contract.json`.
- Per-case frozen inputs/raw responses/API results:
  `output/gigachat_answer_batch_20261029_v02/cases/<case_id>/prepared/` and `live/`.
- Actual count/usage ledger summary:
  `output/gigachat_answer_batch_20261029_v02/dispatch_summary.json`.
- Final searchable review and offline/source QA:
  `output/gigachat_answer_batch_20261029_v02/review_v02/review.html` and `report.json`.
- Offline replay script:
  `output/gigachat_answer_batch_20261029_v02/postflight_v01.py`.
- Each native request has its own consumed slot under
  `data/experiments/gigachat_answer_runtime_attempts/`; exact SHA256 identities
  are in the per-case contracts and batch contract. The parent dispatch marker
  also blocks rerunning this batch. **The four-call budget is consumed.**

Limitations:

Four new phrasings on development sources, not an independent held-out pilot.
Two accepted answers do not establish 50% scientific accuracy. Source review
retains a wording caveat and a broad extra citation. Both insufficiency controls
failed the runtime contract even though their raw prose declines unsupported
values. Page-text exposure, extraction noise, retrieval relevance and metadata
gaps remain. Case-process isolation limits conclusions about long-lived servers.
Static HTML/ASGI checks are not browser UI acceptance. General context-compression
instrumentation remains deferred.

Next step:

Prepare a minimal offline clarification of the insufficiency contract:
`answerable=false` requires `claims=[]`; an answerable response requires supported,
cited claims. Preserve the existing consistency validator and raw failures.
Conditional schema support would need its own verification; do not silently
convert failed replies into valid abstentions. No such production fix or additional
model call was made in this testing stage.
