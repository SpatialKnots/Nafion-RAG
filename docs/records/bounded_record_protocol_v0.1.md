# Bounded full-record development protocol v0.1

Date: 20 October 2026. Status: engineering development, not scientific admission.

## Fixed scope before inference

One task selects at most one conductivity measurement in one article's frozen source regions. The adapter accepts zero or one complete proposal, with all sixteen observations explicitly present or diagnosed. It does not assemble independent field calls, enumerate a whole article, infer work identity, select a text layer, repair OCR, convert units or split range endpoints.

Initial development cases reuse the three already exposed S06 contexts: Sanginov Table 2's footnote-d cell, Istomina's cited prior-work range, and Kayumov's bibliography-only fragment. The table cell is one measurement; the cited range remains one range; the bibliography task expects no measurement. Preserve the existing input bytes and task text. References are authored from existing source-bound development annotations before new inference. They remain assistant-authored, `needs_independent_review`; these inputs are not held out. Unknown fields and scientifically unresolved links remain deferred. This scope does not establish a ten-publication pilot.

## Adapter and execution

The model receives the task and exact source regions with R aliases, never expected answers. Every proposal must declare all sixteen observation names exactly once, a quantity representation, and zero or more unique linkage roles. Present observations require literal raw text and exact evidence. Quotes must occur exactly once in the named region; repeated quotes need longer context. Cross-article context, candidate-filled input, duplicate fields/roles, invented quotes and unknown aliases fail explicitly. Record IDs derive from resolved proposal content; metadata identify the input, request, current code and declared runtime.

Execution uses the existing loopback-only transport with redirects and proxies disabled. Save input, task, request, runtime declaration and manifest before calling the model; save raw response before parsing. Only `finish_reason=stop` is complete. A refusal, truncation, invalid JSON, failed evidence or transport failure is a failed run, never a successful empty result. Empty proposals require a diagnostic and remain model abstentions, not established scientific absence. No automatic repair/retry or acceptance is performed. Every resolved record remains `needs_review`, with `li_ion_confirmation=not_reviewed`.

## Evaluation

Each case declares zero or one expected record, sixteen field expectations, quantity representation and three linkage roles, with a rationale for each deferred dimension. Reference and prediction must bind to identical frozen source regions and task text. Reparse the saved raw response; do not trust recorded success flags. Missing and failed runs remain in case/expected-record denominators. Unexpected or duplicate case IDs stop evaluation.

An absent run directory or missing required run files is explicitly unavailable, with the missing filenames reported. Existing artifacts with mismatched source/task/request checksums instead stop evaluation as an invalid experiment binding.

Report record counts, missed and extra proposals, all sixteen field outcomes, exact raw agreement and source-anchor coverage separately. A longer evidence span can cover an expected anchor; the same raw text at another occurrence cannot. Non-present expectations compare missingness status, not diagnostic prose. Ambiguous or unsupported reference fields are explicitly deferred. Linkage comparison checks role and reference-anchor coverage only; it does not infer scientific entailment. A full-record agreement requires all twenty dimensions (sixteen observations, representation, three links), with no deferred dimension and correct cardinality. A case with no expected record reports correct/false abstention separately; it is not a matched positive record. No tolerance, unit normalization or new scientific acceptance threshold is introduced.

## Delivery boundary

This stage supplies a bounded adapter, a local inference command, full-record evaluation and a review artifact for the fixed development cases. It does not close independent annotation, eligibility/work grouping, whole-article extraction, table-layout support, scientific precision/recall or offline installation acceptance. Production ingestion, retrieval, facts and original PDFs remain unchanged.

## Commands

Use new output directories. Task files are read literally, including any final newline. The runtime manifest must declare the requested model alias and loopback endpoint; the caller is responsible for verifying the executable/model and current server settings. No model is downloaded or started by these commands.

```powershell
.\.venv\Scripts\python.exe -m scripts.records_extract infer data/experiments/records/pilot/stage02_20261020/sanginov/input.json --task-file data/experiments/records/pilot/stage02_20261020/sanginov/task.txt --endpoint http://127.0.0.1:18087 --model ariadne-qwen25-3b-q4km --runtime-manifest output/records_stage02_20261020/runtime_identity.json --output-dir data/experiments/records/pilot/stage02_reproduce/runs/sanginov
.\.venv\Scripts\python.exe -m scripts.records_extract evaluate --reference data/experiments/records/pilot/stage02_20261020/reference.json --run sanginov=data/experiments/records/pilot/stage02_20261020/runs/sanginov --run kayumov=data/experiments/records/pilot/stage02_20261020/runs/kayumov --run istomina=data/experiments/records/pilot/stage02_20261020/runs/istomina --output-dir output/records_stage02_reproduce/evaluation
```

Inference returns exit code 1 for transport/completion/evidence failures. Evaluation still writes its complete report and HTML but returns exit code 1 if any case is missing or invalid. Scientific mismatches are reported in the artifact; evaluator completion does not imply scientific agreement. Reproducing inference needs an active local server, while evaluation needs only the frozen files and installed Python environment. Historical runtime manifests identify historical settings; they do not prove a server is currently running.

The local source contexts/reference include private article text and paths and are intentionally excluded from Git. A fresh clone cannot reproduce the private experiment without those packets. The committed tests use explicitly synthetic sources; they exercise engineering failure modes and are not scientific measurements.
