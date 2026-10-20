# Stage10: protected caption and note groups

Development algorithm `source_layout_groups_v0.1`, opt-in offline replay of the
four unchanged stage07 cases after the unchanged stage08 prepass. No inference,
fresh retrieval, production activation or scientific acceptance. Freeze the
protocol, inputs, selected PDF hashes and code before selection. Keep stages08/09
outputs and default algorithms unchanged.

Use the exact registered PDF text-block geometry established in stage09. Validate
page identity/checksum, complete character coverage, and finite positive block
rectangles before proposing any protection. Unproven geometry supplies no override.

Distinguish a caption marker inside an existing prose block from a separate caption
block. A marker after nonwhitespace text within a prose block protects that whole
block as a reference proposal only when the prefix is an unfinished sentence and
the marker lacks standalone caption punctuation; otherwise it remains ambiguous.
Standalone captions require a block-start Table/Figure/Fig./Таблица/Табл./Рис.
label, number and punctuation. Unknown caption styles retain old protection.

For a separate caption, find the nearest complete prose paragraph above and below
it in the same column. Prose barriers have at least 25 alphabetic words, terminal
sentence punctuation, no caption label or damaged characters, and no explicit
footnote prefix. Column overlap is at least half the narrower block width. The
bounding paragraphs must overlap horizontally and bracket the caption vertically.
Take every intervening text block in that column, including numeric rows, labels,
captions and note blocks, plus both complete bounding paragraphs as context.
Require their rectangles to lie inside the enclosure, allowing 3 PDF points of
edge tolerance; reject crossing blocks and intervening prose as ambiguous. Merge
only identical groups; keep independent proposals separate.

Footnotes explicitly starting with *, dagger/double dagger, Note/Notes/Примечание
or a letter-and-parenthesis marker cannot be prose barriers. This is incomplete
note recognition, not a universal table or figure parser. Unmarked/complex notes,
cross-column and cross-page relations remain limitations. Open enclosures do not
override broad stage09 fallbacks. Explicit continued/continuation/продолжение/
окончание captions also retain the old fallback. Visual content is not serialized
or interpreted.

Retain every proposed group's whole member blocks, including bounding paragraphs,
regardless of query rank, plus the unchanged stage09 anchor/condition/neighbor
selection. Assess unresolved structural risks on the remaining text only. Six
numeric-dominant short lines, formula damage or ambiguous captions outside the
protected blocks still retain the full prepass fragment. Never repair source text,
reconstruct table cells, reorder columns, clip characters, or remove page material
just to pass the existing transmission scope guard.

Output new exact W windows with original chunk/page/layer/PDF provenance; persist
every group/member/rectangle/range, reference proposal, unresolved boundary and
omission. Group recognition is algorithmic, not scientific or human confirmation.
Recompute existing adequacy and complete-page checks on the formatted candidate.
No new answer, token/cost saving or independent accuracy is measured.

Produce a separate four-case HTML/JSON comparison, full source and local PDF links.
Render representative proposed groups over the original page for visual audit;
save annotations only as diagnostic images, never into source PDFs. Verify source
slices and all frozen file hashes again after replay and test default stages08/09
compatibility. Do not repair a frozen run in place if an audit exposes a failure.
