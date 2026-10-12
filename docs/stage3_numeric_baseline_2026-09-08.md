# Stage 3: numeric extraction baseline, 2026-09-08

## Changed

Added `docs/numeric_fact_cases.json`: eight targeted development probes with ten
numeric targets, transcribed after visual review of original PDF pages. Added
`scripts/stage3_numeric_audit.py`: a read-only audit of the existing
`rule_based_numeric_v1` extractor on actual stored chunks. Production extraction,
database schemas, structured facts and original PDFs were not modified.

Each probe retains the article checksum, exact page and original-layer fragment,
fragment offset/hash, numeric targets, unit, operator, material and conditions.
Context labels were authored from visual inspection; they are not independent
scientific gold. The evaluator verifies original PDF hashes before and after the
run, exact page-text fragments, and selected-layer chunks containing those fragments.
Its report records actual chunk IDs, page ranges, source types, text-layer and text
hashes, all extracted candidates, and numeric target matches. It does not call the
structured-fact refresh/apply operation.

## PDF review

Poppler rendered three original pages to PNG at a maximum dimension of 1700 pixels;
all three were visually inspected in this session:

- Dissertation of Chernyuk S.D., PDF page 110: shared conductivity unit in the
  table header, merged EC solvent cell, two distinct membrane/temperature rows.
- Sanginov 2021, PDF page 9: approximate conductivity in the prose below Figure 10
  and the lower temperature bound in the left column. No graph digitization.
- Istomina 2021, PDF page 7: the cited H+ Nafion/water comparison and background
  crystallinity range in prose. These are not Li-Nafion/EC-SL measurements merely
  because Figure 4 discusses that system on the same page.

Rendered review artifacts:
`tmp/pdfs/stage3_numeric/dissertation110.png`, `sanginov9.png`, `istomina7.png`.
Original file paths and verified hashes are in the local JSON report. To reproduce
rendering, use `pdftoppm -f PAGE -l PAGE -scale-to 1700 -png -singlefile PDF PREFIX`.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_audit --output data/exports/stage3_numeric_baseline_20260908.json --check
.\.venv\Scripts\python.exe -m ruff check scripts/stage3_numeric_audit.py
.\.venv\Scripts\python.exe -m pytest tests/unit/test_structured_facts.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json
```

- Audit: **4/10 numeric targets detected**, all values found in **3/8 probes**.
  `--check` returned **1** because extraction and structured-context requirements
  are incomplete. Source integrity checks completed without errors.
- Existing structured-fact tests: **2 passed**. Ruff passed.
- Corpus manifest matched, with no missing, extra or changed articles.
- Full suite was not rerun in this audit-only step.

| Probe | Visually reviewed target | Detection in stored chunks |
| --- | --- | --- |
| EC, Li-Nafion 115, 30 °C | 1.90 × 10⁻⁴ S/cm | Missing |
| EC, Li-Nafion 117, 40 °C | 1.43 × 10⁻⁴ S/cm | Missing |
| Li-Nafion / EC-SL, omega(SL)=0.20, room temperature | Approximately 2 × 10⁻⁴ S/cm | Missing |
| Lower conductivity temperature limit | ≤ −40 °C | −40 found; comparator not represented |
| H+ Nafion/water, increase in W | Less than 10% | 10 found; bound and material not represented |
| H+ Nafion/water, W upper bound | W did not exceed 40% | 40 found; bound and material not represented |
| Water-uptake comparison temperatures | 40 to 80 °C | Both endpoints missing |
| Extruded Nafion crystallinity | Approximately 7–17% | Only 17 found; interval not represented |

## Findings

1. **Table context:** the shared Cyrillic unit `См/см` is in the header while
   values are on separate lines. The extractor matches number-plus-unit on one
   line; it cannot reconstruct these rows, membrane types or merged solvent cells.
2. **Typography:** the Sanginov text uses `2 × 10 −4 S cm −1`, with U+2212 minus
   signs. Existing exponent and unit patterns only accept ASCII minus. The
   Istomina temperature unit uses `◦C` (U+25E6), not `°C` (U+00B0).
3. **Ranges and bounds:** a scalar candidate does not represent “less than”,
   “did not exceed”, approximation, or a range. The crystallinity candidate is
   `17%`; the lower endpoint and range interpretation are absent. Finding a scalar
   is therefore not a scientifically complete fact.
4. **Context representation:** `StructuredFactCandidate` has no structured
   `operator`, `material` or `conditions` fields. All eight probes require such
   context. Source-chunk links preserve access to the prose, but do not establish
   that the correct material and measurement conditions were extracted.

## Limitations

The 40% figure is **target detection coverage on selected probes**, not general
recall or precision. The pages were chosen to expose failure classes; their numeric
content is not exhaustively annotated, so precision is not measured. Matching
checks scalar value, normalized unit, field and candidate text present in the
annotated fragment. It does not prove sample association or exact occurrence
identity when identical tokens repeat inside a chunk. Overlapping chunks can yield
duplicate candidates; each target is counted once if any matching candidate exists.

Only original text layers were evaluated. No OCR comparison, new text extraction,
graph digitization, formula interpretation, external retrieval or answer generation
was performed. Dissertation table entries and cited background comparisons were
checked as claims printed in those PDFs, not independently verified against their
underlying primary studies. Current confidence constants are not measured
probabilities of scientific correctness.

## Verdict and next implementation

The first source-backed stage 3 baseline is reproducible. Numeric facts are not
ready for automatic scientific comparisons.

Next patch should address **typographic numeric/unit recognition only**, using
source-backed examples and synthetic guards against partial exponent matches.
Preserve exact source text and existing units; measure before/after on this fixed
fixture. It must not infer missing table units or treat range endpoints as complete
measurements. Operator/range representation and material/condition association need
an explicit schema and migration decision, with diagnostics and separate evaluation.
Original PDFs must remain immutable; stage 2 scientific acceptance remains open.
