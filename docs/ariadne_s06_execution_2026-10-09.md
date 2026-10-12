# ARIADNE S06: first local model smoke, 2026-10-09

## Verdict

Local installation and inference are verified. Qwen2.5-1.5B-Instruct Q4_K_M ran on this laptop using two CPU threads. All three first development outputs were rejected by the strict smoke harness. No scientific records were accepted or created. This model/prompt/contract combination is not ready for automatic extraction.

S06 remains in progress: one model and one fixed prompt were tested. No model comparison, independent gold evaluation or extractor quality acceptance was completed. The original failed outputs are preserved; none was repaired or silently retried.

## Changed

Added `app/records/smoke.py`, the `app.records.cli smoke` command and 19 synthetic unit cases. The harness sends only saved source context to an explicit loopback HTTP endpoint, requests constrained JSON and checks all ten fields, explicit missingness, exact evidence quotes and raw-value containment. HTTP proxies and redirects are disabled. Responses, truncation, JSON/schema/quote failures and timings are preserved. New output directories are required; existing experiments are not overwritten.

This is a structured-field smoke adapter with its own `records_smoke_fields_v0.1` contract. It does not generate full `RecordCandidate` objects or change database schemas, ingestion, OCR, chunking, retrieval or existing answer routes. All results retain `scientific_admission=not_evaluated` and `review_state=needs_review`.

Details and invocation: [local model smoke](records/local_model_smoke.md).

## Installation evidence

The user explicitly authorized this model's installation and launch after asking about its purpose, size, load and suitability. Installation is portable inside ignored `data/experiments/records/runtime/`; no global runtime, service or automatic startup was installed.

- Hardware: Intel Core i5-1135G7, 4 physical cores/8 logical processors, 16,969,424,896 bytes physical RAM. GPU inventory reports Intel Iris Xe; GPU inference was not used.
- Model: [official Qwen repository](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF), revision `91cad51170dc346986eccefdc2dd33a9da36ead9`.
- File: `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes (about 1.12 GB / 1.04 GiB).
- Verified model SHA-256: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`.
- Runtime: [official llama.cpp release b11429](https://github.com/ggml-org/llama.cpp/releases/tag/b11429), commit `d81235049384534c167caea52b85a694f6103d14`.
- Archive: `llama-b11429-bin-win-cpu-x64.zip`, 19,398,918 bytes; verified release SHA-256 `1283323272b04cd07905816a597a0da810918102de958f4ff6f7bbaa70ed2efe`.
- Executable: `data/experiments/records/runtime/llama-b11429/llama-server.exe`; SHA-256 `7e236243c9b670c6a49410c03186fd575c57a0efe3fd8a21d8727503d571d5b6`. Actual version output: `0.6.0-dev`, build 11429, commit `d81235049`, Clang 20.1.8, Windows x86_64.

The initial `v0.6.0` release metadata did not contain the Windows binaries; the actual downloaded artifact is the explicitly recorded `b11429` release. Both metadata captures remain in the runtime directory. Model and archive hashes matched their official download metadata before extraction/launch.

Server arguments saved in `server_identity_v01.json`:

```text
-m D:/Nafion-RAG/data/experiments/records/runtime/qwen2.5-1.5b-instruct-q4_k_m.gguf
--alias ariadne-qwen25-15b-q4km --host 127.0.0.1 --port 18086
--threads 2 --threads-batch 2 --prio -1 --poll 0
--ctx-size 8192 --parallel 1 --gpu-layers 0 --no-webui
```

The hidden process used Windows `BelowNormal` priority. `/health` returned `{"status":"ok"}`; server logs recorded model loading and loopback listening. API request structure follows the [official server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

## First development runs

All requests used the same system prompt, temperature 0, seed 42, maximum output 1536 tokens, timeout 600 seconds and JSON Schema constrained decoding. Source selection was manual/oracle; prompt input excluded existing manual answers. These runs test extraction in supplied context, not retrieval or whole-PDF table recognition.

| Run directory under `data/experiments/records/smoke/` | Context/task | Observed result | Elapsed | Output tokens |
|---|---|---|---:|---:|
| `sanginov_table_20261009_v01` | Table 2 header, own row with footnotes, AC method and composition basis | `output_contract` failure: `Duplicate smoke field`; completion finished normally | 97.243 s | 1490 |
| `kayumov_bibliography_20261009_v01` | Bibliographic entry only; no measurement | `response_envelope` failure: `Incomplete completion: length` | 83.923 s | 1536 |
| `istomina_prior_work_20261009_v01` | Cited-result paragraph, current-article method and reference [26] | `output_contract` failure: `Non-empty output must include all ten smoke fields with explicit missingness`; completion finished normally | 55.952 s | 792 |

Observed generation rates from server response timings were 17.01, 18.75 and 16.77 tokens/s respectively. These numbers describe these requests, with their actual cache state; they are not a general throughput benchmark. The second and third prompts reused 191 cached tokens.

Manual inspection of the preserved model text found additional errors beyond the first validator failure:

- Sanginov: repeated `property_name`, `composition_basis`, `temperature` and `sample_label`; `EC/SL` assigned to sample; conductivity/activation-energy/oxidation-potential units assigned to composition basis. The requested conductivity value and footnote-specific temperature were absent. A long method quote lost source line breaks and therefore was not an exact substring. Quote validation was not reached because field-set validation failed first.
- Kayumov: instead of an empty result, the partial output asserted `room temperature`, `Li-ion` and `S/cm`, none of which occurs in the supplied entry. Citation text was normalized, and fields repeated. The actual terminal failure was truncation; these additional observations come from inspecting the saved partial text, not a successful downstream validation.
- Istomina: returned only five fields and invented `Sodium fluoride` as composition basis. A cited paragraph was flattened across source line breaks. Missing value and origin fields prevented evaluating the requested reference attribution as a complete proposal. The response did not establish a valid method assignment.

The above is agent inspection of development outputs, not independent scientific adjudication. No precision, recall, acceptance rate or general model capability estimate is reported. Zero accepted records does not imply that extraction accuracy was measured as 0%.

## Resources and process lifecycle

Initial observed working set was 1,915,326,464 bytes. Windows peak working set at final measurement was 2,027,077,632 bytes, about **1.89 GiB**. Final working set before stopping was 1,962,377,216 bytes. `memory_during_smoke_v01.json` and `memory_after_smoke_v01.json` preserve timestamped observations.

This measures the server process working set, not total system memory, total commit, maximum load of a larger model or interactive responsiveness. No simultaneous user-work benchmark was performed. Two threads and reduced priority limit configured load; they do not guarantee an unaffected laptop.

The experiment process was PID 24480. Path and start time were verified before stopping it. An initial stop guard rejected a timestamp conversion that had dropped UTC information; the guard was corrected and verified against the actual process start time (difference 0.0172602 seconds). The first rejected attempt did not stop a process. Final stop at `2026-10-09T08:57:12.3206169Z` completed; `server_stop_v01.json` records `exited=true`. Model weights remain installed. The historical runtime identity describes this completed process, not a future launch.

## Tests run

- New smoke unit cases: **19 passed in 1.78 s**. Synthetic tests cover Unicode offsets, non-verbatim/ambiguous/unknown quotes, missing fields, endpoint restrictions, preserved failures, truncated response and overwrite refusal. They do not run a model or establish scientific accuracy.
- Full regression: **677 passed, 1 warning in 9.23 s**, using a fresh `tmp/s06_full_20261009_v01` directory outside the restricted sandbox. Warning: existing Starlette/httpx deprecation.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 82 source files**.
- Actual local inference: **three requests completed; all three rejected**, with raw artifacts preserved.
- Original PDF bytes for all three development-source articles: **three SHA-256 matches** against stored source identities, captured in `source_pdf_checks_v01.json`. This does not revalidate current database page text.

Executed full regression command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  --basetemp D:/Nafion-RAG/tmp/s06_full_20261009_v01
```

## Limitations and next step

The ten-field array contract and current prompt exposed repetition, field-role confusion, hallucinated missing conditions and loss of exact quoting. Constrained JSON decoding did not establish scientific correctness. Neither a larger model nor a different prompt was tested, so these runs cannot attribute every failure solely to parameter count.

The next bounded experiment should simplify the model-facing contract: fixed named fields or one field per request, explicit field semantics and shorter evidence spans. Run it on the same frozen contexts, preserve the failed baseline and compare schema completion, exact quoting and field attribution separately. Do not normalize bad quotes into apparent success. If quality remains inadequate, compare a larger local model within measured memory limits. No other model was downloaded in this experiment.

Independent annotation, scientific completeness/linkage decisions, accepted records and production extraction remain open. Runtime files and scientific prompts are private ignored artifacts, not a distributable offline release. The harness records caller-supplied runtime identity; installation hashes and local process logs provide this experiment's evidence, not cryptographic attestation of every later endpoint.
