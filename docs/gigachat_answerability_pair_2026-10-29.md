# GigaChat: exact duration / qualitative criterion live pair

29 October 2026, Asia/Yekaterinburg. The user authorized continuing with the
proposed two-case live pair after the generic requested-information instruction.
The protocol and case expectations were frozen before generation. Both model
slots are now consumed, with no retries or fallback.

Changed:

- Added a bounded development check with a repeated exact-duration question and
  a qualitative equilibrium-criterion control. No production source, prompt,
  parser, schema, model, retrieval/scoring, limits, DB, index or PDF was changed
  during this stage.
- Prepared each case through the actual ASGI `/answer` chain with automatic
  retrieval, read-only repeatable-read database transactions and offline cached
  query embeddings. Each preparation/send used a fresh process because the
  earlier ORM/cache lifecycle issue remains unresolved.
- Frozen protocol: `docs/records/gigachat_answerability_pair_protocol_v0.1.md`;
  cases: `docs/records/gigachat_answerability_pair_cases_v0.1.json`;
  contract and 186-file code snapshot:
  `output/gigachat_answerability_pair_20261029/study_contract_v01.json` and
  `source_snapshot_v01/`. The driver is `run_case_v01.py` in that output root.
- Preserved raw native responses, exact request bytes, public API results,
  usage/timing, retrieval trace, full selected source pages, original-PDF hashes
  and append-only attempt reservations. Created searchable HTML with both cases,
  all four selected documents in the agreed TAC columns and explicit missing
  metadata/uncollected fields:
  `output/gigachat_answerability_pair_20261029/review_v01/review.html`.

Tests run:

| Case | Native result | Public result | Requested behavior |
| --- | --- | --- | --- |
| Exact measurement dwell duration, Kayumov 2021 | `stop`, valid JSON, `answerable=true`, one claim using exact `E3` | HTTP 200, `answered` | Not met: criterion supplied instead of an exact time or abstention |
| Qualitative thermal-equilibrium criterion, Kayumov 2021 | `blacklist`, generic provider restriction message | HTTP 502, `GigaChat response is incomplete or filtered; expected finish_reason=stop` | Not completed: no scientific answer to evaluate |

- Actual model: `GigaChat-2-Max:2.0.30.01`, personal scope. Exactly two model
  POSTs and two OAuth exchanges; zero automatic retries or fallback. Network
  execution used ordinary escalation after the previously established sandbox
  socket restriction. Both native bodies were below the 100000-byte cap, with
  the existing 1200 output-token limit and 120-second per-request timeout.
- Duration native request: 72406 bytes, SHA256
  `800e7898c57e809a55cced46ffb7f024adad98994c34a1468151650f55c1d737`.
  It matched the earlier offline candidate byte-for-byte. API parameters,
  automatic retrieval/evidence, sources and article metadata also matched the
  preceding live duration case byte-for-byte.
- Criterion native request: 80783 bytes, SHA256
  `1ec1c853cdd31dd4606b095a6892405e382a6db3db10c2ab3ac0976090317899`.
  Before generation, its automatically selected Kayumov evidence contained the
  declared equilibrium/unchanged-spectrum cues. This eligibility check is not
  an entailment classifier.
- Offline ASGI replay reproduced the exact public status and full JSON body
  for both cases, including the HTTP 502. Replay forbade database connections
  and used saved retrieval and native responses; no new model/network calls.
  Prepared/live/snapshot manifests, current frozen bindings and registry-result
  identity verified. Older batch and abstention manifests/results/slots verified
  without reopening historical admission contracts.
- Ruff passed for both new output scripts. Static HTML QA verified two case
  cards, four TAC rows and ten existing original-PDF links. Credentials were
  scanned without printing them; no matches. No browser rendering is claimed.
- The earlier 180 affected unit tests belong to the instruction-change stage;
  they were not rerun or counted as fresh tests here. The existing
  Starlette/httpx TestClient deprecation warning remains visible.

Observed scientific relation:

The duration response states that samples were held until thermal equilibrium,
judged by unchanged spectra, and cites `E3`. Kayumov's registered original text
on page 3 supports that criterion. It does not provide the requested numerical
measurement dwell duration in the selected method evidence. The model invented
no numeric duration but again substituted related context for the requested
answer despite the new explicit instruction. Page 2 preparation periods, such
as at least 24 hours or two days of soaking, refer to other stages. Exact source
windows, page/layer identities, offsets and PDF hashes are in `report.json` and
the expandable HTML; extraction noise is retained.

Provider-reported usage:

| Case | Input | Output | Total |
| --- | ---: | ---: | ---: |
| Duration | 12543 | 99 | 12642 |
| Criterion, blacklist | 1 | 0 | 1 |
| Sum as reported | 12544 | 99 | 12643 |

The filtered response's reported single input token is preserved literally.
It is not a measured request-token count or a billing estimate. No monetary
cost or information-retention/compression metric is inferred.

Limitations:

- Two exposed development cases, reviewed by the assistant; no independent gold
  annotation, accuracy estimate or scientific acceptance. The criterion query
  may retrieve different evidence, so this pair is not an identical-evidence
  causal experiment. The duration failure is a direct observation, not proof
  about every question or every possible prompt.
- `blacklist` is the provider's actual finish reason. Its trigger is unknown;
  neither the scientific topic nor a particular evidence fragment is established
  as the cause. There was no attempt to bypass the filter or change the request
  after observing it.
- Format/citation validation still cannot establish coverage of the requested
  information. No local semantic validator was added. Absence of an exact time
  is scoped to the selected evidence, not an article/corpus-wide proof.
- Long-lived-server ORM/cache behavior remains unverified. Fresh processes
  preserve the earlier diagnostic rather than resolve that infrastructure issue.

Verdict:

The generic requested-information instruction did not resolve the repeated
duration case. The positive qualitative control was blocked by the provider;
it cannot establish that qualitative answering works under the new instruction.
Current strict rejection preserved the filtered failure as HTTP 502. Both new
slots and all older budgets are closed. Next useful work is offline design and
testing of requested-information coverage and clearer provider-filter
diagnostics; further live calls require a separately declared scope. Preserve
these failures as regression evidence, without hard-coded question answers,
silent response repair or claims of general scientific reliability.
