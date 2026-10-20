# ARIADNE: bounded Terms scientific-relation pilot scope

Date: 2026-10-14. Status: concrete implementation scope prepared after the
[stage12 conflict source audit](terms_conflict_audit_2026-10-14.md).
The initial scope below is retained as planning history. A bounded automatic
subset is now implemented in [stage16](tac_stage16_relation_pilot_2026-10-14.md):
two explicit templates, a source-bound immutable sidecar and read-only table
diagnostics for all 33 documents. See the [implemented contract](terms_relation_contract_v0.1.md).
This does not claim completion of every requirement below or scientific acceptance.

Scope update after the subsequent user request on the same date: future Terms
relations must be proposed and processed automatically, with read-only source
diagnostics and abstention. Per-case user resolution is not a requirement.
The initial worksheet remains development evidence, not automatic production output.

## Inputs and development cases

Bind to the unchanged stage12 snapshot
`5bb8c2f73a797a02551d758d7ebb10240d708077c2fb396f9bdcd419f6e5bcd6`
and its complete inventory, contexts, classification and source/policy hashes.
Keep the original 33 documents in stage review exports, including rows without
relation proposals. Limit the first manual worksheet to the seven selected
development documents: Ma 2009, Istomina 2021, Guo 2020, Kim 2015, Lin 2023,
Nagasubramanian 2011 and Satoh 2013. Source IDs, not these convenient labels,
determine identity. These are already development documents, not holdout data.

The nine existing worksheet cases are source-bound examples, not a gold set:

| Case | Scope and proposed handling |
| --- | --- |
| Ma: proton conductivity → membranes | Proposed class-level property-of; sample/conditions unresolved |
| Istomina: conductivity → Li-Nafion membranes | Proposed property-of for the exact same Abstract sentence |
| Istomina: glass transition temperature → ionomer | Proposed property-of; endpoint type/reference sample require review |
| Istomina: glass transition temperature → DSC | Deferred: method missing from Terms and different TAC contexts |
| Guo: charge-carrier concentration → EIS + interface modeling | Deferred: missing method endpoint; composite/model-derived procedure must remain explicit |
| Kim: critical gelation concentration → cast membranes | Abstain: dispersion and cast membrane are different objects; correlation is insufficient |
| Lin: conductivity → increasing salt concentration | Abstain: composition strategy is not a measurement method; prospective/cited wording |
| Nagasubramanian: future temperature performance as completed result | Abstain: authors state that results will be published later |
| Satoh: comparative viscosity in contaminated Conclusions | Deferred: boundary_error and multiple comparison objects retained |

The worksheet is under `output/terms_conflict_audit_20261014/`. Its three
proposed links have six existing exact TermUse endpoints. All endpoint types
and links are assistant proposals; no numeric record, sample identity or
scientific acceptance is implied.

## First implementation boundary

Implement a separate experimental sidecar, bounded automatic proposer and
source-bound validator/diagnostics. Start with `property-of` and `measured-by` only. No automatic
co-occurrence-to-relation rule, model inference or full-corpus scientific accuracy
claim is needed for this pilot. `component-of`, `under-condition`, cross-article
equivalence, production retrieval and numerical record extraction remain later work.

Relations must reference explicit endpoints, full exact context/evidence,
snapshot/input/policy identity, direction, a substantive reason and a declared
producer/reviewer. Do not inherit classification acceptance or accept links merely
because endpoint quotes match. Proposed endpoint types are independent review
questions. Missing/ambiguous endpoints and incomplete evidence are explicit states.

The current candidate inventory lacks the full method names in the four inspected
Ma/Guo/Istomina/Kim cases, despite those names occurring in source text. Therefore:

1. Preserve the existing generator and inventory; do not inject invented Terms.
2. Permit a separately declared source-span endpoint proposal only if its exact
   source identity, offsets, quote and hash validate. Mark its inventory membership
   absent and its type/link uncertainty explicit. Define this contract before implementing it.
3. Until that contract exists, retain missing-method cases as deferred; a relation
   with an invented term/use ID must fail validation.
4. Retain Guo's `combined with interface modeling` qualifier. Decide the domain
   meaning of measured-by for derived properties explicitly; do not label the
   procedure as a direct measurement merely to fit the predicate.

Cross-context links require a separately explicit multi-evidence record and
review of linkage/attribution. Do not automatically join Abstract and Conclusions
or bind every listed property to every listed method. Source-boundary errors
remain visible even if a local relation later receives a positive decision.

## Algorithm versions, persistence and restore

The existing Terms ledger is archival; do not silently extend its schema or
reuse an old manual assignment as a relation decision. Plan separate immutable
relation snapshots bound to input, endpoint, source and algorithm/policy versions.
Changed evidence produces a new version; earlier results remain inspectable.
Unknown/ambiguous/unsupported states remain explicit and are not sent to a user
resolution queue. No confirm/correct/reject form is required for this workflow.

Algorithm output never creates human-confirmed status. Classification, relevance,
endpoint type, origin and relation uncertainty remain distinguishable. Backup/restore
includes snapshots, source-span definitions, policy versions and algorithm history;
physical original PDFs remain immutable/external. Independent domain annotation
may assess accuracy separately and does not become a compulsory per-case UI task.

## Acceptance and reporting

Meaningful checks must cover wrong/unknown endpoint IDs, direction/type mismatch,
altered quotes/offsets/layers, missing methods, stale evidence, multi-object
ambiguity, adjacent cited results, negation, future results, incompatible snapshots,
concurrent revision conflicts and complete history restoration. An exact quote
check establishes traceability, not a scientifically correct relation.

Add explicit bibliography-only, negated and multi-sample negative cases before
claiming the stage5 negative-case scope complete. The present nine examples do
not cover all of those cases; do not manufacture them or call coverage complete.
Unsupported table/footnote cases must be deferred or moved to a separately
supported full-text/record workflow, not inferred from a flat TAC string.

At a completed engineering stage run the repository's relevant targeted tests,
Ruff, mypy and full pytest checks. Generate a separate HTML table of all 33 scope
documents with the agreed eight columns, complete expandable TAC/Terms,
source/diagnostic details and explicit relation proposal/review state. Verify
browser layout, text, controls and original-source links through a permitted
browser surface. The current audit's blocked browser QA is not a passing precedent.

Report engineering completion separately from scientific adjudication. No new
accuracy threshold, precision/recall value, workflow superiority, independent
sample size or time saving is asserted. Disabling/removing the private relation
sidecar and router must restore the previous Terms/retrieval behavior. Ingestion,
numeric records and production database schemas are outside this pilot.

## Changed / Tests run / Limitations / Verdict

Changed: concrete input/work scope, nine planning examples, endpoint and review
boundaries, required negative cases and rollback/acceptance criteria.

Tests run: the worksheet's source references and six existing endpoints were
checked by the artifact audit; see its executed-check report. Future relation
runtime tests are specified above, not claimed as executed.

Limitations: relation schema/validator/store/UI remain future work. Method endpoint
policy, measured-by semantics for derived properties and scientific labels require
domain review; the examples are development material, not an independent benchmark.

Verdict: bounded stage5 implementation scope prepared; no scientific acceptance
or completed relation implementation is claimed.
