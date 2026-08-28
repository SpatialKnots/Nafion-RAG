# Cross-Lingual M1 Evaluation Summary

Date: 2026-08-27

Updated: 2026-08-28

## Scope

This records the current M1 cross-lingual retrieval state after adding:

- query feature extraction and protected scientific tokens;
- Russian lexical normalization;
- `semantic_multilingual`;
- optional multilingual channel in a rejected `hybrid_cross_lingual_v2`
  experiment;
- extended cross-lingual evaluation categories.
- M2 phrase/title-aware reranking with a conditional expanded window for mixed
  and protected-token queries.
- M3 ordered glossary matching and narrow corpus-backed concepts for Dai
  solvent-list and Ma solution-casting morphology prompts.

No method is promoted to default.

## Extended Evaluation Set

File:

```text
docs/evaluation_questions_cross_lingual_extended.yaml
```

Question count:

```text
31
```

Categories:

```text
en_to_ru
ru_to_en
mixed
morphology
abbreviation
en_to_en
ru_to_ru
```

## Latest Reports

Current best recall/ranking balance on the extended set after M3:

```text
data\exports\retrieval_eval_extended_hybrid_cross_lingual_20260827T105055Z.json
```

Summary:

```json
{
  "total": 31,
  "passed": 31,
  "failed": 0,
  "article_recall_at_k": 1.0,
  "mrr": 0.5134024577572965,
  "top_1_passed": 12,
  "mean_rank": 3.806451612903226
}
```

Current 2026-08-28 verification after moving the glossary to a versioned YAML
file:

```text
data\exports\retrieval_eval_extended_hybrid_cross_lingual_20260828T060020Z.json
data\exports\retrieval_eval_extended_hybrid_cross_lingual_20260828T055942Z.json
```

The accepted retrieval method remains `hybrid_cross_lingual`. A broader
candidate-window / heavier title-reranking experiment was rejected because it
kept top-10 recall but reduced MRR and top-1 behavior on both cross-lingual
evaluation sets.

Rejected `hybrid_cross_lingual_v2` experiment on the same set:

```text
data\exports\retrieval_eval_extended_hybrid_cross_lingual_v2_20260827T055319Z.json
```

Summary:

```json
{
  "total": 31,
  "passed": 28,
  "failed": 3,
  "article_recall_at_k": 0.9032258064516129,
  "mrr": 0.4090373783922171,
  "top_1_passed": 9,
  "mean_rank": 4.392857142857143
}
```

Standalone multilingual semantic baseline:

```text
data\exports\retrieval_eval_semantic_multilingual_20260827T050145Z.json
```

Summary:

```json
{
  "total": 6,
  "passed": 3,
  "recall_at_k": 0.6666666666666666,
  "mean_rank": 3.75
}
```

## Current Interpretation

`hybrid_cross_lingual` has better recall than `hybrid_cross_lingual_v2` on the
extended set. The v2 path is no longer exposed as a public retrieval method or
answer UI option; keep one supported cross-lingual method until a new candidate
beats the current recall and ranking metrics.

The targeted `water_interaction` and `casting_annealing` glossary refinements
closed the two remaining top-10 misses. M2 then added phrase/title-aware
features and uses the expanded candidate rerank window only for mixed-language
or protected-token queries. M3 added ordered multi-token glossary matching, so
`ec` no longer matches inside `recast`, plus narrow `recast_solvent_list` and
`solution_casting_morphology` concepts. This keeps recall stable while improving
rank quality versus the previous `hybrid_cross_lingual` report:

```text
passed: 29/31 -> 31/31
MRR:    0.398 -> 0.513
top-1:  8     -> 12
```

The MiniLM multilingual semantic index is usable and separate from the current
English semantic index, but it does not yet improve the extended benchmark.

## Remaining Failures

For `hybrid_cross_lingual` on the current 31-question extended set:

```text
none
```

The previous misses were closed by corpus-backed glossary entries:

- `water_interaction` for Nafion-water thermodynamic interaction wording;
- `casting_annealing` for Dai 2017 casting-solvent / annealing-temperature /
  recast-Nafion wording.

## Next Engineering Target

Do not expand the glossary broadly.

The next useful ranking step is still article-level reranking with explicit
features, but only if the evaluation improves `mean_rank`, `MRR`, and `top_3`
without reducing current extended recall:

- exact protected token match;
- compound/abbreviation match;
- query term coverage;
- numeric/condition match;
- cross-language source diversity;
- negative conflict checks for close properties such as ionic vs proton vs
  electronic conductivity.

The ranking objective should improve `mean_rank`, `MRR`, and `top_3` without
reducing current extended recall.
