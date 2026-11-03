# Frozen protocol: offline feature-window selection v0.1

2026-11-02, Asia/Yekaterinburg. Written before executing the new candidates.

Purpose: test whether generic source-text requirements before the feature-window
cutoff retain requested evidence. This is exposed development, not independent
scientific evaluation. No production app changes, new search/DB/embedding/model/
OAuth calls, native requests, slot reservations or changes to historical outputs.

Inputs: all 76 cases and all four arms of
output/retrieval_ablation_20261031/capture_v02. Historical arm, query, corpus,
variant top-k, feature-window size, final top-5 and original raw texts are fixed.
Existing channels are replayed, not searched again. All current baseline full
traces and recorded boundaries must reproduce before comparison.

Finite query scope: original question contains all five existing generic cue
families Nafion, dispersion, particle, morphology/shape, solvent. No outcome
forms, sizes, solvents, article IDs, titles, page numbers or reference text enter
the candidate algorithm. Other questions are exact no-ops.

Two candidates, with no outcome-based tuning in this version:

1. body_coverage: raw full_text contains all five cue families. This is a
   deliberately weak lexical comparator; snippet/title cannot supply a cue.
2. local_relation: all five cues and an explicit dependency/change cue occur
   in one sentence. Reject sentences with explicit negation, future/proposal,
   question, or mixed-material control cues. Missing attachment remains
   unresolved. This is a necessary-cue proposal, never scientific admission.

Split source sentences at .!? followed by whitespace and blank paragraphs;
decimal points stay intact. Preserve exact raw offsets/text. Map ligatures
only in the matching view. Do not inherit subjects or conditions across
sentences; do not equate co-location with verified ownership. No stemming,
new source normalization, values/units conversion or outcome vocabulary.

Placement: keep legacy ranking and article diversity, then stable-partition
that existing sequence by candidate qualification before selecting the same
feature window. Run the existing feature scorer inside that fixed-size window;
stable-partition its output by the same qualification. Keep the tail and all
later article/language diversity, evidence selection and adequacy unchanged.
This is one declared window-selection policy with two source qualifiers.

Record input/selected-window/output identities and every candidate diagnostic,
including exact sentence spans and unresolved/rejection reasons. No injection,
duplication, score/text/metadata edits of SearchResult objects are allowed.

Primary observations: eight existing exact Kim windows in final generation
evidence and at intermediate boundaries; gains and losses separately, per
arm/query. These are exposed anchors, not eight independent experiments.
Secondary: all existing fixture article identities using the v0.2 repository
matcher, final evidence identity/order/full-record changes, adequacy/status
changes, all declared-negative cases including inherited qext044 conflict.
Outside-scope full trace must be exactly unchanged. No acceptance from coarse
article hits alone. No candidate rollout in this iteration.

Before corpus comparison freeze constructed controls with explicit expected
cue eligibility: positive RU/EN relations, wrong property/object/material,
negation, future, question, separate-sentence cue borrowing, title-only cues,
dispersed cue lists and anaphora/implicit-relation false-refusal cases. Report
weak-comparator false qualifications and strict-candidate false refusals as
development observations, never scientific false-answer rates.

Verification: unit tests for qualification, raw spans, identity/order/no-op,
fixed window and budget invariants; all 304 baseline replays; corrupted raw
source and boundary rejection; all 33 original PDF hashes, fresh eight anchor
windows, input/source bindings; reproducible candidate replay. Network denied
and DB/embedding/provider guards active. Generate standalone review HTML with
all 33 scoped TAC works, original eight columns, expandable full fields,
search, real PDF links, per-case changes and full morphology evidence.

Completion: publish actual outcomes and limitations even for zero gains or
regressions; preserve failures separately, never tune v0.1 after observing
corpus results. Independent stage4 remains open, plan75%.
