# Frozen protocol: cross-lingual requested-relation audit v0.1

2026-11-02, Asia/Yekaterinburg. User authorized the next offline iteration.
Written before measuring the new analyzer on corpus evidence.

Scope: source-only finite RU/EN relation proposals for the original-question
family Nafion + dispersion + particle + morphology/shape + solvent. Parse
requirements from the ORIGINAL question, not search variants or reference
answers. Keep unsupported query qualifiers explicit; do not silently drop them.
No production/runtime/gate/index/prompt/schema/threshold changes, new DB/search/
embedding/model/OAuth calls, native requests, slots or model downloads.

Inputs: 304 saved final evidence sets from the 76-case/four-arm
retrieval_ablation_20261031/capture_v02, plus the 24 actual scoped candidate
traces of retrieval_window_selection_20261102/review_v02. Prior outputs,
protocols, labels, hashes and guards are immutable. Verify manifests/current
bindings; use all 33 TAC works from the frozen inventory. Source text and
metadata are never rewritten. No article ID/title/DOI/page/answer outcome enters
the analyzer. IDs are output addresses and source integrity checks only.

Analyzer design:

- Matching view maps existing ligatures and line-break word hyphenation back
  to exact raw offsets. Decimal punctuation and finite scholarly abbreviations
  must not create spurious sentence boundaries. Split clauses at sentence,
  paragraph, semicolon and explicit contrast boundaries. No cross-chunk links.
- Detect source-local directed textual dependency, with explicit Nafion particle
  morphology attachment. A material elsewhere in the clause is insufficient.
  Require solvent and dispersion cues in the same linked span, or the one
  permitted exact adjacent antecedent below; report every missing role.
- One finite context exception: an immediately preceding affirmative clause
  explicitly identifies particles in/of a Nafion dispersion, and the next
  adjacent sentence begins with possessive Their morphology / Их морфология.
  No blank paragraph, different object/material/form/status or general heading
  inheritance. Plain pronouns/implicit relations stay unresolved.
- Distinguish affirmative dependency, observed null effect, unperformed tests,
  lack of evidence, proposal/future, question and uncertain/hypothetical text.
  Null effect with an explicit observed/measured cue can inform a dependency
  question. Bare negation is unresolved, not a blanket absence-of-information
  verdict. The previous 22-control labels remain untouched; new controls define
  this different textual-candidate criterion explicitly.
- Extract exact condition surfaces (temperature, percent concentration,
  duration, explicit H/Li/Na-Nafion form) with source spans. Same-clause values
  remain unverified; outside fields unassigned. Query numeric/form/room-
  temperature requirements must match exact local surfaces; no 25C/room-T,
  percent/basis, units, range/point or Na/H/Li equivalence. Unsupported wording
  blocks textual-requirements status. No value is propagated.
- Output source candidates / unresolved / exclusions, never scientific
  admission. A role match is not entailment or experimental/value ownership.
  Existing baseline adequate true/false is retained separately. Report
  candidate disagreements as review proposals, not real runtime decisions.
- Detect byte-exact repeated raw evidence and repeated proposal spans across
  article IDs. Keep every provenance row and original order, no dedup/reranking
  changes; different PDF hashes remain different originals.

Before corpus measurement freeze constructed RU/EN controls: affirmative and
observed-null relations, missing study/evidence, future/hypothesis, other known
and unknown material owners, wrong object/property, cue borrowing, explicit
antecedent versus implicit/anaphoric cases, exact versus mismatched conditions,
form changes, cross-evidence borrowing and duplicated source observations.
Assistant-authored development labels are NOT independent scientific gold.
Do not tune this algorithm after observing corpus outcomes; failures remain
in the v0.1 report and inform a separately versioned iteration.

Measurements: on each of 328 frozen evidence sets compare unchanged recorded
baseline metadata with a fresh production-service preparation replay on its
frozen retrieval output (provider/DB/embedding/search-network guarded). Full
trace and boundary status must reproduce. Run analyzer twice and require exact
identity. Out-of-scope policies preserve the baseline and declare no new relation
assessment. Count actual records and source-local proposals/exclusions/missing
roles; list baseline disagreements separately per old arm/window qualifier.
Do not equate candidate count with answer completeness. Existing 8 Kim anchors
stay evaluation-only and require fresh PDF extraction; no reference input to
the analyzer. No new ranking-window evaluation or generic scientific accuracy
claim. Thresholds are not lowered and only-Nafion coverage cannot authorize.

Verification: semantic boundary/control/raw-offset/conditions/duplicate tests;
328 actual service trace replays, repeated diagnostic executions, corrupted raw
source and baseline trace rejection; all 33 PDF hashes and 8 fresh anchors;
current immutable input bindings; static local HTML QA with all 33 TAC rows,
original 8 columns, full expandable values, source text, search and PDF links.
Browser/full-suite/mypy status must be stated accurately. Preserve errors.

Publish actual outcomes even for no recovered proposals or remaining false
qualifications/refusals. Do not deploy either a sidecar or a lexical gate bypass.
Independent stage4 remains open until new external references, answer-quality
plan75%; query rewriting stays separately deferred, all live budgets closed.
