# ARIADNE Terms classification contract v0.1

Implementation: `app/terms/classification.py`, `app/terms/taxonomy_v01.json`,
`scripts/tac_term_classification.py`. Development scope: frozen TAC stage10,
not production indexing, database migrations or scientific acceptance.

## Inputs and identities

Exporter requires the same snapshot, profiles, complete inventory and exact
contexts used by stage10. It validates those contracts and physical PDF hashes
before classification. Original PDFs and all extraction outputs remain immutable.

Taxonomy file: `tac_terms_taxonomy_v0.1`, state `draft_requires_domain_review`.
The three axes are type, role and origin. File-byte SHA256 and canonical JSON
content SHA256 bind the policy; rule IDs, code hashes and full policy are retained.
Normalization casefolds and collapses whitespace for exact phrase matching only.
It does not rewrite stored terms, quotes, offsets, hyphenation or PDFs.

Classification target is one existing TermUse, with its term_id, mention_id and
context_id. No aggregation across articles changes identities. Assignment ID
hashes `classification`, use_id, axis, taxonomy file hash and canonical proposals.
Manual reasons/reviewer declarations are part of this proposal payload. Timestamp
is provenance, not assignment identity. A policy/source change requires a new
bound output; accepted decisions are not reused because acceptance is not implemented.

## Assignments and evidence

Sidecar schema: `tac_term_classification_v0.1`, state
`proposed_not_scientifically_accepted`. Exactly one assignment per use per axis:

- `proposed`: one distinct candidate category, possibly multiple supporting proposals;
- `unclassified`: no supported rule/manual proposal, retained with diagnostics;
- `unresolved`: multiple distinct candidate categories, all retained with conflict diagnostics.

There is no accepted state or invented probability. Source boundary diagnostics
propagate independently; an assignment never repairs a TAC section.

Each proposal records category, producer (`policy` or `manual_proposal`), bases and
declared reviewer. Basis contains rule_id, source_region_id, Unicode-codepoint
start/end, exact quote, quote_sha256 and rationale. Exact-name policy cites the
mention region. An adjacent-cue rule cites the containing context region from
the cue through the selected mention. Manual proposals cite the full frozen
context and their reason. All references/slices are reconstructed by validation.

The term source remains stage10's full provenance: article/PDF/layer identities,
paths and hashes, page, page text hash and exact offsets. Consumers require stage10
contexts; a classification file alone is not an independent scientific source.

Manual input schema: `tac_manual_classification_proposals_v0.1`; contexts_sha256,
taxonomy_sha256 and proposals are required. Proposals specify existing use_id,
axis, substantive category, reason, declared_reviewer and reviewer kind
`assistant`/`human`. Unknown targets, unknown categories and duplicate proposals
for the same use/axis/category are rejected. A declared human reviewer is not
authentication or independent review, and does not create accepted status.

## Subsets and saved views

Category membership includes candidate categories from proposals. A conflicting
assignment also belongs to unresolved; an unknown assignment to unclassified.
Aggregation to term ID uses set union of memberships over the scoped uses. Thus
a term can belong to known and unknown groups when different uses differ.
Every group retains matching use_ids as well as distinct term_ids; count is the
number of distinct article-local term IDs, never number of mentions.

`subset` applies AND filters to the SAME use before projecting distinct terms.
It cannot join a role from one occurrence to origin/type from another occurrence.
Orders: original inventory rank; normalized Unicode-codepoint alphabetical order
plus term_id; first matching-use page/start/use_id plus term_id. Graph global source
order additionally prefixes frozen article order. Sorting changes no stored records.

Sidecar contains 20 frozen axis/category view definitions: filters, rank order,
taxonomy/context hashes, review_revision_cutoff=0 and proposals-only state.
The graph exports the user's current subset as `tac_terms_view_v0.1`, including
scope, query, sort, ordered term_ids and input hashes. This is a reproducible
definition/result export; interactive review persistence and import are absent.

## Compatibility and limitations

Stage09 inventory and stage10 contexts retain their schemas and bytes. Review
exporter gains optional `--classification`, requires contexts and keeps eight
columns. Graph gains optional `--classification`; classified payload is explicitly
`tac_terms_graph_v0.2`. Without it, v0.1 structural payload remains supported and
classification modes are disabled. Previous HTML outputs are kept separately.

Policy coverage is deliberately bounded. No synonyms, acronym expansion, language
translation, broad headword rules, full-text scanning or model proposer is added.
Manual examples are assistant proposals in one development abstract. Exact-source
validation proves traceability, not correct taxonomy, relation or experimental linkage.
