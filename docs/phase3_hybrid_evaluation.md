# Phase 3 Hybrid Retrieval Evaluation

Date: 2026-08-04

## Evaluated Configuration

- corpus: `literature`, 16 articles, 379 chunks;
- corpus manifest: `docs/corpus_manifest.json`, verified unchanged;
- exact component: `exact_ilike`;
- semantic component: `semantic_cosine` with `BAAI/bge-small-en-v1.5`, dimension 384;
- fusion: equal-weight reciprocal rank fusion;
- RRF constant: 60;
- candidate multiplier: 5;
- final `top_k`: 10;
- component candidate depth: 50;
- evaluation set: `docs/evaluation_questions.yaml`, 24 questions.

The RRF parameters were fixed before evaluation. No parameter sweep or weight tuning was performed on the evaluation set.

## Results

| Metric | Exact | Semantic | Hybrid | Hybrid vs exact |
| --- | ---: | ---: | ---: | ---: |
| Passed | 24/24 | 22/24 | 24/24 | 0 |
| Top-1 passed | 18/24 | 17/24 | 20/24 | +2 |
| Recall@10 | 1.0 | 1.0 | 1.0 | 0.0 |
| Mean rank | 1.4583 | 1.5000 | 1.3333 | -0.1250 |
| Empty queries | 0 | 0 | 0 | 0 |

Generated local reports:

- `data/exports/retrieval_eval_exact_20260804T051337Z.json`;
- `data/exports/retrieval_eval_semantic_20260804T051252Z.json`;
- `data/exports/retrieval_eval_hybrid_20260804T050957Z.json`;
- `data/exports/retrieval_comparison_20260804T051344Z.json`.

## Improvements And Regressions

Hybrid introduced no top-k PASS regression against exact.

Four questions improved from a non-top-1 exact result to a top-1 hybrid result:

- `q04_li_nafion_sanginov_2021`;
- `q09_istomina_mixing_temperature_2021`;
- `q21_sanginov_broad_li_nafion_conductivity_2021`;
- `q22_cho_broad_dmfc_pvdf_2015`.

Two questions regressed at top-1 while remaining PASS within top-10:

- `q12_chernyuk_nafion_water_thermodynamics_2023`: exact rank 1, semantic rank 4, hybrid rank 2;
- `q19_chernyuk_2024_enthalpy_solutions`: exact rank 1, semantic rank 4, hybrid rank 5.

Every hybrid result retains the final RRF score, exact/semantic component ranks, raw component scores, article, chunk, page range, source type, and snippet.

## Acceptance And Default

The candidate satisfies the agreed technical acceptance threshold: no loss in top-k PASS or recall, aggregate top-1 improves by two, mean rank improves, and evidence traceability is preserved.

`hybrid` is available through explicit method selection. `exact` remains the default because changing the default requires a separate user decision. RAG answer generation remains outside this gate.

## Rollback

Rollback does not require database, corpus, vector index, or PDF changes. Remove hybrid method dispatch and its configuration while leaving exact and semantic implementations intact.
