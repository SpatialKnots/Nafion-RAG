# Stage11: closed ruled table proposals

Algorithm `source_ruled_tables_v0.1`, offline on the unchanged four stage07 cases.
Compose stage08 prepass, unchanged stage09 anchors/conditions/neighbors and stage10
layout protection with this new explicit mode. No inference, OCR, DB operation,
retrieval/label tuning, cell reconstruction or production activation. Freeze input,
code, selected PDF hashes and new rule/table registries before selection.

Read horizontal vector rules from the same registered selected PDF. Require exact
source text/hash equality. Only finite horizontal line/rectangle drawing paths at
least 120 PDF points wide and at most one point high qualify. No stitching broken
segments or interpreting images. Keep original drawing indices and coordinates.

For a block-start Table/Таблица/Табл. label and number (punctuation or newline allowed),
find the first full-width rule within 16 points below the caption. Caption bounds
must fit its horizontal span within 3 points. A closing rule must match both
endpoints within 3 points, occur below it and precede the next table caption or
same-column prose paragraph. Use the last such rule, retaining intermediate header
rules. Explicit continued captions remain unresolved.

Include every complete registered text block intersecting the closed table band;
crossing blocks invalidate the proposal. Require at least two member blocks and
four numeric tokens. This conservative grammar does not support every table style.
Proposals preserve whole source blocks and table header/rows as one protected group,
not assigned cells, row/column relations or scientifically accepted numeric records.

Attach complete explicitly prefixed notes below the closing rule in the same
horizontal span, with a maximum 12-point gap between blocks. Stop at non-note text.
For body star/dagger markers, every marker must have a matching note-line definition
inside the group; missing definitions keep the table unresolved. Other superscript
or unmarked note conventions are not universally recognized. Keep provenance and
diagnostics; never invent missing note text or continue onto another page silently.

Retain stage10 grouping and source-quality diagnostics. A long prose block starting
with a Table/Figure reference followed by shows/presents/lists/summarises (or listed
Russian equivalents) may be protected as a whole reference paragraph when no
caption punctuation is present. This is an explicit lexical proposal, not a caption
or a new table. No document IDs, expected labels or historical answers drive rules.

Protect every proposed group and exact member ranges, plus unchanged query/condition/
neighbor selection. Structural risks outside protected blocks retain the wide
fallback. Do not repair source text, drop unknown data to pass scope checks, alter
the complete-page guard, or claim figure content was extracted from images.

Generate separate four-case HTML/JSON with full sources, rule/table/member/bbox
evidence, unresolved cases and existing adequacy/scope checks. Render actual table
proposals with overlays and inspect headers, numeric rows and notes. Keep stage10
and earlier outputs unchanged; verify compatibility, all exact source slices and
frozen hashes after replay. No new model answers or token/cost/accuracy measures.
