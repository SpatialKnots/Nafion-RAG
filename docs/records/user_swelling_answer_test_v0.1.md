# User-question end-to-end answer test v0.1

User question, verbatim: «Какая максимальная степень набухания Li-Nafion при
комнатной температуре задокументирована?» The user requested a neural answer
through the full current answer architecture and then supplied this question.
This authorizes one new bounded case; it does not reopen any previous slots.

Use the actual in-process ASGI POST /answer, current Settings, configured
literature collection, hybrid_cross_lingual retrieval/top-k, local embedding/index,
production reranking, evidence selection/deduplication, adequacy checks, GigaChat
factory/adapter and claim/citation validation. No manual evidence substitution,
question rewriting, prompt tuning, ranking/threshold/cache modification or bypass
of a gate. ASGI TestClient does not exercise browser rendering, a running web
server's network/proxy stack or a long-lived multi-request session lifecycle.
Ingestion/OCR/chunk/index creation are represented by existing immutable inputs.

Prepare and send in separate fresh processes with the existing smoke observation
helper, PostgreSQL repeatable-read/read-only transactions and cached local
embeddings with downloads disabled. Scope only the helper's process-local
question, version and protocol; its source file and production behavior remain
unchanged. Freeze exact native body, ranked retrieval, selected evidence, source
pages/layers/original PDF identities, metadata and code/index/cache hashes before
transport. The helper's authorization label is generic; this protocol and the
new study record identify the actual current question/permission.

Maximum one GigaChat model POST and one OAuth exchange: GigaChat-2-Max,
GIGACHAT_API_PERS, existing verified TLS, 1200 output tokens and 120 seconds per
HTTP request. No automatic retry/recovery, fallback, account/balance reads,
purchase or scope change. Native body ceiling 100000 bytes, no clipping. These
are token/time limits, not a monetary-cost cap. Reserve a new append-only global
SHA slot before OAuth. Failure/interruption consumes the allowance. A production
gate may end the case with zero provider calls; do not force a model answer.
Known sandbox socket restrictions require ordinary execution escalation.

Live retrieval/source/evidence/native bytes must match the frozen preparation.
Observe the actual original provider transport and save raw reply bytes before
production parsing. Do not persist OAuth bodies/credentials/tokens. Preserve
HTTP status/body, errors, abstentions, request/response hashes, returned model,
usage and timing; never repair a failed response into a valid answer. A new
output folder cannot reset a consumed model slot.

After the one run, replay its frozen retrieval/native bytes through the actual
ASGI route offline, with DB/network forbidden, and compare the full status/body.
Report the model's answer unchanged, separately from assistant source inspection.
For a numeric maximum check material identity, swelling definition/unit, solvent,
temperature, equilibrium/procedure context, comparison scope and exact source
page/table. A largest value among selected chunks does not prove a maximum over
the entire corpus or literature; absence in selected excerpts is excerpt-local.
Do not invent an expected numeric answer before reading the selected evidence.

The recent event/ownership modules remain offline. They accept event proposals,
not arbitrary answer prose; do not manufacture an event proposal/model call or
claim automatic semantic ownership validation. Where their interface is not
applicable, say so and inspect cited source relations separately.

Deliver all actual trace/request/raw response/diagnostics, original PDF links
and selected-document metadata in a searchable HTML review with the eight TAC
columns. Mark missing/uncollected fields. No XLSX or compulsory case/Terms forms.
One user-question development run is not independent scientific accuracy or MVP
acceptance. Preserve all prior outputs, failures and closed budgets.
