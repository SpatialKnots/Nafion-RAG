# ARIADNE automatic Terms context policy v0.3

Date: 2026-10-14. Extends [v0.2](terms_automatic_contract_v0.2.md).
The Terms workflow remains automatic and read-only. Historical manual decisions
are archival; no user resolution queue, writable form or scientific confirmation
is introduced.

## Version and compatibility

Default taxonomy: `app/terms/taxonomy_v03.json`, schema `tac_terms_taxonomy_v0.3`.
Default classification: `tac_term_classification_v0.3`. The previous taxonomy
files are unchanged and explicit v0.1/v0.2 reproduction remains supported.
New outputs use new paths and immutable prepared snapshots. Existing article,
Term, Mention, Context and TermUse identities and source slices are preserved.
No ingestion, text/OCR extraction, inventory generation, ranking, retrieval,
production database schema or numeric-record behavior changes.

## Rules and evidence

The type rules are inherited unchanged from v0.2. Eleven `anchored_context`
rules add bounded grammatical cues for study object, composition component,
comparison, method, own report, cited work and hypothesis. Background remains
unknown without a supported rule. No category is assigned solely because a word
occurs near another word or belongs to a particular article/section.

An anchored rule has exactly one `__TERM__` placeholder. It is replaced with
the escaped exact existing mention and a generated named capture. Both capture
offsets must equal the selected mention offsets. Rules cannot introduce new
mentions or TermUse IDs. Material/object/method-dependent roles require one
unambiguous compatible type, including inherited adjacent cues in v0.3.

The match is extended to the end of the local clause/sentence for evidence and
qualifier checks. Explicit negation, future/planned wording and bracketed numeric
citations cause abstention. Rules do not inherit attribution across sentences or
TAC contexts. PDF line breaks and two explicitly supported hyphenated predicate
spellings remain exact in the source and basis; matching never repairs text.

Own report means an explicit author/current-study attribution proposal. It does
not prove that an experiment succeeded, establish a numerical result or resolve
sample identity. Named `et al.` and previous-work reporting cues can propose
cited-work origin without resolving a bibliography identity. Hypothesis requires
explicit hypothesis/assumption wording; generic `may` is insufficient. Unsupported
grammar, lists, unrecognized language/words and damaged text remain unknown.
Competing category proposals remain unresolved, without a task for the user.

Each basis retains rule ID, source region, exact offsets, exact quote, quote hash
and rationale. Subsets still intersect axes on the same TermUse and then project
distinct article-local Terms; roles from separate uses are never joined.

## Corpus changes and limits

Running `scripts.tac_term_classification` on a different validated frozen corpus
recomputes every assignment and subset. Old classification sidecars cannot be
applied to changed contexts. This is a versioned CLI pipeline; ingestion-triggered
Terms rebuilds, learned category discovery and production retrieval integration
remain unimplemented. No independent scientific accuracy is claimed.

Executed development-stage evidence and observed counts are in
[stage15](tac_stage15_context_roles_2026-10-14.md).
