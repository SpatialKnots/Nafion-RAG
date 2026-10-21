# Records stage16: independent-pilot readiness and one-to-one evaluation

20 October 2026. S04/S13–S15 engineering preparation.
[Protocol](records/pilot_evaluation_protocol_v0.1.md).

## Changed

The user confirmed no independent annotator is currently available. Independent
scientific evaluation and chemist-time measurement therefore remain blocked by
an external prerequisite. This stage prepares auditable inputs/evaluation; it
does not replace the missing expert with assistant-authored gold or timed work.

Added `app/records/pilot_audit.py`, `app/records/pilot_evaluation.py`,
`scripts/records_pilot_evaluate.py` and 32 constructed test cases. The new audit
verifies a historical source-only packet, its complete artifact inventory,
source-content fingerprint, source-only bundles, exact stored-page regions,
selection audit, summary counts and original/selected PDF hashes. It retains
every document and exposes missing scientific prerequisites. No-hit documents
do not become negative scientific labels.

The new `records_pilot_reference_v0.1` supports multiple expected records per
case, explicit author/kind/exposure/scope declarations and per-record deferred
dimensions. Context files are SHA-bound and must equal the embedded source-only
context. Expected observations, identities and exact evidence are revalidated.
Unannotated empty cases are not confirmed scientific negatives. An independence
declaration requires a declared human and annotation before outputs; neither
claim is authenticated or accepted as automatic scientific proof.

`records_pilot_evaluation_v0.1` reuses the existing twenty-dimension exact
text/status/anchor/representation/linkage policy. It performs deterministic
maximum bipartite matching: one prediction per reference, one reference per
prediction. Complete agreements are maximized first; compatible deferred pairs
are added by augmentation, allowing exact ties to move without unmatching a
fully evaluable reference. Duplicate predictions cannot increase matched
reference count. Exact duplicate reference entries with changed IDs are rejected,
and duplicate linkage roles cannot disappear into a dictionary.

Unavailable/invalid predictions retain their expected counts and diagnostics.
Input/source identity mismatches stop evaluation. Precision/recall are null
when annotation/output is unavailable or any expected dimension is deferred;
recall also requires a declared exhaustive supported scope. Empty denominators
stay null. These are finite-reference agreement metrics, not automatically
scientific correctness or admission. Existing schemas, metrics, numeric rules,
source text, ingestion/retrieval and full-record editor logic are unchanged.

The protocol also defines a future counterbalanced human-time study, including
the complete reading/search/check/correction/export process, final-quality
comparability, failures and missing observations. The earlier 8–12-task/two-
chemist proposal remains a planning target. No participants, task completions,
timestamps, elapsed human time or labor savings were manufactured.

## Source-packet audit

Supplied snapshot: `data/experiments/records/pilot/stage01_20261014/`.
Verified source fingerprint:
`f133dcf1d95bf94d38f0d1cf49da24ca55082a42a8867e51f6f343fd84811a94`.

- 33 documents, 493 original-PDF/stored pages, 493 complete source regions;
- 33 distinct original/selected PDF paths verified in this packet;
- six lexical selection candidates, not six scientifically eligible publications;
- all 33 retain the packet's development-only exposure designation;
- scientifically eligible-publication count, independent reference and untouched
  work-level split remain unestablished;
- independent annotator unavailable, as reported by the user;
- zero human-time observations supplied to this audit; savings are null.

The 10–15-publication target is not fulfilled by lexical hits, supplements,
dissertations or PDF counts. A new random split of this exposed packet cannot
be described as untouched evaluation. This audit verifies the supplied snapshot;
it did not query the current database or establish scientific corpus suitability.

Output: [all-document source/readiness HTML](../output/records_stage16_20261020/cohort_v01/review.html),
`cohort_v01/report.json` and `manifest.json`. It includes complete expandable
source pages, local PDF links, search, recorded metadata and all blockers.

## Historical development replay

Froze the stage06 reference, its four saved runs and their batch artifact hashes
before the new comparison. The reference remains authored by the coding agent
with `needs_independent_review`. Its original fields, anchors, missingness and
34 deferred dimensions were not repaired or promoted to independent gold.

The existing full evaluator reparsed all four raw Responses artifacts offline.
Its summary remained identical: 21 matching dimensions, five mismatches and 34
deferred dimensions. Every restored candidate's records and source regions
matched its saved bundle. Regenerated run/timestamp/export-code metadata is not
claimed to equal the historical original.

The new one-to-one evaluator accounts for all four bounded cases and all three
expected/proposed positive records. It finds one compatible deferred pair and
two nonmatching prediction/reference pairs under the unchanged exact policy;
the empty bibliography result agrees with the finite development reference.
These disagreements include source-text boundary/status differences and are
not two independently established scientific errors. No complete reference
agreement is established. Both final precision and recall remain null because
34 expected dimensions are deferred; human-time savings remain null.

All outputs of the repeated new comparison are byte-identical, including
reference/prediction copies, HTML, JSON and manifest. Historical artifacts
retain their hashes. No new inference, external API request, database write,
annotation or review confirmation occurred. The stage15 user review store's
code context remains compatible because its files were not modified.

Output: [development comparison HTML](../output/records_stage16_20261020/evaluation_v01/review.html),
`evaluation_v01/report.json`, `manifest.json`, `repeat_v01/`,
`raw_replay_v01/`, `development_reference_v01.json`, `scope_v01.json` and
`replay_qa.json`. Private helper scripts remain under the stage16 output root.

## Tests run

- New targeted suite: **32 passed**, 7.61 seconds. Synthetic cases cover
  multi-record/reversed matching, duplicates, wrong values, deferred ambiguity,
  exact/deferred assignment ties, missing/invalid outputs, unannotated scope,
  caller-declared independence, changed context/PDF identities, source-packet
  tampering, HTML escaping and complete artifact/scope preservation.
- Full regression: **1463 passed**, one existing Starlette/httpx deprecation
  warning, **168.41 seconds**. Run outside the sandbox because HTTP tests stalled
  in earlier stages. JUnit:
  `output/records_stage16_20261020/pytest_full_v01.xml`.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 114 source files.
- Independent brute-force assignment enumeration verified the complete-first,
  total-compatible matching priority on **1024 constructed 3×3 graphs**. This is
  an algorithm test, not independent scientific annotation or measured material
  data. Result: `matching_exhaustive_qa.json`.
- Actual frozen source-packet audit, old raw-response replay, saved-candidate
  equality checks and two identical new evaluation exports passed as above.
- CLI help executed. `git diff --check` passed, with existing LF/CRLF notices.
- Static HTML/artifact postflight verified all 33 document sections, 493 exact
  source-page texts and PDF/page link targets, plus four comparison cases and
  eight distinct comparison PDF/page links. Input/output/PDF hashes matched;
  deferred counts and null final rates remained intact. `static_qa.json` records
  these checks separately from browser acceptance.

An additional source/runtime snapshot was created and checksum-verified at
`output/records_stage16_20261020/baseline_final_v01/`: 454 selected source files,
18 untracked within that selection, fingerprint
`bb5bf01d70d668eb3675d15be988151425c7f109a7e1f1e60f429b4d92ee0476`.
The snapshot includes a source ZIP, environment metadata and observed installed
dependency pins; no missing dependencies or installed-version requirement
mismatches were reported. This freezes the implemented source state, not a clean
installation or a public release. This additional snapshot/postflight reporting
was appended afterward; application code and tests did not change.

An initial targeted pass had 31 cases before adding the exact/deferred tie
counterexample. Initial typing/lint errors were corrected before the final
32-case and full runs. No passing result is inferred from those failed checks.

Browser interaction with these file-based reports was not attempted: earlier
file-URL navigation was explicitly prohibited. Static artifact verification is
separate from visual/click acceptance. The existing localhost editor was not
changed to serve these reports as a workaround.

## Reproduction

Use fresh paths; existing outputs are never overwritten:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_pilot_evaluate audit --packet data/experiments/records/pilot/stage01_20261014 --annotator-availability unavailable --output-dir output/records_pilot_audit_new
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_pilot_evaluate evaluate --reference output/records_stage16_20261020/development_reference_v01.json --prediction sanginov_abstract=data/experiments/records/pilot/stage06_20261020/runs/sanginov_abstract/candidates.json --prediction sanginov=data/experiments/records/pilot/stage06_20261020/runs/sanginov/candidates.json --prediction kayumov=data/experiments/records/pilot/stage06_20261020/runs/kayumov/candidates.json --prediction istomina=data/experiments/records/pilot/stage06_20261020/runs/istomina/candidates.json --output-dir output/records_pilot_evaluation_new
```

Saved source/reference/model outputs are private and absent from a clean clone.
Current runtime/source fingerprinting does not prove clean installation,
offline model extraction or portability to another workstation.

## Limitations

Independent scientific evaluation, eligible work grouping/split, full-article
record detection/recall, calibrated scientific checks and expert-time study
remain open. No actual B/C/D scientific comparison or ≥30% savings claim is
supported. The saved reference is exposed and provisional; exact coordinate
agreement cannot establish sample/condition entailment. Protocol targets and
caller provenance declarations do not count as completed experiments.

## Verdict

Source readiness audit, one-to-one evaluation machinery and a reproducible
development replay are delivered. The independent pilot itself is not complete:
an eligible cohort, independent chemist/reference and comparable human-time
observations are still required. No new scientific-accuracy or MVP-completion
percentage is claimed.
