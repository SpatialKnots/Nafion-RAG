# Requested-context retention, runtime repair v0.1

User requested elimination of measured retrieval losses and checking sufficiency
without blindly relaxing the gate. No external API/OAuth/download/slots or live
resends. Preserve all older source, requests, outputs and guards. Freeze the old
runtime before mutation; record its exact drift separately.

Implement two finite, general query families (no benchmark IDs/article IDs/page
numbers/expected values): Li-Nafion equilibrium swelling AND swelling enthalpy;
Li-Nafion EC/SL mixing-temperature uptake with heating/cooling AND structure.
Match bilingual body-only source facets, ignoring titles as evidence. For the
first family require a table with explicitly labelled swelling enthalpy per mass
and equilibrium swelling in percent; a cohesion-energy parameter table alone
does not qualify. For the second retain both cycle/uptake and structural
amorphous/crystalline/plasticiser contexts from one work. This is source-context
retention, never scientific entailment or performed-status verification.

At each lossy cut (original hybrid and final cross-lingual top-k), reserve at most
one chunk per requested facet using deterministic greedy coverage within one
article; prefer an article covering all facets and preserve stable ties. Do not
add chunks, alter raw text/scores/units, expand channels, or change top-k. If no
facet matches, keep the exact original order/metadata. If top-k cannot retain all
facets, report missing coverage rather than silently declaring completeness.
Run the same retention after answer selection, so an unrelated selection bonus
cannot move retained context behind the final cut. Existing thresholds unchanged.

Before measurement: constructed positive/negative controls in RU/EN; unrelated
material, title-only cue, cohesion versus swelling quantity, unrelated methods,
structure-only/temperature-only fragments, cross-article joins, low top-k,
determinism/raw identity. Then full-service frozen-channel replays of all five
and76 older cases; report every changed scope, label loss, gate decision and
displaced condition surface. Verify selected source text with frozen corpus.
Prepare fresh read-only Q03/Q04 through real search, no provider, only after
offline checks. No tuning after outcomes without a separately versioned design.

Q01/Q05 source presence does not alone justify gate admission. Separately check
the full requested scope; record missing quantities/conditions and lexical
language mismatch. Do not replace the gate with author match or any-citation
presence. Numeric ownership validation and synthesis correctness remain distinct
from retrieving a table. Deploy only bounded changes supported by controls and
regression evidence; do not claim a new model answer without a real authorized call.
