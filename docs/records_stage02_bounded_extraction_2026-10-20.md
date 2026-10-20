# Records stage02: bounded adapter and full-record evaluator

Date: 20 October 2026. Project: ARIADNE. Engineering implementation is complete; usable model extraction and scientific acceptance are not established.

## Changed

Preserved earlier work in `0101a9c` (automatic TAC/Terms) and `4e8660a` (source-only records stage01). Before editing, froze 383 source files with fingerprint `041f30f4216edfd2fa3deba63c10aac836f2b500ae30461eeafce40e638e2cf9`. The local watcher config remains uncommitted and has a separate copy at `output/records_stage02_20261020/terms_pipeline_config.before.json`.

Added `app/records/extraction.py`, `app/records/full_evaluation.py`, `scripts/records_extract.py`, 36 synthetic test cases and the [bounded protocol](records/bounded_record_protocol_v0.1.md). A fixed task selects zero or one measurement in one article. Each proposal declares sixteen observations, quantity representation and unique linkage roles. Quotes must match unique exact occurrences. Independent single-field calls are not assembled into a record. Existing candidate schema, scientific units, production ingestion/OCR/chunking/retrieval, database and facts are unchanged. Candidates remain `needs_review`, with Li-ion confirmation `not_reviewed`.

The evaluator reparses raw responses and binds input, task, request and runtime declaration. It compares twenty dimensions, separating raw agreement, source anchors, representation, linkage proposals, omissions, extras and abstentions. Deferred dimensions prevent full-record agreement. Missing artifacts remain unavailable in the denominator; mismatched existing checksums stop evaluation.

## Frozen development experiment

Reused three exposed S06 source contexts and their exact task strings. Reference expectations come from existing assistant-authored ten-field annotations, frozen before new inference: two expected records, one bibliography negative, and nine deferred dimensions per positive record, including all three linkage roles. This is neither independent gold nor holdout. Only the first historical raw-answer variant is used; legitimate alternatives require explicit review.

All runs used the installed Qwen2.5-3B-Instruct Q4_K_M: CPU 2 threads, context 8192, `max_tokens=4096`, seed 42, temperature 0, transport timeout 300 s. Executable/model SHA-256 checks passed. The server listened on `127.0.0.1:18087`; the inference runner did not read reference answers. No automatic retry or outcome-dependent budget change was performed.

| Case | Task scope | Observed result | Seconds |
| --- | --- | --- | ---: |
| Sanginov | Table 2 cell with footnote d | `transport / TimeoutError: timed out` | 300.179 |
| Kayumov | Bibliography-only context | `transport / TimeoutError: timed out` | 300.086 |
| Istomina | Prior-work range in reference [26] | `transport / TimeoutError: timed out` | 300.120 |

There are zero integrity-valid cases and three unavailable cases. Both expected records and all forty expected dimensions remain unavailable in the denominator. No successful record, correct model abstention or scientific accuracy is claimed. Missing responses are not scientific negatives. Server logs contain intermediate average generation rates around 6–8 tokens/s; no completed content is available to assess field/linkage quality or establish the sole cause of failure. A different budget, format or model has not been validated. The owned model process was stopped after the experiment.

## Artifacts and reproduction

- Frozen inputs/tasks/reference/pre-inference manifest: `data/experiments/records/pilot/stage02_20261020/`. Reference SHA-256: `ecf6efdae49f3afe551a733580a4af4f0876c22b4f6204971bc240a950dfda01`.
- Real attempts: `data/experiments/records/pilot/stage02_20261020/runs/{sanginov,kayumov,istomina}/`. Input, request, runtime declaration, manifest and result remain available. No complete response or candidates file exists.
- [Final JSON](../output/records_stage02_20261020/evaluation/report.json), [HTML of all three cases](../output/records_stage02_20261020/evaluation/review.html), separate repeat at `output/records_stage02_20261020/evaluation_repeat/`.
- [Artifact verification](../output/records_stage02_20261020/artifact_verification.json), [verification summary](../output/records_stage02_20261020/verification_summary.json), runtime/server/cleanup diagnostics in `output/records_stage02_20261020/`.
- `baseline_ready/`: 388 files before the final missing-metadata handling fix. Import of both new modules from that source copy passed using the existing venv. Initial import generated sixteen `.pyc` files; only those generated cache files were removed, then `-B` import and checksum verification passed. Current final source snapshot: `output/records_stage02_20261020/baseline_final/`, identified by its manifest.

Commands are in the [protocol](records/bounded_record_protocol_v0.1.md). Offline evaluation needs frozen files and the installed Python environment, without a running model/database. Both final evaluations returned exit code 1 because responses were unavailable, while writing complete reports. Summary and case content repeated identically; whole-report timestamps/code metadata are not claimed byte-identical. The pre-inference protocol copy is unchanged; reproduction commands and missing-metadata clarification were added only to current documentation.

## Tests run

- Original baseline: **1054 passed**, one existing Starlette/httpx warning, 83.54 s. Sandbox run stalled after five tests and was interrupted; only the separate unrestricted run is counted successful.
- Final full regression: **1090 passed**, one existing Starlette/httpx warning, 103.76 s. The 36 new tests use synthetic sources, not scientific measurements or real inference.
- Intermediate final targeted records suites: **128 passed**, 10.30 s. Four subsequent missing-metadata cases were then included in the final full run.
- Ruff `app tests scripts`: passed. Mypy: 97 app files, passed.
- Three actual loopback inference attempts: all timeout, not successful extraction tests.
- Static HTML/artifact checks: all three cases, eight exact source regions, eleven expandable details and eight existing PDF/page targets; all three PDF hashes, frozen input/task/reference/protocol bindings and captured artifact hashes verified. Repeat evaluation has identical summary/cases.
- Browser rejected the local `file://` URL under its security policy. No workaround was used; visual layout, clicks and individual PDF opening are not verified.

## Limitations

Whole-article enumeration, table-cell/layout parsing, independently accepted work grouping, a 10–15 eligible-publication cohort, independent annotation, scientific acceptance and production integration remain open. The earlier pool has six lexical document candidates, including a supplement and dissertation; that is not six independently eligible publications.

Synthetic tests validate engineering behavior, while real attempts validate failure preservation only. The generic CLI records a caller-declared runtime and does not independently attest the current server. No clean dependency installation, full offline recovery or new live database/retrieval benchmark was run. Private source packets are excluded from Git and absent from a clean clone.

## Verdict

Baseline preserved; bounded adapter, full-record evaluator, CLI and reproducible review artifacts delivered. Local model extraction is not accepted: three timeouts, zero complete results. Next bounded experiment must establish completion within a measured runtime budget and assess the model-facing format while retaining this negative baseline. Independent scientific reference and corpus eligibility remain separate open tasks.
