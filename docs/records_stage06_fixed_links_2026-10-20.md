# Records stage06: fixed named linkage slots

Date: 20 October 2026. Development comparison, not independent scientific acceptance.

## Changed

Added `app/records/fixed_links.py`, explicit OpenAI-only `--wire-format span_fixed`, extraction version `records_openai_span_fixed_v0.1` and wire schema `records_span_fixed_reply_v0.1`. Full linkage now has three required named keys: sample_value, property_value and conditions_measurement. Each contains evidence spans and a note, or explicit null for an unsupported proposal. Multiple evidence spans for one role share that slot's array. Missing/extra keys, role strings inside a slot, legacy arrays and empty non-null evidence are rejected. New-format parsing rejects duplicate JSON keys at every object depth rather than silently keeping the last value.

Conversion retains all non-null roles, notes and source-coordinate evidence in the existing candidate representation. Null omits a proposal without establishing absence or scientific disproval. The sixteen observations, scalar/range representation, token map, exact source slicing and raw/evidence containment retain stage05 validators. Candidates remain needs_review / Li-ion confirmation not_reviewed. Old formats and duplicate-role rejection remain unchanged. No database, original PDF, ingestion/OCR/chunking/retrieval behavior, output candidate schema, metric, threshold, global RAG setting or dependency was changed. [Predeclared protocol and CLI](records/fixed_link_slots_protocol_v0.1.md).

## Frozen experiment

The user authorized stage06 and four bounded attempts. Same exact stage04/05 reference/input/task bytes; reference SHA-256 remains `be40335d686490d430d0091d1a2b6e8d312d4947f887b5537c6c833b9f6af1c6`. These exposed assistant-authored cases remain needs_independent_review; expected text boundaries, missingness and deferred dimensions were not changed. Three positive records retain sixty dimensions; bibliography is a separate negative.

Frozen order: Sanginov Abstract, Sanginov table, Istomina cited result, Kayumov bibliography. Abstract uses unchanged span_compact as a development control; full cases use span_fixed. Every token map and the compact native request hash matched stage05. Before inference, froze protocol, all inputs/tasks/reference, source token maps with character offsets, original/layer PDF hashes, actual native requests and code. Pre-inference snapshot: 404 files, fingerprint `a29a4227c7c2109b9721f1e5c952715f88c85c5adcd837730ad2d1e5eeee1796`, at `output/records_stage06_20261020/baseline_ready/`.

Provider settings unchanged: fixed HTTPS Responses endpoint, gpt-6-astra alias, medium reasoning, default service tier, strict JSON Schema, store=false, stream=false, truncation disabled, no tools/temperature/seed. Compact output/reasoning cap 2,048; each full cap 8,192; total cap 26,624. Timeout 180 seconds each. Exactly one attempt per case, sequentially; no retries, repair, duplicate removal, model switch, budget extension or execution-order deviation. Original PDFs/full stored pages, local PDF paths, reference answers and credentials were not sent in model messages.

## Actual results

| Case | Elapsed | Input / output tokens | Result |
| --- | ---: | ---: | --- |
| Sanginov Abstract control | 2.980 s | 879 / 87 | Integrity valid; four exact raw fields and null sample abstention. Full record deferred. |
| Sanginov footnote-d table | 27.674 s | 4,235 / 2,069 | Integrity-valid scalar candidate with three named linkage proposals; one exact-reference mismatch. |
| Istomina cited prior work | 28.026 s | 4,527 / 1,837 | Integrity-valid range candidate with three named linkage proposals; four exact-reference mismatches. |
| Kayumov bibliography | 5.352 s | 1,771 / 53 | Explicit measurements=[]; correct development-negative abstention. |

All four native responses completed and passed wire and evidence integrity. There are three positive candidates of three expected, zero missed or extra records in valid runs, and one correct negative abstention. **No positive candidate achieves full reference agreement or scientific acceptance.**

Unchanged atomic evaluator over all sixty dimensions: **21 match, 5 mismatch, 34 deferred**, zero unavailable. Full-record outcomes: one deferred, two mismatch, one not_applicable. The evaluator's CLI success criterion concerns failed/missing integrity cases, so four valid cases are not a scientific pass criterion. All source-coordinate selections were inspected: **82 individual references, zero invalid coordinates**, counting repeated references. Actual non-null slot roles, every evidence span and every note matched the resolved candidates exactly.

The table candidate selects the footnote-d value `1.1 × 10 −4`, applicable `20 °C`, `This work`, exact plasticiser fraction `ω(SL) = 0.40` and scalar representation. Nine of ten non-deferred field/status values agree; composition_basis uses the longer exact source phrase `mass fraction of sulfolane in the EC/SL binary plasticiser`, while the reference expects `mass fraction`. No text-boundary tolerance or reference change was introduced. Conditioning now reconstructs original text without stage04's model-written character corruption. These are bounded source observations, not independent confirmation of sample/measurement relationships.

Istomina preserves the conductivity and temperature ranges, range representation and cited prior-work attribution. It does not assert the supplied current-article method, conditioning or uncertainty as the method/conditions/error for the cited result. Four mismatches remain: sample status ambiguous/null versus the reference's membrane descriptor; a longer exact plasticiser phrase; method status unsupported versus not_found_in_context; and a longer exact origin phrase. All four retain source evidence and diagnostics. These are exact-reference/status disagreements, not four established scientific errors. Proposed linkage remains scientifically unreviewed and deferred in the reference.

The stage05 duplicate conditions_measurement response remains rejected and unmodified. The new wire's named slots prevent that particular valid-output shape, and raw duplicate keys are explicitly rejected rather than deduplicated. This stage completes the planned format comparison, but it is not an isolated causal estimate: prompts/schemas differ, the provider is remote, references are exposed and only four cases are used.

## Usage, privacy and cost

Observed total: **11,412 input, 4,046 output, 15,458 total tokens**. Input metadata reports 10,524 cache-write and zero cached-read tokens. Requested and returned model IDs were gpt-6-astra for all four calls; this alias is not a dated immutable snapshot. Request/response IDs, raw responses and usage remain in local artifacts.

Conservative estimate **$0.344950**: all input charged at the verified same-day upper input/cache-write rate of $12.50/million, plus output at $50/million. This is not an invoice, actual billing verification or provider-enforced dollar cap. Existing credential/destination/privacy controls remain in force; store=false is not Zero Data Retention. Official sources: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [model/rates](https://developers.openai.com/api/docs/models/gpt-6-astra), [data controls](https://developers.openai.com/api/docs/guides/your-data).

## Tests run

- Targeted fixed links, spans, native OpenAI, compact and full extraction suites: **101 passed**, 5.40 s.
- Full regression: **1,155 passed**, one existing Starlette/httpx deprecation warning, 54.50 s. Seventeen new synthetic cases cover nullable named slots, evidence/note preservation, missing/extra/legacy roles, duplicate JSON keys, observation uniqueness, invalid coordinates, old duplicate-role rejection, native failure persistence and unchanged evaluation semantics. Initial fixture assertions used an incorrect literal end offset and tried to append to a tuple; only those test fixture mistakes were corrected.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 101 source files.
- Four actual API attempts: all integrity valid as described above; reported separately from passing software tests.
- Offline replays of stages02–05: identical summaries and all scientific case/candidate fields, including record IDs, evidence, outcomes and diagnostics. Excluded only regenerated candidate-bundle run_id and created_at metadata. An initial stage05 replay incorrectly supplied paths for its two unattempted cases, changing missing-run diagnostic wording; the corrected replay uses the original run map. Both replay artifacts remain saved; metrics/reference/raw outputs were not changed.
- Original/layer PDF hashes, inputs/tasks/reference/protocol, token maps and actual request hashes matched frozen manifests. Pre-inference code snapshot verified. Compact request and token maps matched stage05 preflight bytes. Slot-to-candidate checks retained all actual evidence spans and notes.
- Static HTML: four case rows, nine existing local PDF links, exact escaped source fragments, expected/actual fields, named slots, prior-stage outcomes and usage. Credential scan of 178 experiment/review artifacts found no exact configured credential and printed no key.
- Browser visual/click checks were not run: local-file navigation was blocked by browser policy earlier in this session. Static checks do not substitute for visual acceptance.

Private artifacts, excluded from Git:

- `output/records_stage06_20261020/comparison.html` and `comparison.json` — all four cases, source-coordinate and named-slot audit, raw fields, stage05 comparison and diagnostics.
- `output/records_stage06_20261020/evaluation/review.html` and `report.json` — unchanged full-record evaluation.
- `output/records_stage06_20261020/qa.json` — source/replay/static checks.
- `data/experiments/records/pilot/stage06_20261020/` — frozen preflight/reference/token maps, exact requests, native raw responses, usage and manifests.

Clone contains source/protocol/report; private corpus, responses and credentials are not included. CLI reproduction needs fresh output paths and incurs new calls; offline replay requires no key/network.

## Limitations

Four exposed oracle-selected fragments are not independent scientific evaluation or whole-corpus retrieval. Thirty-four dimensions remain deferred, five disagree with the development reference, and exact coordinates do not validate semantic entailment. Named roles can still attach semantically wrong evidence. The tokenizer cannot split a word/digit token or create arbitrary discontiguous raw values. Alias/remote runtime, absent browser QA and unverified billing limit stronger claims. No production integration, fresh independent cases, clean installation or end-to-end retrieval/generation benchmark was performed in this format stage.

## Verdict

Stage06's structural objective is met: named linkage slots, strict duplicate-key handling, lossless candidate conversion, regression compatibility and all four bounded real cases are verified. Scientific admission remains open. The next development check should exercise the full existing question → corpus retrieval → selected evidence → GPT answer → citation checks chain with frozen questions and retrieval outputs, rather than extend this exposed four-case reference as if it were independent gold.
