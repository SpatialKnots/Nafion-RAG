# End-to-end answer trace v0.1 (stage07)

Date: 20 October 2026. Bounded development audit of existing corpus retrieval and answer generation.

## Frozen questions and source scope

Before live retrieval, select three unchanged questions from `docs/evaluation_questions_cross_lingual.yaml`: `xling_ru_sanginov_ec_sl_conductivity`, `xling_ru_istomina_swelling_temperature`, `xling_en_chernyuk_2023_water_thermodynamics`; and the unchanged negative `qext039_absent_mars_regolith` from `docs/evaluation_questions_extended.yaml`. Freeze exact question text, existing expected DOI/answerability metadata and source-file hashes before preparation. These are exposed development questions and expectations, not independent gold. No question tuning, manual chunk/page selection, additional retrieval or output repair after seeing outcomes.

Use the existing collection `literature`, `hybrid_cross_lingual`, top_k=5, existing query expansion/ranking, evidence selection/deduplication and adequacy gates. Keep all existing thresholds, schema/migrations, ingestion/OCR/chunks, index, scientific metrics and global RAG configuration unchanged. Database transactions are read-only and repeatable-read. Snapshot articles, selected page/layer text, chunks, index manifest/files and original/layer PDF hashes before API calls. Verify relevant exact source text and hashes and preserve missing/gap/derived-source diagnostics rather than repairing them.

## Trace and provider boundary

Add an optional observer to the existing answer service, invoked after automatic selection/adequacy computation and before any provider call or gate return. It receives deep copies, so trace collection cannot mutate production retrieval/evidence. Save raw ranked retrieval, final model evidence, adequacy/selection diagnostics and exact expected request. Dry preparation uses an explicit PreparationComplete boundary, never a fabricated model response or counted abstention. Gates that reject evidence retain their actual insufficient_evidence outcome and make no API request.

Run the same full answer_question chain again for live attempts. Require the live retrieval/selection trace and actual question/evidence/request bytes to match the frozen preparation before sending. A mismatch aborts without a model call; never fall back to manually selected evidence or silently use a different index. Record all four questions in denominators, including gates, errors and unattempted cases. Preserve the provider's raw native response, IDs and usage before parsing. Production claim/citation validation and response assembly run after generation.

Use a development-only provider injection with gpt-6-astra and native Responses; keep the globally configured legacy gpt-4.1-mini provider unchanged. Reuse existing scientific answer system prompt and user evidence formatting. In particular, the production answer formatter collapses whitespace for the model; preserve original chunk text separately and label this existing transformation. This audit does not claim exact raw quote copying from model answers. Native output has answerable plus claims with text/citation_ids. Completed native single-message/single-text output and claim structure are checked; refusals/incomplete responses remain failures, not negative-case success. Source ID validation does not establish claim entailment.

Use the existing fixed HTTPS transport with normal TLS validation, disabled proxy forwarding, no redirects or retries. Credentials remain in memory; no Authorization header or key enters artifacts. Only automatically selected model evidence/metadata and question are sent, not corpus files, complete stored pages, local PDF paths or expectation labels. Store=false, stream=false, truncation disabled, default tier, medium reasoning, no tools/temperature/seed. Alias is not an immutable snapshot; store=false is not Zero Data Retention. Current official [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [model/rates](https://developers.openai.com/api/docs/models/gpt-6-astra) and previous provider/privacy protocols apply.

## Limits and failures

At most one live model call per question, sequentially in frozen order; a gate makes zero calls. Each permitted call has max_output_tokens=4096 (including reasoning), timeout 180 seconds and a 100,000-byte serialized-request ceiling with no clipping. Maximum four attempts / 16,384 generated tokens. Stop remaining cases on transport/provider/completion-contract failure, live/frozen binding mismatch or source-integrity drift. Retain service citation-validation failures as failures. No retry, text repair, alternate provider/model, additional context or budget increase.

Record actual usage and a conservative estimate using same-day verified stage04 rates: all input $12.50/million, output $50/million. This is not an invoice or billing hard cap. Gate rejection and a correct scientific negative are distinct: report the exact gate reason, expected label and unmeasured entailment. Keep source/algorithm traceability and exact local PDF links.

## Review and validation

Deliver local HTML and JSON with all four questions, automatic retrieval ranks, final evidence, gate diagnostics, exact request, answers/claims, source/citation checks, PDF links, usage and failures. Separate expected-document retrieval, evidence adequacy, provider completion, citation structure and scientific assessment; do not collapse them into unsupported accuracy. Assess known missing or unsupported relationships with diagnostics. Preserve any unavailable or derived sources explicitly. Static HTML checks are not browser visual/click acceptance.

Software tests cover observer timing/copy isolation, gates without provider calls, live/frozen binding mismatches before network, native failures/truncation/unknown citations and source-only requests. Run full regression and source snapshots. No mandatory per-Term/manual user labeling workflow. A fresh clone lacks the private corpus/artifacts, and independent quality annotation remains separate work.
