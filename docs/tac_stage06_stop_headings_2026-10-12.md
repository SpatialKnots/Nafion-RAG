# TAC stage 06: bounded stop-heading repair

Date: 12 October 2026, Asia/Yekaterinburg. Isolated development extractor.

## Changed

Updated the experimental extractor to `tac_section_proposals_v0.6`. The shared
anchored STOP pattern recognizes `Conﬂicts of interest` / `Conﬂict of interest`
with the source `ﬂ` ligature, and `CRediT author statement`, retaining the existing
`CRediT authorship contribution statement` variant. The patch changes only these
two regex branches and the explicit version. It does not normalize source strings
or adjust offsets after matching. Full-line anchoring remains in effect; ordinary
body mentions of these phrases are not newly accepted as headings.

On the unchanged 33-document, 493-selected-page, 619-chunk snapshot, exactly two
C fields changed. Peng 2021 no longer includes its conflict-of-interest heading
and statement. Sanginov 2021 no longer includes author roles. The scientific
Conclusions paragraphs, original starting offsets and exact source text are
retained. Both new endings were rechecked visually against the original PDF page
renders (Peng page 8, Sanginov page 12), and verified as exact prefixes of the
preceding source-bound proposal ending at the administrative heading.

No T/A field changed; coverage remains T 33/33, A 30/33, any C evidence 30/33
(27 explicit sections and three labelled summary-passage rows). Authors/Journal/Year
values are unchanged: 32/33, 29/33, 30/33, respectively. Original PDFs, production
application files, extraction/OCR, chunks, retrieval scoring and glossary are unchanged.

Final HTML, with two changed-cell badges and prior text available in diagnostics:
`output/tac_stage06_20261012/ARIADNE_TAC_stage06_stop_headings_2026-10-12.html`.

## Updated development audit

Only the two changed C fields received new visual boundary assessments. The other
97 field assessments are carried unchanged from stage 05 after verifying identical
proposals. The sidecar records the prior review hash and this limited review scope.
It is not a new independent whole-corpus evaluation or human acceptance.

| Field | No observed boundary issues | Boundary errors | Missed | Not separately delimited |
| --- | ---: | ---: | ---: | ---: |
| Title | 32 | 1 | 0 | 0 |
| Abstract | 30 | 0 | 0 | 3 |
| Conclusions / labelled summary passages | 24 | 6 | 1 | 2 |
| Total | 86 | 7 | 1 | 5 |

The descriptive assistant-review ratio increases from 84/94 applicable fields
(89.36%) to 86/94 (91.49%). Raw slots stay at 99, with five explicit structural
exclusions and the duplicate Welch upload retained. Filled-cell coverage remains
93/99. These ratios do not establish independent scientific parsing accuracy.

Remaining cases: graph/page furniture in Guo, Yu, Satoh and the dissertation;
unheaded administrative material in Чернюк 2023; truncated C in Nagasubramanian;
title footnote in Lin 2023; missed implicit Russian summary in Резницких 2021.
Recommendations within the dissertation require a separately stated scope rule.

## Tests run

- Targeted extractor/front-matter/continuation tests: **65 passed in 3.16 s**.
  Nine added synthetic cases cover the new heading variants, source ligature
  preservation, exact offsets, compatibility with layout stopping and negative
  body mentions. They are regression fixtures, not independent scientific gold.
- Full pytest: **835 passed, 1 warning in 17.81 s**, fresh basetemp outside sandbox.
  Command: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp D:/Nafion-RAG/tmp/tac_stage06_full_20261012`.
  Output: stage06 `pytest_full.log`. Warning: existing Starlette TestClient/httpx deprecation.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Exact source validation passed for all new proposals. Original PDF hashes and
  saved reviewed-page render hashes match; **88 production app files** match the
  before baseline. Metadata values are identical to stage 04.
- Final headless Edge QA: **33 rows, 8 columns, 33 PDF links, 99 assessment badges,
  two changed-cell badges, 8 problem rows**. All current T/A/C text, review notes,
  **91 metadata values** and **273 local link targets** checked. Search, expand and
  combined problem filter work; no page errors. Both screenshots visually inspected.
- MuPDF diagnostics remain in `extract_final.log` and profiles: **59 page warning
  entries**, including repeated extraction calls; not 59 unique damaged pages.
- Frozen replay on the unchanged 46 questions: all summary metrics exactly equal
  stage 04. Production/expanded controls 46/46; TAC-only 42/46; TAC-deep 44/46;
  TAC-deep with rescue 45/46. No fresh live retrieval or latency benchmark ran.

## Inputs and reproduction

- Before baseline: `output/baselines/20261012_before_tac_stage06/`, 298 files,
  fingerprint `adb36e23ca59b294014b7a070f7eb1a312dbd261cad0439342ef78cc06845efc`.
- Frozen corpus: `data/experiments/tac/20261012_v01/corpus.json`, SHA-256
  `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
- Previous proposals: stage04 `profiles_final_v02.json`; previous review: stage05
  `boundary_review_final.json`. Both preserved separately.
- New profiles, metadata, review, summary, change list, source integrity and replay:
  `data/experiments/tac/20261012_stage06/`.
- Recipes and artifact hashes: stage06 `recipes/` and `artifact_inventory_final.json`.
  Original visual source pages are reused from the stage05 render manifest, not rerendered.

Reproduce with new output destinations; the exporter refuses overwrite:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_experiment extract --snapshot data/experiments/tac/20261012_v01/corpus.json --output NEW_PROFILES.json
.\.venv\Scripts\python.exe -m scripts.tac_metadata --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --output NEW_METADATA.json
.\.venv\Scripts\python.exe -m scripts.tac_experiment replay --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --baseline-report data/experiments/tac/20261012_v01/comparison/report.json --questions docs/evaluation_questions_extended.yaml --output NEW_REPLAY_DIRECTORY
```

To render the saved assessed output without regenerating review decisions:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage06/profiles_final.json --metadata data/experiments/tac/20261012_stage06/metadata_final.json --previous-profiles data/experiments/tac/20261012_stage04/profiles_final_v02.json --boundary-review data/experiments/tac/20261012_stage06/boundary_review_final.json --output NEW_REVIEW.html --source-root D:/Nafion-RAG
```

## Limitations

This handles the observed `ﬂ` spelling and two supported CRediT headings, not all
damaged glyphs, ligatures or possible administrative headings. It leaves the six
other C errors, title footnote and missing summary visible. Source glyph damage
is retained; boundary correctness does not certify scientific text fidelity.
No production integration, Terms extraction, human gold or new model inference
is introduced. Private literature text and local paths remain in ignored artifacts.

## Verdict

The scoped stop-heading repair is implemented, verified and available for review.
Two confirmed boundary errors are resolved, with no observed changes to other TAC
fields or frozen retrieval metrics. Independent 95% accuracy remains unsupported.
Next bounded work: restore the incomplete Nagasubramanian Conclusions before
attempting general removal of graph/page furniture across multi-page sections.
