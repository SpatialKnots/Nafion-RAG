# Fixed named linkage slots v0.1

Date: 20 October 2026. Records stage06 development comparison, not scientific acceptance.

## Explicit format change

Add OpenAI-only `--wire-format span_fixed`, native extraction version `records_openai_span_fixed_v0.1` and wire schema `records_span_fixed_reply_v0.1`. Keep all historical full/compact/span versions and the default local backend unchanged. Preserve tokenization `records_token_spans_v0.1`, source strings, candidate schema, metrics, source traceability and needs_review/not_reviewed state.

Full measurement linkage becomes an object with three required keys: `sample_value`, `property_value`, `conditions_measurement`. Each is `{evidence: [TokenSpan, ...], note: nonempty}` or explicit null if unsupported. Missing keys, extra keys, role strings inside a slot, legacy linkage arrays and empty non-null evidence fail. Multiple evidence spans supporting one role belong in that slot's one array. Conversion produces zero or one existing linkage proposal per named key, retaining all evidence spans and notes. Null omits a proposal and does not establish scientific absence or disproval. New-format parsing rejects duplicate JSON keys at every object depth rather than silently overwriting them.

The sixteen observation fields, representation, source-token coordinates, raw/evidence containment and literal source reconstruction retain stage05 rules. Named slots eliminate duplicate role entries from valid new wire outputs, not incorrect semantic associations. Historical duplicate-role responses must remain rejected by their original validators. No answer is deduplicated or repaired.

## Frozen scope and execution

The user authorized this stage and a new bounded four-case comparison. Copy the same reference/input/task bytes from stage05/stage04. Do not revise expected raw boundaries, missingness, dimension definitions or deferred linkage labels after output. These exposed assistant-authored cases remain needs_independent_review; three positive records, sixty dimensions and one bibliography negative. No independent accuracy claim.

Order: `sanginov_abstract`, `sanginov`, `istomina`, `kayumov`. The first uses unchanged `span_compact` as a development control; the three full cases use `span_fixed`. Freeze protocol, exact inputs/tasks/reference, source token maps, native request bodies, original/layer PDF hashes, implementation snapshot and rates before inference. Compare the compact request and token maps with stage05 preflight hashes. Only selected source plus token IDs enters the API; no complete pages, PDF paths, reference answers or keys enter prompts.

Retain verified stage04 provider/settings: fixed HTTPS Responses endpoint, `gpt-6-astra` alias, medium reasoning, default service tier, strict JSON schema, store=false, stream=false, truncation disabled, no tools/temperature/seed. One attempt per case, sequentially. Compact limit 2,048 output/reasoning tokens, full limit 8,192 each; total cap 26,624. Timeout 180 seconds per call. Stop remaining cases on transport/provider/completion-contract failure; retain evidence-integrity failures and continue. No retries, repair, model switch or budget increases. Pending/failed cases remain denominators. A changed prompt/schema is not a controlled causal benchmark.

Use existing environment/.env credentials privately; preserve fixed destination, normal TLS, disabled proxy forwarding, no redirects, raw response persistence, refusal/incomplete handling and redacted HTTP error artifacts. No global RAG setting changes. Store=false is not Zero Data Retention. Conservative cost estimate uses the verified same-day stage04 rates: all input at $12.50/million, output at $50/million; not an invoice or hard dollar cap. Record actual usage, returned model IDs and request/response IDs. Do not claim immutable alias or billing verification.

## Tests, evaluation and review

Test named-slot null semantics and lossless evidence/note conversion, schema requirements, missing/extra/legacy roles, duplicate JSON keys, invalid coordinates, observation uniqueness, native raw response persistence, unchanged evaluation and rejection of historical duplicates. Software tests use synthetic inputs without paid calls.

Reparse raw responses using the existing full-record evaluator with unchanged reference. Report exact raw/status and source-anchor mismatches, range/scalar representation, deferred dimensions, extra/missed records, failures and negative abstention. Inspect all selected coordinates and own-work/prior-work/footnote decisions without changing scientific labels. Replay stages02–05, comparing summaries and scientific fields while excluding only regenerated candidate-bundle run_id and created_at metadata.

Deliver a separate local HTML/JSON review of all four cases, including unattempted cases if stopped, exact source, original PDF links, expected/actual fields, named slots, usage, failures, prior-stage comparison and limitations. Static checks do not establish browser visual/click acceptance. Raw literature/response artifacts stay out of Git. End-to-end corpus retrieval and independent scientific evaluation are separate checks after this bounded format experiment.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m scripts.records_extract infer data/experiments/records/pilot/stage06_20261020/sanginov/input.json --task-file data/experiments/records/pilot/stage06_20261020/sanginov/task.txt --backend openai --model gpt-6-astra --wire-format span_fixed --reasoning-effort medium --max-tokens 8192 --timeout-seconds 180 --output-dir data/experiments/records/pilot/stage06_20261020/runs/sanginov
```

Fresh output paths only. Offline evaluation needs no key/network. [Official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs); [prior provider/data/rate protocol](openai_comparison_protocol_v0.1.md); [source token contract](token_span_protocol_v0.1.md).
