# Stage 2: local experimental links, 2026-09-08

## Changed

Error class: `unlinked_experimental_context`. A fragment can contain all requested
terms while its temperature, swelling and cycling statements concern different
experiments. The existing synthetic counterexample reproduced this false accept.

Inspected the checked-in source fragments `istomina_heating` and
`istomina_figure4` in `evidence_relation_cases.yaml`. They explicitly associate
mixing temperature with solvent uptake and uptake with heating/cooling. The
source-verified evaluation was run before and after the change. No new PDF visual
review or independent scientific annotation was performed.

Implemented **diagnostic-only** local links for the cycle question family:
temperature–swelling, swelling–heating, and swelling–cooling. Each pair is checked
within one eligible statement, with the existing exclusions for non-observations.
Pair matches may occur in different statements of the same fragment; they are
never combined across fragments. Composition questions do not acquire these links.

Relation diagnostics are now version **3**, with explicit policy
`diagnostic_only_not_adequacy_veto`. Fragment diagnostics add `local_links` and
`missing_local_links`; each link identifies matching statement indices. Relation
diagnostics add `local_link_candidate_indices`. Indices refer to normalized
statement segmentation, including gaps left by excluded statements, not PDF
offsets. Existing source text and traceability remain intact.

The candidate veto was **rejected** after exposing a new false refusal. Production
`matching_evidence_indices`, `missing` and adequacy decisions retain version 2
semantics. No ranking, selection, thresholds, database schema or extraction change
was made.

The stress runner now supports `--local-links-candidate` for offline evaluation.
Reports explicitly identify `decision_policy`, retain the actual production
decision under `actual`, and store the evaluated decision in `evaluated_adequate`.
Four additional synthetic association cases are tracked separately in
`evidence_relation_association_cases.json`; the original ten cases are unchanged.

## Tests run

Final results:

| Dataset | Production | Candidate veto |
| --- | --- | --- |
| Original 10 synthetic cases, agreement | 8/10 | 9/10 |
| Original false accepts / false refusals | 1 / 1 | 0 / 1 |
| Additional 4 association cases, agreement | 3/4 | 2/4 |
| Additional false accepts / false refusals | 1 / 0 | 1 / 1 |

The candidate rejects the valid pronoun reference in `pronoun_reference_observed`
because “This response” refers to swelling without repeating the term. It still
accepts `distinct_samples_with_local_links`, where individual links concern
different samples. These fixtures are authored development counterexamples, not
independent scientific gold or corpus prevalence estimates.

Source-backed relation evaluation: **31/36** before and after, zero integrity
errors; zero false accepts and five false refusals on the original annotation set.
The 36 decisions represent nine cases across two languages and two adequacy modes.
All quality audits below returned **1** under `--check`, correctly exposing
remaining disagreements.

```powershell
.\.venv\Scripts\python.exe -m scripts.stage2_relation_stress_audit --output data/exports/stage2_relation_links_final_20260908.json --check
.\.venv\Scripts\python.exe -m scripts.stage2_relation_stress_audit --local-links-candidate --output data/exports/stage2_relation_links_candidate_20260908.json --check
.\.venv\Scripts\python.exe -m scripts.stage2_relation_stress_audit --cases docs/evidence_relation_association_cases.json --output data/exports/stage2_relation_association_final_20260908.json --check
.\.venv\Scripts\python.exe -m scripts.stage2_relation_stress_audit --local-links-candidate --cases docs/evidence_relation_association_cases.json --output data/exports/stage2_relation_association_candidate_20260908.json --check
.\.venv\Scripts\python.exe -m app.evaluation.cli evidence-relations --output data/exports/evidence_relation_links_final_20260908.json --check
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/relation_links_final_tests_20260908
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
```

- Final full suite: **435 passed**, one existing Starlette/httpx warning.
- Focused relation tests: **32 passed**; eight cases added in this step.
- Ruff passed; mypy passed on 71 source files. `git diff --check` passed.
- Initial baseline reports: `stage2_relation_links_before_20260908.json` and
  `evidence_relation_links_before_20260908.json` in `data/exports/`.
- Intermediate `*_after_20260908.json` and `stage2_relation_association_20260908.json`
  reports describe the temporarily tested veto, not final production behavior.

## Limitations

Local word pairs do not resolve sample identity, conditions, anaphora, causality
or scientific entailment. Sentence splitting remains heuristic. Diagnostics do
not repair the remaining false accepts or paraphrase-related false refusals.
No fresh retrieval run, external generation, full-corpus statement annotation or
independent scientific acceptance was performed.

## Verdict

Keep the diagnostics and offline candidate evaluation; reject the local-link
production veto because it causes a demonstrated regression without solving sample
association. Stage 2 scientific acceptance remains open. Further relation gating
needs source-backed sample/condition and reference annotations, not additional
word-pair constraints. Stage 3 numeric-extraction auditing may begin under the
roadmap's existing parallel-audit allowance; it must not be reported as closure
of stage 2 or as approval of generated scientific comparisons.
