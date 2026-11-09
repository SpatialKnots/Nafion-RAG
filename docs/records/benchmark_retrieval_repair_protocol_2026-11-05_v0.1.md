# Five-question retrieval repair, offline v0.1

Scope: user-authorized offline loss diagnosis and a bounded retrieval candidate.
No external model/OAuth calls, downloads, live slots, retries or rewritten answers.
Q01–Q05 are now exposed development cases, not an independent test set.
Existing outputs, references, native requests and historical bindings stay immutable.

Capture the actual unchanged answer service, all search-channel and ranking boundaries,
and the collection's chunk inventory in read-only transactions ending in rollback.
Only the frozen question-only packet enters capture. Stop at the generation boundary;
provider construction and generation are forbidden. Reference answers/pages are read
only later by the evaluator. Compare each fresh baseline with its historical trace.
Report drift instead of assuming identity. Local embeddings use existing offline cache.

First candidate, fixed before measurement: run the existing cross-lingual feature
reranker over all already-fused candidates rather than its current bounded prefix.
Keep channel calls, query variants, final top-k, evidence selector and adequacy gate.
This tests an existing cutoff; it cannot recover chunks missing from fusion.
Replay frozen channels with the actual service. Preserve displaced evidence and
report gate changes as software behavior, never scientific answerability.

If this candidate is insufficient, a separately versioned second candidate may
test article-scoped chunk retrieval. Its algorithm and controls must be fixed
before measuring it. No article IDs, reference pages, benchmark IDs or expected
answers may enter candidate logic. No production rollout based only on five cases.

Evaluate source membership, exact reference-text retention, loss stage, changed
evidence/conditions and existing regression cases. Article/page membership alone
does not establish an answer, and lexical matching does not establish ownership.
Keep failures, raw context, input hashes, source offsets and measured denominators.
Deliver a before/after report, diagnostics, meaningful tests and an explicit verdict.
