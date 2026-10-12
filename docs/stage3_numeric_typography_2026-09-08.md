# Stage 3: numeric typography, 2026-09-08

## Changed

Error class: `typographic_numeric_unit_tokens`. The source-backed baseline missed
`2 × 10 −4 S cm −1` in Sanginov 2021, PDF page 9, and `80 ◦C` in Istomina 2021,
PDF page 7. Implemented matching for Unicode minus, superscript exponents in
coefficient-times-ten notation, middle-dot multiplication and the alternate degree
glyph. Normalization applies only to parsed numeric/unit fields;
`field_value_text` preserves the exact matched source text.

Added guards against extracting suffixes of unsupported/malformed scientific
numbers, identifiers and compound units. For example, unsupported `10-9 S/cm`
must not become a conductivity of −9, and `2.8 nm/min` must not become a length
of 2.8 nm. This does not implement every scientific-number or compound-unit syntax.
Existing recognized additive notation and diameter markers have regression tests.

The cap remains **12 facts per chunk**. An initial whole-corpus comparison found
13 existing values displaced by new matches in seven chunks. The final selection
uses the previous recognizer only to prioritize existing recognition slots;
new candidates fill spare slots. Corrected full-number matches may replace old
partial matches. Output remains in source order. The old recognizer cannot authorize
a match rejected by the new one. This explicit selection change prevents losses
caused solely by adding new typographic matches under the unchanged cap.

No original PDF, stored text, table layout, database schema, unit scale or confidence
threshold changed. `mS/cm` remains mS/cm, not S/cm. Source identifier
`rule_based_numeric_v1` is retained for the existing refresh lifecycle; audit
reports include extractor hashes to distinguish implementations. No refresh/apply
of persisted `structured_facts` was performed.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_audit --output data/exports/stage3_typography_after_20260908.json --check
.\.venv\Scripts\python.exe -m scripts.stage3_typography_compare --baseline-ref 4656690 --output data/exports/stage3_typography_corpus_diff_20260908.json
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/numeric_typography_final_tests_20260908
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
```

- Final full suite: **457 passed**, one existing Starlette/httpx deprecation warning.
- Ruff passed; mypy passed on 71 source files. The added corpus comparison script
  was also linted and executed after the final suite.
- The same fixed PDF fixture was run before editing production code:
  `data/exports/stage3_typography_before_20260908.json`.
- Numeric target detection: **4/10 → 6/10**; all targets detected within a probe:
  **3/8 → 4/8**. No previously detected target disappeared from this fixture.
- Audit source hashes and exact stored fragments verified successfully. Both
  before and after `--check` returned **1**: missing values and unrepresented
  scientific context remain.

The new detections are approximately 0.0002 S/cm and 80 °C. The latter is only
the upper endpoint of the source's 40–80 °C interval; it is not a complete range.
The two table conductivities, lower endpoint 40 °C, and crystallinity lower
endpoint 7% remain missing. Operators/materials/conditions remain absent from the
candidate structure in all eight probes.

## Whole-corpus compatibility audit

Added `scripts/stage3_typography_compare.py`, which executes extraction code from
an explicitly selected trusted local git revision on the same stored chunks and
compares it with the working implementation. It records the resolved commit and
both code hashes. The uncapped run is an in-memory diagnostic and restores the
production cap immediately; it does not persist facts.

Against `46566902a4e4e695ac801384fef7b32a9b4d7232`, across **619 chunks**:

- 186 chunks changed candidate sets;
- 284 prior candidate tuples removed; 330 added;
- **zero** prior still-recognizable tuples displaced by the cap.

These are changes in candidate tuples, not corrected-scientific-fact counts.
Inspected removal examples include DOI suffixes read as Kelvin, partial powers of
ten read as negative conductivities, rates read as lengths or temperatures, and
ratios read as masses. The full set of changed candidates has **not** received
scientific review. No corpus-wide precision or absence of scientific regressions
is claimed. The report retains source text for that follow-up review.

## Limitations

The measured improvement is targeted development coverage, not general accuracy.
Guards may conservatively omit ambiguous or unsupported notation. Tables still
need row/header association, and intervals/bounds still need structured operators.
New typographic facts can be omitted from already-full chunks by the compatibility
priority. Existing confidence constants remain heuristics. Numeric recognition does
not establish material identity, measurement conditions or scientific entailment.

## Verdict

Typography recognition and compatibility tests are implemented; targeted numeric
coverage improved. Persisted facts were not refreshed. Before relying on bulk
scientific comparisons, review changed corpus candidates and design explicit
range/bound and material/condition representation. Stage 3 scientific acceptance
and the earlier stage 2 relation acceptance remain open.
