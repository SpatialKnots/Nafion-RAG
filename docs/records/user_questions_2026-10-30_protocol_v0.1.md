# Three user questions: prospective preparation protocol

30 October 2026, Asia/Yekaterinburg. Questions are copied verbatim from this chat
into `user_questions_2026-10-30_v0.1.json`, before new retrieval/generation.

This is a user-authored query set, not independently annotated gold or an unseen
topic/source holdout. Known topical overlap is declared separately. Criteria
express the requirements of the questions, not expected scientific answers.
No independent accuracy score or scientific acceptance may be computed from
assistant-authored post-hoc source interpretation alone.

Preparation uses the current unchanged `/answer` route/service, GigaChat-2-Max
factory/prompt, collection `literature`, `hybrid_cross_lingual`, top-k 5,
`claims`/`auto`, current offline local embedding/index inputs. Freeze the actual
settings, selected source text/layer, article/chunk/page identities, native
request bytes and software/PDF/index hashes. Do not fix question spelling,
ranking, schema, thresholds, context or model limits to obtain an answer.

Run each question in a fresh process, with PostgreSQL repeatable-read/read-only
transactions and no retries. Process isolation is not a fix or validation of
the unresolved long-lived cache/ORM problem. Local DB reads are permitted;
PDFs, ingestion state and index files remain immutable.

Stop at the production provider transport boundary without real OAuth/model
requests. The preparation contract declares zero currently authorized live
attempts and zero slot reservations. A native request over 100000 bytes is
reported blocked without clipping or raising the ceiling. Preserve original
adequacy rejections and incomplete diagnostics. Full source pages in these
raw-chunk requests are disclosed; this is not compact-packet admission.

Prospective assessment dimensions: requested-information coverage, quantity/
material/method/condition ownership, comparison universe, correct citations,
direct source support, unreported assumptions, omissions, valid abstention and
software/provider failures. Leave them unscored before actual answers and
independent reference assessment. Preserve original model/API results and
separate later assistant critique; HTTP success is not scientific correctness.

Review includes all three questions and every selected work in the agreed TAC
HTML columns, full expandable source text, original PDF/page links, unknown
metadata and declared preflight blockers. Store earlier failures independently.

Future live scope, only if separately authorized after this review: at most
three new model POSTs and three OAuth exchanges, at most one pair per eligible
frozen case, no retry/fallback, GigaChat-2-Max, max_tokens=1200, timeout 120 s
per HTTP request. No automatic continuation of failed/filtered/truncated cases.
Existing closed budgets/slots are not reused. Authorization does not turn
selected sources into a complete corpus/literature comparison.
