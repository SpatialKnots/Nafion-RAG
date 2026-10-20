# TAC stage15: automatic role and origin cues

Date: 2026-10-14. Scope: all 33 frozen development documents, no manual decisions.

Changed: new default taxonomy/classification v0.3 extends v0.2 with eleven
source-anchored grammatical rules for roles and attribution, retaining unknowns
and exact evidence. Type rules and inventory generation are unchanged. Negation,
future/citation qualifiers and ambiguous role-dependent types abstain. Context
rules cannot resolve one use by borrowing a role from another. See the
[v0.3 contract](terms_automatic_contract_v0.3.md).

The separate stage15 prepared snapshot is
`61fba942ac5614ae05b1c40f8c715f16918af7179738c7985eb86aacb4296237`.
Its exports are `output/tac_stage15_20261014/ARIADNE_TAC_stage15.html` and Atlas.
The final additional inherited-cue type guard is included in the combined final
stage16 snapshot. Candidate outputs and earlier prepared snapshots are retained;
classification file provenance differs between runs even when corpus assignments
are unchanged. The final classification input is
`data/experiments/tac/20261014_stage15/classification_final_v03c.json`.

Observed development counts: role 3 proposed / 4,192 unclassified; origin 64
proposed / 4,131 unclassified. Types remain 1,208 proposed / 2,979 unclassified /
8 unresolved. Only study-object and own-report cues match this corpus. Other
implemented categories have synthetic contract coverage, not observed corpus
coverage. These are output counts, not classification accuracy.

Tests run: synthetic checks cover exact offsets/quotes, same-use intersections,
new corpus recomputation, passive-head attachment, component versus object,
named cited work, explicit hypothesis, method type ambiguity, PDF line breaks,
negation/future qualifiers and sentence isolation. An initial two failures exposed
component attachment and future-attribution problems; both were fixed before the
passing runs. The final targeted classification/relation set passed 46 tests.
Stage15 static integrity checks preserve all 33 rows, full TAC/91 metadata values,
all inventory/source identities, 113 local targets, 120 source/input hashes,
recomputed subsets and zero manual events. Full combined checks are in stage16.

Limitations: role coverage is deliberately small. Unknown roles/origins are not
sent to the user. No learned category discovery, ingestion-triggered Terms job,
general discourse parser or independent scientific benchmark is implemented.

Verdict: automatic bounded role/origin classification is implemented; broader
scientific completeness remains unestablished. Historical manual workflow stays disabled.
