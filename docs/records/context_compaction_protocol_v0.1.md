# Stage08: conservative source context compaction

Development-only algorithm `source_page_compaction_v0.1`. Scope: the four frozen
stage07 questions, selected evidence and registered source pages. No new retrieval,
database operation, query/model tuning, annotation revision, or inference. Freeze
input, source and algorithm hashes in the output manifest before compaction.

This stage removes proven identical page occurrences within each question and
proposes exclusion of bibliography using an explicit standalone reference heading
or a deliberately narrow consecutive numbered-reference grammar. The latter
requires at least three consecutive entries, each with `//` and a publication
year, with no unexplained body prefix (prefix at most 20% of the page). These
are algorithm proposals, not scientific or human-confirmed labels. Ambiguous
numbered text, other reference styles and unproven page alignment are retained
with diagnostics. No source document ID, expected DOI, question label, previous
answer, or model judgment participates in the exclusion rule.

Page alignment permits only trimming page-edge whitespace and whitespace between
pages. Retained text is an exact contiguous slice of the original chunk and page
layer. Record both half-open Unicode character ranges, layer ID/type, article,
original PDF path/hash and page. New development citation IDs cannot be substituted
into historical stage07 answers. Preserve original chunks, pages, source type,
damaged formulas, captions, conditions and footnotes on retained pages. Reference
exclusion may still be mistaken; expose every omission and source for review.

This conservative stage does not implement question-specific sentence windows.
Do not cut a page arbitrarily to satisfy the page-text transmission restriction.
Before any future call, the optional development-provider scope guard checks the
actual formatted user message for complete registered page text, using the
existing whitespace formatter. A positive match fails before request transmission
and creation of a provider attempt directory. Missing source-page registry also
fails when the guard is enabled. Stage07 provider defaults remain unchanged.

Recompute the existing adequacy diagnostic on the candidate context with the same
cross-lingual concept terms, separately from this transmission guard. Neither
adequacy nor scope acceptance establishes scientific entailment. Report context
characters and UTF-8 request bytes, retained/omitted page counts and source
coordinates. Do not estimate token savings from characters or claim improved
answer accuracy without new measurements. A blocked candidate has no new model
answer, usage or answer quality comparison.

Produce a separate local searchable HTML and JSON comparison of all four cases,
full before/after evidence, omissions, gate diagnostics and original-PDF links.
Validate exact source slices and current PDF hashes; verify stage07 frozen input
hashes again after replay. This is offline replay, not a fresh end-to-end retrieval
or a database snapshot check. No external calls or paid tokens are permitted in
this stage. A later narrower context algorithm needs its own declared version.
