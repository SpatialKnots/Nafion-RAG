# Stage 2: explicit non-observation statements, 2026-09-08

## Changed

Error class: `non_observational_relation_context`. The lexical adequacy gate
counted experimental cues even when a sentence explicitly said that the experiment
was not performed or presented a hypothesis. The synthetic stress audit reproduced
this class before the change; its labels are development expectations, not new
corpus evidence. Existing source-backed relation annotations are the compatibility
check, not evidence of the prevalence of this error class.

`app/generation/relation_requirements.py` now excludes cue-bearing sentences with
explicit unperformed-measurement or hypothesis markers before checking necessary
context. The scope remains the same two question families. Matching uses normalized
text; stored evidence and original PDFs remain unchanged. A separate observed
sentence or fragment can still supply context. A measured null effect is retained:
“did not affect” is not treated as “did not measure”.

Relation diagnostic version is now **2**. Each fragment retains `matched` and
`missing`, and adds `raw_matched` plus `excluded_statements` with sentence index,
normalized text and exclusion reasons. These are matching diagnostics, not source
offsets. The existing `missing_relation_context` refusal and service metadata
propagation remain in use. Retrieval scoring, evidence selection, glossary rules,
database schemas and adequacy thresholds are unchanged.

## Tests run

Source baseline: `4656690`; stress fixtures and runner added in the preceding work
remain unchanged for this before/after comparison.

```powershell
.\.venv\Scripts\python.exe -m scripts.stage2_relation_stress_audit --output data/exports/stage2_relation_statement_after_20260908.json --check
.\.venv\Scripts\python.exe -m app.evaluation.cli evidence-relations --output data/exports/evidence_relation_statement_after_20260908.json --check
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/relation_statement_tests_20260908
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json
```

Both audits were also run before editing production code, using corresponding
`*_before_20260908.json` paths. Results:

| Dataset | Before | After |
| --- | --- | --- |
| Ten synthetic lexical stress cases: agreement | 4/10 | 8/10 |
| Synthetic false accepts / false refusals | 5 / 1 | 1 / 1 |
| Original source-backed relation decisions: agreement | 31/36 | 31/36 |
| Original false accepts / false refusals | 0 / 5 | 0 / 5 |

Both `--check` commands returned **1** before and after: disagreements remain.
Original annotation integrity errors: zero in both runs. Those 36 decisions
represent nine cases, two languages and two adequacy modes, not 36 independent
scientific questions.

- Focused relation tests: **24 passed** (13 added cases), including glossary-veto
  precedence, RU/EN non-observations, observed null effects, cue borrowing from an
  excluded sentence, independent supporting evidence and unchanged question scope.
- Full suite: **427 passed**, one existing Starlette/httpx deprecation warning.
- Ruff passed; mypy passed on 71 source files.
- Corpus manifest matched; no missing, extra or changed articles.
- Replay of 348 saved retrieval windows: zero changed adequacy decisions and
  zero changed selections against `tmp/stage2_retention_after.json`. Output:
  `tmp/stage2_relation_statement_replay.json`. None of these questions triggered
  relation requirements; this checks out-of-scope compatibility only. Reproduction:

```powershell
.\.venv\Scripts\python.exe -m scripts.stage2_adequacy_replay tmp/stage2_relation_statement_replay.json tmp/stage2_grouping_audit.json tmp/stage2_grouping_user.json tmp/stage2_grouping_cross_lingual.json --baseline tmp/stage2_retention_after.json
```

## Limitations

This is a narrow veto, not a measurement classifier or entailment model. Explicit
patterns do not cover all hypotheses, modality, passive forms, abbreviations or
negations. Sentence segmentation is heuristic. A sentence combining a historical
hypothesis with its confirmation can be rejected; an unrelated negative clause in
the same sentence can also cause a false refusal. Conversely, cues from unrelated
positive statements can still combine within one fragment.

The remaining synthetic false accept is exactly that unrelated-experiment case.
The paraphrased observation still produces a false refusal. These problems were
not patched by adding fixture-specific synonyms or globally rejecting negation.
Independent source-backed examples of the new error class and scientific review
remain necessary. No external generation or new retrieval-ranking evaluation was
performed. Existing annotation quality and corpus-wide answer correctness are not
established by these checks.

## Verdict

Implemented a scoped safeguard with explicit diagnostics and passing software
checks. Four targeted synthetic false accepts are removed without changing the
original relation-audit results. Scientific acceptance remains open. Next work:
source-backed evaluation of statement status and association with the same
experiment, including alternative wording and observed null effects.
