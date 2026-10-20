# Stage11: closed ruled tables with tail rejection

Algorithm `source_ruled_tables_v0.2`. This explicitly supersedes only the new
experimental v0.1 table mode, not stages08–10. The v0.1 run is rejected: visual
inspection found one proposed table omitted its last row and a letter note.
Its source snapshots, raw candidates and review remain preserved. Two synthetic
counterexamples reproduced the old admission failure before this correction.

Use the unchanged four stage07 development questions, PDF/source registrations,
stage08 prepass, stage09 selection and stage10 protection. No inference, OCR,
DB operation, fresh retrieval, question/label tuning or production activation.
Freeze this new protocol, code, inputs, rule/table registries and selected PDF
hashes before the fresh v0.2 replay; never repair the v0.1 output in place.

Retain the v0.1 declared geometry grammar: horizontal vector line/rectangle paths
at least 120 PDF points wide, at most one point high; top rule within 16 points
below a block-start table caption; matching closing endpoints within 3 points
before the next prose/table barrier. Require exact registered text/block geometry,
complete enclosed blocks, at least two data/header blocks and four numeric tokens.
Keep every original drawing index, source rectangle and character range.

Retain all explicit note blocks within the same horizontal span, chained by gaps
of at most 12 points after the closing rule. Every body star/dagger marker must
have its definition in those notes. **New rejection:** any other text block within
12 points of the closing rule or last attached note makes the table tail unresolved,
even if that text resembles prose. This prevents treating a later row, an unsupported
letter note or a close paragraph as proof of a closed table. Do not extend the
boundary by guessing its meaning; retain the existing broad fallback instead.

Other v0.1 behavior remains: continued tables rejected, crossing rectangles rejected,
no cell assignment or table reconstruction, no stitching vector segments, no figure
OCR or missing-note synthesis. Whole leading prose reference paragraphs may be
protected using the explicitly listed verbs; they are not counted as table groups.
Protect exact accepted group blocks plus unchanged query/condition/neighbor blocks;
unresolved risks outside those groups retain the full prepass fragment.

Generate a fresh separate four-case HTML/JSON and actual table overlays. Inspect
headers, rows and notes in every proposed table. Repeat earlier-mode compatibility,
exact slice/PDF/code/registry hash checks and full appropriate regression. Preserve
the failed run and corrected-run scope/gate outcomes; no model answer, token/cost
saving or independent scientific accuracy can be claimed from this offline replay.
