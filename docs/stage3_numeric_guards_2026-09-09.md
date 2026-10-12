# Stage 3: scalar boundary guards, 2026-09-09

## Changed

Added conservative validation to `app/facts/extraction.py` for the four blockers
identified in the September 8 PDF review. Unsupported bare powers of ten no longer
yield exponent suffixes; uncertainty operands no longer become measurements;
inverse/powered/compound unit suffixes cannot be truncated to supported simple
units; ambiguous en/em dashes and separated signs cannot silently become positive
scalars. Prefix validation also sees preceding lines. Unit suffix validation stays
within the current line, so a separate row with a negative measurement remains valid.

Complete coefficient-times-ten notation, ordinary attached negative signs and
exact source lexemes remain supported. No schema, unit conversion, confidence,
source identifier or 12-fact cap changes were made. Persisted facts and PDFs were
not modified. Existing unrelated working-tree changes were retained.

Added synthetic boundary regressions and exact historical fragment regressions.
Added `scripts/stage3_numeric_guard_audit.py` to replay the four reviewed blockers
against stored chunks, page layers and original PDF checksums. This is source-bound
regression verification, not fresh visual or independent scientific acceptance.

Source baseline: `46566902a4e4e695ac801384fef7b32a9b4d7232`. The typography patch
already existed uncommitted before this task. Its local snapshot was preserved as
`tmp/stage3_extraction_before_guard.py`, SHA256
`4ba6b5143853e955f4a975862cffdef87accb8a845df1665ea8d6bdcb8bc3533`.
Final extractor SHA256:
`cd91db51bfd350f5388c7929ecadac94c1bb93e87627c1c245a5bce0316e9425`.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/numeric_guard_full_tests_20260909
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_guard_audit --output data/exports/stage3_numeric_guard_sources_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_audit --output data/exports/stage3_numeric_guard_baseline_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_typography_compare --baseline-ref 4656690 --output data/exports/stage3_numeric_guard_corpus_diff_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_change_review --diff data/exports/stage3_numeric_guard_corpus_diff_20260909.json --labels docs/numeric_guard_change_review.json --output data/exports/stage3_numeric_guard_change_review_20260909.json --check
```

- Full pytest: **492 passed**, one Starlette/httpx deprecation warning.
- Ruff on `app tests scripts`: passed. Mypy: passed, 71 source files.
- The broader `ruff check .` failed with 47 findings in temporary scripts and
  access-denied warnings under `tmp`; no repository-wide lint success is claimed.
- An intermediate targeted test failed because its expected fixture ID was
  `lost_sign` instead of the actual `dash_sign`; corrected before the full run.
- Source replay: **4/4 rejected**, original PDF checksums and exact stored page
  fragments verified. No new PDF visual review was performed.
- Fixed numeric probes: **5/10**, down from 6/10. The lost target is `17` in
  `7–17%`: a range endpoint is no longer emitted as a standalone measurement.
  The range itself is still unsupported. The complete scientific-notation target
  remains detected. These probes do not measure overall precision or recall.
- Git-baseline diff across **619 chunks**: 269 changed chunks, **517 removals and
  361 additions**. This includes the preceding uncommitted typography patch.
- A local pre-guard comparison (`python -X utf8 -m tmp.numeric_guard_compare`)
  found 147 changed chunks, **259 removals and 57 additions**. The additions fill
  slots freed by rejected candidates; none are automatically scientifically approved.
  Its report is `data/exports/stage3_numeric_guard_patch_diff_20260909.json`.
  The first diagnostic print failed under cp1251 after writing the report; the
  UTF-8 rerun completed successfully.
- Fresh review queue: **878 unreviewed**, `bulk_refresh_ready=false`; `--check`
  returned **1**, as required. Source and original-file checks completed. Historical
  annotations were not copied as approvals into the new diff.

## Limitations

Conservative rejection also removes range endpoints, spaced signs and partial
compound units. This can reduce useful numeric coverage until those structures
have an explicit representation. Cross-line unit suffixes remain unsupported.
Association with material, operator and measurement conditions is still unresolved.

The unchanged cap diagnostic flags three candidates present without the cap but
absent with it: `523 K`, `100 nm` and `1.5%`. Inspection of stored text explains the
movement: the earlier occurrence belongs to `423–523 K`, `20–100 nm` or `1–1.5%`
and is now rejected; a later independent occurrence falls beyond the cap. This is
a remaining coverage limitation, not unexplained new-value displacement. Their
later contexts were inspected as stored text, not newly checked in PDF. Changing
cap/selection policy is a separate decision.

Neither the 57 patch additions nor the complete 878-change queue received new
scientific approval. Review JSON diagnostics preserve this explicitly. The review
command remains an audit gate, not an enforcement hook in the refresh CLI.

## Verdict

The four demonstrated false scalars are blocked, with software regressions and
live source verification. **Do not bulk-refresh persisted facts yet.** Next work:
review the new candidate diff, assess the three cap losses, and design explicit
support for ranges, uncertainty and scientific values before claiming better
scientific coverage. Stage 3 scientific acceptance remains open.
