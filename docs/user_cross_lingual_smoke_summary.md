# User Cross-Lingual Smoke Summary

Date: 2026-08-27

Updated: 2026-08-30

## Scope

This smoke set contains 25 user-style Russian, English, and mixed-language
questions for checking the current `hybrid_cross_lingual` behavior outside the
curated extended benchmark.

Question file:

```text
docs/evaluation_questions_user_cross_lingual.yaml
```

Report:

```text
data\exports\retrieval_eval_extended_hybrid_cross_lingual_20260830T190857Z.json
```

## Summary

```json
{
  "total": 25,
  "passed": 25,
  "failed": 0,
  "article_recall_at_k": 1.0,
  "mrr": 0.8368253968253968,
  "top_1_passed": 19,
  "mean_rank": 1.8
}
```

Immediate pre-M4 baseline on the same machine:

```text
data\exports\retrieval_eval_extended_hybrid_cross_lingual_20260830T122542Z.json
```

```json
{
  "passed": 24,
  "failed": 1,
  "article_recall_at_k": 0.96,
  "mrr": 0.5035714285714286,
  "top_1_passed": 10,
  "mean_rank": 4.083333333333333
}
```

## Category Summary

```text
user_en_to_en: 5/5
user_en_to_ru: 6/6
user_mixed:    3/3
user_ru_to_en: 6/6
user_ru_to_ru: 5/5
```

## Failures

```text
none
```

## Current Interpretation

The language barrier is mostly handled at top-10 for user-style prompts. M4
article-diverse feature windows and narrow intent bonuses substantially improved
ranking while preserving the same 24/25 article recall. The later
property-confusion survey-evidence gate preserved the same smoke metrics. The
source-type ambiguity gate closed the remaining water-thermodynamics miss by
preferring DOI-bearing standalone main-text evidence for English "Russian paper"
wording while keeping dissertation context visible.

M3 closed the real Dai solvent-list miss and the Ma solution-casting morphology
regression by adding ordered glossary matching and narrow corpus-backed concepts.
The previous remaining miss was a source-type ambiguity: dissertation reference
context crowded out the standalone Chernyuk 2023 article in the inspected top-k.

RU-to-EN improved versus the previous smoke run:

```json
{
  "passed": 6,
  "failed": 0,
  "mrr": 0.6944444444444445,
  "top_1_passed": 3,
  "mean_rank": 1.8333333333333333
}
```

## Next Targets

- Continue improving EN-to-RU ranking for lithium-form thermodynamics and
  transport wording without reducing current top-10 recall.
