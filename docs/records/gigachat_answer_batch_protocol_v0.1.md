# GigaChat four-question development batch v0.1

29 October 2026, Asia/Yekaterinburg. The user explicitly requested continuing
testing after the successful post-fix live smoke. This authorizes a bounded new
batch on four newly phrased development questions. This is not a held-out or
independent scientific evaluation: the assistant knows the earlier sources.

The exact questions and prospective assessment rules are versioned in
`gigachat_answer_batch_cases_v0.1.json`. Keep all four in denominators, including
preparation failures, local gate rejection, transport/schema/citation failure,
provider abstention and unattempted cases. Do not tune questions after model
outcomes or replace failed cases with easier ones.

Budget: at most four GigaChat model POSTs and four OAuth exchanges, one per
eligible case, with zero automatic retries, fallback, purchases or scope upgrades.
Each request retains `GIGACHAT_API_PERS`, `GigaChat-2-Max`, a 1200-output-token
ceiling, 120 seconds per HTTP request and the 100000-byte native-body ceiling.
Thus the total output-token ceiling is at most 4800, not a monetary cap. No
models/balance reads. Cases rejected locally are not sent to the provider.
Dispatch outside the sandbox through normal escalation because its socket
restriction is already established. No infrastructure retry allowance here.

Reuse the actual ASGI `/answer`, native production factory/adapter/transport,
source-preserving retrieval, existing gates and strict ID validation. Defaults:
collection `literature`, `hybrid_cross_lingual`, top-k 5, style `claims`, language
`auto`. No production prompt/model/retrieval/scoring/schema changes in this batch.
Use process-local scoped question/protocol bindings in the development wrapper;
restore them between cases. Do not change the previous smoke runner on disk.

First prepare all cases with real read-only PostgreSQL transactions and offline
cached local embeddings, stopping before external inference. Freeze exact
questions, requests, ranked traces, final evidence, source pages/layers/PDF hashes,
article metadata, code/cache/index hashes and preparation statuses. Any preparation
failure stays a typed diagnostic. Conflicting source/code bindings block dispatch.
Save a prospective batch contract and source snapshot before any live call.

Live question/evidence/source/request drift blocks that case before model POST.
Reserve the batch once before dispatch and use the existing append-only SHA256
slot for each model request. Neither changing output paths nor rerunning the
batch may reset attempts. Failure/interruption consumes reservations. Old live
smoke/DSC outputs and their slots remain untouched. No implicit batch extension.

Evaluate separately: local gate behavior; transport and native schema completion;
production citation syntax; evidence support; preservation of units, conditions,
article identity and methods; and appropriate insufficiency/abstention. Valid IDs
or HTTP 200 do not establish scientific correctness. Negative controls are scoped
to the actual selected evidence, not proof that the complete corpus lacks data.
Keep unknown/ambiguous context and extraction damage visible; do not repair raw
responses, silently normalize IDs or turn transport errors into scientific absence.

Inspect claims against exact cited source windows after the run, recording
page/layer/offset/PDF identities and contradictory/missing support. Label this
assistant-authored exposed-case review, never independent gold/accuracy. Native
usage and timing are observations, not billing verification or speed benchmarks.
Offline replay may reuse saved retrieval and response bytes without DB/model calls.

Deliver a separate searchable HTML with all four case cards, full expandable
request/response/evidence/diagnostics, and all selected documents in the agreed
eight-column TAC table with original-PDF links. Mark missing metadata and
uncollected Abstract/Conclusions/Terms explicitly. Keep this stage separate from
earlier outputs. No XLSX, manual Terms workflow or context-compression feature.
