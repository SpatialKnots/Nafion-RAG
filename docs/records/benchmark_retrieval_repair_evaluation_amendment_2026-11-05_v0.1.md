# Evaluation clarification; candidate and inputs unchanged

The first completed offline review (review_v01) called changes to the complete
adequacy metadata `gate_changed` / `old_gate_changes`. Those include matched terms
and coverage, not only changes to the allow/refuse decision. The raw report and
its source snapshot remain immutable. Do not interpret that counter as decision
changes or scientific errors.

review_v02 separately reports `adequacy_metadata_changed` and
`gate_decision_changed` (the existing adequate boolean), adds static HTML link/TAC
verification and binds both new test modules. No selection/candidate/query/scoring
change. Re-run the exact offline service comparisons to verify the clarification;
compare every saved case/arm result with review_v01 for deterministic identity.
No external API, new corpus search/embedding, database calls, or live slots.
