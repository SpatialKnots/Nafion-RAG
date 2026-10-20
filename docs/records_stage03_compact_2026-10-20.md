# Records stage03: compact response on one real clause

Date: 20 October 2026. Development experiment, not independent scientific evaluation.

## Changed

Added explicit `records_compact_extraction_v0.1` in `app/records/compact.py` and `--wire-format compact` to the existing CLI. The new wire object has five fixed required keys: sample label, author property name, raw value/range, unit and temperature/range. Each contains an exact source substring or null. The old full format remains the default. Both formats use the existing loopback transport, completion checks, exact evidence resolver and failure artifacts. The full-record evaluator explicitly recognizes the compact version and rechecks its actual request and raw completion.

Unrequested dimensions and null proposals expand to `unsupported` with different diagnostics. No missing scientific fields, representation or linkage are invented: representation stays `unparsed`, links remain absent, candidates remain `needs_review` / Li-ion confirmation `not_reviewed`. Candidate schema, scientific units, production ingestion/OCR/chunking/retrieval, database and original PDFs are unchanged. [Protocol and commands](records/compact_record_protocol_v0.1.md).

## Fixed source and reference

One 149-character stored clause from Sanginov 2021, physical PDF page 1, starting at the best-sample statement and ending before the electronic-conductivity clause. The original page was rendered with Poppler and visually inspected. The fragment's range, unit, temperature and generic sample wording were checked against that page. Source whitespace, line wrapping, Unicode signs, offsets and original PDF checksum were preserved; no new OCR or text repair was performed.

Input, task, reference and protocol were frozen before inference in `data/experiments/records/pilot/stage03_20261020/`. Reference SHA-256: `85d96d954e4c0f46fb2406d6e6d1a33ed18ee37d88d453a97aebeb4ed68e1c6b`. It reuses exposed assistant-authored source annotations and is `needs_independent_review`. Four exact raw fields are evaluable; sixteen full-record dimensions, including sample identity and linkage, remain deferred. A separate bounded check expects sample abstention. This does not establish sample identity or article-wide absence.

The pre-inference source snapshot has 392 files, fingerprint `4220a9dfeb2dcb7ebb6331ef1cde1868e881e1af415f3fa728652994f18ff967`, at `output/records_stage03_20261020/baseline_ready/`.

## Observed model result

One real attempt using the same installed Qwen2.5-3B-Instruct Q4_K_M and executable as stage02; hashes verified. CPU 2 threads, context 8192, temperature 0, seed 42, output limit 256 tokens, transport timeout 90 seconds. Only the selected clause was sent, without full-page text or reference answers. No concurrent full test suite was run during inference.

Response completed with `finish_reason=stop` in **9.445 seconds**, using 234 prompt tokens and 64 completion tokens. The candidate failed literal evidence validation. No automatic retry, normalization, field repair, alternate model or budget extension followed.

| Field | Literal audit |
| --- | --- |
| sample_label | `null`, matching the preliminary bounded abstention expectation |
| property_name | Exact author wording and one unique source occurrence |
| value | Contains the unit and removes original spaces in exponents; no exact source occurrence |
| unit | A single space, occurring 30 times; not a valid unit proposal |
| temperature | Removes the original space between `+` and `80`; no exact source occurrence |

Only one of the four expected raw fields matches exactly; null sample abstention matches separately. These counts are finite development-reference observations, not scientific accuracy. The atomic full-record evaluator rejects the candidate and retains all twenty dimensions as unavailable; the separate literal audit exposes the partially correct response without admitting a record. No `candidates.json` was produced.

The context, output format and budgets differ from stage02. Completion in this experiment does not establish a controlled speedup, the sole cause of the earlier timeouts, or useful general extraction. It does establish that this local model/runtime can finish this small structured request within its declared budget. Model-generated exact copying and separating quantity from unit remain unresolved.

## Tests run

- Targeted compact/full compatibility suites: **115 passed**, 5.99 s.
- Full regression: **1103 passed**, one existing Starlette/httpx deprecation warning, 50.55 s. Thirteen new test cases use synthetic inputs and cover fixed keys, null semantics, altered/invented spans, single-region scope, no full-page leakage, truncation, partial candidate state and deferred full-record evaluation.
- Ruff `app tests scripts`: passed. Mypy: no issues in 98 app source files.
- Actual local request: completion succeeded; literal/candidate validation failed as described above. This is not counted as a successful extraction test.
- Replayed all three stage02 full-format artifacts: identical summaries and cases; expected exit code 1 remains because those raw responses are unavailable.
- Pre-inference snapshot checksums verified. Input/reference/protocol and original PDF hashes unchanged. Static HTML checks: five field rows plus header, exact escaped source text and existing PDF target. Browser visual/click checks were not run: local file navigation was already blocked by browser policy in this session.
- Dedicated server stopped after the one attempt. PID, executable and integer start-time ticks guard passed. Immediate port check still observed a listener; a later read-only check verified both process and port absent. Cleanup diagnostics are retained.

## Artifacts and reproduction

- [Field-by-field HTML](../output/records_stage03_20261020/compact_review.html) and [literal audit JSON](../output/records_stage03_20261020/literal_audit.json).
- [Full evaluator report](../output/records_stage03_20261020/evaluation/report.json) and [full evaluator HTML](../output/records_stage03_20261020/evaluation/review.html).
- Raw unmodified completion/request/result and frozen source packet: `data/experiments/records/pilot/stage03_20261020/`; no model answers enter the frozen reference.
- Runtime declaration, server/cleanup logs and before-inference source baseline: `output/records_stage03_20261020/`. Current final source snapshot: `output/records_stage03_20261020/baseline_final/`, identified by its manifest.
- Source-page render: `tmp/pdfs/records_stage03_sanginov_page1.png`. Original PDF remains unchanged.

Inference and offline evaluation commands are in the protocol. The private source/reference/model are absent from a clean clone; a clean dependency installation and current live database/retrieval acceptance were not tested. The generic CLI records a caller-declared runtime; this experiment separately verified executable/model hashes.

## Limitations

One assistant-selected oracle clause, no independent reference, no retrieval or whole-article recall, no distractor/table test and no accepted full record. Compact nulls do not distinguish absence from ambiguity. Scientific sample/property/conditions linkage remains unverified. The raw response is intentionally retained with its errors; whitespace normalization must not be described as exact evidence preservation.

## Verdict

The bounded completion goal is achieved: a complete response arrived within budget. The useful-record goal is not achieved: three raw fields failed literal extraction. Next limited engineering experiment should test source-span selection with deterministic recovery of original text, preserving this failed-copying baseline and keeping scientific linkage separate.
