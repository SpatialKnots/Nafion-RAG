# Stage 2: synthetic relation stress audit, 2026-09-08

## Changed

Added ten explicitly synthetic development cases in
`evidence_relation_stress_cases.json` and the reproducible runner
`scripts/stage2_relation_stress_audit.py`. Cases are authored counterexamples,
not quotations, corpus fragments, independently reviewed annotations or a held-out
scientific acceptance set. Their expected labels require observed experimental
support; a measured null effect counts as support, an untested hypothesis does not.

The runner exercises the actual lexical evidence-adequacy gate, saves all input
texts, decisions and diagnostics, and hashes the fixture and three relevant
implementation files. It performs no retrieval, database access or generation.
Production gate behavior and thresholds are unchanged.

## Tests run

On source baseline `4656690` with the added audit files:

```powershell
.\.venv\Scripts\python.exe -m scripts.stage2_relation_stress_audit --output data/exports/stage2_relation_stress_20260908.json --check
.\.venv\Scripts\python.exe -m pytest tests/unit/test_relation_requirements.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check scripts/stage2_relation_stress_audit.py
```

- Audit: 10 cases, 4 agreements, 5 false accepts, 1 false refusal. All ten
  questions triggered a relation requirement. `--check` returned **1**, correctly
  signaling disagreement; this is a failed support-quality check.
- Existing relation-requirement tests: **11 passed**.
- Ruff: passed.

False accepts were the EN composition experiment explicitly not performed, EN
composition hypothesis explicitly untested, EN and RU cycle experiments explicitly
not performed, and unrelated experiments within a single fragment. All received
`sufficient_distinctive_term_coverage`. The paraphrased positive cycle experiment
was refused with `missing_relation_context`.

Positive observed relations, the observed null effect, and the split-fragment
negative control agreed with labels. The null-effect example is essential:
rejecting every sentence containing negation would introduce a new false refusal.

## Limitations

This measures deliberately constructed lexical-gate failure modes, not their
frequency in the local corpus or generated answers. No new PDF review, retrieval
evaluation, glossary-mode evaluation, full test suite or external model run was
performed. One Russian negative example does not establish bilingual coverage.
Fixture expectations are development labels awaiting independent review.

## Verdict

The previous zero-false-accept result on the nine original development cases does
not generalize to these synthetic counterexamples. Stage 2 remains open. The next
implementation must distinguish reported measurements, unperformed experiments,
hypotheses and measured null effects, and link cues to the same experiment.
Do not patch this by globally rejecting negation or adding query-specific synonyms.
Before accepting a production change, evaluate source-backed examples and compare
both existing relation annotations and these stress cases, reporting remaining
false accepts and false refusals separately.
