# Phase 3 Semantic Retrieval Evaluation

Date: 2026-08-04

## Evaluated Configuration

- corpus: `literature`, 16 articles, 379 chunks;
- corpus manifest: `docs/corpus_manifest.json`, verified unchanged;
- embedding runtime: FastEmbed 0.8.0;
- embedding model: `BAAI/bge-small-en-v1.5`;
- embedding dimension: 384;
- similarity: cosine over normalized passage and query vectors;
- vector manifest schema: 2;
- vector manifest SHA-256: `ffc3e9628d21657726cc5dc3459db029ab8f8e985a863c580267cd65f6954de8`;
- evaluation set: `docs/evaluation_questions.yaml`, 24 questions;
- `top_k`: 10.

## Results

| Metric | Exact | Semantic | Semantic delta |
| --- | ---: | ---: | ---: |
| Passed | 24/24 | 22/24 | -2 |
| Top-1 passed | 18/24 | 17/24 | -1 |
| Recall@10 | 1.0 | 1.0 | 0.0 |
| Mean rank | 1.4583 | 1.5000 | +0.0417 |
| Empty queries | 0 | 0 | 0 |

Generated local reports:

- `data/exports/retrieval_eval_exact_20260804T045348Z.json`;
- `data/exports/retrieval_eval_semantic_20260804T045315Z.json`;
- `data/exports/retrieval_comparison_20260804T045355Z.json`.

## Regressions

Both failed semantic questions still ranked the expected article first. They failed because the returned top-10 snippets did not contain every expected keyword:

- `q20_ma_table_solvent_aggregation_2009`: missing `DMAc`;
- `q23_welch_broad_sans_morphology_2012`: missing `SANS` and `morphology`.

## Top-1 Improvements

Semantic moved four questions that were not exact top-1 passes to top-1 passes:

- `q04_li_nafion_sanginov_2021`;
- `q06_welch_dilute_solvent_sans_2012`;
- `q21_sanginov_broad_li_nafion_conductivity_2021`;
- `q22_cho_broad_dmfc_pvdf_2015`.

## Verification

- corpus manifest check: PASS;
- environment doctor: all checks PASS;
- exact evaluation before and after implementation: identical summary;
- semantic API-path smoke query: 3 results with article/chunk/page evidence and `semantic_cosine` method;
- unit tests: 98 passed;
- Ruff: passed;
- mypy: passed for 38 source files.

## Verdict

Semantic retrieval is operational and preserves source-linked evidence, but this model does not outperform the exact baseline on the accepted evaluation set. `exact` remains the default. `semantic` remains available only through explicit method selection. Hybrid retrieval was implemented and evaluated later in `docs/phase3_hybrid_evaluation.md`; the later answer layer is documented in `docs/phase4_rag_answers.md`.
