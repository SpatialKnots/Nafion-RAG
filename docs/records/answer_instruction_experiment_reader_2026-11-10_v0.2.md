# Offline reader correction v0.2; instruction unchanged

First preparation stopped at the first saved answered native: the whitelist's
original question omits the pre-existing service prefix «По статье …», while
the actual native preserves it. This is a reader error, not prompt/model drift.
No native/body/question is repaired or overwritten. Original runner, freeze_v01
and incomplete preparation_v01 retained; no successful v0.1 measurement claim.

Separate v0.2 reader recovers the delivered question from its saved native's
Question/Evidence boundaries. It must end with the exact original question.
Both forms are saved. Baseline must reconstruct the entire previous native
byte-for-byte before any candidate comparison is accepted. Candidate adds only
the fixed general instruction to that exact delivered question and sources.
For rows lacking a provenance path, original-question preparations are labelled
as such; no historical native equivalence is claimed for them.

Instruction/module/default behavior unchanged. freeze_v02/preparation_v02 are
exclusive new outputs. This amendment changes the reader only; no model call,
translation, retrieval, source addition, gold-derived question augmentation,
new result or independent evaluation. All prior live scopes remain closed.
