# Li-Nafion record pilot initialization v0.1

Date: 14 October 2026. Project: ARIADNE. This protocol precedes new record extraction.

## Purpose and scope

Prepare a reproducible source-only corpus for the user-selected Li-Nafion conductivity scenario. The eventual target is 10–15 scientifically eligible publications. A lexical hit is a selection candidate, not an eligible publication or an experimental record. A document without a hit is not a negative scientific label.

Freeze all documents from the declared local profile, including documents without hits, so annotation can inspect missed material and source-selection bias remains visible. Export every stored selected-text page separately, without top-k retrieval, TAC filtering, re-OCR, text repair, chunk changes or conversion of units. Preserve article ID, original PDF path/hash, stored page number, recorded layer ID, layer PDF hash and exact text. Keep empty stored pages and missing original-PDF pages in diagnostics; neither becomes a scientific negative.

The corpus is development-only. Existing articles have already been used during retrieval/TAC/model development; they are not an untouched evaluation set. No random development/test split is declared in this initialization. Independent evaluation will require a separately fixed work-level split and an uncontaminated input set. Same-DOI or same-PDF grouping is a lexical identity diagnostic; related papers, supplements and repeated experiments require separate source evidence. No grouping is silently converted into scientific equivalence.

## Separation of artifacts

1. Source-only packet: all declared documents, complete available selected pages, original PDF links and source-integrity diagnostics. Do not include record proposals, model answers, suggested field labels, lexical highlights or prefilled annotation decisions.
2. Selection audit: versioned lexical profile and candidate IDs, target-size shortfall and all unselected documents. Keep this separate from the source-only view. It does not establish absence or suitability.
3. Protocol and manifest: input/profile/code/schema/source hashes, baseline fingerprint, runtime and artifact inventory. Record all outputs before subsequent extraction. Existing packets must not be overwritten.

The packet contains zero annotations and zero candidate records. Its existence is not independent annotation, a reference dataset or evidence of extractor accuracy. Independent quality annotation remains separate from automatic user workflows, particularly Terms; no per-Term resolution task is introduced.

## Scientific annotation and evaluation contract

Retain the existing `li_nafion_candidate_v0.1` contract and its exact raw-text/evidence requirements. The user-selected mandatory groups are sample identity, conductivity property/value/unit, temperature, medium/composition/basis and measurement method. Preserve origin, preparation, conditioning, approximation and uncertainty separately. Missing information in an inspected context is `not_found_in_context`; it must not be promoted to article-wide `not_reported`.

For each eligible measurement, independently identify the sample, author property wording, raw value and unit, scalar/range/bound representation, original operator/approximation/uncertainty, temperature, medium and composition basis, method and experimental/calculated/reference/unknown origin. Evidence must support both fields and their linkage. Identical values across papers or repeated abstract/table mentions are not automatically independent experiments. General methods must not be transferred to a cited prior-work value. Footnote overrides and empty table cells must remain explicit.

Annotate the entire declared relevant article scope before inspecting system outputs. Record annotator identity, inspected scope, elapsed time, ambiguity and unsupported layouts. For double annotation, preserve both outputs and disagreements before adjudication. No assistant-generated labels are called independent scientific gold; evaluator metadata must distinguish development reference from independently annotated reference.

Define denominators before an extraction run: all eligible reference measurements, all proposed measurements, all unsupported/ambiguous cases and failures. Structural/evidence integrity, field agreement, full-record agreement, linkage/origin errors, omissions and abstentions must be reported separately. Matching a valid JSON schema or a literal quote is not scientific correctness. No accuracy metric is reported while the reference is absent. No new numeric tolerance, unit normalization or acceptance threshold is introduced here.

## Initialization completion

- Source baseline includes current runtime assets as well as Python files; secrets and private corpus data remain excluded from the source package.
- Every profiled document is accounted for; each stored page is exported or explicitly diagnosed.
- Exported regions match live selected sources, original PDFs retain their SHA-256, and repeat exports have identical source identities/text.
- Source-only HTML opens locally and exposes exact complete page text and original files.
- A manifest identifies profile, protocol, baseline, code and output bytes. No annotations, scientific suitability decisions or extraction success are invented.

This stage completes initialization, not S04 scientific annotation, S07 extraction or full block 4. Next: independently establish eligible measurements/work groups, then implement and evaluate a bounded source-region-to-record adapter against development cases. An independent reference cannot be supplied by the same agent that develops the extractor.
