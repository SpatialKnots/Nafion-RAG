# Component-context v0.3: execution notes

2026-11-03, Asia/Yekaterinburg. Original failed/partial attempts are preserved.

- Initial read-only source inspection under the Windows cp1251 console raised
  UnicodeEncodeError on a Greek character. Repeated with Python `-X utf8`;
  source data were not changed.
- preflight_v01.xml:1 failed/87 passed. An explicit same-sentence component
  declaration's `solvents` word was counted as an independent variable.
  Before corpus measurement, distinguish only the literal solvent word INSIDE
  the exact accepted declaration of a single named ratio. Independent variables
  still block. Added context-negation and negative-observation controls before
  measurement. This run also retained two pytest cache permission warnings;
  later runs disable the cache provider explicitly.
- preflight_v02.xml:91 passed. preflight_v03.xml:96 passed. tests_v01.xml:
  274 passed across12 affected test modules, including96 new tests. These are
  overlapping executions, not additive distinct test counts.
- Ruff initially reported I001 on the verifier import block. Its formatter
  split an aliased import, exposing E402 on the newly split line. Added the
  same intentional-import `# noqa: E402` annotation as the neighboring imports.
  All five new Python files subsequently passed Ruff.
- review_v01 started concurrently with the final import-comment correction.
  The runner froze the verifier BEFORE that correction. Exact snapshot diff
  shows only the added `# noqa: E402` comment; analyzer/control/protocol logic
  did not change after measurement. Do not relabel this snapshot as current or
  rewrite its frozen_inputs.json. Preserve its partial files and failure;
  execute a new review_v02 with all current hashes consistently frozen.
  Actual v01 outcome: all328 per-record files were written; end-of-run
  `files.verify(bindings)` raised `Frozen input changed:
  D:\Nafion-RAG\scripts\verify_component_context_review.py`. No final report,
  HTML or manifest was declared successful for v01. The failed328 replays are
  separate from the final successful run's count, never pooled as independent
  scientific observations.

No original outputs, earlier analyzers, PDFs, runtime/gate or live budgets were
changed. The new corpus candidate must not be tuned after measured outcomes.

## Separately versioned v0.4 continuation

- v0.3 review_v02 completed328 actual trace/status replays and1968 repeated
  top-level diagnostics. Raw corpus outcomes unchanged:20/36 partial sets,
  39 observations/one unique relation, zero complete sets or newly bound
  context edges. Its static/graph QA passed:329 bindings,1806 corpus graph
  spans,2790 graph spans including controls/parents,88 context/rejection spans,
  33 TAC rows/eight columns/41 local PDF links and six fresh real windows.
- Two post-measurement adverse probes were then run and saved separately in
  posthoc_adverse_probes_v01.json. Both incorrectly gave textual completeness:
  a joined `alphaandbeta` delimiter and `absence of evidence for the effect`.
  Original v0.3 code/results and these adverse results remain unchanged.
- Before implementing v0.4, wrote the separate v0.4 protocol; added eight
  exposed/constructed negative variants. v0.4 requires standalone word
  delimiters and blocks explicit RU/EN evidence-absence cues. No numerical
  owners or runtime permissions are introduced.
- A source-generation patch initially failed to find the anticipated renamed
  test-file line. Inspected actual file names and corrected the new runner
  before v0.4 tests/measurement; no previous sources/results were changed.
- v0.4 preflight:9 tests passed; Ruff four v0.4 files passed. These tests include
  all139 constructed controls and six real windows through the actual controls
  runner, plus preservation of the two original v0.3 false results.
- The full v0.4 affected suite and corpus run are separately recorded; earlier
  attempts are not added to final distinct-test or independent-evidence counts.

Final v0.4 outcome:

- tests_v04.xml:283 tests passed(105 introduced in this iteration); Ruff all9
  new Python files passed. No full-suite or mypy execution claimed.
- review_v04:328 actual service replays/1968 repeated diagnostics, exact v0.2
  matches,292 outside-scope baselines preserved;20/36 partial sets/39 observations
  of one unique relation;0 newly bound context edges/complete requirements.
- qa_v04.json passed:338 bindings,33 PDF hashes/eight fresh reference windows,
  six fresh real windows,1806 corpus graph spans/2842 including controls+parents,
  92 context/rejection spans,33 TAC rows/eight columns/41 existing PDF links.
- Separate final read-only comparison of all48 old full-requirement expectations
  against v0.4 returned zero differences, including negative/condition controls.
  All338 current bindings and review_v04 manifest still matched after updates
  to the unbound project decision-memory/progress/roadmap documentation.
- Corpus candidate was not tuned after its results. No runtime rollout or
  independent scientific acceptance; no new DB/search/embedding/model/OAuth/
  native request/slots. Plan completion remains75%.
