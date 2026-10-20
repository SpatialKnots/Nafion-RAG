# Stage09: source-bound block windows

Declared development algorithm: `source_block_windows_v0.1`. Offline replay of
the same four stage07 inputs after unchanged `source_page_compaction_v0.1`.
No inference, new retrieval, scientific labels, question changes or production
activation. Freeze input/code/selected-layer file hashes before selection. Earlier
stage07/08 artifacts remain immutable. This stage tests source-bound windows;
it does not promise transmission eligibility or scientific acceptance.

Use complete PDF text blocks rather than splitting sentences at ambiguous decimal
points, initials, abbreviations and broken line wraps. Read the registered selected
PDF layer only. Its current checksum is recorded, and PyMuPDF plain text plus the
concatenation of text blocks must equal the frozen registered page text exactly.
Unproven geometry, partial nonwhitespace block boundaries or missing maps retain
the entire prepass fragment with an explicit diagnostic. No fuzzy matching, OCR,
new extraction storage, character repair, reconstruction or normalization.

Query anchors are the existing frozen evidence-selection distinctive terms.
Select at most two anchor blocks per page by distinct matched-term count, breaking
ties in original text order. Additionally retain every block matching the declared
measurement/condition/definition heuristic, irrespective of anchor rank. Retain
one adjacent block on either side of each selected block. Merge only adjacent
selected blocks into exact contiguous slices; never concatenate separated source
passages into one evidence item. Record every block's reasons, selections and
omissions. No anchor and no condition match is an unknown/unselected passage,
not evidence of topic absence. This is lexical candidate selection, not semantic
entailment or independently measured recall.

Preserve the whole prepass fragment if a standalone table/figure caption occurs,
six or more short lines are numeric-dominant, or control/replacement/private-use
characters indicate unresolved formula/text geometry. The numeric heuristic counts
nonempty lines up to fifty characters with digits comprising at least half of
alphanumeric characters. This deliberately broad structural protection preserves
headers, rows, captions and footnotes together while their boundaries are unknown.
Do not trim such a page merely to evade the existing complete-page guard.

The condition heuristic covers numerical physical units, measurement/preparation
and equilibrium terms, sample/weight definitions and uncertainty cues in English
and Russian. Its full versioned regex lives in source. Retaining matching blocks
does not prove all conditions are recognized or every scientific relation is intact.
Page-spanning paragraph/table relations and unavailable adjacent pages remain
unresolved; expose diagnostics and do not claim automatic scientific acceptance.

Every output has a new `W` citation ID and exact half-open Unicode coordinates in
the original chunk and registered page, with article, PDF hash/path, page, selected
layer ID/type, fragment checksum and input/prepass IDs. Preserve original source
type and text verbatim. Do not rebind historical answers to the new evidence IDs.

Recompute unchanged adequacy and complete-page diagnostics on the actual candidate
user message. Scope rejection and scientific adequacy remain independent. No new
model answers, token or cost savings are measured. Generate a separate searchable
four-case HTML/JSON showing prepass/window text, original full source, every omitted
block and reason, exact coordinates, structural fallbacks and original PDF links.
Validate source slices and hashes again after replay. Existing output directories
must be refused. Record failures rather than repairing the frozen run in place.
