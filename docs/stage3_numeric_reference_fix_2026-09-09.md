# Stage 3: figure-reference and rate guards, 2026-09-09

## Changed

Reject compact figure-panel tokens such as `Fig. 2g`, `Figure 5g`, `Fig. 5k`
and simple reference lists as numeric mass/temperature candidates. The rule
requires an explicit English/Russian figure cue; ordinary compact `5g` and `5K`
measurements remain recognized. A later valid identical lexeme is still eligible.

Reject per-time suffixes `min`, `s`, `h` with inverse exponent forms, including
the stored escaped control glyph in `10 mm min\u00011`. These are unsupported
rates, not scalar numerator units. Their signed exponent cannot become a new
measurement after punctuation. No source text is normalized or rewritten.

Visually checked Dai PDF p. 3 (printed p. 58, section 2.6: 10 mm min⁻¹ deformation
rate) and Yu PDF p. 7 (printed p. 100: Fig. 5g and Fig. 5k). Three exact source
regressions are in `numeric_reference_cases.json`. Extended the source audit with
`--additional-labels`, validating nonempty reviewed false-addition cases and unique
case IDs. Its report includes the additional fixture hash.

Production cap remains 12. Database facts, original PDFs, schemas, confidence,
source identifiers and unit conversion remain unchanged.

Final extractor SHA256:
`8742647bed82b96ce39e1ce52c0604e495311896daea32cb59e4b6d0cbc015ca`.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/numeric_reference_full_tests_20260909
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_guard_audit --include-cap-review --additional-labels docs/numeric_reference_cases.json --output data/exports/stage3_numeric_reference_sources_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_audit --output data/exports/stage3_numeric_reference_baseline_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_typography_compare --baseline-ref 4656690 --output data/exports/stage3_numeric_reference_corpus_diff_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_change_review --diff data/exports/stage3_numeric_reference_corpus_diff_20260909.json --labels docs/numeric_reference_change_review.json --output data/exports/stage3_numeric_reference_change_review_20260909.json --check
```

- **523 passed**, one Starlette/httpx deprecation warning. Ruff and mypy passed.
- Live source replay: **10/10 false candidates rejected**; exact page fragments
  and original PDF checksums verified.
- Fixed target detection: **5/10**, unchanged; not general precision/recall.
- Across **619 chunks**, Git-baseline diff: 285 changed chunks,
  **607 removals, 374 additions**. Includes preceding uncommitted extraction work.
- Relative to the glyph-fix checkpoint: **43 removals, 11 additions**. Identity
  delta saved as `data/exports/stage3_numeric_reference_patch_delta_20260909.json`.
- New review queue: **981 unreviewed**, `bulk_refresh_ready=false`; `--check`
  exited **1**, as required. No old approval annotations were transplanted.
- Cap diagnostic still reports three displaced candidates.
- `git diff --check` completed; Git warned about configured LF-to-CRLF conversion.

## Limitations

The PDF render reported `Invalid Font Weight` warnings; relevant passages were
legible. Visual labels are assistant review, not independent scientific review.

The figure rule is intentionally scoped to compact g/k panel identifiers with
explicit cues, not a general document-reference parser. The rate rule covers the
listed per-time forms within a line; arbitrary compound units and cross-line
denominators remain unsupported.

Stored contexts of all 11 newly exposed candidates were inspected, including
energy cutoffs, a barrier, figure scales, temperatures and percentages. This is
not new PDF approval or attribution to a specific experiment. General scientific
acceptance of the 981-change diff is still open. An empty annotation queue's zero
blocker count does not indicate zero scientific errors.

## Verdict and next step

The reviewed figure-reference and rate failures are blocked with software and
live-source regressions. **Do not bulk-refresh persisted facts.**

Next implement occurrence diagnostics without changing production selection:
record exact accepted/rejected spans, rejection reason, duplicate handling and
cap omissions. Distinguish a rejected early range endpoint from a later valid
identical lexeme. Preserve chunk and page-layer provenance; do not assign a page
by guess for multi-page chunks. Use these diagnostics to review the new diff and
evaluate selection changes before altering cap or scientific output schemas.
