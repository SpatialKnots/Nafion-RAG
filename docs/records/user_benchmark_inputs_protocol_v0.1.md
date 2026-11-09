# Five question-only /answer preparations — 2026-11-03

User instruction: «подготовь входы». Preparation only; no dispatch authorization.

Freeze the current application/helper/test sources before executing the five
cases. Only `docs/records/user_benchmark_questions_2026-11-03_v0.1.json` enters
the worker. SHA256:
`d0d3ed5983b9e8b2a2bca6f26f1853232a6e7fa76035ae8e5c87fc8ab6c0609a`.
Require the original ordered Q01–Q05, exact packet schema and verbatim questions.
ID is orchestration metadata; it never enters the /answer body. No expected
article ID, PDF path, reference answer, quotation, condition annotation or
assistant source note may be supplied to retrieval/generation.

For each question use a fresh serial process, current default collection,
retrieval method and top-k, claims/auto. Invoke the actual ASGI /answer path with
read-only REPEATABLE READ DB transaction/rollback, local existing index/model,
offline embedding flags, without rebuild/download/query rewriting. Freeze all
runtime/source/index bindings. This is not repeated-request cache/ORM validation.

The worker denies reads of the benchmark intake folder, other docs/records and
the supplied benchmark Markdown; whitelist only this protocol and the pinned
question-only packet. Corpus PDFs remain valid retrieved sources. Do not use
gold to rank, choose evidence, change the gate or decide which cases to prepare.
The worker has no send mode. Replace the provider transport with an offline
OAuth placeholder and capture native chat bytes before network dispatch. A
simulated OAuth exchange is not a real OAuth call. External sockets are denied.

Keep actual trace/source registry/article metadata and either the exact local
HTTP status/body (if gate blocks) or the exact unsent native request. Preserve
raw failures and partial outputs. Never bypass a gate refusal. Keep a 100000-byte
review cap from previous preparation workflows as an explicit future-review
blocker, not a runtime limit; no clipping. Report actual sizes/hashes, selected
source identities/pages, qualifier/adequacy metadata and unresolved diagnostics.
No retries/fallbacks or slots; maximum real model and OAuth attempts: zero.

Validate packet rejection/leakage controls, fake transport boundaries, blocked
and oversized preparations, and restoration of monkeypatch state. Independently
verify prepared manifests/runtime bindings/native hashes and fresh PDF pages.
Render one local HTML with all five cases and all selected TAC works, eight
columns, full expandable metadata/raw source context, search and PDF links.
No XLSX. Unknown metadata stays explicit. No comparison with gold or answer scores.

All prior live budgets remain closed. Model stays GigaChat-2-Max / 1200 output
tokens / 120s; a future live scope requires explicit new approval after this
concrete review. Do not treat this protocol or the benchmark's internal rules
as authorization. Independent evaluation stays open; answer-quality plan75% work.
