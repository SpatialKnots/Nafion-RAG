# GigaChat DSC named-span experiment v0.1

28 October 2026, Asia/Yekaterinburg. Frozen before the second model response.
User authorized the proposed offline implementation followed by one separately
budgeted GigaChat call with `Выполняй`. No OpenAI call or production provider
change is authorized by this protocol.

## Comparison and scope

Parent source: `output/records_stage49_20261027/run_v01`.
Baseline: `output/gigachat_dsc_20261028/live_v01`. Preserve all baseline bytes,
the failed outcome, raw response, usage, hashes and consumed attempt slot. Freeze
the complete baseline output manifest as new experiment inputs before sending.
The question, B1-B4 identity evidence, full M1 text, PDF, page and text layer are
unchanged. This experiment changes prompt, reply schema and model-facing catalog
together; it does not isolate their individual causal effect or create a holdout.

Same `GigaChat-2-Max`, default sampling, 4096 output-token limit, 180 s model
timeout and fixed official v1 endpoint. One new model attempt, no retry, fallback
or response repair. Actual model version may differ; record what is returned.
Use the existing personal-Scope verified-TLS transport, read-only models/balance
admission and persistent checkout-wide reservation keyed by the new request hash.
Model/auth errors stay errors. No purchase, billing upgrade or PAYG Scope.

## New selection contract

- `fields` is an object with exactly six required named properties, not an array:
  instrument, sample_handling, measurement_environment, flow_rate,
  temperature_range, temperature_programme. Extra keys and duplicate JSON keys
  are rejected. Each field has status, selected span_ids and diagnostic.
- Present fields require unique known IDs; other statuses require no IDs.
  Complete/partial/abstention must agree with all six named statuses. IDs must be
  in original source order; do not silently sort or deduplicate a bad reply.
- Build neutral M1 body sentence spans by punctuation followed by whitespace and
  an uppercase English letter, after the section-heading newline. This finite
  rule is for this exposed English DSC source, not a universal sentence parser.
  Preserve whitespace, Unicode, units and semicolon-linked clauses byte-for-byte
  after UTF-8 encoding. Heading plus concatenated spans must equal exact M1.
- Only IDs and exact source text are added to the model-facing packet; the
  original complete source packet remains available. No topic-to-ID answer key
  is sent. An entire sentence may support several fields; this is a proposal,
  not proof that each scientific relation holds.
- Freeze the catalog before predictions. For this source, identify exactly one
  complete sentence containing the literal `temperature programme` cue. Keep all
  semicolon-linked steps, holds and homogenisation wording in that single span.
  Missing/ambiguous cue is a preparation error. A present programme must include
  that entire span. A non-present programme remains explicit, with no invented
  evidence or forced positive answer. This versioned guard is source retention,
  not validation of numeric meaning or sample applicability.
- Resolve selections by code to exact catalog substrings, then validate them
  through the unchanged original DSC Reply/unique-M1-quote/PDF-offset validator.
  Unknown IDs, foreign/bibliographic citations, catalog drift, reversed order,
  duplicate IDs, missing protected programme or inconsistent states fail closed.
  Returned diagnostics remain unvalidated model prose.

## Preservation, checks and deliverables

Use separate new source files so previous frozen code bindings remain valid.
Reconstruct historical source admission, source/code/runtime bindings, byte and
full-page guards. Recheck after dispatch. Save exclusive request, catalog,
contract, parent and baseline snapshots, raw response before parsing, exact
decoded source proposals, actual metadata/usage/errors, hashes and HTML review.
Credentials stay in memory and ignored `.env`; redact any literal echo and block
acceptance if redaction changed a model response. OAuth bodies are never saved.
Timeout/interrupt/storage failure after reservation does not refund an attempt.

Offline tests must cover named schema missing/extra/duplicate fields, status
consistency, unknown/duplicate/reversed IDs, punctuation/Unicode/line-break
retention, complete temperature sequence, wrong/non-method sources, catalog and
source drift, complete/partial/abstention, preflight admission, one-attempt
reservation, transport/storage failure and secret handling. Run appropriate old
DSC regression checks, Ruff and mypy before the model call. Use constructed
transports; no tests are presented as real model outcomes or independent gold.

Compare both observed runs without repairing the first response: field coverage,
exact source-reference integrity, programme retention, declared model, measured
elapsed time and actual token usage. Restored exact text is a property of this
codec, not evidence that the model learned faithful copying. One run per format
does not establish statistical superiority, generalized accuracy or savings.

Export searchable read-only HTML with all six fields, exact source text and
diagnostics; link the separately copied historical TAC table for the one-document
DSC scope, preserving its missing/unimplemented fields and local PDF links.
Scientific entailment, relevance, completeness and sample applicability require
separate source-based assessment; no independent acceptance is claimed.

Official API/schema references:
https://developers.sber.ru/docs/ru/gigachat/guides/structured-output
https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/gigachat-api
