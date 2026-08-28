# User Cross-Lingual Smoke Summary

Date: 2026-08-27

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
data\exports\retrieval_eval_extended_hybrid_cross_lingual_20260827T105020Z.json
```

## Summary

```json
{
  "total": 25,
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
user_en_to_ru: 5/6
user_mixed:    3/3
user_ru_to_en: 6/6
user_ru_to_ru: 5/5
```

## Failures

```text
user_xling_014_en_chernyuk_water_sorption
```

Query:

```text
Which Russian paper discusses Nafion-water sorption thermodynamics?
```

Expected:

```text
Чернюк 2023, DOI 10.31857/s2308112023700463
```

Observed top result:

```text
Диссертация Чернюк С.Д.
```

Interpretation: partial target ambiguity. The dissertation contains strong
Nafion-water sorption thermodynamics reference context, while the expected target
was the standalone Chernyuk 2023 paper.

## Current Interpretation

The language barrier is mostly handled at top-10 for user-style prompts, but
ranking is still not strong enough for comfortable top-3 use.

M3 closed the real Dai solvent-list miss and the Ma solution-casting morphology
regression by adding ordered glossary matching and narrow corpus-backed concepts.
The remaining miss is a target ambiguity rather than a clear language-barrier
failure.

RU-to-EN improved versus the previous smoke run:

```json
{
  "passed": 6,
  "failed": 0,
  "mrr": 0.27559523809523806,
  "top_1_passed": 1,
  "mean_rank": 6.666666666666667
}
```

## Next M3 Targets

- Decide whether `Nafion-water sorption thermodynamics` should accept the
  dissertation as relevant, or whether the question should explicitly target the
  Chernyuk 2023 article.
- Improve RU-to-EN top-3 ranking without reducing current top-10 recall.
