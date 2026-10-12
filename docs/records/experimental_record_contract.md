# Experimental Li-Nafion record contract v0.1

Status: development proposal, 9 October 2026. This module is separate from production ingestion, retrieval, `structured_facts`, and numeric review. It does not provide extraction, scientific admission, a human decision store, or an interactive review UI. An offline review worksheet generator is available; it leaves decisions blank.

## Scope and user decisions

The first pilot concerns conductivity of the lithium form of Nafion. Preserve the author's property name. An author claim of Li-ion conductivity remains separate from independent confirmation. The user selected sample identity, temperature, medium composition, and method as mandatory conditions for the first comparative table; incomplete proposals remain on review.

`readiness.py` checks whether corresponding observations and linkage proposals are present. It also requires material form, property, value, unit, composition basis, and sample/property/conditions linkage proposals as technical prerequisites. These additional checks make the selected conditions interpretable; their presence does not prove their scientific correctness. Every candidate remains `needs_review`, even when all prerequisites are present. `li_ion_confirmation` is restricted to `not_reviewed`. No accepted-record state exists in this version.

## Source representation

`SourceRegion` records article UUID, original PDF path and SHA-256, physical PDF page number (1-based), recorded text layer UUID/type, layer PDF path and SHA-256, complete stored page text, page text SHA-256, region boundaries, exact fragment, and fragment SHA-256. The selected layer is read from the stored `Page`; the adapter does not run text quality selection again. Explicit original/OCR access is also supported.

For selected access, `Page.text` must equal the recorded `PageTextLayer.text`. Both registered PDF paths must resolve inside the existing allowed document roots. The original's observed SHA-256 must match the article checksum. The text layer's source PDF must be the registered article PDF for that layer. OCR PDF bytes receive their own snapshot hash; this hash is checked again during live validation. Original PDFs are only read.

The source is **stored page text**. Page records have no paragraph/table `source_type`; the adapter does not infer one from overlapping chunks. Chunk range, bounding boxes, table cells, figure coordinates, section semantics, and work grouping are not inferred. Multi-page evidence uses separate regions.

`start` and `end` use zero-based Unicode codepoints, with an exclusive end. They are not UTF-8 byte offsets, JavaScript UTF-16 offsets, PDF coordinates, or character positions in a normalized string. Preserve ligatures, whitespace, line breaks, exponent signs, units, and spelling. `EvidenceSpan` boundaries are relative to the region's fragment, not the complete page. Repeated identical quotes at different page offsets have different region IDs.

`region_id` hashes article identity, original hash, page number, text layer UUID/type, layer PDF hash, page text hash, and region boundaries. Paths and selection labels are excluded from this content identity; live validation also compares the resolved paths. Selection basis and its note remain explicit: `manual_development`, `expert_oracle`, `fixed_page`, or `retrieval`. The label records the producer's declared selection method, not an independently verified experiment design.

## Candidate representation

Observations use `present`, `not_found_in_context`, `ambiguous`, or `unsupported`. A present observation requires raw text and exact evidence containing that text. Non-present observations require a diagnostic note and cannot assert a raw value. They may cite ambiguity/context evidence. `not_reported` is deliberately absent: this adapter does not document exhaustive article review.

The quantity preserves raw value and raw unit separately, with proposed `scalar`, `range`, `bound`, or `unparsed` representation. Approximation and uncertainty have separate observations. Numeric parsing, inequality interpretation, conversions, tolerances, component fractions, and temperature normalization are not implemented. A raw temperature range must not be silently paired with conductivity endpoints. `room temperature` stays literal.

Sample, material form, preparation, author's property name, temperature, medium, medium composition, composition basis, conditioning, method, origin, and author's Li-ion claim are distinct observations. Work-group identity is optional and unverified. Linkage proposals cite exact fragments with a role and diagnostic note. A quote's existence cannot establish sample/value/conditions linkage by itself.

The bundle verifies unique region/record IDs, region checksums, exact substring boundaries, article membership, and every field/linkage evidence reference. Empty `records` means context export only; it is not automatically a verified negative label.

The exported [JSON Schema](li_nafion_candidate_v0.1.schema.json) describes structure. The Python validator is required for hashes, exact substring matches and cross-reference checks: a generic JSON Schema validator cannot perform these checks.

## CLI

From the repository root, using the existing environment:

```powershell
.\.venv\Scripts\python.exe -m app.records.cli --help
.\.venv\Scripts\python.exe -m app.records.cli source `
  --article-id aec95165-f993-4576-9dba-0ec4bb8ecee1 --page 1 `
  --selection-basis manual_development `
  --selection-note 'Development context only; not scientific gold.' `
  --output data/experiments/records/sources/new_page_export.json
.\.venv\Scripts\python.exe -m app.records.cli validate `
  data/experiments/records/development/sanginov2021_abstract_candidate_v01.json --live
.\.venv\Scripts\python.exe -m app.records.cli manifest `
  data/experiments/records/development/sanginov2021_abstract_candidate_v01.json `
  --operation manual_candidate --source-root . `
  --output data/experiments/records/development/new_manifest.json
```

`source` and live `validate` start a PostgreSQL read-only transaction. They do not commit records or annotations. `schema`, offline `validate`, and `manifest` need no database connection. Writes use exclusive creation and refuse overwriting any existing output. Failures propagate with their exception and diagnostic; a failed command does not become an empty successful result.

`source-pages --article-id UUID --pages 3 8 11 12 ...` exports distinct complete page regions in the declared order, without concatenating text. It rejects empty/non-positive/duplicate scopes. A missing or inconsistent page fails the batch before bundle output is written; it does not silently produce partial context. Full-page batches do not support arbitrary cell/coordinate inference.

`review-packet INPUT --output NEW.md` renders a validated candidate/context bundle as an offline worksheet. It includes field-level citations and blank reviewer decisions; source/context packets without candidates remain explicitly unlabeled. It neither verifies current sources unless you separately run live validation, nor persists decisions, calculates accuracy, or creates independent gold. Use candidate-filled packets for review, and original source/context without those answers for blinded annotation.

Offline validation checks the serialized text/evidence contract. `--live` additionally compares the recorded layer, stored page text, PDF bytes, and resolved paths to the local corpus. It verifies the explicitly recorded layer, not whether a later ingestion run still selects that layer as best. It does not re-extract text from the PDF or validate OCR accuracy.

## Manifest

`manifest` validates the same artifact bytes it hashes. It records bundle run ID, producer, declared operation, artifact path/hash/size, schema version/hash, current `app/**/*.py` and `pyproject.toml` hashes, code fingerprint, Python/platform, selected dependency versions, and source region IDs. It never reads `.env` or includes keys or PDF bytes.

The manifest identifies current code at capture time, not the code of an unrecorded earlier extraction. It is not a complete dependency lock or an offline package. It does not bundle the corpus, detect malicious manifest modification, or assert scientific correctness. Use the S01 baseline for a source/runtime snapshot and live validation for source availability.

## Next implementation boundaries

Before scientific admission: identify samples and compositions in methods/results, review accepted representations and linkage rules, establish work grouping and independent gold, and add a separate human decision/revision model. Local model runs, table adapters, extractor, evaluation, export and review UI remain subsequent tasks.
