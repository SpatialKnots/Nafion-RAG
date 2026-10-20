# Records stage04: separate OpenAI backend and four frozen requests

Date: 20 October 2026. Development comparison; independent scientific acceptance was not performed.

## Changed

Added `app/records/openai_backend.py` and explicit `--backend openai` to `scripts.records_extract`. The existing local backend remains the default. OpenAI mode uses native Responses structured outputs at the fixed HTTPS endpoint, with `store=false`, normal TLS validation, no environment proxies, redirects or automatic retries. Keys remain in memory; request artifacts omit Authorization. Original source strings pass unchanged into the existing wire validators and literal resolver. The evaluator recognizes two explicit OpenAI extraction versions and reconstructs the saved request and runtime declaration before reparsing native raw responses. General RAG configuration was not changed.

The backend saves input, request, runtime settings and source/code manifest before sending, then raw response bytes before parsing. It retains usage and wire proposals when evidence validation fails. Refusals, incomplete responses and malformed/multiple text blocks are failures, not extraction abstentions. Candidate schema, units, evidence rules, metrics, database, ingestion, OCR, retrieval and original PDFs were preserved. See the [predeclared protocol](records/openai_comparison_protocol_v0.1.md).

## Frozen experiment

The user authorized four selected-text requests to OpenAI. Account model availability was checked with a read-only request before inference. Requested and returned model IDs were both `gpt-6-astra`; this is an alias, not an immutable dated snapshot. Only previously selected source regions and the original task/system messages were sent. Complete stored pages, original PDFs, reference answers and local PDF paths were not sent.

Exactly copied stage03 compact Abstract case and three stage02 full cases into `data/experiments/records/pilot/stage04_20261020/`. Combined reference SHA-256: `be40335d686490d430d0091d1a2b6e8d312d4947f887b5537c6c833b9f6af1c6`. The reference remains assistant-authored, exposed development material with `needs_independent_review`; expected values were not revised after inference. Three expected positive records retain sixty dimensions; bibliography is a separate negative.

Four actual native request bodies, input/task bytes, protocol, source PDF hashes, rates and settings were frozen before inference. Pre-inference source snapshot: 396 files, fingerprint `28721dc71b67297d761095c83a451268182a64b9991bbd65c7e4c9dce9f690e7`, at `output/records_stage04_20261020/baseline_ready/`. One later CLI help-text correction does not change inference or evaluation logic and is included in the final source snapshot.

Settings: default service tier, medium reasoning, strict schema, no temperature or seed, no tools, no truncation, 180-second transport timeout per request. Compact limit 2,048 output/reasoning tokens; each full limit 8,192. Exactly one attempt per case, no retry, repair, model switch or budget extension. Total declared generated-token cap: 26,624.

**Protocol deviation:** prose requested Abstract → table → cited result → bibliography. Preparation reused historical reference order, freezing and executing Abstract → table → bibliography → cited result. The last two were reversed. The frozen manifest, raw outputs and order were preserved; no rerun was used to conceal this deviation. Calls were independent with no shared conversation. No controlled latency/order-effect inference is made.

## Observed results

| Case | Elapsed | Output tokens | Result |
| --- | ---: | ---: | --- |
| Sanginov Abstract, compact | 3.895 s | 64 | Exact property, value, unit and temperature; sample null matches the bounded abstention expectation. Candidate passes integrity; full record remains deferred. |
| Sanginov footnote-d table | 31.810 s | 2,169 | Completed wire response; atomic evidence rejection. Conditioning citation has zero exact source occurrences. No candidate admitted. |
| Kayumov bibliography | 3.229 s | 52 | Explicit empty measurement array; correct development-negative abstention. |
| Istomina cited prior work | 31.659 s | 2,195 | One integrity-valid range candidate; three exact development-reference mismatches and nine deferred dimensions. |

Sanginov's table proposal selected `1.1 × 10 −4`, `20 °C` through footnote d, and `This work`. It kept plasticiser composition separate from final membrane composition in its notes. The conditioning quote introduced `equilibrat- \nning`, absent from the selected source. This single invalid citation rejects the whole candidate; twenty expected dimensions remain unavailable. A separate per-field audit exposes the raw proposal, including eight of ten non-deferred field/status agreements, without treating them as admitted extraction results or silently repairing the quote.

Istomina preserved the conductivity range, unit and associated temperature, the `range` representation and explicit attribution to prior work [26]. It left current-article method, conditioning and error out of the cited result. Three mismatches remain: sample wording `best sample` versus the reference's membrane descriptor; a longer exact plasticiser phrase; and a longer exact origin phrase. The latter two cover the reference evidence but differ in raw text. These are exact-reference mismatches, not three established scientific errors. No labels or scoring rules were changed after seeing them. Linkage remains proposed and its unresolved reference dimensions remain deferred.

Atomic evaluator: **3 integrity-valid cases / 4; 2 positive candidates / 3 expected; 1 correct negative abstention**. Across sixty record dimensions: **12 match, 3 mismatch, 25 deferred, 20 unavailable**. No positive full record obtains complete agreement. Evaluation exits **1**, correctly retaining the failed table case. These finite counts do not establish independent accuracy.

Saved local comparisons: all three stage02 full attempts timed out at 300 seconds; stage03 compact completed in 9.445 seconds but failed literal validation, with one of four raw fields exact. GPT completed all four and the compact fields matched four of four. Model, provider, schema enforcement, seed/temperature availability, reasoning and token budgets differ; this does not isolate a causal factor or establish a controlled speedup.

## Usage, privacy and cost

Observed aggregate usage: **4,132 input, 4,480 output, 8,612 total tokens**. Input details report 2,909 cache-write and zero cached-read tokens. Raw request/response IDs and usage remain in local run artifacts.

Conservative estimate **$0.275650**: charge every input token at the highest observed input/cache-write rate ($12.50/million), plus output at $50/million. This is an estimate, not an invoice or provider-enforced dollar cap. Actual account billing was not checked. Rate basis: official [model information](https://developers.openai.com/api/docs/models/gpt-6-astra) and [pricing](https://developers.openai.com/api/docs/pricing), verified before inference. `store=false` does not imply Zero Data Retention; see [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).

## Tests run

- Targeted native/OpenAI, compact and full extraction suites: **66 passed**, 4.26 s.
- Full regression: **1,120 passed**, one existing Starlette/httpx deprecation warning, 50.59 s. Seventeen new synthetic cases cover source-only messages, strict native requests, response failures/refusal, fixed transport destination, credentials, persisted failures, exact evidence and evaluator request tampering. Synthetic tests make no paid requests.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 99 source files.
- Four real API attempts: three integrity-valid cases and one rejected candidate as above. These are reported separately from passing software tests.
- Offline replays of stage02 and stage03: identical historical summaries and every case. Their prior failed outcomes remain failures.
- Source PDF and text-layer PDF hashes unchanged; input/task/request/reference/protocol hashes matched the frozen manifest. Pre-inference source snapshot verified. Credential scan of 112 experiment/review artifacts found no exact configured credential; no secret was printed.
- Static HTML audit: all four case rows, nine existing source-PDF links, exact escaped source fragments and per-field proposals present. Browser visual/click checks were not run because local-file navigation was blocked by browser security policy earlier in this session.

Private outputs, excluded from Git:

- `output/records_stage04_20261020/comparison.html` — searchable four-case comparison, expected/actual raw fields, sources, usage and failures.
- `output/records_stage04_20261020/comparison.json` — detailed offline field/citation audit, including the failed candidate.
- `output/records_stage04_20261020/evaluation/review.html` and `report.json` — unchanged full-record metric definitions applied to native API outputs.
- `output/records_stage04_20261020/qa.json` — source, replay and static-check evidence.
- `data/experiments/records/pilot/stage04_20261020/` — frozen inputs/reference/protocol/requests, raw responses, manifests, IDs and usage.

CLI reproduction uses fresh output paths and incurs new requests; the predeclared protocol provides the command. Offline evaluation and artifact inspection require no key or network. A clone contains code/protocol/report, not the private corpus or raw experiments.

## Limitations

Four exposed fragments are too small for general quality claims. The reference is not independent gold, contains deferred dimensions and exact text-boundary choices. Source selection is oracle-assisted; no whole-article extraction, independent evaluation, corpus-wide benchmark, production deployment, billing verification or clean-environment installation was performed. The alias and remote runtime prevent a deterministic replay guarantee. Table evidence copying remains fallible; no automatic scientific admission was added. Execution-order deviation and missing browser visual QA remain explicit.

## Verdict

The separate GPT API path is usable for the next bounded development experiment: it completes the planned cases and improves the compact literal result on this fixed source. It does not yet justify unattended admission of full scientific records. Next useful step: an explicitly versioned source-span selection experiment that reconstructs text from immutable offsets and evaluates sample/condition/origin binding, with fresh independent cases. Preserve this stage's failure and reference unchanged.
