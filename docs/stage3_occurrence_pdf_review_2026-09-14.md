# Stage 3: source review of numeric occurrences, 2026-09-14

## Changed

Reviewed 13 complete rendered PDF pages from seven originals: Fan pp. 3, 5, 6,
9; Kim p. 4; Guo pp. 2-3; Yu p. 8; Choi p. 11; Laporta pp. 6-7;
Sanginov pp. 3-4. Page numbers are PDF positions, not printed page numbers.
Selection covers all 11 candidates newly exposed by the reference/rate guard
patch and the three baseline cap losses. This is targeted development review,
not a random sample of the corpus or an estimate of precision.

Regenerated the Git-baseline diff for the diagnostic extractor: 981 changes
(374 additions, 607 removals), unchanged in count. Saved 13 new, source-verified
decisions in `numeric_occurrence_change_review.json`, bound to that diff.
The inspected but unresolved fourteenth candidate remains unapproved.
Full observations, source snippets and occurrence decisions are recorded in
`numeric_occurrence_pdf_review.json`.

Extended the review validator to check optional occurrence-bound annotations:
exact chunk offsets, lexeme, decision, reason and source line. Partial bindings
fail explicitly. Old fragment-only annotations retain their existing behavior;
this does not turn them into occurrence-level approvals. The validator checks
source integrity, not the scientific correctness of the assistant's labels.

### Findings and decisions

| Candidate/source | PDF finding | Decision in current diff |
| --- | --- | --- |
| Fan `0.91 eV`, p. 5 | EC radical decomposition barrier | Addition acceptable as value/unit; reaction attribution remains unstructured |
| Fan `400 eV`, p. 9, three chunks | Plane-wave cutoff in periodic calculations | Three additions acceptable; one source parameter, not three independent measurements |
| Kim `94 °C`, p. 4 | Ethanol dispersing temperature | Addition acceptable |
| Guo `25°C`, p. 3, two chunks | Explicit treatment-temperature label in Fig. 1a | Two additions acceptable; not a measured response |
| Fan `129%`, p. 3 | Relative increase of electrolyte resistance for EC/DMC | Addition acceptable as percentage; not absolute composition |
| Yu `10 nm`, p. 8 | Fig. 7 caption explicitly identifies scale bars | Blocker: `numeric_measurement/length` lacks the scale-bar role; not SEI thickness |
| Choi `55%`, p. 11 | Roughly 55% yield for EME, separately roughly 55% for F3EME | Blocker: approximation missing and different syntheses collapsed as lexical duplicates |
| Laporta `523 K`, pp. 6-7 | Early range endpoint rejected; later water-treatment condition omitted by cap | Coverage blocker; do not restore the range endpoint |
| Guo `100 nm`, pp. 2-3 | Early range endpoint rejected; later approximately 100 nm at 250 °C omitted | Coverage blocker; restoration must preserve approximation and condition |
| Sanginov `1.5%`, pp. 3-4 | Uncertainty range, then upper bound on calculated bond-angle error | Removal acceptable; do not restore a plain percentage |
| Fan `10 nm`, p. 6 | Fig. 5h scale bar and Fig. 5i thickness arrow share identical extracted lines | Unresolved; selected occurrence cannot be assigned a visual role by line matching |

The two cap blockers are repeated confirmation of previous findings, not newly
discovered defects. The two new blockers concern role/approximation and scientific
identity rather than incorrectly read digits. No automatic broad exclusion rule
follows from these examples: figure labels can also be valid treatment conditions.

Occurrence diagnostics expose an additional distinction in Laporta: a later
`523 K` occurrence concerns cited thermal degradation, while the first eligible
one concerns incomplete dissolution during water treatment. Lexical deduplication
is not scientific equivalence. Choi provides a second concrete counterexample.

### Review queue

- **4 blockers, 9 acceptable, 968 unreviewed; `bulk_refresh_ready=false`.**
- Of those 968, one was inspected but remains ambiguous; 967 were not reviewed
  in this pass. No previous approvals were automatically transferred.
- Acceptable labels cover the specified numeric extraction change and source
  context only; they do not approve downstream material attribution or comparisons.
- Production extractor, cap 12, database facts and PDFs were unchanged this turn.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m scripts.stage3_typography_compare --baseline-ref 4656690 --output data/exports/stage3_occurrence_corpus_diff_20260914.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_change_review --diff data/exports/stage3_occurrence_corpus_diff_20260914.json --labels docs/numeric_occurrence_change_review.json --output data/exports/stage3_occurrence_change_review_20260914.json --check
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_numeric_occurrence_review.py tests/unit/test_numeric_change_review.py -p no:cacheprovider --basetemp=tmp/occurrence_review_final_tests_20260914
.\.venv\Scripts\python.exe -m ruff check scripts/stage3_numeric_change_review.py tests/unit/test_numeric_occurrence_review.py
```

Final targeted tests: **6 passed**. Initial test run had two failures caused by
an incorrect hand-written fixture offset; corrected 12:17 to 13:18, then reran.
Ruff passed. Full suite was not rerun for this audit-validator-only change.
The preceding extraction patch's 536-pass result is historical, not a new run.

The source audit verified original PDF checksums, live chunk text, page-layer
fragments, candidate provenance, diff/extractor hashes and all 13 occurrence
bindings. `--check` exited **1**, as expected for blockers/unreviewed changes.
This is a scientific acceptance gate failure, not a source-integrity failure.

Rendering used Poppler, with local intermediates under
`tmp/pdfs/occurrence_review_20260914/`. Preparation and label assembly scripts
are `tmp/prepare_occurrence_review.py` and `tmp/label_occurrence_review.py`.
Preparation first encountered a Windows default-decoding error and then a
repeated-line ambiguity. UTF-8 was made explicit; repeated lines were retained
as ambiguous and never granted a unique occurrence binding.

## Limitations

Assistant visual review only; no independent scientific review. Poppler reported
`Invalid Font Weight` and missing `Symbol`/`ArialUnicode` display-font diagnostics.
The cited numeric passages were legible. Ambiguity in Fan is semantic/spatial,
not a missing-font inference. Stored source text was not normalized or rewritten.

The detailed review records retain the first matching line fragment for ambiguous
Fan locations and explicitly mark `ambiguous_line_match`; these locations are
not asserted to map either selected/duplicate occurrence to a particular panel.
Unique-line bindings are still text-based source checks, not PDF coordinates.
Raw matching cannot prove correct experimental attribution.

## Verdict and next implementation

**Reject bulk refresh and retain cap 12.** The targeted PDF review is complete;
the full 981-change scientific acceptance remains open.

Next add diagnostic scientific-role flags for explicit scale bars, approximation
and inequality cues, without changing production selection. Preserve separate
occurrences with identical values as distinct evidence until scientific identity
is established. Test the explicit Yu scale-bar caption against the positive Guo
treatment-temperature label; include Choi's two syntheses and Laporta's different
523 K statements. Do not change deduplication or the persisted fact schema until
their effects on the cap and corpus output are evaluated separately.

Then continue PDF review of the remaining queue using those distinctions. A larger
cap cannot solve missing roles, bounds or scientifically distinct duplicates.
