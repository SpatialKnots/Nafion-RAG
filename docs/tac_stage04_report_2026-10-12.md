# TAC stage 04: continuations and implicit summary passages

## Changed

The isolated TAC detector is now `tac_section_proposals_v0.5`. The new `scripts/tac_section_flow.py` extends unfinished proposals only when exact source adjacency, typography and column/page geometry support a continuation. It stops at detected headings, front-matter metadata, incompatible geometry/style and missing page numbers. A next-page continuation remains a separate exact page span. The supported window is the current page and one immediately following page; this is not a general reconstruction of all PDF reading order.

`tac_front_matter.py` now maps a repeated fragment in a separate PDF block when its exact text follows a mapped anchor and it is adjacent on the same visual row. An ambiguous fragment at a distant location remains excluded. This recovered Nagasubramanian's final `electrolyte.` fragment. Mohammadi's Abstract now continues into the right column and ends at `and can be used in CA process.`; the adjacent publisher copyright marker is excluded using its source boundary, without altering the quoted text.

For documents without an explicitly headed C section, a late, block-initial `In summary`, `In conclusion`, `To summarize`/`To summarise` or `В заключение` can propose a summary passage. Introductory/inline mentions, unsupported short blocks and material after a recognized References heading are excluded. Exact source paragraphs remain separate; they are not generated summaries. Besenhard has two passages about different materials, not a combined article-level Conclusions section.

Experimental profiles now explicitly include `conclusion_kind`: `section`, `summary_passages` or `not_detected`. Source validation rejects unsupported values and a summary role inconsistent with its proposal methods. The new field and method names are versioned experimental output changes; production schemas and storage are unchanged. The HTML labels implicit summaries as `Итоговые фрагменты; отдельный раздел Conclusions не найден` and preserves all eight main columns, previous text, source links and changed-cell badges.

On the unchanged 33-document scope:

| Output | Stage 03 | Stage 04 |
| --- | ---: | ---: |
| Title proposals | 33 | 33 |
| Abstract proposals | 30 | 30 |
| Explicit Conclusions sections | 27 | 27 |
| Additional rows with summary passages | 0 | 3 |
| Rows with any C evidence | 27 | 30 |

Two Abstract fields changed; three C fields changed; no Title fields changed. Three new C rows represent two unique works: Besenhard, Welch and a repeated Welch upload (`priority3_e2e_upload`). The two Welch records have identical selected page text hashes but different PDF byte hashes. The frozen experiment retains both records; neither evaluation denominator nor gold labels were silently changed. Metadata values are unchanged: Authors 32/33, Journal 29/33, Year 30/33, 91 non-null fields.

Counting explicit sections and summary passages together gives 93/99 filled TAC cells (93.94%). This broadens the C evidence category; it is not 94% independently verified parsing accuracy. Explicit C coverage remains 27/33.

Final HTML: `output/tac_stage04_20261012/ARIADNE_TAC_stage04_final_v02_2026-10-12.html`.

## Inputs and reproducibility

- Frozen corpus: `data/experiments/tac/20261012_v01/corpus.json`; SHA-256 `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`; 33 articles, 493 selected pages, 619 chunks.
- Final profiles and metadata: `data/experiments/tac/20261012_stage04/profiles_final_v02.json`, `metadata_final_v02.json`. Main extractor/component hashes are recorded in the profiles; HTML records input hashes.
- Previous profiles: `data/experiments/tac/20261012_stage03/profiles_final_v03.json`.
- Final replay: stage04 `comparison_final_v02/report.json`.
- Final audits: `changes_final_v02.json`, `boundary_audit_final_v02.json`, `continuation_development_checks_v02.json`, `source_integrity_final_v02.json`.
- Read-only PDF renders and source hashes: stage04 `visual_audit/`; five original pages, four works.
- Before baseline: `output/baselines/20261012_before_tac_stage04/`, 292 files, fingerprint `96d0e2a07e9b5969d521bc375225c36f5e906506c4aa306eaf1ab1f1d7aa977a`.
- After baseline: `output/baselines/20261012_after_tac_stage04/`. Recipes and artifact hashes: stage04 `recipes/`, `artifact_inventory.json`.

Earlier intermediate outputs are retained. Only filenames above are final. The final v02 proposals are identical to the preceding run; v02 pins the additional guard against continuing across a missing PDF page.

Reproduction from the repository root, with new output destinations:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_experiment extract --snapshot data/experiments/tac/20261012_v01/corpus.json --output NEW_PROFILES.json
.\.venv\Scripts\python.exe -m scripts.tac_metadata --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --output NEW_METADATA.json
.\.venv\Scripts\python.exe -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --metadata NEW_METADATA.json --previous-profiles data/experiments/tac/20261012_stage03/profiles_final_v03.json --output NEW_REVIEW.html --source-root .
.\.venv\Scripts\python.exe -m scripts.tac_experiment replay --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --baseline-report data/experiments/tac/20261012_v01/comparison/report.json --questions docs/evaluation_questions_extended.yaml --output NEW_COMPARISON_DIRECTORY
```

## Tests run

- Final full pytest: **813 passed, 1 warning in 12.69 s**, `pytest_full_v02.log`. Fresh basetemp, outside sandbox because prior full sandbox runs hung. Existing warning: Starlette TestClient/httpx deprecation. Fifteen new synthetic geometry/HTML tests plus one repeated-fragment mapping test cover the new rules; synthetic fixtures are not scientific gold.
- Before the last missing-page guard, targeted TAC tests: **63 passed in 1.68 s**. The added missing-page test ran in the final full suite.
- `ruff check app tests scripts`: **All checks passed** after the final code change.
- `mypy app`: **Success: no issues found in 84 source files**; production app was unchanged thereafter.
- Unchanged development boundary labels: **19/19** trimmed exact text matches (T 8/8, A 7/7, C 4/4). Agent-authored labels informed development; they are not independent gold.
- All profile evidence validated against frozen page text, exact offsets, selected layer and hash. **33 original PDF hashes** and **88 production app file hashes** match the before baseline.
- Five rendered original PDF pages visually inspected: Mohammadi 1, Nagasubramanian 1, Welch 4, Besenhard 4 and 5. Confirmed target beginnings/endings and exclusion of adjacent Experimental, publisher text and bibliography. This is a selected development review, not independent corpus-wide acceptance.
- Final headless Edge QA: **33 rows, 8 columns, 33 original links, 5 changed cells, 3 summary labels**, exact agreement with all A/C quotes and 91 metadata values; search/expand work; no page errors. `output/tac_stage04_20261012/browser_verification_final_v02.json`; both final screenshots visually inspected.

Unchanged frozen replay inputs, 46 questions and scoring/rescue/evaluator:

| Path | Passed | Article recall | Chunk recall |
| --- | ---: | ---: | ---: |
| Production frozen control | 46/46 | 1.000000 | 1.000000 |
| Expanded-pool control | 46/46 | 1.000000 | 1.000000 |
| TAC-only | 42/46 | 0.947368 | 0.769231 |
| TAC-deep | 44/46 | 0.947368 | 0.923077 |
| TAC-deep with rescue | 45/46 | 0.973684 | 1.000000 |

Pass totals do not improve. TAC-only MRR changed from 0.859649 to 0.872807; TAC-deep judged-hit fraction changed from 0.343776 to 0.339160 and rescue judged-hit fraction from 0.300000 to 0.292105. These are mixed development replay effects, not an overall retrieval gain. Strict TAC-deep still loses the two Sanginov supplement questions; rescue still loses `qext025_sanginov_sup_dielectric_constant`. No fresh production retrieval or latency benchmark was run.

## Limitations

1. Geometry, paragraph markers and terminal punctuation are heuristics. A terminal sentence does not independently establish full section completeness. Page continuation has synthetic positive/negative tests but no naturally spanning Abstract example was added to this development corpus.
2. Summaries may concern subsections or different materials. They remain explicitly labelled passages; no semantic assertion of complete article-level Conclusions is made.
3. A remains unproposed for Besenhard and the Sanginov supplement; Sasaki 2009 has no separately delimited A proposal. C remains unproposed for Sasaki 2009, Резницких 2021 and the supplement. These statuses do not assert that the original documents lack all relevant evidence.
4. OCR/glyph repair, damaged author metadata, external metadata lookup, independent gold, production ingestion integration, Terms, work/supplement links and full-text safety remain separate work. Original text fragmentation/control characters are retained.
5. Layout warnings remain recorded (59 page warning entries, including repeated extraction calls; not 59 unique damaged pages). Production schemas, extraction/OCR, chunks, retrieval scoring and glossary were not modified.
6. Saved JSON/HTML and recipes are private development artifacts containing literature fragments and local paths, not a cleared public release.

## Verdict

The authorized continuation and implicit-summary cycle is implemented, tested and available for HTML review. Both known Abstract truncations were corrected, and two unique works gained source-bound summary evidence. Independent parsing accuracy and 95% completion are not established. Review these five changed cells before expanding rules or admitting outputs to production.
