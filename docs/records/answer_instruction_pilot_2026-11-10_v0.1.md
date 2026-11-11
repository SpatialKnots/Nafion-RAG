# Answer instruction pilot: five exposed development questions

Authorization: user «давай проведём испытание» after experimental general
instructions were prepared and tested. New scope, separate from all closed
rewrite/answer scopes. Maximum five model POSTs and five OAuth exchanges,
one attempt per frozen candidate request; no retry, fallback or continuation.
Any unused allowance expires when this scope closes. Production stays unchanged.

Predeclared cases, chosen for known defects (not random/independent evaluation):
1. rewriting_v02 / Satoh_07: identification versus unconfirmed possible products.
2. rewriting_v02 / Fan_05: ownership of interphase composition, SEI versus CEI.
3. rewriting_v02 / Satoh_06: mixture qualifier attached to cycling efficiency.
4. rewriting_v01 / Fan_10: electrode mass basis of specific energy.
5. rewriting_v02 / Satoh_03: completeness of requested density comparison.

Use exactly the previously frozen delivered question, raw sources/order,
model GigaChat-2-Max, max_tokens1200, timeout120s, claims/Russian/schema/system.
Candidate differs only by the frozen general instruction. No new question
rewriting or retrieval/DB/preparation, no new source/gold/modelled answer in input.
Baseline is the historical actual answer on the matching native, not a new
paired baseline draw; temporal/model/stochastic differences remain uncontrolled.

This is a direct actual-provider experiment on frozen admitted evidence,
not a new production /answer API or end-to-end retrieval test. Keep raw native
response, unmodified parsed result, citation validation and finite audit separate.
Audit never repairs, hides or replaces a new model answer. Abstention is recorded
as abstention rather than improved correctness. No aggregate accuracy score.

Before sends: verify source/parent/PDF hashes and byte-exact regeneration of both
baseline and candidate; exclusive new native-request ledger slots. Instrument
existing real GigaChat transport for at most one OAuth and one model request.
Network is permitted only for those endpoints during actual transport. No other
network/DB access. Full source snapshots, no credentials/token persistence.

After sends: close every allowance, compare each goal with exact cited raw spans,
check other visible omissions/novel errors, report returned model/finish/usage
when actually present. Post-hoc exposed implementation review is not independent
scientific acceptance. No prompt edits or reruns based on observed outputs.
