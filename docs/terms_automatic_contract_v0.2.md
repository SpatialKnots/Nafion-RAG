# ARIADNE automatic Terms classification v0.2

Date: 2026-10-14. Terms classification and subset formation are automatic;
there is no per-Term user decision task. This supersedes the active manual
workflow in review contract v0.1. Independent quality evaluation is separate
from using the automatically generated subsets.

## Policy and compatibility

`app/terms/taxonomy_v02.json`: schema `tac_terms_taxonomy_v0.2`, state
`automatic_context_policy`. The classification CLI uses it by default and emits
`tac_term_classification_v0.2`. Assignments retain proposed/unclassified/unresolved,
exact use identities and source evidence. Automatic output never becomes a
human-confirmed or accepted scientific assertion.

Legacy taxonomy/classification v0.1 remains supported for historical replay.
`taxonomy_v01.json` is unchanged. Version 0.2 rejects manual input, including
an explicit empty manual-input object. CLI `--manual` is legacy-replay only;
it is not part of the current automatic workflow.

## Exact context rules

Type rules may use `context_phrase`: a regex with a named `term` capture. It
applies only when that capture's absolute Unicode-codepoint span equals the
selected mention's start/end. A cue targeting another occurrence cannot label
this occurrence. The full matched source slice, region/offsets, quote hash,
rule ID and rationale are retained. Matching whitespace or explicit split-word
spellings never rewrites source text, units, ligatures or original PDFs.

The bounded policy covers glass-transition/decomposition/gas-generation onset,
charge-carrier/critical-gelation concentration phrases, preparation/ambient
modifiers, ranges/dependences, saturation conditions and explicit thermal
preparation/comparison clauses. Contextual type matches replace generic exact
type proposals for that mention. Highest declared context priority wins; equal
priority with different categories stays unresolved. Specific property frames
have priority 10, condition frames 0. These are rule priorities, not scientific
thresholds, probabilities or calibrated confidence.

Some patterns allow 30, 100, 160 or 180/200 non-sentence-punctuation characters
as explicitly declared in the policy. They do not join separate TAC contexts
or repair section boundaries. Negative/future wording does not become a
completed-result claim merely because the quantity's type is recognized.
Role/origin retain the narrow supported rules; unmatched uses remain unknown.

Generic electrolyte concentration retains property/condition alternatives
when context rules are inconclusive. Both candidate memberships and unresolved
remain visible, with no request that the user choose a category. Rules do not
contain article-specific IDs or hand-entered classifications of the audited cases.

## Subsets, UI and archives

Subsets apply AND filters to the same use, then project distinct article-local
term IDs. Different occurrences cannot supply different parts of an intersection.
A replacement corpus is classified afresh; unknown labels do not inherit results
or annotations from unrelated prior documents. Ingestion-job integration is
separate work; the experimental CLI pipeline must currently be run explicitly.

The live Atlas requires a v0.2 snapshot containing only policy proposals. Old
snapshots remain immutable/exportable. Policy or input changes require a new
bound classification/snapshot. Selection, source contexts, sorting, subset
exports and read-only diagnostics remain available. User confirmation/correction/
rejection/uncertainty/restore, reviewer/reason forms and manual view switches
are removed.

`POST /ui/terms-review/decision` always returns 410 without writing an event,
including requests from a cached old form or malformed requests. The state
endpoint exposes `workflow_mode=automatic`, `manual_decisions_enabled=false`,
an empty effective decision/history overlay and cutoff zero. Its legacy `queue`
key now provides read-only algorithm diagnostics.

Live and v0.2 static exports use algorithm assignments only. Old manual events
cannot change their subsets. The old ledger schema, backup/restore and archive
export remain for preserving history. Nonzero manual revision cutoffs are rejected
for automatic table/graph exports. Source-integrity failures remain explicit;
registered PDF/PNG delivery still verifies hashes.

## Limitations

Type recognition does not identify a sample, validate relevance, establish a
measurement method or resolve origin. The frozen 33 documents are development
material, and agreement with an assistant audit is not independent accuracy.
Scientific-relation extraction and ingestion-triggered Terms rebuilds remain
separate implementation tasks.
