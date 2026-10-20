# Guarded TAC + Terms replay protocol v0.2

Fixed before the first v0.2 evaluation, 2026-10-14. The v0.1 failure motivated
this design. The same 46 questions are now regression/development data; this is
not a fresh holdout or independent confirmation. No query-specific exceptions,
relevance labels, desired rankings or parameter search enter the reranker.

## Inputs and arms

Use the immutable v0.1 replay report, its validated corpus/profile/inventory/
context/classification inputs and original production top-10. Preserve v0.1
outputs. Reverify input/code/PDF hashes and classification reproduction. Reevaluate
the original baseline with the same evaluator; report metric drift separately.

Evaluate these fixed arms:

1. Original production.
2. Original TAC RRF, restricted to production top-10 (membership-only repair).
3. Original typed Terms RRF, restricted to production top-10 (Terms-only ablation).
4. Original combined TAC/typed Terms RRF, restricted to production top-10.
5. Guarded TAC context scoring.
6. Guarded typed Terms phrase scoring.
7. Guarded TAC + typed Terms scoring (the candidate).

Every arm returns all original chunk IDs exactly once. Membership preservation
protects the existing article/chunk recall but does not guarantee good ordering
or negative-case behavior. The old 20–24 candidate pool is not used to introduce
new results. No ingestion, extraction, taxonomy or production scoring is changed.

## Query and specificity policy

Use the same query variants as v0.1. Scoring text alone folds case, whitespace and
the existing fi/fl/ff ligatures. Tokens use the v0.1 `[\w+-]+` grammar, length at
least two and its seven stopwords. Source quotes/offsets remain unchanged.

Compute document frequencies from all selected page texts, counting a known work
once: normalized DOI, otherwise SHA256 of its exact concatenated selected-page
text. Record this grouping as a declared heuristic; missing-DOI duplicates and
supplement/main-paper links are not guessed. Weight query tokens with
`idf(t) = 1 + log((N+1)/(df(t)+1))`. Compute full Term phrase frequencies across
the complete inventory, by the same work groups, with the same IDF equation.
No relevance judgments are used to calculate frequencies.

For TAC, use only a reviewed `pass` context whose complete exact quote occurs in
the chunk, with matching page/layer. Its score is the maximum weighted query-token
coverage of that exact context across the query variants. No global article-level
bonus is transferred to an unrelated chunk.

For Terms, require a `proposed` type assignment on that exact TermUse, reviewed
context, page/layer match, and its exact containing clause present in the chunk.
The clause is a source slice delimited by `. ! ? ;`; this is a lexical boundary
heuristic, not scientific sentence parsing. Require the entire normalized Term
phrase to occur with word boundaries in a query variant. A phrase must have at
least two tokens: one generic word alone cannot reorder results. Its score is
Term-phrase IDF times weighted query coverage of its source clause. Take the
maximum supported phrase score rather than accumulating nested phrases or
repeated mentions. Preserve diagnostics/evidence for all contributing signals.
This does not prove a scientific relation, sample identity or author attribution.

## Guarded ordering, fallback and duplicates

Start with original production order. Make stable adjacent swaps only when the
challenger's original-query token matches in full text contain every such match
of the defender, at least one active contextual signal is strictly stronger, and
no other active contextual signal is weaker (Pareto rule). No weights or score
cutoffs are tuned. Repeated passes terminate when no admissible adjacent swap
remains; ties preserve original order.

If an article has no reviewed Abstract or Conclusions context, its result slots
stay at their original positions. Swaps cannot cross such slots. This protects
unsupported and supplementary sources without inferring missing sections.
After guarded reordering, compare the existing evidence-adequacy decision with
the baseline decision. If it changes in either direction, roll back the whole
query order and record the reason. This gate is a lexical diagnostic, not truth.
The three membership-only RRF ablations do not receive these guards, so their
remaining ordering regressions are visible.

Display the final candidate in a separate work-grouped view. Group repeated
uploads using the declared work IDs and preserve all ten chunk identities,
article/PDF paths, page ranges and text layers inside groups. Grouping changes
presentation only, not flat metrics or stored Terms. Report first-judged-work
ranking separately; do not compare its units with flat chunk MRR.

## Metrics, acceptance and deliverables

Keep all v0.1 metric definitions and the same 38 answerable/eight negative cases.
For the guarded combined candidate require equal top-10 membership, no decrease
in article/judged-chunk recall, no additional negative-case failures, complete
traces, and a positive MRR or nDCG change to declare a development ranking gain.
If no gain appears, report no gain rather than selecting a better-looking arm as
the new primary candidate. Preserve every rank regression and abstention reason.
No production deployment or general superiority claim follows from this run.

Save separate versioned code/protocol/input/PDF bindings, full outputs, a searchable
expandable comparison, work-grouped candidate view and the complete stage17
eight-column TAC table covering all 33 documents. Reproduce the result in a second
run. Independent document-level evaluation and user-time measurement remain open.
