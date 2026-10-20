# Stage07: automatic retrieval to a source-linked GPT answer

Date: 20 October 2026. Bounded development audit of the existing answer chain; not independent scientific evaluation.

## Changed

Added an optional trace observer to `answer_question`. It receives deep copies of ranked retrieval, final selected evidence and existing adequacy/selection diagnostics after preparation and before either a gate return or a provider call. It cannot mutate pipeline data. Existing search scoring, selection, gates, thresholds, defaults, answer/citation schema and scientific metrics were preserved.

Added `app/evaluation/answer_trace.py`: a development-only native Responses provider, explicit dry-preparation boundary, canonical trace/request hashes, live/frozen equality checks, raw response persistence and provider diagnostics. It reuses the production scientific system prompt and user evidence formatter, then returns ordinary claims to existing service citation validation and answer assembly. It uses the previously tested fixed HTTPS/native-response transport. It is injected only for this experiment; the globally configured legacy OpenAI/gpt-4.1-mini provider, HTTP/UI wiring and `.env` remain unchanged. No database writes, migrations, PDF changes, ingestion/OCR/chunking changes or index rebuild occurred. [Predeclared protocol](records/end_to_end_protocol_v0.1.md).

## Frozen inputs and source state

Before retrieval, copied these exact existing development questions and their expectation/source hashes:

1. `xling_ru_sanginov_ec_sl_conductivity`: «Как смесь этиленкарбоната и сульфолана влияет на ионную проводимость Li-Nafion?»
2. `xling_ru_istomina_swelling_temperature`: «Как температура смешения влияет на набухание литированной мембраны Nafion в этиленкарбонате и сульфолане?»
3. `xling_en_chernyuk_2023_water_thermodynamics`: “What are the thermodynamic interactions of PFSA Nafion with water?”
4. `qext039_absent_mars_regolith`: “zirconium cerium extraterrestrial regolith perchlorate electrolyte”.

First three are unchanged entries from `docs/evaluation_questions_cross_lingual.yaml`; the negative is unchanged from `docs/evaluation_questions_extended.yaml`. They are exposed development questions and expected-document/answerability labels, not independent gold. They were not tuned after seeing retrieval or answers. Expected labels were not passed to the model or used to select pages/chunks.

Database had 33 articles, 493 selected pages, 814 stored original/OCR page-layer rows, 619 chunks, two collections and two vector-index states. Collection literature used the existing hybrid_cross_lingual method and top_k=5. Active BGE index manifest SHA-256: `d1d13f2271c28f2c1082e8251bff572f7b93e9ba25a77daa4b2087a84e6b1569`. Corpus/table/PDF/index snapshot fingerprint: `18c9df4032897aaf576ad0e07beb4045fc39561ebf340c72e1abff4bca15b1ac`. Frozen checks cover 49 original/OCR PDF files and 27 index artifacts. Source packets retain chunk IDs/text/checksums, article identity, original PDF path/hash, pages, source type and exact registered layer/page text. No selected source packet has missing layer pages.

Before paid inference, ran the actual pipeline with an explicit PreparationComplete boundary instead of a fake model answer. Saved complete ranked results, final evidence, gate diagnostics, source packets and exact native requests for all eligible questions. Gate rejection is an actual insufficient_evidence response, not a simulated model abstention. Pre-inference source snapshot: 408 files, fingerprint `79291f45dd48b27b3996793f747b3dd835ea05dc05ff2869324c1729e008efbb`, at `output/records_stage07_20261020/baseline_ready/`.

## Runtime recovery

The initial read-only index check succeeded, but first retrieval failed before any GPT call because the default temporary FastEmbed cache contained no BGE model files: `Could not load model BAAI/bge-small-en-v1.5 from any source.` Restored the same configured model ID to `data/processed/model_cache/` from its package-declared model repository. Actual snapshot: `aa8f8b060edb00e03bfdd08813a2949946c8ba55`; observed dimension 384. Eight model/tokenizer/revision file hashes are frozen in the preflight manifest. Download warned that Windows symlink optimization was unavailable; ordinary cached copies were used.

Preparation/live retrieval used process-local FASTEMBED_CACHE_PATH pointing to that workspace cache and HF_HUB_OFFLINE=1. No index was rebuilt and no global configuration was changed. The original index-time weight checksums were not independently recorded; matching model IDs alone cannot prove bit-identical historical query/index-time weights. This limitation is retained. The failed preparation was an infrastructure failure before the frozen API batch, not a paid retry or an altered question. Local replay requires the same process cache settings or a separately configured available runtime.

## Live chain and actual results

Re-ran the complete answer_question chain in a fresh read-only repeatable-read transaction. Every live ranked retrieval/selected-evidence trace matched frozen bytes. The observer also revalidated its source packet before generation. Every actual model request matched preflight bytes before transmission. No manual evidence substitution, extra retrieval, fallback, retry, context clipping or answer repair followed.

| Frozen question | Retrieval / selection | Full-chain elapsed | Result |
| --- | --- | ---: | --- |
| EC/SL conductivity, Russian | 5 / 5 | 23.982 s | Answered, 3 claims, 4 used citations; expected Sanginov paper retrieved and cited. |
| Mixing temperature/swelling, Russian | 5 / 5 | 22.451 s | Answered, 3 claims, 3 used citations; expected Istomina paper retrieved and cited. |
| Nafion/water thermodynamics, English | 5 / 5 | 24.236 s | Answered, 5 claims, 3 used citations; expected Russian Chernyuk paper retrieved and cited. |
| Negative regolith query | 5 / 5 | 1.651 s | insufficient_evidence; gate reason insufficient_distinctive_term_coverage; zero provider calls, claims or answer citations. |

**Three actual GPT requests, three answers, one gate refusal without API. Eleven claims all reference supplied evidence IDs.** All three positive expected documents occur in automatic retrieval, selected evidence and final citations. There are zero failed or unattempted questions. These are structural trace and finite expected-document observations, not independent scientific accuracy, entailment or completeness scores. The negative gate agrees with the existing label but does not prove topic absence from every corpus page.

Provider-only elapsed times were 11.115, 12.755 and 15.877 seconds, respectively. Full-chain times also include retrieval and trace/source checks; no controlled performance benchmark or speedup claim is made. Requested/returned model IDs were gpt-6-astra. Settings: default tier, medium reasoning, strict native schema, store=false, stream=false, truncation disabled, no tools/temperature/seed, max_output_tokens=4096 including reasoning per permitted call, timeout 180 seconds, 100,000-byte request ceiling without clipping. Order, attempts, model and token limits held. A source-scope protocol deviation was identified after the run: selected chunks include complete extracted page text, as detailed below.

## Scientific/source observations

Answers and model requests remain unchanged. A separate coding-agent review is labeled needs_independent_review and is not gold annotation. The selected source supports the principal EC/SL conductivity range, composition and activation-energy numbers, and the mixing-temperature/swelling numbers 82.2%, 88.1%, 132.5%, approximately 1.5 times and approximately 200%. The swelling answer keeps Sanginov and Istomina contributions separate. These spot checks do not establish all eleven claims as independently correct; cited prior-work passages must not be counted as independent experimental replication.

The English water question exposes a concrete retrieval weakness: two of five selected chunks, E3/E4, are dissertation bibliography material. The answer did not cite them. Chernyuk's extracted formulas contain control characters and broken reading order. The model reconstructs an enthalpy expression and thermodynamic interpretation; original-PDF review remains required before scientific acceptance. Cho's supplied table contains the cited 15.1/3.1/12.0 water-population values. The full exact source, damaged characters, source pages and review notes remain visible; no OCR or formula repair was applied.

Original chunk text is preserved in trace/source packets. The production answer formatter already collapses whitespace for model messages; this transformation is recorded explicitly and is separate from the exact-copy records experiments. Source ID validation guarantees only that a supplied source was named, not that it supports every numerical or causal statement.

## Usage and privacy

Actual total: **37,666 input, 1,580 output, 39,246 total tokens**. Input metadata reports 37,657 cache-write and zero cached-read tokens. Conservative estimate **$0.549825**, charging all input at $12.50/million and output at $50/million using the same-day verified model/rate basis. This is not an invoice, billing verification or provider-enforced dollar cap. No usage is attributed to the gate-rejected query. Alias/remote runtime prevents an immutable replay guarantee.

Only questions and automatically selected chunks/metadata entered GPT requests; PDF files, local PDF paths, expectation labels and credentials were not uploaded. **Protocol deviation:** the frozen protocol also said complete stored pages would not be sent. Existing source-preserving chunks concatenate complete extracted page text, and the final provider receives their full text. Thus that no-complete-page-text condition was not met. Selected source packets expose this explicitly; no page-level exclusion or sentence compression was applied. Raw requests and the original protocol are preserved without repair. This does not imply the entire corpus was transmitted, but the selected context is broader than that protocol wording promised. No additional calls were made after discovering it.

Post-run comparison using the existing whitespace formatter found thirty complete-page references inside submitted chunks, representing twenty-two distinct article/page pairs across the three requests. These are observed source-scope diagnostics, not extra inference or answer-quality metrics. The final audit/HTML displays the deviation explicitly. A corrected final source snapshot at `output/records_stage07_20261020/baseline_final_v2/` includes this reporting correction and the model-cache Git exclusion; the earlier final snapshot is retained separately. Application logic/tests did not change after their full regression.

Keys/Authorization remain outside artifacts/Git. Store=false is not Zero Data Retention. Official sources: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-6 Astra/rates](https://developers.openai.com/api/docs/models/gpt-6-astra), [data controls](https://developers.openai.com/api/docs/guides/your-data).

## Tests run

- Targeted trace/generation tests: **47 passed**, 1.31 s. Twelve new synthetic cases cover observer timing/copy isolation, gate rejection without model calls, changed trace/request rejection before network, dry preparation, source-only prompt formatting, raw native success/failure persistence, incomplete/refusal/invalid outputs/timeouts and existing-service rejection of unknown native citation IDs. Synthetic tests make no paid calls.
- Full regression: **1,167 passed**, one existing Starlette/httpx deprecation warning, 66.40 s. Ruff app/tests/scripts passed; mypy found no issues in 102 app source files.
- Four real live question chains: the three answers and one gate refusal described above, separate from passing software tests. Frozen traces and requests matched exactly; existing claim/citation validation ran, and raw native answers were independently reparsed offline against the frozen evidence IDs. Final claims/citation sets matched the raw native output.
- Pre/post database transactions were read-only. A separate fresh postflight transaction, beyond the live repeatable-read view, matched the original corpus fingerprint. All frozen PDF/index/model file hashes, question/source/protocol hashes and pre-inference code snapshot verified.
- Static HTML: all four question rows, twenty existing original-PDF links, full selected source, exact request, ranked retrieval, gate reasons, answer/claim data and source-quality review notes. Credential scan of 58 experiment/review artifacts found no exact configured credential and printed no key.
- Browser visual/click checks were not run: the earlier local-file navigation security rejection was preserved. Static inspection is not browser acceptance. HTTP/UI endpoints were not exercised.

## Local artifacts and replay

Private, excluded from Git:

- `output/records_stage07_20261020/review.html` — searchable four-question end-to-end review.
- `output/records_stage07_20261020/report.json`, `qa.json`, `review_notes.json`, `runtime_recovery.json` — chain/source/citation audit, review caveats and runtime evidence.
- `data/experiments/records/pilot/stage07_20261020/` — frozen questions/protocol/corpus/model hashes, ranked traces, selected sources, requests, actual responses, usage and fresh postflight evidence.

For the existing private working copy, offline inspection can be regenerated with `python -m output.records_stage07_20261020.audit`; it makes no model call or database query. Live/preparation helper scripts refuse overwriting core run artifacts. New live inference requires separately declared fresh paths; do not rerun the completed paid batch in place. A clone contains the reusable observer/provider, synthetic tests, protocol and report, but lacks private corpus, raw artifacts and downloaded model cache. Dependency/source snapshots are local evidence, not a portable installation guarantee.

## Limitations

Only four exposed questions; no held-out or independent scientific annotation, full-corpus recall/answer completeness measurement, production Responses deployment, browser QA, clean installation or billing verification. The no-complete-page-text protocol condition was not met: full selected chunks include complete page content. Bibliographic retrieval noise and damaged formula text remain observable. Runtime model restoration does not independently verify historical index-time weights. Gate correctness/source-ID validity/expected-document hits must not be reported as scientific answer accuracy. All scientific entailment remains needs_independent_review.

## Verdict

The intended architecture is demonstrated on this bounded live corpus: the existing code automatically searches and selects evidence; GPT is invoked only at final answer generation; production citation checks assemble source-linked answers, and an inadequate query is rejected before API use. The experiment is not a full protocol/scientific acceptance because the page-text scope condition was not met. The next useful development target is a separately versioned, code-only reduction of selected context and bibliographic/overlapping noise, preserving relevant conditions, captions and footnotes, plus source-quality diagnostics and new independent questions before broader quality claims.
