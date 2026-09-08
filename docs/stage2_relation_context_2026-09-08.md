# Stage 2: necessary experimental context, 2026-09-08

## Changed

Added `app/generation/relation_requirements.py` and integrated a veto into
`assess_evidence_adequacy`. The new rule applies only to dependency questions
explicitly mentioning (1) mixture composition and conductivity, or (2) mixing
temperature, swelling, heating and cooling. Other questions retain the previous
decision logic. English and Russian query cues are recognized.

For composition questions, at least one evidence fragment must include conductivity,
mixture and a composition-series cue. For cycle questions, one fragment must include
mixing temperature, swelling/solvent uptake, heating and cooling. Cues cannot be
assembled from separate evidence items. Unicode ligatures, whitespace and PDF
line-end word hyphenation are normalized only for this matching operation; source
text and PDFs remain unchanged.

Missing context vetoes both lexical and glossary-based acceptance with reason
`missing_relation_context`. Passing this check cannot independently authorize an
answer or override missing substances. Existing adequacy thresholds are unchanged.
Diagnostics include rule version, scope, required relations, matched/missing cues
per evidence index and indices meeting all necessary cues. The answer metadata,
retrieval evaluation and UI expose the additional `relation_requirements` field.
Retrieval ranking, selection, database schemas and original PDFs are unchanged.

## Tests run

- Full pytest: **414 passed**, one existing Starlette/httpx deprecation warning.
- Ruff on `app tests scripts`: passed. Mypy on `app`: passed, 71 source files.
- Live relation evaluation: all 11 fragments verified, zero integrity errors.
  Report: `data/exports/evidence_relation_context_eval_20260908.json`.
- Corpus manifest check against `data/exports/corpus_manifest_stage1_20260907.json`:
  match; no missing, extra or changed articles.
- Replay of 348 saved retrieval windows against `tmp/stage2_retention_after.json`:
  zero changed decisions and zero changed selections. **Zero questions triggered
  the new rule**; this verifies out-of-scope compatibility only. Replay artifact:
  `tmp/stage2_relation_context_replay.json`.

| Same development annotations | Before | After |
| --- | ---: | ---: |
| True accepts | 11 | 11 |
| True refusals | 12 | 20 |
| False accepts | 8 | 0 |
| False refusals | 5 | 5 |
| Agreement | 23/36 | 31/36 |

There are nine scientific cases, two languages and two adequacy modes, not 36
independent questions. All eight changed decisions are cross-lingual false accepts
for separate-solvent rows, background composition discussion, the out-of-scope
swelling statement and the fixed-temperature conductivity experiment. Lexical
decisions are unchanged. The new unit tests additionally exercise split evidence,
irrelevant leading evidence, line hyphenation, out-of-scope questions and veto
precedence over glossary coverage.

Reproduce the source-verified audit:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation.cli evidence-relations --output data/exports/evidence_relation_context_eval_20260908.json --check
```

`--check` returns **1** because five disagreements remain. This is not a successful
scientific acceptance run. The original baseline report is preserved separately.

## Limitations

This is a necessary-context heuristic, not entailment or experiment validation.
Rules were developed using these annotations; the improvement is not an independent
test result. The annotations themselves await independent scientific review.
Alternative wording can cause false refusals. Co-occurrence in a long fragment can
pass despite unrelated statements; negated, hypothetical or unperformed experiments
can contain all cues. The rule does not verify material identity beyond the existing
substance catalogue, numerical conditions, causal direction or contradictions.
It does not repair the five lexical false refusals or broaden candidate retrieval.

## Verdict

The scoped veto and diagnostics are implemented and tested. Independent in-scope
examples, particularly negations and alternative experimental descriptions, are
needed before claiming relation-validation quality. Stage 2 remains open.
