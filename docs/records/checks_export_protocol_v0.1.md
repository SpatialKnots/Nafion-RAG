# Record checks and comparative export v0.1

20 October 2026. Development-only S09/S12 increment. This does not complete the
full-record pilot, persistent decision storage, independent evaluation or offline
extraction acceptance.

## Scope and invariants

Read a declared list of saved `li_nafion_candidate_v0.1` bundles, including empty
bundles. Revalidate their exact evidence contract and verify every original and
selected-layer PDF against its recorded SHA-256 before writing output. This is
file verification, not a fresh database/layer-selection check or PDF text
re-extraction. Do not change candidate schemas, source text, units, ingestion,
retrieval, extraction, scientific metrics or existing completeness policy.

`records_checks_v0.1` emits individual `pass/fail/unknown` checks with rule IDs,
reasons, field names and original evidence spans:

- Required-field presence delegates to `li_nafion_completeness_v0.1`.
- Each expected linkage role must have exactly one proposal. Missing/duplicate
  roles fail this new technical check; old bundle validators are unchanged.
- Every proposed linkage's scientific support remains `unknown`, even when
  its exact quotation and coordinates pass integrity validation.
- Scalar notation recognizes only an ASCII decimal with optional ASCII/Unicode
  sign, optionally followed by `e/E` exponent or multiplication by a power of
  ten. A multiplied power requires a caret, explicit exponent sign or Unicode
  superscript digits. Unmarked `1 × 103` is unsupported rather than repaired to
  `1 × 10−3`. Coefficient/exponent substrings remain exact source strings.
  No numeric conversion, normalization, decimal-comma interpretation, range
  pairing, inequality parsing or unit conversion is performed. Other notation
  and declared non-scalar representations remain `unknown`, not false errors.
- Units, numerical meaning, origin, scientific identity and field/linkage
  entailment are not scientifically validated. They remain `unknown`.

Technical outcome is `incomplete` when any check fails, otherwise `unresolved`.
Every record remains `needs_review`, `li_ion_confirmation=not_reviewed`, and
`scientific_admission=not_evaluated`. No check creates accepted records or
human confirmation. This is an automatic report; there are no Terms decisions
or compulsory per-case user forms.

## Output and reproducibility

The new `scripts.records_table` CLI refuses an existing output directory and
duplicate input paths/bytes. Every declared input is included, even if it has
zero records; an empty bundle is not classified as a correct negative.
It writes exact input-byte copies, `table.json`, `table.csv`, searchable
read-only `review.html`, and a manifest of input/PDF/code/output hashes and
runtime/package versions. JSON retains the complete candidate bundles and
exact evidence. CSV retains raw fields, statuses, run/record/article identities,
technical outcome and a JSON pointer to each record's evidence/checks. CSV
strings that a spreadsheet might interpret as formulas receive a leading
apostrophe; `csv_escaped_columns` declares those columns. Exact strings always
remain in JSON and input copies. CSV is a display export, not a round-trip
candidate serialization.

HTML shows all inputs, full fields/statuses/notes, all checks, all exact source
regions and PDF page links. Text is escaped, whitespace is preserved, and
scientific limitations remain visible. No external scripts/services are used.
Metadata absent from the candidate contract is not invented.

Validate all inputs/PDFs and render outputs before creating the output directory.
Integrity/file failures propagate; they must not become empty successful rows.
Output write failures propagate and may leave a visibly incomplete directory.
No API/model/database call is made. Originals and historical artifacts are read
only. Input copies preserve historical extraction context; the current manifest
identifies export/check code, not the historical extraction runtime.

## Planned checks and development replay

Use constructed counterexamples for exact numbers/signs, ambiguous notation,
wrong semantic linkage despite exact evidence, missing/duplicate roles, unsafe
HTML/CSV, source tampering, empty bundles, repeated inputs and overwrite refusal.
Replay all four saved stage06 candidate bundles in declared order: Abstract,
table, cited result, bibliography. Freeze their bytes before replay. These are
exposed development cases, not independent gold or whole-article recall.
Compare repeated exports and verify original input/PDF hashes after running.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_table --help
# Pass every declared bundle, including a zero-record context, to a fresh path:
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_table --inputs PATH1 PATH2 --output-dir output/records_table_new
```

Persistent edits/decisions, automatic whole-article enumeration, cell
reconstruction, independent annotation, scientific acceptance and installation
on a second machine remain separate steps.
