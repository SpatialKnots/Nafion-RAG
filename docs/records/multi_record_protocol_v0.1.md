# Multi-record span extraction and frozen smoke v0.1

21 October 2026. Stage20, ARIADNE. Separate development format; historical
single-record replies, candidate schemas and scientific metrics remain intact.

## Contract and limits

`records_multi_fixed_reply_v0.1` contains zero to four measurement proposals,
each with the existing sixteen source-token observations, representation and
three required nullable named linkage slots. Four is a declared operational
reply budget, not a scientific threshold or article-wide maximum. Reaching
four requires `partial` coverage and source-supported unresolved diagnostics,
even if the model believes there are exactly four. Never silently truncate.

Coverage is the model's claim only: `claimed_complete_in_context`, `partial`,
`unsupported` or `no_measurements_proposed`. Partial/unsupported replies require
exact in-context source spans explaining unresolved scope. Unsupported/empty
states cannot contain records; claimed complete cannot contain unresolved scope
or zero proposals. The declared returned count must equal the actual count.
Zero proposals are not independent evidence of absence. No scientific admission
or automatic article-wide completeness is created by this contract.

Reject duplicate JSON keys at every level. Reuse the unchanged fixed-link/span
resolver one measurement at a time, revalidate the assembled candidate bundle,
and reject repeated field/status/raw-coordinate signatures even when notes or
evidence phrasing differ. Do not merge separate temperatures/samples or treat
equal numbers at different source positions as duplicate experiments. Preserve
ranges, missingness, footnote overrides, prior-work origin and exact source text.
Coordinate validation does not establish semantic linkage or scientific truth.

## Frozen development smoke

Use four exact already-exposed stage19 bounded contexts, in this order:

1. Sanginov abstract `bb8ddb09defe9e75907352cddb97e7d0a8a3d76c60b7890b63f6fe24a61ccaeb`.
2. Istomina prior-work passage `b2f4442678f51b9c6339e798f9701c7fcf21c7847869cc46cf72fc5f92584fdf`.
3. Istomina method-only passage `ba348bbe9ec470bce6f1e774781ea14ad3efefced206fb5898f25340163f5670`.
4. Kayumov protected Table 2 `9ce019ff311edf6345ce5abfe635c952b2743cd4db0f4eadf429a9a92875a446`.

Selection is an explicit assistant development exercise, not an independent
sample or reference dataset. No expected record labels/values are sent. The
task is identical: propose every supported conductivity observation, preserve
author property/origin wording, and expose unresolved/budgeted scope. Electronic
conductivity reported for the lithium-form membrane remains labeled as reported,
not renamed Li-ion conductivity. Such a candidate may be scientifically out of
the eventual pilot scope; do not force a scientific category here.

Before any network call, freeze every source bundle, exact actual request,
source/context/code/protocol hashes and the complete 62-page registry. Only
selected source quotes/token IDs and task are transmitted, without local paths,
full stored pages, reference values, source inventory or private credentials.
Run the existing complete-page guard on decoded source/task text and the actual
serialized user message, against all 62 source pages. Recheck inputs, PDFs,
prepared request bytes and code before and after each call. A mismatch stops
the remaining cases. Never bypass a failed scope guard or select replacements.

Use the previously used development alias `gpt-6-astra` with native Responses,
medium reasoning, max_output_tokens=8192, timeout=180 seconds and at most
100000 serialized request bytes. At most four sequential calls / 32768 output
tokens including reasoning. No retry, alternate model, output repair or budget
increase. The fixed HTTPS transport, TLS validation, disabled proxies/redirects,
store=false, stream=false, truncation disabled and default tier remain as before.
No cost/invoice or Zero Data Retention claim follows from these settings.

Stop remaining cases after transport, HTTP, provider-completion, schema,
evidence-integrity or frozen-binding failure. Retain partial/unsupported coverage
as explicit valid-format outcomes; they do not warrant automatic expansion to
all 352 contexts. A failed/incomplete reply is not a successful abstention.
An infrastructure failure is recorded once, without a second provider attempt.

## Evidence and reporting

Preserve raw native response/usage/returned model/request IDs before parsing.
Keep declared coverage, every unresolved source span, all measurements and
pass/fail/unknown checks. Never infer independent quality or omissions from a
model's completeness claim. Keep all four cases in denominators, including
stopped/unattempted cases and unavailable usage. Export local HTML/JSON with
source/PDF links and raw/parsed artifacts; do not replace the user's review store
or automatically accept scientific records. Repeat offline raw-response replay
and verify source/record content equality independently of run timestamps.

Software tests cover multi-record samples/temperatures/ranges, duplicate keys
and proposals, foreign/invalid spans, coverage/count contradictions, note-only
duplicate evasion, footnote/condition preservation, prior-work literal origin,
full-page guards, truncation/refusal, source drift and fail-stop behavior.
Independent annotation, human time and scientific metrics remain separate.

API structure/refusal/incomplete handling was checked against
[official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
on 21 October 2026. Schema adherence is distinct from scientific correctness.
