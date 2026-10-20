# OpenAI records comparison v0.1

Date: 20 October 2026. Development comparison, not independent scientific acceptance.

## Frozen scope and authorization

The user authorized a separate GPT API backend and a four-case comparison. Reuse exactly the stage03 short-clause source/task/compact schema and the three stage02 source/task/full schemas: Sanginov footnote-d table cell, Istomina cited range and Kayumov bibliography negative. Preserve historical artifacts. No reference answers enter inference. Freeze the combined assistant-authored reference, copied input/task bytes, source PDF hashes, actual requests, code and settings before any paid inference.

These exposed development cases are not independent gold or held-out data. The combined reference has three expected positive records, sixty record dimensions and one explicit bibliography negative; unresolved dimensions remain deferred. Existing raw-answer variants and linkage limitations remain in force. API results must not be promoted to scientific reference labels.

## Provider and fixed execution settings

Use `gpt-6-astra`, verified in the configured account's read-only model list and current official documentation. The public/account listing provides an alias, not a dated immutable snapshot. Record requested and returned model IDs, response/request IDs and raw usage. Model availability listing does not establish task performance or guarantee a successful generation request.

Use only `https://api.openai.com/v1/responses`, default service tier, `reasoning.effort=medium`, `store=false`, `stream=false`, `truncation=disabled`, strict JSON Schema. Preserve the existing system prompts and source/task message strings exactly. Temperature and seed are omitted for this reasoning API; this compatibility change is recorded, not a claim of deterministic reproduction. No tools, file upload, retrieval or extra model access is enabled.

One attempt per case, sequentially: short clause first, table, cited result, bibliography. `max_output_tokens=2048` for compact and 8192 for each full record, including reasoning tokens; total cap 26,624 generated tokens across the four attempts. Timeout 180 seconds per request. No hidden retries, repair loop, model switch, budget increase or text normalization. Stop the remaining batch on transport/provider/completion-contract failure; source-evidence mismatches are retained as case results and do not suppress the other planned cases. Pending cases remain in evaluation denominators.

The official standard short-context Astra rates observed on this date are $10 input, $1 cached input, $12.50 cache writes, $50 output per million tokens. Preserve the rate/source snapshot in the private preflight manifest. Report usage and an explicitly labeled conservative cost estimate, not an invoice. Bound output tokens and attempt count in code. A dollar estimate is not a provider-enforced billing cap; rates, cache details and actual account charges require billing verification. No global RAG provider/model configuration changes.

## Privacy and credentials

Credentials come from process environment or local `.env`, preferring `OPENAI_API_KEY` then `RAG_OPENAI_API_KEY`; never write keys or Authorization headers to requests, manifests, logs or Git. The destination is fixed HTTPS with normal TLS validation, proxy-environment forwarding disabled, and redirects forbidden. Original PDFs, complete stored pages and local file paths are not sent; only the existing selected-text messages and routine source identifiers are sent. The serialized local bundle retains full page/source provenance for evidence validation.

`store=false` disables application-state storage for this request; it is not Zero Data Retention. API abuse-monitoring retention may still apply. Input text leaves the local system for OpenAI under the user's authorization; private frozen texts/responses remain excluded from Git. HTTP error diagnostics explicitly redact the exact credential before local persistence.

## Response and evaluation rules

Save raw bytes before parsing. Only a completed response with one completed assistant message and one JSON output-text block is accepted for parsing. Refusals, incomplete responses, tool outputs, multiple text fragments and errors remain failures. Reasoning metadata is not concatenated with the answer. Preserve raw response and usage even when exact source validation fails; do not reconstruct a fake Chat Completions envelope.

Reuse the existing wire validators, literal source resolver and full-record evaluator. Add explicit OpenAI versions to request/runtime binding validation and response parsing. Keep original missing/extra counts, raw/source-anchor agreement, representation, deferred dimensions and linkage comparisons. Retain failed cases in denominators. Full reference agreement is not scientific entailment or independent accuracy. Also inspect per-field raw proposals for failed candidates rather than hiding partially correct output behind atomic rejection.

Deliver a local HTML review of all four cases, original-source links, raw expected/actual fields, failures, usage and limitations, plus JSON and a stage report. Static HTML/source checks do not substitute for browser visual/click acceptance.

## Official sources verified before implementation

- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-6 Astra model](https://developers.openai.com/api/docs/models/gpt-6-astra)
- [Migration compatibility](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra)
- [Pricing](https://developers.openai.com/api/docs/pricing)
- [Data controls](https://developers.openai.com/api/docs/guides/your-data)

## CLI

```powershell
.\.venv\Scripts\python.exe -m scripts.records_extract infer data/experiments/records/pilot/stage04_20261020/sanginov_abstract/input.json --task-file data/experiments/records/pilot/stage04_20261020/sanginov_abstract/task.txt --backend openai --model gpt-6-astra --wire-format compact --reasoning-effort medium --max-tokens 2048 --timeout-seconds 180 --output-dir data/experiments/records/pilot/stage04_20261020/runs/sanginov_abstract
```

Use fresh output paths. OpenAI mode does not accept a local runtime manifest, custom endpoint or non-default seed. Local mode stays the default and still requires its runtime manifest. Offline `evaluate` needs no API key or network. Inference/evaluation failures keep their nonzero exit status.
