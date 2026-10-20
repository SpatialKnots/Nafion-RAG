# Source-token record selection v0.1

Date: 20 October 2026. Separate development experiment; no scientific acceptance.

## Contract

Add explicit OpenAI-only `span_full` and `span_compact` wire formats. Historical full/compact wire schemas, candidate schema, source text, metrics and defaults remain unchanged. Full selection preserves sixteen observations, representation and three possible linkage roles; compact preserves five nullable fields, unsupported unrequested dimensions, unparsed representation and no inferred linkage.

Tokenizer version `records_token_spans_v0.1` uses Python Unicode regex `\d+|[^\W\d_]+|_|[^\s]`: digit runs, word runs excluding digits/underscore, underscore, then individual non-whitespace characters. IDs start at zero per selected source region. It is an evidence-addressing tokenizer, not a model tokenizer or scientific interpretation. Source text is not normalized. Numbered token text accompanies the exact selected source; complete pages, PDF paths and reference answers stay local.

Each selection is `{region, start_token, end_token}`, with inclusive token endpoints and strict nonnegative integers. Code maps these IDs to Unicode codepoint offsets relative to the immutable source region, then slices the original string. Whitespace, newlines, ligatures, signs and repeated occurrences retain their exact positions. Leading/trailing whitespace alone is not selectable. Selection boundaries cannot split one word/digit token; this expressiveness limit is explicit and not repaired by arbitrary text generation.

Full fields select a tight raw span and supporting evidence spans. A raw span must be contained by coordinates in at least one evidence span in the same region; identical words elsewhere do not satisfy containment. Unknown IDs, out-of-range or reversed endpoints, wrong types, unsupported non-null values, missing/duplicate fields, duplicate roles and malformed completion envelopes fail explicitly. No clipping, fuzzy matching, normalization or replacement of a failed answer. Repeated source text can be selected unambiguously by position; old literal-wire uniqueness rules remain unchanged for old formats. Candidates remain needs_review / not_reviewed. Verbatim reconstruction prevents model-written quote corruption but does not validate semantic selection, units, attribution or linkage.

## Frozen stage05 scope

Use exactly the four source/task/reference cases from stage04 in this order: `sanginov_abstract`, `sanginov`, `istomina`, `kayumov`. Copy original input/task and reference bytes unchanged. Do not revise expected text boundaries or unresolved reference dimensions after outcomes. These exposed assistant development cases are not independent gold; retain the three positive records, sixty dimensions and separate bibliography negative. No corpus retrieval or whole-article extraction benchmark is claimed.

Before any paid inference, freeze copied inputs/tasks/reference, this protocol, token maps with character offsets, all actual native request bodies, original/layer PDF hashes and a source snapshot. Use existing authorized OpenAI destination, credential handling and native completion contract from [stage04](openai_comparison_protocol_v0.1.md). Preserve `gpt-6-astra`, medium reasoning, default service tier, strict JSON Schema, store=false, stream=false, truncation disabled; no tools, seed or temperature. Do not change global RAG settings.

One attempt per case, sequentially. Compact output/reasoning limit 2,048; each full limit 8,192; total 26,624. Timeout 180 seconds each. Stop remaining cases on transport/provider/completion-contract failure; retain evidence-selection failures and continue the planned batch. No retry, automatic repair, model switch or budget increase. Failed/unattempted cases remain in denominators. New requests have different prompts and token-address maps; this is a versioned format comparison, not an isolated model or speed benchmark.

## Evaluation and review

Reparse raw responses offline with the existing full-record evaluator and unchanged references/metrics. Retain mismatches, missing/extra records, unavailable dimensions and deferred linkage/scientific issues. Include an independent artifact-level source audit of every selected coordinate and raw field, including proposals rejected atomically. Do not promote recovered text or reference agreement to scientific truth. Explicitly compare own-work versus cited-result attribution, table cell footnote, sample wording and conditions. Replay stage02/03/04 artifacts to protect historical behavior.

Generate separate local HTML and JSON covering all four cases, expected/actual raw fields, stage04 outcomes, original PDF links, exact source, coordinates, failures, usage and limitations. Static checks cannot claim browser visual/click acceptance. Keep raw literature, keys and response artifacts out of Git. Record actual usage and conservative cost estimate using verified stage04 rates ($12.50 per million for all input as an upper-rate estimate, $50 per million output), not an invoice or hard dollar cap. Billing is not checked. See [official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs) and the prior protocol's model/pricing/data-control sources.

## CLI

```powershell
.\.venv\Scripts\python.exe -m scripts.records_extract infer data/experiments/records/pilot/stage05_20261020/sanginov/input.json --task-file data/experiments/records/pilot/stage05_20261020/sanginov/task.txt --backend openai --model gpt-6-astra --wire-format span_full --reasoning-effort medium --max-tokens 8192 --timeout-seconds 180 --output-dir data/experiments/records/pilot/stage05_20261020/runs/sanginov
```

Use fresh output directories. Existing runs cannot be overwritten. Offline evaluation requires no key/network. Independent cases and end-to-end retrieval evaluation remain later work.
