# Stage 3: reviewed glyph and compound-unit guards, 2026-09-09

## Changed

The extractor now rejects the three false candidates identified in the cap review:
U+F0B1 uncertainty operands, literal escaped `\u0001` or U+0001 unit suffixes,
and mass prefixes of `g Ah⁻¹`/`mg mAh⁻¹`. No glyph is globally normalized or
assigned an invented numeric meaning. Exact source text remains unchanged.
The capacity denominator exponent also cannot be rescued as a new signed
measurement in text such as `2.4 g Ah−1. g,h, ...`.

Added exact PDF-reviewed fragment regressions, synthetic boundary cases and
positive mass/length/conductivity controls. Extended the read-only source audit
with `--include-cap-review`; its default still checks the original four cases.
It now permits terminal CR/LF trimming for chunk membership only: full page text
and its checksum still have to match the reviewed fragment exactly. The first
seven-case replay stopped on Choi's terminal newline; inspection confirmed that
the page fragment ends in LF while the stored chunk does not. The revised replay
passed without weakening the page-source check.

Production cap remains 12. Database facts, original PDFs, confidence values,
unit conversion and schemas were not changed. Historical review labels were
preserved; a separate empty annotation set binds to the regenerated diff.

Final extractor SHA256:
`9953b6903a265a4520f6dd66c5562d70b51122b1c3200a795bef03a08ddfbb1a`.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/numeric_glyph_final_tests_20260909
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_guard_audit --include-cap-review --output data/exports/stage3_numeric_glyph_sources_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_audit --output data/exports/stage3_numeric_glyph_baseline_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_typography_compare --baseline-ref 4656690 --output data/exports/stage3_numeric_glyph_corpus_diff_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_change_review --diff data/exports/stage3_numeric_glyph_corpus_diff_20260909.json --labels docs/numeric_glyph_change_review.json --output data/exports/stage3_numeric_glyph_change_review_20260909.json --check
```

- **506 passed**, one Starlette/httpx deprecation warning.
- Ruff passed; mypy passed on 71 source files.
- Live source replay: **7/7 false candidates rejected**, including the preceding
  four blockers. Stored page fragments and original PDF checksums verified.
- Fixed target detection remains **5/10**, not overall extraction precision/recall.
- Across **619 chunks**, the Git-baseline diff has 276 changed chunks,
  **570 removals, 369 additions**. It includes earlier uncommitted extraction work.
- Relative to the preceding guard checkpoint: **62 removals, 17 additions**;
  candidate identity delta saved in
  `data/exports/stage3_numeric_glyph_patch_delta_20260909.json`.
- Cap diagnostic still flags three candidates; no cap change was made.
- Fresh queue: **939 unreviewed**, `bulk_refresh_ready=false`; review `--check`
  returned **1**, as required. Zero annotated blockers in this new empty queue
  must not be interpreted as zero scientific errors.

## Limitations

No new visual PDF review was performed; the seven source replays use historical
assistant-reviewed fragments. The changes reject known malformed structures;
they do not implement general unit parsing, uncertainty, bounds or ranges.

Inspection of the newly exposed candidate contexts found figure-reference forms
such as `Fig. 2g`/`Fig. 5k` becoming candidates and a compound deformation-rate
unit `10 mm min` followed by an encoded inverse suffix being truncated. Those
remain unresolved. An intermediate diff also exposed `−1. g` from the capacity
denominator; that in-scope failure was fixed and covered before the final run.

The 17 newly exposed candidates are not automatically accepted. The full new
diff still needs scientific review; original annotations are not reused as new
approvals. Occurrence provenance and cap omissions remain separate work.

## Verdict

The three reviewed error forms are blocked, including denominator-suffix rescue.
**Do not bulk-refresh facts.** Next: reject figure-reference numeric matches and
the verified compound rate-unit pattern with source-backed regression cases,
then expose accepted/rejected occurrences and cap omissions for review. Do not
increase the cap merely to restore identical lexemes.
