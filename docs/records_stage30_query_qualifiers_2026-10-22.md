# Stage30: necessary query qualifier checks

22 October 2026. Version `query_qualifiers_v0.1`.
[Prospective protocol](records/query_qualifiers_protocol_v0.1.md),
[constructed references](records/query_qualifiers_cases_v0.1.json),
[inherited stage29 observations](records_stage29_query_packet_2026-10-22.md).

Changed:

- Implemented a separate necessary-mention assessment for explicit material
  phrases, article surname/year forms and a finite RU/EN conductivity/DSC/TGA/EIS
  mention catalogue. There are no hardcoded observed surnames or missing materials.
  Raw question/evidence offsets remain exact; matching uses token-local NFKC/case
  folding and declared separator rules. It does not rewrite stored source text.
- All recognized requirements must occur within one selected article. Literal
  material phrases cannot be assembled from different chunks or sentences. Article
  identity is checked against bound author/year metadata, never references, body
  text, filenames or guessed titles. Missing metadata remains `unknown_metadata`.
- Added an explicitly injectable `QualifierGuardProvider`. After the existing
  adequacy gate, it can abstain before calling the wrapped provider. Allowed calls
  preserve original evidence/options; a failed old gate can never be upgraded.
  Constructed integration tests exercise the existing `answer_question` path.
- Added frozen prepare/export CLI and searchable read-only HTML for all four
  inherited contexts and all 24 constructed references. Existing production
  routes/default provider, adequacy thresholds, retrieval, selection, database,
  extraction and old packet schemas remain unchanged. This version is opt-in.

## Frozen offline comparison

The code, protocol, tests, constructed questions/expectations and inherited
context/source bindings were frozen **before** the real comparison. No subsequent
rule, alias, reference or question tuning was performed. The four old contexts
remain exposed observations. Constructed references are developer-authored
necessary-mention cases, not independent scientific answer labels or held-out data.

| Observed question | Old gate allowance | New necessary-mention allowance | Observed diagnosis |
| --- | --- | --- | --- |
| conductivity_protocol | yes | yes | Conductivity mention found; equilibration and full question entailment are not assessed |
| dsc_protocol | yes | no | Author/year metadata unknown; DSC mention not found in selected evidence |
| preparation_atmosphere | no | no | Original insufficiency rejection preserved |
| absent_material | yes | no | Exact `Mars regolith` phrase not found; conductivity alone cannot replace it |

The allowance count changes from **3 to 1** in these saved contexts. This does not
establish two independently measured scientific errors or a precision improvement.
The remaining allowance is necessary mention coverage only. All **19 baseline
Evidence objects**, source registries, prompts and diagnostics remain unchanged.
Stage29 packet files still verify and retain their complete-page prohibition:
**0/4 network eligible**. The new lexical guard does not waive that prohibition.

All **24/24 constructed expectations agree**. They cover missing/positive material
phrases, substring/split/cross-article failures, same-article mention aggregation,
aliases/Unicode, multiple method requirements, unknown or conflicting bibliographic
metadata, RU forms, no automatic material translation, old refusals and unresolved
markers. The explicit negation case deliberately passes a *mention-only* check;
it demonstrates that the presence of `DSC` does not prove DSC was performed.

No new retrieval, query embeddings, database lookup/write or generative API call
was performed for this comparison. Metadata absent from stage29 was not invented
or filled from a changing live database. No answer, measurement or claim was created.

Tests run:

- Targeted constructed/software tests: **50 passed**, no failures/errors/skips;
  `pytest_target_v03.xml`. This includes wrapper abstention/delegation, explicit
  integration with `answer_question`, baseline-refusal preservation, exact raw
  spans, immutable inputs and frozen artifact drift/exclusive output.
- Full regression: **1977 passed**, one existing Starlette/httpx deprecation
  warning, no failures/errors/skips; `pytest_full_v01.xml`. It ran outside the
  sandbox using dedicated temporary/cache directories, in **328.48 seconds**.
- `ruff check app scripts tests`: passed. `mypy app`: passed, **140 source files**.
  Initial import/type/lint diagnostics were fixed before freezing. The first test
  attempt had six temporary-directory setup errors; the next found a conflicting
  manifest-hash check defect. Both were corrected before the successful frozen
  implementation; the earlier results remain saved.
- Two real offline exports are byte-identical across report, HTML and manifest.
  **821** preparation and **824** per-export bindings verify. Postflight checks
  resolve **46 query spans**, **131 evidence mention occurrences** and **3 metadata
  occurrences** against exact raw text and article/citation/page identities.
  Repeated occurrences are not distinct experiments or independent successes.
- Static HTML: four observed cards, 24 constructed cards, one search input, no
  forms and **37** existing artifact/PDF links. Browser acceptance remains
  unverified after the prior local-file navigation rejection.
- Exact configured-credential scan across **8** prepared/export artifacts: zero
  matches. The credential was not printed. All original PDFs, inherited index/code
  bindings and old stage29 packet exports verify unchanged.

Limitations:

- Finite grammar and catalogue, not general chemical NER or query understanding.
  Unrecognized selectors, paraphrases, morphology, relations, units, conditions
  and unsupported query tails remain unvalidated. Outside recognized scope, the
  old allowance is retained explicitly; an empty evidence set is always blocked.
- Literal phrases can over-reject translated, inflected or complex expressions.
  Phrase capture ends at declared punctuation. No composition identity or scientific
  equivalence follows from lexical matching. No unmeasured generalization claim.
- Same-article mention aggregation is not same-sample or same-experiment linkage.
  Negated, hypothetical or cited-work mentions may pass necessary coverage. Origin,
  applicability, measurement existence and answer entailment remain unverified.
- Article metadata is externally supplied source data, not independently validated
  by this module. Offline unknown metadata cannot establish article mismatch or
  corpus absence. No mandatory per-Term manual review is introduced.
- The guard is not the production default; current UI/API responses do not expose
  its assessment automatically. Explicit callers can inspect `provider.assessment`.
  No new provider support, scientific precision/recall, cost/time saving, browser
  rendering, clean install or other-machine restore is claimed.

Verdict:

The bounded qualifier contract and offline comparison are complete. Explicit
injection blocks the two observed missing-qualifier allowances without changing
the historical gate or dropping source evidence. It is a necessary check, not
scientific sufficiency or permission to send the stage29 full-page packets.
Before default activation, integrate its diagnostics into an explicit answer
preparation mode and assess additional independently referenced question families;
retain fail/unknown evidence and the separate complete-page guard.

## Local artifacts and reproduction

Root: `output/records_stage30_20261022/`.

- `prepared_v01/plan.json`, `manifest.json`: pre-comparison input/reference/code
  snapshot, including inherited traces and explicit missing metadata status.
- `run_v01/review.html`, `report.json`, `manifest.json`: all 28 cases.
- `run_repeat_v01/`: byte-identical second offline export.
- `postflight_v01.py`, `postflight_v01.json`: spans, source/manifest hashes, original
  baseline preservation, old packet integrity, static links and credential QA.
- `pytest_target_v01.xml`, `pytest_target_v02.xml`: preserved early diagnostics;
  `pytest_target_v03.xml`: successful targeted run.
- `pytest_full_v01.xml`: full-regression result, separate from scientific evaluation.
- `baseline_final_v01/`, `final_qa_v01.json`: source/dependency snapshot and final QA,
  excluding private corpus, database, model weights, run outputs and credentials.

Offline re-export to a fresh directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.query_qualifiers export --prepared output/records_stage30_20261022/prepared_v01 --output-dir output/records_stage30_new_export
```

This makes no API or retrieval call. The clone alone lacks private predecessor
artifacts required for this particular inherited comparison. Exclusive directories
prevent overwriting the original results.
