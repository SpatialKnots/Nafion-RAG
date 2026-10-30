# Answer presentation v0.1

30 October 2026. Step 3 of the answer-quality plan.

Implement a presentation-only trace capture for UI requests: retain the exact
generation evidence and bind it to the already retrieved chunk/article/pages.
Do not perform extra retrieval, DB reads or source repair to improve a saved
answer. API JSON/claim schema, ranking, thresholds and token limits stay fixed.
Render human-readable title/page links beside claims and in the answer; preserve
unknown metadata. Give each claim expandable, untruncated raw source context
when it is available from the same trace, with its text layer. Distinguish
raw source, system-derived tables and text actually supplied to the model.
If only a saved display excerpt is available, label that limitation explicitly.
The displayed context is not automatically a validated supporting quotation.

Add a versioned GigaChat user-prompt instruction for direct conclusion,
relevant conditions/quantity definitions, experimental/model-derived distinctions
and scoped limitations. Do not invent fields or force length. URLs and source
labels come from registered application metadata, not model-generated references.
This is prompt guidance: new model behaviour/content quality is untested.

Use three frozen successful user/runtime answers: the Li-Nafion swelling answer,
measurement conditions, and equilibrium comparison from 29 October. Preserve
their original API/native bytes and statuses. Render before/after independently
of generation. Build a separate unsent prompt candidate for each and verify that
the JSON response schema and request limits remain unchanged. No reservations,
model/OAuth calls or DB operations. Do not pretend new prompt bytes match old
requests. Historical input bindings may show declared application-code drift;
keep the original snapshots and hashes instead of rewriting old bindings.

Tests cover full context that contains a number missing from the display excerpt,
multiple works/pages, unknown metadata, unsafe source text escaping, repeated
citation IDs, mismatched identities, derived/raw separation and absence of trace.
Use software/source checks and browser QA where available; record unavailable
checks. Independent scientific accuracy/acceptance remain outside this stage.
