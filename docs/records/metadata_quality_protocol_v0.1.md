# Metadata quality audit v0.1

Prospective stage36 protocol, 23 October 2026. Evaluation only; the stage35
`registered_tac_metadata_v0.1` / `tac_file_metadata_v0.1` extractor stays unchanged.

## Scope and sequence

Use all articles in the existing 33-document TAC snapshot except the ten articles
in the frozen stage35 applied report: 23 documents, with no outcome-based sampling.
Require current database article identities to match that snapshot. Capture current
registered physical pages 1–2 with exact text/layer IDs and original/selected PDF
hashes before running the extractor on this scope. Keep all missing and unusual
layouts, supplements, duplicates and conference abstracts. Do not infer values
from database titles, filenames, PDF dates, DOI strings or external services.

Freeze protocol, extractor source hashes, input snapshot and source PDFs. Before
viewing new predictions, create source-based reference annotations for every scoped
document and all three fields. References include complete ordered bylines, printed
publication/issue year and printed journal name, with exact selected-text spans.
Inspect original first-page images as well as selected text; inspect page 2 when
needed. Printed issue/citation year takes precedence over online/copyright year.
Journal is not applicable only when the document explicitly identifies a different
publication type. A supplement without an explicit journal/year remains unknown,
even if the parent publication can be guessed. A genuinely ambiguous source may
retain alternatives; do not force one value.

Freeze annotations and evaluation code before predictions. Record annotation
origin as assistant source annotation, created without seeing these new outputs.
This is separate from extractor outputs, NOT an independent human scientific gold
standard. The corpus was already exposed to earlier TAC development; disjointness
from stage35 does not establish an unseen training/development holdout. No human
confirmation, representative corpus accuracy or scientific acceptance is claimed.

## Comparisons fixed before outcomes

For each reference field, use `known`, `unknown`, `ambiguous` or `not_applicable`.
Known authors are the full ordered list, not merely a matching first surname.
Explicit source-supported aliases may be frozen before predictions. Comparison
only collapses whitespace and Unicode case, with NFC normalization; punctuation,
initials, order, missing people and extra people are not silently repaired.
Year requires integer equality. No fuzzy matching, transliteration or post-outcome
alias additions. Exact text evidence validates reference provenance; it alone does
not establish a correct semantic interpretation.

Report per-field known-reference count, correct proposed count, wrong proposed
count, abstentions and wrong status (including inappropriate not-applicable).
Report correct/known coverage and correct/(correct + wrong) among proposals on
known fields, with explicit numerators and denominators. These bounded agreement
metrics are not general precision/recall or independent scientific accuracy.
Report unknown, ambiguous and not-applicable cases separately. A proposal on an
unknown reference is unscored, never an automatic error or success. A proposal
where the reference is not-applicable is a status error. Retain every prediction,
alternative, source quote and diagnostic. Do not mutate database metadata or tune
the extractor during this audit.

## Deliverables and checks

Produce exclusive new directories for capture, reference freeze, predictions and
review; never overwrite prior stages. Bind all files by SHA-256, reject drift and
incomplete/duplicate annotation scope, validate all reference and prediction spans,
and preserve full source text for offline replay. Repeated offline review exports
must be byte-identical. Database access uses a read-only transaction. Compare all
article metadata and metadata-history fingerprints before/after; verify original
and selected PDF hashes. No retrieval, embedding, generation or external metadata
request is needed.

The searchable read-only HTML includes every scoped document and the columns
Title, Authors, Journal, Year, Abstract, Conclusions, Terms, original PDF link.
Show references beside algorithm proposals, field verdicts and full diagnostics.
Historical TAC sections may be reused only with exact current PDF/text/layer
verification and a separately identified historical snapshot. Terms are not newly
computed or confirmed. Keep missing sections and metadata explicit. Inspect the
review in a browser if supported; otherwise record the actual limitation.

Tests cover incomplete references, source/code/reference drift, corrupt spans,
full author-list/order mismatches, abstentions, unknown and not-applicable handling,
escaped HTML, source links and deterministic replay. Run targeted regression and
repository lint/type checks. Broaden testing only if the change affects runtime.
