# Stage 3: changed-candidate review, 2026-09-08

## Changed

Created a complete review queue for the previous typography diff: **614 candidate
changes** (330 additions, 284 removals). The queue verifies current extractor hash,
diff identity, exact stored chunk text, candidate article/chunk IDs and original
PDF checksums. Each entry includes source metadata, page range, selected text
layer, chunk hash and all literal occurrences with context. Repeated lexemes are
explicitly not treated as unique attribution to one measurement.

Added `scripts/stage3_numeric_change_review.py` and
`docs/numeric_change_review.json`. Five targeted decisions are annotated after
visual PDF review. Annotations bind to the exact diff hash and retain exact
page-layer fragments and their hashes. An unreviewed candidate cannot acquire
approval merely because its lexeme is present in source text. Stale diffs or
extractor code cause explicit failure before database access.

Production extraction was **not changed** in this audit. No facts were refreshed,
no database writes were performed, and original PDFs were read only.

## Visually reviewed decisions

| Source | Change | Decision |
| --- | --- | --- |
| Sanginov 2021, PDF p. 1, abstract | Adds `−9 S cm −1` as conductivity −9 | **Blocker:** printed electronic conductivity is approximately 10⁻⁹ S/cm at 25 °C. The exponent suffix was read as a signed value. |
| Istomina 2021, PDF p. 9, prose above Figure 6 | Adds `18 ◦C` as temperature 18 | **Blocker:** source says 212 ± 18 °C; 18 is the uncertainty, not an independent temperature. |
| Doi 2018, PDF p. 4 / printed p. 3 | Adds `783 cm` as length 783 | **Blocker:** this is a Raman band at 783 cm⁻¹. The ASCII inverse-unit suffix was dropped. |
| Istomina 2021, PDF p. 5, section 3.1 | Adds `16 ◦C` as positive temperature | **Blocker:** source prints the eutectic temperature as —16 °C. The candidate discards the dash/sign. |
| Doi 2018, PDF p. 3 / printed p. 2, header | Removes `00036K` as temperature | **Acceptable removal:** this string belongs to DOI `10.1039/C8SE00036K`, not a Kelvin measurement. |

Five original pages were rendered and inspected: Sanginov p. 1; Istomina pp. 5
and 9; Doi pp. 3 and 4. Review images are in `tmp/pdfs/stage3_review/`.
Poppler emitted `No display font for 'Symbol'` and `No display font for
'ArialUnicode'` for the Doi render. The relevant numeric text and DOI header were
legible, but the rendering warnings are retained as a limitation.

These are assistant PDF-reviewed development labels, not independent scientific
review. Statements cited by the papers were not checked against their original
underlying experiments.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_change_review --diff data/exports/stage3_typography_corpus_diff_20260908.json --output data/exports/stage3_numeric_change_review_20260908.json --check
.\.venv\Scripts\python.exe -m ruff check scripts/stage3_numeric_change_review.py tests/unit/test_numeric_change_review.py
.\.venv\Scripts\python.exe -m pytest tests/unit/test_numeric_change_review.py tests/unit/test_structured_facts.py -q -p no:cacheprovider --basetemp=tmp/numeric_review_tests_20260908
```

- Review queue: **4 blockers, 1 acceptable removal, 609 unreviewed**.
  `bulk_refresh_ready=false`; `--check` returned **1**, as required.
- Source identity and original-file integrity checks completed without errors.
- Focused tests: **26 passed**, including stale-diff and stale-extractor refusal.
- Ruff passed. Full suite was not rerun for this audit-only addition.

The review command is an audit gate, **not an enforcement hook** in the existing
refresh/apply CLI. Its readiness flag reflects the supplied annotations, not
independent scientific acceptance. Updating source code requires a new diff and
review labels; prior reviewed outcomes must not be silently reused.

## Limitations

All 614 changes have traceable queue entries; only five received visual scientific
review in this step. No general precision or recall is inferred from this targeted
sample. No unreviewed removal is automatically classified as an improvement, and
no new scalar is automatically called a valid measurement. The current extractor
still exposes the four demonstrated blockers until a subsequent fix is implemented.
Their presence alone is sufficient to reject bulk refresh; exhaustive approval of
the remaining 609 candidates is not claimed.

## Verdict and next patch

**Do not bulk-refresh persisted facts with the present extractor.** The typography
patch's software tests and improved target coverage did not establish scientific
correctness on the wider corpus.

Next fix should prevent partial bare powers of ten and incomplete inverse units
from becoming scalars, and refuse uncertainty operands and ambiguous dash signs
until their structure is represented. Add regressions from the verified source
fragments and preserve valid ordinary negative temperatures and complete
coefficient-times-ten notation. Then regenerate the corpus diff, rerun the fixed
numeric baseline and review affected candidate changes before considering apply.
