# GigaChat four-question batch: isolated-process execution v0.2

29 October 2026. Inherit all questions, budget, source/evaluation rules and
limitations from `gigachat_answer_batch_protocol_v0.1.md` and the unchanged
`gigachat_answer_batch_cases_v0.1.json`. No question or scientific criterion is
changed. The user-authorized upper bound remains four model calls total.

The initial same-process preparation is preserved separately at
`output/gigachat_answer_batch_20261029/`: one ready case, three explicit
`DetachedInstanceError` preparation failures, zero model/OAuth calls. Its source
snapshot preserves the earlier runner/protocol. Code inspection found cached ORM
rows in `LoadedVectorIndex.rows_by_chunk_id`; the test explicitly rolls back each
read-only session. This is an observed lifecycle limitation of repeated preparation
in one process, not a model failure or a scientific lack of evidence.

Prepare and dispatch every declared case in its own fresh Python process at
`output/gigachat_answer_batch_20261029_v02/`. Each worker installs the same network
policy and runs the unchanged real ASGI/retrieval/provider chain. Do not disable
the configured vector-index cache, change retrieval/model settings, manually edit
evidence or fix production cache logic in this stage. Process isolation must be
reported; repeated requests in a long-lived production server remain untested.

Freeze the new wrapper, tests, this protocol and the inherited protocol/case file,
plus all case/source/cache/index bindings. A parent dispatch marker and per-request
SHA256 slots prohibit repeats. Workers may send only after parent authorization
and a frozen ready case; each still permits at most one OAuth and one model POST.
Do not retry a failed worker. Keep unknown worker outcomes explicit rather than
assuming zero tokens or a successful abstention. Record worker stdout/stderr with
credential redaction and retain preparation failures in their original output.

No additional generative budget is created by offline re-preparation. All four
questions remain in the final report, including gate-rejected or failed workers.
