# Twelve real excerpts: preliminary relation review v0.1

The user authorized twelve real experimental excerpts with questions, exact
quotes and preliminary source-linked annotation, then offline prototype checks.
Use the existing 25-page frozen registry from experiment_sentence_links_20261029 /
review_v02; select twelve distinct page intervals from five works. This is
purposeful selection from already exposed texts, not random or held-out data.
Keep overlapping contexts and the known impedance/spectra example explicit.

Freeze real_experiment_cases_v0.1.json and unchanged prototype code before
evaluation. Do not tune the prototype against these new expectations. Preserve
each raw quote, page offsets/hash, text-layer ID and immutable original PDF hash;
provide full registered pages and article metadata in the review output. No OCR,
text repair, page joining, ingestion, DB, retrieval, embedding or model calls.

Annotations are assistant-authored preliminary source readings, not independent
gold. Questions and qualitative expected answers are recorded for later review;
the prototype does not generate or score scientific answers. The relation graph
is evaluated separately on seven explicitly required source dependencies and two
forbidden same-measurement interpretations. Distinguish procedure sequence from
measurement context and finite-template scope. Unannotated pairs are not assumed
negative. Include unresolved annotation notes rather than force a label.

Score only directionally aligned parent/child anchors. An annotation span must
be an exact raw substring and map uniquely into different graph units; otherwise
report unmappable/ambiguous and do not count it as an ordinary prototype miss.
Report matched/missed preliminary dependencies, forbidden interpretations,
unannotated proposals, cases without proposals and open annotation notes.
These are descriptive development counts, not independent accuracy or recall.

Deliver searchable HTML for all twelve cases, full graph/diagnostics, original
page links and the agreed TAC columns for every selected work. Missing metadata
and uncollected fields remain explicit. Keep all earlier outputs and closed
model budgets intact. Runtime /answer and scientific admission remain unchanged.
