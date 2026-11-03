# Kim2015 retrieval and adequacy audit, 31 October 2026

Scope: reproduce the frozen question and final trace from
`output/user_reference_20261030_01/preparation_v01`; capture the actual internal
retrieval boundaries using unchanged production code and local models/index.
The external reference and PDF windows are diagnostic targets only. They must
not enter query construction, retrieval, ranking, evidence or generation.

Database: one repeatable-read, read-only transaction, verified with SHOW and
rolled back. External network is forbidden; model/OAuth attempts and new slot
reservations must be zero. An explicit exception stops before generation.
No provider response is fabricated. Original PDFs, historical manifests,
requests, budgets and results remain unchanged. New outputs use exclusive creation.

Record full source-bearing rows, nested call parents, queries and limits.
Distinguish article presence from exact page/text-anchor presence. Analyse
parallel channels separately. A reproduction diagnosis requires equality of
the entire historical final retrieval/evidence/metadata trace; do not call
new internal boundaries historical observations.

Replay real fusion/ranking/evidence logic from saved channel outputs with DB
connections forbidden. Deliberately corrupt an expected boundary and require
rejection. Verify all historical input bindings and original PDF checksums;
freshly extract the eight reference windows and selected source pages.

Explain lexical admission using actual evidence, exact matched surfaces and
the production gate predicates. Any constructed counterexamples are exposed
assistant-authored development controls, not independent annotations or a
new semantic validator. No ranking, threshold, prompt, schema or runtime fix.

Deliver JSON capture/review, searchable local HTML with all captured TAC works
and eight agreed columns, tests, source checks and a written report. Preserve
failures and untested checks. Independent evaluation remains open; plan work
stays 75% unless the separate evaluation set is actually completed.
