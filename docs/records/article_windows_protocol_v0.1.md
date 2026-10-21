# Whole-article bounded context plan v0.1

21 October 2026. Development continuation of records stage18.

## Scope and purpose

Use exactly the three frozen stage18 tasks (four source PDFs, including a
proposed supplement), not top-k retrieval or only earlier oracle fragments.
This stage builds and executes the offline context planner. It does not run a
model or claim article-wide record extraction/recall. The existing model reply
allows at most one measurement per request; using it as an exhaustive article
extractor would leave an unmeasured omission risk. Multi-record generation and
its live-run budget must be frozen separately after reviewing this plan.

Verify the stage18 manifest, code/input/output hashes, task declarations,
source-only bundles, every original/selected PDF and original PDF page count.
Require all declared page/source identities to match the unchanged inventory.
Never overwrite outputs. Preserve complete source text alongside planned slices.

## Deterministic context algorithm

Read the exact registered selected PDF with the existing block reader. Both
plain page text and the complete ordered block concatenation must equal the
saved selected page text. No fuzzy alignment, text repair, OCR, new ingestion,
numeric normalization, chunk/scoring/schema changes or bibliography deletion.
Missing text/pages or unproven geometry are retained as explicit deferred pages.

Reuse source-bound layout proposals and closed ruled tables v0.2. A protected
group is the full contiguous source interval enclosing its member blocks,
including intervening blocks and its already-declared context blocks. Merge
overlapping group intervals; never divide such a group. Outside these groups,
each whole text block is a core unit. Every block belongs to exactly one core
unit, including headers, bibliography, methods and no-keyword passages.

Unresolved caption/table/footnote/numeric-layout/damaged-text risks outside
protected groups defer the entire page; do not split that page to evade risk.
Source graphics remain separately registered with exact hashes, lines and
coordinates. Their scientific role, missing information and OCR completeness
remain unknown. Protected text tables do not establish cell semantics or
complete graphical evidence.

For each core unit retain one complete neighboring block on each side, expanding
to include any intersecting protected group in full until stable. Preserve this
as one exact contiguous source slice, never synthetic concatenation. A slice
larger than 6000 Unicode characters is deferred, not clipped. This explicit
development context ceiling is not a scientific threshold or token budget.

Apply the existing full-page guard to decoded plain context and its JSON user
message. A context containing a complete verified source page is deferred.
Cross-page dependencies remain unresolved, especially first/last blocks; do not
declare that a short context contains every relevant sample/condition/method.
No proposed context is automatically transmission-approved or scientifically
accepted. Text windows and graphical-source diagnostics remain separate.

## Audit and outputs

Record a denominator for every task, document, page, block and core unit. Block
accounting covers exactly the registered page text or defers the whole page.
Neighbor overlap does not create additional measurements. Retain exact repeated
context identities/linked core units; identical text across different documents
does not establish duplicated experiments. Record citation/prior-work and
unmeasurable/failed-measurement lexical cues with exact source spans, without
classifying their scientific meaning or removing them.

Export source-only context bundles, per-page mappings/risks/protected groups,
source graphics, all deferred cases, JSON manifests and searchable HTML with
full source text and working local original-PDF/page links. Preserve algorithm,
policy, input snapshot, runtime versions and dependency code hashes. Recheck all
inputs, PDFs and code after planning. Repeated exports must match byte-for-byte.

Use constructed regression cases for group boundaries, oversized units,
full-page guards, missing/foreign/tampered sources and exact coverage. Inspect
real source layouts for at least a prose window, protected table and a deferred
case. Software checks, visual inspection and independent scientific evaluation
must remain distinct. No independent annotations, human time or accepted
scientific records are manufactured.
