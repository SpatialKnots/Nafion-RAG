# Stage 3: cap losses and newly exposed candidates, 2026-09-09

## Changed

Reviewed eight complete PDF pages: Laporta pp. 6–7, Guo pp. 2–3, Sanginov
pp. 3–4, Dai p. 4 and Choi p. 5. Added nine decisions to
`numeric_guard_change_review.json`, bound to the unchanged 878-change diff hash
`9e5d5292bb59cdf293466549b301578bac52aa497ae473763e9d2fd1e74d443e`.
The review command verifies original checksums, exact stored page fragments,
chunk identity and extractor hash before accepting those annotations.

Added `scripts/stage3_numeric_cap_audit.py` for reproducible read-only trials of
caps 12, 16 and 24. Production extraction, its cap, database facts and original
PDFs were not changed. The trial cap is restored even if extraction fails.

### Three cap losses

| Candidate | Visual evidence | Decision |
| --- | --- | --- |
| `523 K`, Laporta, chunk `5114deb4-0aab-4e40-b089-e5b06c245a85` | P. 6 has range 423–523 K; p. 7 separately describes water treatment at 523 K, with incomplete dissolution. | Later supported occurrence is lost under the cap; removal is a coverage blocker. Do not rescue the earlier range endpoint. |
| `100 nm`, Guo, chunk `d26b5890-b91b-408e-9c04-480fa01467b2` | P. 2 has range 20–100 nm; p. 3 reports approximately 100 nm Li2O thickness at 250 °C. | Later supported occurrence is lost; coverage blocker. Approximation and treatment condition still need explicit representation. |
| `1.5%`, Sanginov, chunk `fc4dcb1f-455a-4e97-92ed-3dd77331c0c5` | P. 3 has uncertainty range 1–1.5%; p. 4 has calculation error ≤1.5% for bond angles. | Accept removal of an unqualified scalar. The later occurrence is a bound, not evidence for restoring a plain percentage. |

Thus the earlier description of all three as independent values was too broad:
the third requires an inequality operator. Two are coverage losses; one exposes
a representation problem. These annotations concern the selected chunk, not a
claim that the entire article lost that number.

### Three newly exposed false candidates

| Added candidate | PDF finding | Decision |
| --- | --- | --- |
| `8 nm`, Guo p. 3 | Text gives 30 ± 8 nm. Stored U+F0B1 bypasses the uncertainty guard. Other literal matches include the tail of 2.8 nm/min and figure uncertainty labels. | Blocker: uncertainty is emitted as thickness. |
| `1659 cm`, Dai p. 4 | Section 3.2 gives an FT-IR band at 1659 cm⁻¹. Stored escaped control glyph in the inverse suffix is not caught. | Blocker: wavenumber is misclassified as length. |
| `8 g`, Choi p. 5 | Fig. 3 caption gives electrolyte-to-capacity ratio approximately 8 g Ah⁻¹. | Blocker: compound unit is truncated to mass. |

The audit inspected the stored contexts of all 57 additions introduced by freeing
slots in the guard patch, then selected suspicious forms and positive controls
for visual review. This is targeted review, not a random sample or a precision
estimate. Other suspicious candidates are not automatically assigned verdicts.

Positive controls: `1 cm` Li-foil electrode diameter (Sanginov p. 3) and cited
conductivity `0.013 S/cm` at 10 wt.-% water (Laporta p. 7) have supported numeric
values and units. Removal of range-only `100 nm` in Guo's p. 2-only chunk is also
acceptable. Material/condition inference and cited underlying experiments were
not independently validated.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_cap_audit --diff data/exports/stage3_numeric_guard_corpus_diff_20260909.json --output data/exports/stage3_numeric_cap_sensitivity_20260909.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_change_review --diff data/exports/stage3_numeric_guard_corpus_diff_20260909.json --labels docs/numeric_guard_change_review.json --output data/exports/stage3_numeric_cap_review_20260909.json --check
.\.venv\Scripts\python.exe -m pytest tests/unit/test_numeric_cap_audit.py tests/unit/test_numeric_change_review.py tests/unit/test_structured_facts.py -q -p no:cacheprovider --basetemp=tmp/numeric_cap_audit_tests_20260909
```

- Targeted pytest: **61 passed**, including restoration after a deliberate audit
  failure and rejection of a range endpoint at the larger diagnostic cap.
- Source-verified review queue: **5 blockers, 4 acceptable, 869 unreviewed**.
  `bulk_refresh_ready=false`; `--check` exited **1**, as required.
- Original checksums and annotated page fragments verified successfully.
- Full pytest was not rerun for this audit-only addition.

### Cap sensitivity on 619 chunks

| Trial cap | Candidate count | Added over cap 12 | Targets recovered in their affected chunks |
| --- | ---: | ---: | --- |
| 12 (production) | 2424 | 0 | None |
| 16 | 2617 | 193 | `523 K` |
| 24 | 2771 | 347 | `523 K`, `100 nm`, `1.5%` |

At production cap, matching candidate identities occur in 8 other Laporta chunks,
2 other Guo chunks and 2 other Sanginov chunks respectively. This is candidate
availability only: identical lexemes do not prove identical measurements,
conditions or complete article-level evidence coverage.

## Limitations

Eight pages were visually reviewed by the assistant; no independent scientific
review. Poppler reported missing display fonts `Symbol` and `ArialUnicode` during
the initial six-page rendering. The relevant numeric passages were legible; the
warnings were not suppressed. Renderings are local audit intermediates under
`tmp/pdfs/numeric_cap_review/`.

The newly discovered extraction errors remain in production code at this audit
checkpoint. No claim of 878-change acceptance is made. The existing review command
is still an audit gate, not enforcement in the refresh CLI.

## Verdict and next implementation

**Keep cap 12 and reject bulk refresh.** A larger cap is not a targeted solution:
it exposes hundreds more candidates and returns an unsupported bound as well as
the two useful values.

Next patch should reject the verified U+F0B1 uncertainty operand, escaped inverse
suffix and compound `g Ah⁻¹` suffix while preserving exact original text. Use these
page-bound fragments as regressions, regenerate the diff and review newly freed
slots. Avoid globally replacing unknown glyphs with invented scientific meaning.

Then add occurrence-level provenance/diagnostics before changing selection policy:
distinguish accepted occurrence from rejected earlier identical text, retain page
and exact context, and report cap omissions. Bounds, approximation, ranges and
uncertainty need an explicit representation before scientific comparison. Any
schema change must be documented as such; no automatic corpus refresh follows
from passing software tests.
