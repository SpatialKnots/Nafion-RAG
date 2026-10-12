# TAC stage 03: front matter and review table

## Changed

Experimental detector `tac_section_proposals_v0.4` now merges short title continuations before rejecting short lines, uses exact mapped PDF line geometry, skips supported manuscript cover pages, and searches for an explicit Abstract on the article start page and the following page. A byline/layout fallback proposes unlabelled abstracts without relying on particular scientific phrases. Conference abstracts receive a separate status when no distinct Abstract section is delimited. Quotes, Unicode offsets, selected text layers and page hashes remain unchanged source evidence.

On the frozen 33-document development corpus, proposed Title coverage increased from 32 to 33; Abstract from 21 to 30; Conclusions stayed at 27. Compared with stage 02, eight Title fields and eleven Abstract fields changed; zero Conclusions fields changed. These are coverage counts, not independently measured accuracy or completeness. Nine formerly absent Abstract proposals were recovered: Peng, Cho, Yu, Satoh, Doi, Lin, Nagasubramanian, Sasaki (review), and Kim. The metadata values are identical to the preceding metadata stage: Authors 32/33, Journal 29/33, Year 30/33, 91 non-null fields.

The HTML keeps eight columns, source links, exact expandable text and diagnostics. Changed Title/Abstract/Conclusions cells have an `Изменено` badge, and previous text is available under source diagnostics. This is an HTML-only review artifact; no XLSX was produced.

Final artifact: `output/tac_stage03_20261012/ARIADNE_TAC_stage03_final_2026-10-12.html`.

## Inputs and reproducibility

- Frozen corpus: `data/experiments/tac/20261012_v01/corpus.json`, SHA-256 `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`; 33 articles, 493 selected pages, 619 chunks.
- Final sections: `data/experiments/tac/20261012_stage03/profiles_final_v03.json`. Includes extractor and helper component hashes.
- Final metadata: `data/experiments/tac/20261012_stage03/metadata_final_v03.json`.
- Previous sections: `data/experiments/tac/20261012_stage02/profiles_final_v02.json`.
- Final comparison: `data/experiments/tac/20261012_stage03/comparison_final_v03/report.json`.
- Final audits: `boundary_audit_final.json`, `changes_final.json`, `source_integrity_final.json` in the stage directory. Earlier intermediate profiles/audits are retained; they are not the final result.
- Before baseline: `output/baselines/20261012_before_tac_stage03/`, 289 files, source fingerprint `89434b1805aea3996a5564d06e22823b600be8db03af03664e1de3170b0cf1b2`.
- After baseline: `output/baselines/20261012_after_tac_stage03/`. Recipes and artifact hashes: stage directory `recipes/` and `artifact_inventory.json`.

Run from the repository root, always with fresh output destinations:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_experiment extract --snapshot data/experiments/tac/20261012_v01/corpus.json --output NEW_PROFILES.json
.\.venv\Scripts\python.exe -m scripts.tac_metadata --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --output NEW_METADATA.json
.\.venv\Scripts\python.exe -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --metadata NEW_METADATA.json --previous-profiles data/experiments/tac/20261012_stage02/profiles_final_v02.json --output NEW_REVIEW.html --source-root .
.\.venv\Scripts\python.exe -m scripts.tac_experiment replay --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --baseline-report data/experiments/tac/20261012_v01/comparison/report.json --questions docs/evaluation_questions_extended.yaml --output NEW_COMPARISON_DIRECTORY
```

## Tests run

- Full pytest: **797 passed, 1 warning in 9.61 s**, `pytest_full_v03.log`. Used a fresh basetemp outside the sandbox because earlier sandbox runs hung. Existing warning: Starlette TestClient/httpx deprecation.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Unchanged development boundary annotations: **19/19** exact trimmed text matches, T 8/8, A 7/7, C 4/4. These agent-authored cases informed development and are not independent gold.
- Final source validation checked every proposal's page, offset, text layer, exact quote and checksum, including document type evidence. **33 original PDF hashes** and **88 production app file hashes** match the before baseline.
- Read-only visual development review: 11 original PDF pages for ten documents, with PNGs, stderr and source hashes in `visual_audit/`. This is a selected development review, not a corpus-wide completeness audit.
- Headless Edge QA: **33 rows, 8 columns, 33 source links**, exact JSON agreement for Abstract/Conclusions and all **91 metadata values**, 19 changed-cell badges, working search/expand, no page errors. `output/tac_stage03_20261012/browser_verification_final.json`; both final screenshots visually inspected.

Replay uses the same frozen candidate pools and unchanged 46 questions, scoring/evaluator and rescue rules. It is not a fresh production retrieval or latency benchmark:

| Path | Passed | Article recall | Chunk recall |
| --- | ---: | ---: | ---: |
| Production frozen control | 46/46 | 1.000000 | 1.000000 |
| Expanded pool control | 46/46 | 1.000000 | 1.000000 |
| TAC-only | 42/46 | 0.947368 | 0.769231 |
| TAC-deep | 44/46 | 0.947368 | 0.923077 |
| TAC-deep with rescue | 45/46 | 0.973684 | 1.000000 |

Pass totals remain the same as stage 02. Strict TAC-deep still loses the two Sanginov supplement questions; rescue still loses `qext025_sanginov_sup_dielectric_constant`. Therefore this stage does not justify using TAC as a hard search gate. No newly measured search improvement is claimed.

## Limitations

1. Thirty proposed Abstract blocks do not mean thirty complete abstracts. Nagasubramanian still ends at `CAR-1` before the final `electrolyte.` fragment; Mohammadi ends at `transi-` across a column boundary. Both carry a continuation diagnostic. A terminal sentence alone does not prove completeness; other boundaries still require review.
2. Abstract remains undetected for Besenhard and the Sanginov supplement. Sasaki 2009 is classified from an exact ECS Meeting Abstracts label; a separately delimited Abstract is not proposed. Missing sections are not PDF read failures.
3. Conclusions rules and the six missing Conclusions were not changed in this cycle. Besenhard's damaged byline and Moore's `111` author suffix remain metadata/OCR tasks. No external metadata lookup or OCR repair was added.
4. Page geometry and byline recognition are heuristics. Original line fragmentation, ligatures and glyph defects are retained rather than silently repaired. Layout warnings remain in profiles/logs (59 recorded page warning entries, including repeated extraction calls, not 59 unique damaged pages).
5. Independent boundary gold, human approval, Terms extraction, production ingestion integration, work/supplement links, full-text safety channel and latency measurements remain open. Production schemas, retrieval, OCR, chunking, glossary and database were not modified by this stage.
6. JSON/HTML contain local paths and source fragments. The saved development bundle is private, not a cleared public release.

## Verdict

The bounded front-matter improvement and review table are implemented and tested. Complete TAC acceptance remains open. Review changed cells first, then resolve cross-column Abstract continuations and remaining source/metadata gaps before Terms or production admission.
