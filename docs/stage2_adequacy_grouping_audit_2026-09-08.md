# Stage 2: PBI adequacy and additional grouping audit

Date: 2026-09-08. Application revision: `3727bb0`.

## Changed

Added repeatable read-only audit scripts:

- `scripts/stage2_pbi_audit.py`: scans stored original/OCR page layers, checks
  original PDF hashes, and replays the production answer service with an explicitly
  injected local `ExtractiveAnswerProvider`. No OpenAI request is made.
- `scripts/stage2_grouping_audit.py`: accepts a gold file and output path, searches
  once per query/method, then compares flat, uncapped, cap=1 and cap=2 views of
  that identical top-10 window. It records removed chunks with their original ranks.

Application scoring, adequacy thresholds, default grouping, extraction, schemas,
and original PDFs are unchanged.

## PBI source and answer-gate evidence

Query: `polybenzimidazole phosphoric acid anhydrous fuel cell Nafion composite`.

The source scan covered 814 stored page layers across 33 articles. No matches for
`polybenzimidazol\w*`, word-boundary `PBI`, `phosphoric`,
`полибензимидазол\w*`, or `фосфорн\w*` were found. All 33 original PDF hashes
matched the database checksums. This is a text-layer audit, not visual inspection
of every PDF or proof that OCR cannot have missed a mention.

The production answer service returned `status=answered` with the local extractive
provider. Its adequacy metadata contained:

- matched: acid, anhydrous, nafion, composite;
- absent: polybenzimidazole, phosphoric;
- aggregate coverage: 4/6; top-fragment coverage: 3/6;
- reason: `sufficient_distinctive_term_coverage`;
- concept coverage: no matched concepts, coverage null.

In `app/generation/evidence_adequacy.py`, both the aggregate >=0.6 branch and
the top-fragment >=0.5 branch independently accept this evidence. Adjusting only
one branch will not resolve the observed failure. The heuristic has no distinction
between an indispensable material/reagent and a general topical word.

The retrieval evaluator assesses snippets without concept terms; the answer
service selects/reorders evidence and assesses full chunk text with concept terms.
Both paths accept this case. The defect therefore is not solely a snippet-evaluation
artifact. This run does not establish what an OpenAI-generated answer would say.

Detailed local artifact: `tmp/stage2_pbi_source_audit.json`.

## User grouping results

Ten questions, eight with chunk targets. Article Recall is unchanged by grouping
for every method; trace completeness is true in all sixteen method/view combinations.

| Method | Article Recall flat/cap=2 | Chunk Recall flat → cap=2 | PASS flat → cap=2 |
| --- | --- | --- | --- |
| exact | 0.55 / 0.55 | 0.375 → 0.25 | 2/10 → 2/10 |
| semantic | 0.60 / 0.60 | 0.375 → 0.375 | 3/10 → 3/10 |
| hybrid | 0.70 / 0.70 | 0.75 → 0.625 | 6/10 → 5/10 |
| hybrid_cross_lingual | 1.0 / 1.0 | 1.0 → 1.0 | 10/10 → 10/10 |

Two confirmed cap=2 losses:

- `exact`, `user_reg_002_ru_ec_sl_highest_conductivity`: chunk Recall 1 → 0;
  the lost target requires `Li-Nafion`, `EC/SL`, `conductivity` in Sanginov 2021,
  DOI `10.1016/j.electacta.2021.137914`. Aggregate PASS hides this deterioration
  because the question already fails other conditions in the flat view. A removed
  matching chunk is `931a2ad8-abde-4e08-b889-4beae9ff247d`, original rank 6,
  PDF pages 12–13, original layer, stored source type `table`.
- `hybrid`, `user_reg_004_ru_swelling_li_vs_h`: chunk Recall 1 → 0;
  the lost dissertation target requires `H-Nafion`, `Li-Nafion`, `αLi`.
  Matching chunk `7ecad17d-a7c1-47d6-af2f-bcca3029d328` is removed at original
  rank 10, PDF pages 105–107, original layer, stored source type `main_text`.

Cap=1 loses the same two targets on this set. No user chunk-target losses were
observed for semantic or hybrid_cross_lingual; this is not a universal guarantee.
The complete removed-chunk lists, source pages and original ranks are preserved in
`tmp/stage2_grouping_user.json`.

## Cross-lingual grouping results

31 questions from `evaluation_questions_cross_lingual_extended.yaml`.
All four views preserve article Recall and PASS for each method:

| Method | Article Recall | PASS | Visible chunks flat → cap=2 |
| --- | --- | --- | --- |
| exact | 0.580645 | 18/31 | 307 → 167 |
| semantic | 0.451613 | 14/31 | 310 → 157 |
| hybrid | 0.580645 | 18/31 | 310 → 176 |
| hybrid_cross_lingual | 1.0 | 31/31 | 310 → 310 |

Trace completeness is true for all sixteen combinations. There are zero chunk
targets in this gold: chunk Recall is null, not 1.0. In particular, cap=2 removes
no cross-lingual results on this set, so that comparison cannot demonstrate safety
when a cap actually removes evidence. Artifact: `tmp/stage2_grouping_cross_lingual.json`.

## Decision

Do not change a global numeric coverage threshold just to pass this single
negative example. The next implementation needs a tested way to preserve required
query concepts, including bilingual aliases, while refusing topical-only evidence.
Validate it with positive PBI evidence fixtures, negative material/reagent examples,
and the existing answerable RU/EN gold. Do not hard-code a refusal for this query.

Do not adopt cap=2 as a universal evidence limit: additional user gold already
contains counterexamples. A display limit and the evidence passed to generation
must be evaluated separately. Retaining a route to all source fragments is necessary
when a compact article view is used.

## Tests run

Commands from `D:\Nafion-RAG`:

```powershell
.\.venv\Scripts\python.exe -m scripts.stage2_pbi_audit
.\.venv\Scripts\python.exe -m scripts.stage2_grouping_audit docs/evaluation_questions_cross_lingual_extended.yaml tmp/stage2_grouping_cross_lingual.json
.\.venv\Scripts\python.exe -m scripts.stage2_grouping_audit docs/evaluation_questions_user_regression_extended.yaml tmp/stage2_grouping_user.json
.\.venv\Scripts\python.exe -m app.ingestion.cli doctor
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json
.\.venv\Scripts\python.exe -m pytest tests/unit/test_generation.py tests/unit/test_api_search.py tests/unit/test_evaluation.py -q -p no:cacheprovider --basetemp tmp/stage2_audit_tests_20260908
```

Doctor: all PASS, two ready index states, no stale/failed states. Unit tests:
76 passed. An initial PBI script invocation failed because the local provider
requires `max_claims`; it was corrected to 5 and rerun successfully.
Corpus manifest checks before and after the audits: match. Ruff lint and format
checks passed for both added scripts after formatting corrections.

## Limitations

No visual PDF or browser verification, external generation, latency benchmark,
full failure-recovery test, or full pytest run. Cross-lingual gold has no chunk
targets, so preserved article recall there cannot prove preserved answer evidence.
Grouping operates after top-k without candidate refill. Lower recall in a capped
view is evidence loss within that window, not a change in retrieval scoring.
Raw artifacts remain local under `tmp/`; these scripts require the matching local
corpus, index, dependencies and configuration.

## Verdict

The PBI false-positive gate is reproduced through the answer service. Universal
safety of cap=2 is rejected by additional user gold. Stage 2 remains open; production
behavior has not been patched on the basis of a single counterexample.
