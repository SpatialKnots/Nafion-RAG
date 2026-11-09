# Explicit author/year retrieval candidate, v0.2, fixed before measurement

The first two captured questions show missing reference pages in the fusion
input. Widening feature reranking cannot create those pages. v0.1 remains intact.

v0.2 is an offline candidate, not a runtime rollout or semantic answer validator.
Only the original question, a complete frozen collection inventory, its metadata
and baseline search response enter the algorithm. No gold, IDs of target works,
reference page numbers, expected values, or case-specific synonyms enter selection.

Activation: exactly one explicit Latin author/year construction in the question:
`Surname (YYYY)`, `Surname and/и/& Surname (YYYY)`, or
`Surname et al./и соавторы (YYYY)`. Surnames may contain hyphens/apostrophes.
Match the first surname and year as whole tokens in registered title/authors/year.
If multiple cited references, no matching work, multiple matching records, or no
usable chunks exist, return the baseline unchanged, with explicit diagnostics.
Unique metadata matching is a retrieval hypothesis, not verified bibliography.
Additional surnames missing in metadata remain a diagnostic; do not fabricate them.

For a unique work: include the first nonempty source chunk by stored chunk_index
(abstract/front-page context; never an assumed answer), then the remaining chunks
ranked by count of distinct original-question body tokens, excluding surname/year
and existing RU/EN stopwords. Normalize NFKC/case/ligatures for matching only;
preserve raw source text and chunk/page identities. Stable ties: chunk_index, ID.
Return at most the original final top-k; do not add adjacent pages or rewrite text.
Keep the production evidence selector, gate, model settings and request untouched.

Controls, before measurement: surname boundaries, body-only citations, wrong year,
ambiguous author/year, no citation, empty chunks, multiple citations, determinism,
bounded size, raw immutability, unknown coauthors and explicit source provenance.
Replay the actual service on all five cases and all 76 older frozen baseline cases.
Report both identical and changed cases, labelled article losses/gains, source-span
retention, displaced raw evidence, gate/condition changes and unknown scientific
effects. Old labels are exposed development fixtures, not independent validation.

This candidate addresses explicit references only. Uncited Q03/Q04, numeric
ownership, exhaustive completeness and provider reliability remain separate work.
No external model/OAuth calls, downloads, slots, live reruns or changed gold.
