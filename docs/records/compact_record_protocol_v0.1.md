# Compact literal record experiment v0.1

Date: 20 October 2026. Status: development, not independent scientific evaluation.

## Scope fixed before inference

One short clause from Sanginov 2021's Abstract, physical PDF page 1: the reported single-ion lithium conductivity range and its temperature range. Select the original stored substring starting at `The best sample` and ending at the temperature unit, before the electronic-conductivity clause. Preserve every original character, offset, text-layer identity and PDF hash. This deliberately selected oracle fragment does not test retrieval, whole-article completeness, electronic-conductivity distractors or table parsing.

The fragment does not uniquely identify the sample: the generic wording remains unresolved. The source's complete original page stays in the SourceRegion metadata, but only the selected clause is sent to the model. Freeze the input, task, reference, protocol, executable/model hashes and code before inference. The assistant-authored reference is exposed development material, not independent gold.

## Explicit new wire format

`records_compact_extraction_v0.1` returns exactly five named, required keys: `sample_label`, `property_name`, `value`, `unit`, `temperature`. Each is a literal source substring or null. No explanations, repeated field names, region aliases or model-generated linkage objects. Each asserted string must occur exactly once in the sole source region; the existing literal resolver produces exact EvidenceSpans. Model-generated raw values must not be normalized or repaired.

Null means model abstention; it does not distinguish absence, ambiguity or unsupported extraction. The expanded candidate labels nulls and unrequested fields `unsupported` with separate diagnostics. Quantity representation stays `unparsed`, without endpoint pairing or normalization; no scientific linkage is inferred. Candidate state remains `needs_review`, Li-ion confirmation `not_reviewed`. An all-null answer is an abstention, not a verified scientific negative. The original full wire format and candidate schema remain unchanged.

## Fixed execution and stop rule

Use the same installed Qwen2.5-3B-Instruct Q4_K_M model and runtime as stage02; CPU 2 threads, context 8192, seed 42, temperature 0. New bounded experiment settings: `max_tokens=256`, transport timeout 90 seconds. The reduced context, different wire format and output/time budgets all change together: any outcome cannot establish a controlled speed comparison or the unique cause of the old timeouts.

One actual attempt. Save complete request and raw response; accept completion only with `finish_reason=stop`. On transport, completion or literal failure stop this experiment, retaining its artifacts; no automatic retry, text repair, larger budget or model switch. A completed answer is still checked against the fixed reference before describing usefulness. The dedicated server listens only on loopback and is stopped after the run.

## Checks and evaluation

Before inference, visually inspect the original page and verify its SHA-256. Declare exact source-bound property, complete raw value/range, unit and complete temperature/range expectations. Keep sample identity, all other fields, representation and scientific linkage deferred. Independently inspect every returned key against the frozen reference: a non-null sample identity is an unsupported assertion for this task and must be diagnosed even though scientific sample matching is deferred in the full evaluator.

Use the existing full-record evaluator, extended explicitly for the new wire version. It reparses the raw response, checks source/task/request/runtime bindings and retains all twenty dimensions. Only four raw-field/source-anchor dimensions are evaluable here; sixteen remain deferred. Full-record agreement must not become a pass. Report completion, literal integrity, finite field agreement, sample abstention and missing scientific dimensions separately. Correct JSON or literal equality does not establish chemical correctness or general accuracy.

## Invocation

```powershell
.\.venv\Scripts\python.exe -m scripts.records_extract infer data/experiments/records/pilot/stage03_20261020/input.json --task-file data/experiments/records/pilot/stage03_20261020/task.txt --wire-format compact --max-tokens 256 --timeout-seconds 90 --endpoint http://127.0.0.1:18088 --model ariadne-qwen25-3b-q4km --runtime-manifest output/records_stage03_20261020/runtime_identity.json --output-dir data/experiments/records/pilot/stage03_20261020/run
.\.venv\Scripts\python.exe -m scripts.records_extract evaluate --reference data/experiments/records/pilot/stage03_20261020/reference.json --run sanginov_abstract=data/experiments/records/pilot/stage03_20261020/run --output-dir output/records_stage03_20261020/evaluation
```

Use new output paths for reproduction. Private inputs, reference and raw responses remain local; a fresh clone contains synthetic tests and code but not the article text or installed model. No production ingestion/retrieval/database behavior or old artifacts change.
