# Terms annotation guide v0.1: draft for domain review

Historical annotation guidance, not a current per-Term user task. Since
2026-10-14, [automatic workflow v0.2](terms_automatic_contract_v0.2.md) performs
classification/subset formation; manual UI decisions are disabled. Independent
quality annotation remains a separate evaluation activity.

This guide accompanies TAC stage11. It defines review questions, not a validated
ontology. Source integrity, term relevance, type, role, origin and scientific
relations require separate decisions. UI decisions are not yet persisted.

## Unit and source

Review a concrete TermUse inside its exact containing TAC page fragment. Open the
original PDF when layout, truncation or attribution matters. Source quote/layer,
page/offsets and boundary diagnostics must remain visible. A correct quote does
not prove a correct classification. TAC-only context may be insufficient.

Classify the full selected phrase. Do not assign a compound's type merely because
it contains `Nafion`, `conductivity` or another familiar token. Nested lexical
mentions are separate candidates and may deserve rejection or different labels.
Phrase length does not determine number of memberships. Same labels in different
articles remain distinct; synonyms and cross-article equivalence are out of scope.

## Axes and draft meanings

| Axis | Categories and intended review question |
| --- | --- |
| Type | material/substance: a material or chemical label; object: a described device/specimen/structural object; property: a characterized quantity/feature; process: a transformation/action; method: an analytical/preparative technique; condition: a circumstance/parameter of the described use |
| Role | study_object, composition_component, comparison, method, background: how this particular mention participates in the context |
| Origin | own_report, cited_work, hypothesis: whose claim/use is expressed here and with what attribution |

Object/material boundaries and property/condition boundaries require domain review.
For example `temperature` can name a measured property or a condition. The current
policy retains both proposals as unresolved rather than selecting by arbitrary priority.
`glass transition temperature` and `room temperature` have separate draft rules;
this is still a proposal, not a universally accepted taxonomy.

Unknown and unresolved are retained for each axis. A proposal on one axis does
not fill the other axes. A study-object label does not establish sample identity;
a method cue does not prove attachment to a particular measured result.

## Evidence and exclusions

Type exact-phrase rules cite the selected mention plus an explicit draft lexicon
rule. That supports reproducible policy matching; inspect the broader context to
decide whether the match actually describes the intended concept.

Automated role rules require a directly preceding cue and appropriate type proposal:
`using`/`measured by`/`characterized by` with a full method name;
`compared with/to` or `versus` with material/object; sentence-initial author study
voice immediately before material/object. Keep unmatched or more complex cases unknown.

Automated origin proposals use narrowly adjacent sentence-initial author voice
(`we measured/observed/found`, `our measurements of`) or explicit author hypothesis
(`we hypothesize/assume that`). A nearby citation number, placement in Abstract,
or absence of a citation does not by itself establish origin.

Version 0.1 has no automatic composition_component/background role rule, no cited_work
origin rule, and no multilingual role/origin grammar. They remain unknown unless
an explicit manual proposal supplies context and reason. Negation, reported speech,
ambiguous referents and incomplete TAC should be reviewed, not silently repaired.
Word-per-line geometry and hyphenation are preserved; normalizing matching whitespace
does not authorize joining broken words or changing quotes.

## Development examples and review protocol

Eight manual assistant proposals in one Laporta abstract demonstrate compound type,
study role and author attribution. Two concrete `Nafion` mentions demonstrate different
roles: preparation of the present-study dispersion and comparison with commercial
dispersion. The full exact abstract is their basis. Reviewer kind is `assistant`;
these are not independently accepted human labels or a benchmark.

For each proposed label, check phrase meaning, target occurrence, context support,
source boundary and alternatives. Review term relevance separately from category.
Record a reason and evidence scope for any future correction/rejection; stage4 will
add persistent events and conflict-safe revisions. Until then, use source-bound manual
proposal JSON; it cannot mark scientific acceptance.

An independent evaluation should include positive, negative, ambiguous, cited,
multi-object and damaged-source cases; separate development documents from holdout
by work identity. Do not treat the 33 development documents, output counts or exact
quote checks as classification accuracy, recall or proof of competitive advantage.
