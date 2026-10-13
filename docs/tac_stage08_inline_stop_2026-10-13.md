# TAC stage 08: inline stop-word boundary repair

Date: 13 October 2026, Asia/Yekaterinburg. Scope: the same frozen 33-document
development snapshot, including the duplicate Welch upload. This is an isolated
experimental extractor change, not production indexing or scientific admission.

## Changed

Updated `scripts/tac_experiment.py` to `tac_section_proposals_v0.7`. On the original
Nagasubramanian 2011 PDF, page 6, the text layer encodes most words as separate
lines. The standalone extracted word `results` within `We believe that these
results ...` matched the Results stop heading. A second inline `results` occurs
later in the same paragraph. This was a false section boundary, not a missing
page or a cross-column continuation problem.

The new rule applies only while Conclusions is active, only to the bare academic
words `results`, `discussion`, `methods`, `introduction` and `experimental`, and
only when mapped PDF geometry proves adjacency to preceding regular text on the
same physical row. It requires contiguous exact source offsets, matching regular
typography, nearby horizontal positions and matching vertical positions. A
derived whitespace-folded row is checked against the existing STOP pattern so
fragmented unbold composite headings, such as Materials and Methods, still stop
the section. Stored evidence is never normalized or rewritten. The tolerances
follow the existing front-matter same-row matching rules.

Unknown geometry, bold text, numeric-only preceding fragments, different rows,
distant columns, source gaps and mismatched font sizes retain the conservative
boundary. Each skipped false stop emits an explicit diagnostic with page and
offset. No filename, article identity or manually chosen cutoff is an extractor
input. The experimental output schema stays unchanged apart from its algorithm
version.

Exactly one TAC field changed: Nagasubramanian Conclusions, original layer on
PDF page 6, from `[207, 1670)` to `[207, 2175)`, adding **505 source characters**.
Both paragraphs now end before Acknowledgements. The full original PDF page was
rendered with Poppler and visually inspected; the output equals the exact frozen
page slice, preserves the previous quote as a prefix, and ends at the observed
administrative heading. No other T/A/C proposal changed.

Final review table:
`output/tac_stage08_20261013/ARIADNE_TAC_stage08_final_v02_2026-10-13.html`.
It contains all 33 documents, all eight agreed columns, full expandable TAC text,
Terms proposals, local original-PDF links, source diagnostics and one changed-cell
badge with the previous Conclusions text. Earlier stages and stage08 development
iterations remain separate; only the files ending in `final_v02` are the delivered
stage08 inputs.

## Results

- Coverage remains T **33/33**, A **30/33**, and any C evidence **30/33**, including
  the previously labelled summary passages. Metadata articles are identical to
  stage06, with **91 filled Authors/Journal/Year values**.
- Only Nagasubramanian C received a new assistant boundary assessment. The other
  **98 field assessments** were carried from stage06 after exact proposal checks.
  The development audit now has **87 pass, 6 boundary errors, 1 missed field and
  5 structural exclusions**, across 99 slots / 94 applicable slots. This is not an
  independent accuracy estimate or human acceptance.
- Terms remain `tac_term_candidates_v0.3`: **377 proposals / 1,087 exact evidence
  occurrences**. Thirty-two article outputs are identical to stage07; the
  Nagasubramanian row was regenerated against the expanded C span and its updated
  boundary assessment. Counts alone say nothing about scientific keyword quality.
- Frozen replay on the unchanged 46 development questions exactly matches the
  entire saved stage06 summary: production and expanded-pool controls **46/46**,
  TAC-only **42/46**, TAC-deep **44/46**, and TAC-deep with rescue **45/46**. This
  does not justify using TAC as a hard retrieval gate.

## Tests run

- Targeted extractor/front-matter/section-flow tests: **79 passed in 1.73 s**.
  Fourteen new synthetic cases exercise inline stop words, source fidelity,
  uncertain geometry, real headings and fragmented composite headings. They
  are regression fixtures, not independent scientific gold.
- Final full pytest: **865 passed, 1 warning in 8.05 s**. Log:
  `data/experiments/tac/20261013_stage08/pytest_full_v02.log`. The warning is the
  existing Starlette TestClient/httpx deprecation.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Final headless Edge QA: **33 rows, 8 columns, 99 assessment badges, one changed
  cell, 377 Terms, 1,087 exact quotations and 91 metadata values**. All **1,602
  local link targets** exist. Search, expansion and the combined problem filter
  work; no page errors. Final table and changed-row screenshots were visually
  inspected. The expanded source text retains the original word-per-line layout.
- Final profile/source/review/metadata/Terms validators passed. All **33 original
  PDF hashes**, saved reviewed render hashes and **88 production app file hashes**
  match the corresponding input/baseline evidence. The metadata, Terms proposer,
  front-matter and section-flow implementations and glossary are unchanged.
- Frozen retrieval replay and exact output comparison ran locally; no fresh live
  retrieval, model inference, database mutation or latency benchmark ran.

The first full pytest inside sandbox stalled and was interrupted. The successful
full runs used fresh basetemp directories outside sandbox; no success is attributed
to the interrupted run. Its cause was not established. Initial headless Edge QA
inside sandbox failed while creating its temporary profile; browser QA was retried
outside sandbox. Browser results are recorded separately beside the final HTML.

## Inputs and reproduction

- Git starting point: `a8d1e06`; clean tracked working tree before this patch.
- Before baseline: `output/baselines/20261013_before_tac_stage08/`, **302 files**,
  fingerprint `e890e3b1c3f8b6dc5e15aa3d7d8c0ef58044624417b2420c235f1e64a582df9a`.
- Corpus: `data/experiments/tac/20261012_v01/corpus.json`, SHA-256
  `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
- Previous profiles/review: stage06 `profiles_final.json` and
  `boundary_review_final.json`; previous Terms: stage07 `terms_final.json`.
- Final profiles, metadata, boundary review, Terms, changes, integrity checks and
  comparison reports: `data/experiments/tac/20261013_stage08/*final_v02*`.
- Review and output-check recipes: stage08 `recipes/`. These checks are not inputs
  to the extractor. Private literature text and local paths remain ignored by Git.

Re-extract into new destinations; do not overwrite earlier stage artifacts:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_experiment extract --snapshot data/experiments/tac/20261012_v01/corpus.json --output NEW_PROFILES.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_experiment replay --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles NEW_PROFILES.json --baseline-report data/experiments/tac/20261012_v01/comparison/report.json --questions docs/evaluation_questions_extended.yaml --output NEW_REPLAY_DIRECTORY
```

Render the saved assessed stage08 output to a new HTML destination:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261013_stage08/profiles_final_v02.json --metadata data/experiments/tac/20261013_stage08/metadata_final_v02.json --previous-profiles data/experiments/tac/20261012_stage06/profiles_final.json --boundary-review data/experiments/tac/20261013_stage08/boundary_review_final_v02.json --terms data/experiments/tac/20261013_stage08/terms_final_v02.json --output NEW_REVIEW.html --source-root D:/Nafion-RAG
```

## Limitations

This bounded rule does not reconstruct arbitrary PDF reading order or repair
damaged glyphs. It does not generalize to every possible inline heading word;
first-word-of-row ambiguities deliberately keep the prior behavior. Fragmented
composite headings retain the existing text-order cutoff at the matched fragment,
rather than implementing general heading reconstruction. The remaining five C
boundary errors, title-footnote error and missed Russian summary remain visible.
Recommendations in the dissertation still require an explicit scope decision.
Terms quality, independent section accuracy and Li-Nafion scientific record
acceptance remain open.

## Verdict

The first requested repair is implemented: the confirmed Nagasubramanian
truncation is resolved with exact source evidence and no observed changes to
other TAC fields, metadata or frozen retrieval metrics. Stage08 is available for
user review. Next bounded work is a separately recorded scientific review of
Terms relevance and omissions; production glossary/index integration is not
scientifically accepted by this patch.
