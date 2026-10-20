# TAC + Terms retrieval replay protocol v0.1

Frozen before the first candidate evaluation, 2026-10-14. This is a development
comparison, not independent validation or a user-time experiment.

## Inputs and controls

Use the 33-document, 619-chunk snapshot
`data/experiments/tac/20261012_v01/corpus.json`, the original 46 questions in
`data/experiments/tac/20261012_v01/comparison/questions.yaml` and the saved
`hybrid_cross_lingual` responses from its `report.json`. There are 38 answerable
and 8 negative questions. Preserve all questions and their existing judgments.
Use stage17 TAC profiles, complete Terms inventory and automatic classification
v0.4, bound to the same snapshot. Verify source PDFs and reproduce classification.

The original production top-10 differs from the saved top-20 pool because the
requested retrieval depth changes candidate generation. Therefore the common
pool is the ordered union of original production top-10 followed by saved pool
entries not already present. Its first ten entries reproduce the original
response exactly. Every experimental full-text arm uses this same pool; no
baseline candidate is removed before ranking. Pool size is reported per question.

## Fixed experimental adapter

Terms are not integrated into production retrieval. This replay adds an explicit,
offline adapter; it does not measure an already implemented production feature.
No answer generation, database write, index rebuild or model call is needed.

1. **Production:** original saved top-10, reevaluated with the current evaluator.
   Also retain historical metrics and report any metric drift separately.
2. **TAC soft:** reciprocal rank fusion of common-pool order and current TAC
   top-five article order. TAC scoring uses the existing `rank_tac` policy.
3. **TAC + typed Terms soft:** add a Terms chunk-ranking channel to arm 2.
   A TermUse contributes only when its type assignment is `proposed`, its source
   page is inside the chunk page range, its selected text layer matches the chunk,
   and its exact source quote occurs in the immutable chunk text. Score query
   token coverage against the distinct normalized Term labels represented by
   those uses, using the existing lexical score and the same query variants as
   TAC. A zero score supplies no channel rank. Unknown/conflicting type assignments
   supply no typed signal. No role, origin, relation or sample linkage is inferred.
4. **TAC + all Terms soft:** identical adapter, including untyped inventory;
   this ablation separates the inventory contribution from type filtering.
5. **TAC only:** existing top-five TAC article response. Diagnostic of evidence
   loss when full text is omitted; not comparable full-text chunk units.
6. **TAC shortlist + rescue:** existing shortlist replay over the common pool,
   with full-text rescue to ten. Included to connect to the previous TAC experiment.

Use `rrf_k=60`, the existing baseline RRF constant, equal channel weights and no
outcome-dependent tuning. Break ties by common-pool order. Query scoring never
reads relevance judgments. Exact full-text evidence remains unchanged. A soft
signal may still displace a relevant result from top-10; report every regression.

## Metrics and decision

Retain the existing evaluator's pass, article recall, judged chunk recall, MRR,
nDCG and trace-completeness definitions. Use ten results for full-text arms and
the existing five-article TAC diagnostic. Report top-one hits among 38 answerable
questions, negative-case failures among eight, and paired changes per question.
The reported hit fraction uses incomplete relevance judgments and is not true
precision. Chunk judgments that use lexical `text_contains` are not proof of a
scientific relation. Negative-case pass is the existing adequacy gate's abstention,
not measured correctness of generated answers.

Acceptance for this bounded adapter requires no reduction in article/chunk recall,
no additional negative-case failure, complete source traces, and a positive MRR or
nDCG change against production. Report failure of any condition; do not retune to
make this run pass. No claim of significance, general superiority or user-time
savings can follow from this development corpus. Group known duplicate works by
normalized DOI (otherwise exact selected-page-text hash) in an additional ranking
diagnostic; report repeated question targets rather than treating them as
independent scientific observations. There is no new train/test split.

## Deliverables

Keep input/code hashes, frozen adapter source, complete per-question results,
all regressions and an expandable searchable HTML comparison. Preserve a separate
copy of the stage17 eight-column TAC table covering all 33 documents. Original
PDFs, the active Terms snapshot and production retrieval remain unchanged.
